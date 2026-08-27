// =============================================================================
//  nudec_packer.cpp
//
//  nudec_packer.h の実装。NUDEC コンテナ (.nuanim) の書き出しと索引読み出し。
//  依存: libktx (KTX_FEATURE_WRITE=ON), OpenCV 4.x, C++17
// =============================================================================

#include "nudec_pack.h"

#include <ktx.h>
#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace nudec {
namespace {

// -----------------------------------------------------------------------------
//  定数
// -----------------------------------------------------------------------------
// libktx は vkFormat を単なる uint32 として扱うため、Vulkan SDK には依存しない。
constexpr ktx_uint32_t kVkFormatR8G8B8A8Unorm = 37;
constexpr ktx_uint32_t kVkFormatR8G8B8A8Srgb  = 43;

constexpr uint64_t kChunkAlignment = 16;  // mmap / SIMD 読み出しを想定した整列

// -----------------------------------------------------------------------------
//  小物ヘルパ
// -----------------------------------------------------------------------------
void CheckKtx(KTX_error_code rc, const char* what) {
    if (rc != KTX_SUCCESS) {
        throw std::runtime_error(std::string(what) + " failed: " + ktxErrorString(rc));
    }
}

ktx_pack_uastc_flags ToKtxUastcFlags(UastcQuality q) {
    switch (q) {
        case UastcQuality::Fastest: return KTX_PACK_UASTC_LEVEL_FASTEST;
        case UastcQuality::Faster:  return KTX_PACK_UASTC_LEVEL_FASTER;
        case UastcQuality::Default: return KTX_PACK_UASTC_LEVEL_DEFAULT;
        case UastcQuality::Slower:  return KTX_PACK_UASTC_LEVEL_SLOWER;
        case UastcQuality::Slowest:  return KTX_PACK_UASTC_LEVEL_VERYSLOW;
    }
    return KTX_PACK_UASTC_LEVEL_DEFAULT;
}

constexpr uint32_t CeilDiv(uint32_t a, uint32_t b) { return (a + b - 1u) / b; }
constexpr uint32_t Align4(uint32_t v)              { return (v + 3u) & ~3u; }

uint32_t FullMipLevelCount(uint32_t w, uint32_t h) {
    uint32_t levels = 1;
    while (w > 1u || h > 1u) {
        w = std::max(1u, w >> 1);
        h = std::max(1u, h >> 1);
        ++levels;
    }
    return levels;
}

// ktxTexture2 の例外安全な破棄
struct KtxTextureDeleter {
    void operator()(ktxTexture2* t) const noexcept {
        if (t) ktxTexture_Destroy(ktxTexture(t));
    }
};
using KtxTexture2Ptr = std::unique_ptr<ktxTexture2, KtxTextureDeleter>;

// ktxTexture_WriteToMemory が malloc したバッファの解放
struct KtxMemDeleter {
    void operator()(ktx_uint8_t* p) const noexcept { std::free(p); }
};
using KtxMemPtr = std::unique_ptr<ktx_uint8_t, KtxMemDeleter>;

// -----------------------------------------------------------------------------
//  PNG 読み込み: 必ず 8bit / 4ch RGBA / 連続メモリ に正規化する
//  OpenCV は BGR(A) 順で読むので、ここで RGB(A) に並べ替える。
// -----------------------------------------------------------------------------
cv::Mat LoadAsRgba8(const std::string& path) {
    cv::Mat img = cv::imread(path, cv::IMREAD_UNCHANGED);
    if (img.empty()) {
        throw std::runtime_error("Failed to read image: " + path);
    }

    if (img.depth() == CV_16U) {
        img.convertTo(img, CV_8U, 1.0 / 257.0);  // 65535 -> 255
    } else if (img.depth() != CV_8U) {
        throw std::runtime_error("Unsupported bit depth in: " + path);
    }

    cv::Mat rgba;
    switch (img.channels()) {
        case 1: cv::cvtColor(img, rgba, cv::COLOR_GRAY2RGBA); break;
        case 3: cv::cvtColor(img, rgba, cv::COLOR_BGR2RGBA);  break;
        case 4: cv::cvtColor(img, rgba, cv::COLOR_BGRA2RGBA); break;
        default:
            throw std::runtime_error("Unsupported channel count (" +
                                     std::to_string(img.channels()) +
                                     ") in: " + path);
    }
    if (!rgba.isContinuous()) rgba = rgba.clone();
    return rgba;
}

// -----------------------------------------------------------------------------
//  タイル切り出し
//  (col, row) のタイルを取り出し、tile_w x tile_h に端複製パディングして返す。
// -----------------------------------------------------------------------------
cv::Mat ExtractTile(const cv::Mat& frame, uint32_t col, uint32_t row,
                    uint32_t tile_w, uint32_t tile_h) {
    const int x0 = static_cast<int>(col * tile_w);
    const int y0 = static_cast<int>(row * tile_h);
    const int w  = std::min<int>(static_cast<int>(tile_w), frame.cols - x0);
    const int h  = std::min<int>(static_cast<int>(tile_h), frame.rows - y0);

    cv::Mat roi = frame(cv::Rect(x0, y0, w, h));

    if (w == static_cast<int>(tile_w) && h == static_cast<int>(tile_h)) {
        return roi.clone();  // ROI は非連続なので必ずコピーする
    }
    cv::Mat padded;
    // BORDER_REPLICATE: 端の画素を複製。黒埋めだと境界に濃いブロックノイズが出る。
    cv::copyMakeBorder(roi, padded, 0, static_cast<int>(tile_h) - h,
                       0, static_cast<int>(tile_w) - w, cv::BORDER_REPLICATE);
    return padded;
}

// -----------------------------------------------------------------------------
//  ファイル入出力ヘルパ
// -----------------------------------------------------------------------------
void WriteRaw(std::ofstream& ofs, const void* data, size_t size) {
    ofs.write(static_cast<const char*>(data), static_cast<std::streamsize>(size));
    if (!ofs) throw std::runtime_error("Write failed (disk full or permission denied?)");
}

void ReadRaw(std::ifstream& ifs, void* data, size_t size, const char* what) {
    ifs.read(static_cast<char*>(data), static_cast<std::streamsize>(size));
    if (!ifs) throw std::runtime_error(std::string("Truncated .nuanim while reading ") + what);
}

uint64_t AlignFile(std::ofstream& ofs, uint64_t alignment) {
    uint64_t pos = static_cast<uint64_t>(ofs.tellp());
    const uint64_t pad = (alignment - (pos % alignment)) % alignment;
    if (pad != 0) {
        static const char kZeros[kChunkAlignment] = {};
        WriteRaw(ofs, kZeros, static_cast<size_t>(pad));
        pos += pad;
    }
    return pos;
}

// -----------------------------------------------------------------------------
//  1チャンク分を KTX2 テクスチャ配列として構築し、UASTC 圧縮してメモリに出力
// -----------------------------------------------------------------------------
KtxMemPtr BuildAndEncodeChunk(
    const std::vector<std::pair<int, std::string>>& frames,
    uint32_t first_frame_in_chunk, uint32_t frame_count_in_chunk,
    uint32_t total_frame_count,
    uint32_t frame_w, uint32_t frame_h,
    uint32_t tile_w, uint32_t tile_h, uint32_t tile_cols, uint32_t tile_rows,
    uint32_t level_count, const PackOptions& opt, ktx_size_t* out_size) {

    const uint32_t tiles_per_frame = tile_cols * tile_rows;
    const uint32_t layer_count     = frame_count_in_chunk * tiles_per_frame;

    ktxTextureCreateInfo ci{};
    ci.vkFormat        = opt.srgb ? kVkFormatR8G8B8A8Srgb : kVkFormatR8G8B8A8Unorm;
    ci.baseWidth       = tile_w;
    ci.baseHeight      = tile_h;
    ci.baseDepth       = 1;
    ci.numDimensions   = 2;
    ci.numLevels       = level_count;
    ci.numLayers       = layer_count;
    ci.numFaces        = 1;
    ci.isArray         = KTX_TRUE;
    ci.generateMipmaps = KTX_FALSE;  // ロード時生成フラグ。Basis 圧縮とは併用不可。

    ktxTexture2* raw = nullptr;
    CheckKtx(ktxTexture2_Create(&ci, KTX_TEXTURE_CREATE_ALLOC_STORAGE, &raw),
             "ktxTexture2_Create");
    KtxTexture2Ptr tex(raw);

    // --- 画素の流し込み -----------------------------------------------------
    for (uint32_t f = 0; f < frame_count_in_chunk; ++f) {
        const auto& entry = frames[first_frame_in_chunk + f];
        cv::Mat frame = LoadAsRgba8(entry.second);

        if (static_cast<uint32_t>(frame.cols) != frame_w ||
            static_cast<uint32_t>(frame.rows) != frame_h) {
            throw std::runtime_error(
                "Frame " + std::to_string(entry.first) + " (" + entry.second +
                ") is " + std::to_string(frame.cols) + "x" + std::to_string(frame.rows) +
                ", expected " + std::to_string(frame_w) + "x" + std::to_string(frame_h) +
                ". All frames must share the same resolution.");
        }

        for (uint32_t r = 0; r < tile_rows; ++r) {
            for (uint32_t c = 0; c < tile_cols; ++c) {
                const uint32_t local_layer = f * tiles_per_frame + (r * tile_cols + c);
                cv::Mat level_img = ExtractTile(frame, c, r, tile_w, tile_h);

                for (uint32_t lv = 0; lv < level_count; ++lv) {
                    if (lv > 0) {
                        cv::Mat next;
                        const cv::Size next_size(std::max(1, level_img.cols / 2),
                                                 std::max(1, level_img.rows / 2));
                        // INTER_AREA が縮小時のエイリアシング最小。
                        cv::resize(level_img, next, next_size, 0.0, 0.0, cv::INTER_AREA);
                        level_img = next;
                    }
                    CheckKtx(ktxTexture_SetImageFromMemory(
                                 ktxTexture(tex.get()), lv, local_layer, 0,
                                 level_img.data,
                                 level_img.total() * level_img.elemSize()),
                             "ktxTexture_SetImageFromMemory");
                }
            }
        }
        // frame はここでスコープを抜けて解放される (ピークRAMを抑えるため)
        if (opt.progress) {
            opt.progress(first_frame_in_chunk + f + 1, total_frame_count);
        }
    }

    // --- メタデータ (チャンクを単体 .ktx2 として取り出しても情報が残るように) --
    {
        const char orientation[] = "rd";  // OpenCV は左上原点・下方向
        ktxHashList_AddKVPair(&tex->kvDataHead, KTX_ORIENTATION_KEY,
                              static_cast<ktx_uint32_t>(sizeof(orientation)),
                              orientation);

        std::ostringstream oss;
        oss << "{\"format\":\"NUDEC\",\"version\":" << kNudecVersion
            << ",\"frameWidth\":"  << frame_w
            << ",\"frameHeight\":" << frame_h
            << ",\"tileCols\":"    << tile_cols
            << ",\"tileRows\":"    << tile_rows
            << ",\"firstFrame\":"  << first_frame_in_chunk
            << ",\"frameCount\":"  << frame_count_in_chunk
            << ",\"frameNumbers\":[";
        for (uint32_t f = 0; f < frame_count_in_chunk; ++f) {
            if (f) oss << ',';
            oss << frames[first_frame_in_chunk + f].first;
        }
        oss << "]}";
        const std::string meta = oss.str();
        ktxHashList_AddKVPair(&tex->kvDataHead, "nudecChunk",
                              static_cast<ktx_uint32_t>(meta.size() + 1),
                              meta.c_str());
    }

    // --- UASTC 圧縮 ---------------------------------------------------------
    ktxBasisParams bp{};
    bp.structSize            = sizeof(ktxBasisParams);
    bp.uastc                 = KTX_TRUE;  // ETC1S ではなく UASTC
    bp.uastcFlags            = ToKtxUastcFlags(opt.uastc_quality);
    bp.uastcRDO              = opt.uastc_rdo ? KTX_TRUE : KTX_FALSE;
    bp.uastcRDOQualityScalar = opt.uastc_rdo_quality;
    bp.verbose               = KTX_FALSE;
    bp.threadCount = (opt.thread_count > 0)
                         ? static_cast<ktx_uint32_t>(opt.thread_count)
                         : std::max(1u, std::thread::hardware_concurrency());

    CheckKtx(ktxTexture2_CompressBasisEx(tex.get(), &bp),
             "ktxTexture2_CompressBasisEx");

    // --- Zstd スーパーコンプレッション --------------------------------------
    if (opt.zstd_level > 0) {
        CheckKtx(ktxTexture2_DeflateZstd(tex.get(),
                                         static_cast<ktx_uint32_t>(opt.zstd_level)),
                 "ktxTexture2_DeflateZstd");
    }

    // --- メモリへ書き出し ---------------------------------------------------
    ktx_uint8_t* bytes = nullptr;
    ktx_size_t   size  = 0;
    CheckKtx(ktxTexture_WriteToMemory(ktxTexture(tex.get()), &bytes, &size),
             "ktxTexture_WriteToMemory");
    *out_size = size;
    return KtxMemPtr(bytes);
}

}  // namespace

// =============================================================================
//  書き込み本体
// =============================================================================
PackResult PackPngSequence(const std::unordered_map<int, std::string>& input_seq,
                           const std::string& output_dir,
                           const PackOptions& opt) {

    if (input_seq.empty()) {
        throw std::runtime_error("input_seq is empty.");
    }
    if (opt.max_tile_size < 4u || (opt.max_tile_size % 4u) != 0u) {
        throw std::runtime_error("max_tile_size must be a multiple of 4 and >= 4.");
    }
    if (opt.max_array_layers == 0u) {
        throw std::runtime_error("max_array_layers must be >= 1.");
    }

    // unordered_map は順序不定。フレーム番号昇順にレイヤー順を確定させる。
    std::vector<std::pair<int, std::string>> frames;
    {
        const std::map<int, std::string> ordered(input_seq.begin(), input_seq.end());
        frames.assign(ordered.begin(), ordered.end());
    }
    const uint32_t frame_count = static_cast<uint32_t>(frames.size());

    // ---- 1. 先頭フレームで寸法とタイルグリッドを確定 -------------------------
    uint32_t frame_w = 0, frame_h = 0;
    {
        cv::Mat probe = LoadAsRgba8(frames.front().second);
        frame_w = static_cast<uint32_t>(probe.cols);
        frame_h = static_cast<uint32_t>(probe.rows);
    }

    const uint32_t tile_cols = CeilDiv(frame_w, opt.max_tile_size);
    const uint32_t tile_rows = CeilDiv(frame_h, opt.max_tile_size);
    // 全レイヤーは同寸法である必要があるため、切り上げてから 4 の倍数に整列する。
    const uint32_t tile_w = Align4(CeilDiv(frame_w, tile_cols));
    const uint32_t tile_h = Align4(CeilDiv(frame_h, tile_rows));

    const uint32_t tiles_per_frame = tile_cols * tile_rows;
    const uint64_t total_layers64 =
        static_cast<uint64_t>(frame_count) * tiles_per_frame;
    if (total_layers64 > 0xFFFFFFFFull) {
        throw std::runtime_error("Total layer count exceeds 2^32.");
    }

    const uint32_t level_count =
        opt.generate_mipmaps ? FullMipLevelCount(tile_w, tile_h) : 1u;

    // ---- 2. チャンク分割の決定 ---------------------------------------------
    // 1タイル分の生バイト数 (ミップ込みなら約 4/3 倍)
    const uint64_t bytes_per_tile =
        static_cast<uint64_t>(tile_w) * tile_h * 4ull *
        (opt.generate_mipmaps ? 4ull : 3ull) / 3ull;

    const uint32_t layers_by_budget = static_cast<uint32_t>(
        std::max<uint64_t>(
        1ull, opt.memory_budget_bytes / std::max<uint64_t>(1, bytes_per_tile))
    );
    const uint32_t max_layers = std::min(opt.max_array_layers, layers_by_budget);

    // チャンク境界をフレーム境界に揃える (1フレームのタイル群を分断しない)
    const uint32_t frames_per_chunk = std::max(1u, max_layers / tiles_per_frame);
    if (frames_per_chunk * tiles_per_frame > opt.max_array_layers) {
        throw std::runtime_error(
            "tiles per frame (" + std::to_string(tiles_per_frame) +
            ") exceeds max_array_layers (" + std::to_string(opt.max_array_layers) +
            "). Increase max_tile_size or max_array_layers.");
    }
    const uint32_t chunk_count = CeilDiv(frame_count, frames_per_chunk);

    if (opt.verbose) {
        std::cout << "[nudec] frames=" << frame_count
                  << " size=" << frame_w << "x" << frame_h
                  << " tiles=" << tile_cols << "x" << tile_rows
                  << " (" << tile_w << "x" << tile_h << " each)"
                  << " levels=" << level_count
                  << " layers=" << total_layers64
                  << " chunks=" << chunk_count
                  << " (" << frames_per_chunk << " frames/chunk)\n"
                  << "[nudec] peak staging RAM ~= "
                  << (bytes_per_tile * tiles_per_frame * frames_per_chunk /
                      (1024.0 * 1024.0))
                  << " MiB\n";
        if (tiles_per_frame > 1) {
            std::cout << "[nudec] frame exceeds max_tile_size; split into tiles. "
                         "Shader must recombine using tileCols/tileRows.\n";
        }
    }

    // ---- 3. 出力ファイルを開き、ヘッダ領域を予約 ----------------------------
    std::error_code ec;
    std::filesystem::create_directories(output_dir, ec);
    if (ec) {
        throw std::runtime_error("Failed to create output directory '" + output_dir +
                                 "': " + ec.message());
    }
    const std::string out_path =
        (std::filesystem::path(output_dir) / opt.file_name).string();

    std::ofstream ofs(out_path, std::ios::binary | std::ios::trunc);
    if (!ofs) throw std::runtime_error("Failed to open output file: " + out_path);

    NudecHeader header{};
    std::memcpy(header.magic, kNudecMagic, sizeof(header.magic));
    header.version      = kNudecVersion;
    header.header_size  = static_cast<uint32_t>(sizeof(NudecHeader));
    header.vk_format    = opt.srgb ? kVkFormatR8G8B8A8Srgb : kVkFormatR8G8B8A8Unorm;
    header.frame_count  = frame_count;
    header.chunk_count  = chunk_count;
    header.frame_width  = frame_w;
    header.frame_height = frame_h;
    header.tile_width   = tile_w;
    header.tile_height  = tile_h;
    header.tile_cols    = tile_cols;
    header.tile_rows    = tile_rows;
    header.level_count  = level_count;
    header.layer_count  = static_cast<uint32_t>(total_layers64);
    header.flags        = (opt.srgb ? kFlagSrgb : 0u)
                        | (level_count > 1 ? kFlagMipmaps : 0u)
                        | (opt.zstd_level > 0 ? kFlagZstd : 0u)
                        | (tiles_per_frame > 1 ? kFlagTiled : 0u)
                        | ((tile_w * tile_cols != frame_w ||
                            tile_h * tile_rows != frame_h) ? kFlagPadded : 0u);
    WriteRaw(ofs, &header, sizeof(header));

    // ---- 4. チャンクを1つずつ構築・圧縮・書き出し ---------------------------
    std::vector<NudecChunkEntry> chunk_table;
    chunk_table.reserve(chunk_count);

    uint32_t next_frame = 0;
    for (uint32_t ci = 0; ci < chunk_count; ++ci) {
        const uint32_t n_frames = std::min(frames_per_chunk, frame_count - next_frame);

        if (opt.verbose) {
            std::cout << "[nudec] chunk " << (ci + 1) << "/" << chunk_count
                      << " : frames [" << next_frame << ", "
                      << (next_frame + n_frames - 1) << "] encoding...\n";
        }

        ktx_size_t chunk_size = 0;
        KtxMemPtr chunk_bytes = BuildAndEncodeChunk(
            frames, next_frame, n_frames, frame_count, frame_w, frame_h,
            tile_w, tile_h, tile_cols, tile_rows, level_count, opt, &chunk_size);

        const uint64_t offset = AlignFile(ofs, kChunkAlignment);
        WriteRaw(ofs, chunk_bytes.get(), static_cast<size_t>(chunk_size));
        chunk_bytes.reset();  

        NudecChunkEntry e{};
        e.offset      = offset;
        e.size        = static_cast<uint64_t>(chunk_size);
        e.first_layer = next_frame * tiles_per_frame;
        e.layer_count = n_frames * tiles_per_frame;
        e.first_frame = next_frame;
        e.frame_count = n_frames;
        chunk_table.push_back(e);

        next_frame += n_frames;
    }

    // ---- 5. チャンクテーブルとフレーム番号テーブル ---------------------------
    header.chunk_table_offset = AlignFile(ofs, kChunkAlignment);
    WriteRaw(ofs, chunk_table.data(), chunk_table.size() * sizeof(NudecChunkEntry));

    header.frame_index_offset = static_cast<uint64_t>(ofs.tellp());
    {
        std::vector<int32_t> frame_numbers;
        frame_numbers.reserve(frame_count);
        for (const auto& f : frames) {
            frame_numbers.push_back(static_cast<int32_t>(f.first));
        }
        WriteRaw(ofs, frame_numbers.data(), frame_numbers.size() * sizeof(int32_t));
    }

    // ---- 6. ヘッダを確定値で上書き ------------------------------------------
    ofs.seekp(0, std::ios::beg);
    WriteRaw(ofs, &header, sizeof(header));
    ofs.flush();
    if (!ofs) throw std::runtime_error("Failed to finalize file: " + out_path);
    ofs.close();

    // ---- 7. 結果 -------------------------------------------------------------
    PackResult result;
    result.file_path       = out_path;
    result.file_size_bytes = std::filesystem::file_size(out_path, ec);
    if (ec) result.file_size_bytes = 0;
    result.frame_count  = frame_count;
    result.chunk_count  = chunk_count;
    result.frame_width  = frame_w;
    result.frame_height = frame_h;
    result.tile_width   = tile_w;
    result.tile_height  = tile_h;
    result.tile_cols    = tile_cols;
    result.tile_rows    = tile_rows;
    result.layer_count  = header.layer_count;
    result.level_count  = level_count;

    if (opt.verbose) {
        std::cout << "[nudec] done: " << out_path << " ("
                  << (static_cast<double>(result.file_size_bytes) / (1024.0 * 1024.0))
                  << " MiB)\n";
    }
    return result;
}

void PackPngSequence(const std::unordered_map<int, std::string>& input_seq,
                     const std::string& output_dir) {
    (void)PackPngSequence(input_seq, output_dir, PackOptions{});
}

// =============================================================================
//  読み出し
// =============================================================================
bool IsNudecFile(const void* first_bytes, size_t size) {
    if (first_bytes == nullptr || size < sizeof(kNudecMagic)) return false;
    return std::memcmp(first_bytes, kNudecMagic, sizeof(kNudecMagic)) == 0;
}

NudecIndex ReadNudecIndex(const std::string& path) {
    std::ifstream ifs(path, std::ios::binary);
    if (!ifs) throw std::runtime_error("Failed to open .nuanim: " + path);

    NudecIndex index;
    ReadRaw(ifs, &index.header, sizeof(NudecHeader), "header");

    if (!IsNudecFile(index.header.magic, sizeof(index.header.magic))) {
        throw std::runtime_error("Not a NUDEC file: " + path);
    }
    if (index.header.version != kNudecVersion) {
        throw std::runtime_error("Unsupported NUDEC version " +
                                 std::to_string(index.header.version) +
                                 " (expected " + std::to_string(kNudecVersion) + ")");
    }
    if (index.header.header_size != sizeof(NudecHeader)) {
        throw std::runtime_error("NUDEC header size mismatch (file=" +
                                 std::to_string(index.header.header_size) +
                                 ", build=" + std::to_string(sizeof(NudecHeader)) + ")");
    }

    index.chunks.resize(index.header.chunk_count);
    if (index.header.chunk_count > 0) {
        ifs.seekg(static_cast<std::streamoff>(index.header.chunk_table_offset),
                  std::ios::beg);
        ReadRaw(ifs, index.chunks.data(),
                index.chunks.size() * sizeof(NudecChunkEntry), "chunk table");
    }

    index.frame_numbers.resize(index.header.frame_count);
    if (index.header.frame_count > 0) {
        ifs.seekg(static_cast<std::streamoff>(index.header.frame_index_offset),
                  std::ios::beg);
        ReadRaw(ifs, index.frame_numbers.data(),
                index.frame_numbers.size() * sizeof(int32_t), "frame index table");
    }
    return index;
}

size_t FindChunkForFrame(const NudecIndex& index, uint32_t frame_index) {
    // chunks は first_frame 昇順に並んでいる。
    auto it = std::upper_bound(
        index.chunks.begin(), index.chunks.end(), frame_index,
        [](uint32_t f, const NudecChunkEntry& e) { return f < e.first_frame; });
    if (it == index.chunks.begin()) return index.chunks.size();
    --it;
    if (frame_index >= it->first_frame + it->frame_count) return index.chunks.size();
    return static_cast<size_t>(std::distance(index.chunks.begin(), it));
}

}  // namespace nudec