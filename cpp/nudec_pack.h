// =============================================================================
//  nudec_packer.h
//
//  NUDEC  --  連番フレームのための UASTC/KTX2 コンテナ形式
//  拡張子 .nuanim
//
//  連番PNG を UASTC 圧縮した KTX2 テクスチャ配列に変換し、単一のバイナリ
//  コンテナにまとめる。
//
//  設計方針:
//    - フレーム数の上限なし  : チャンク分割 + ストリーミング書き出しで RAM 一定
//    - 解像度の上限なし      : GL_MAX_TEXTURE_SIZE を超える場合はタイル分割
//    - OpenGL ターゲット     : 各チャンクは単体で有効な .ktx2 (sampler2DArray)
//    - RGBA 8bit 4ch を維持  : VK_FORMAT_R8G8B8A8_SRGB / _UNORM
//
//  このヘッダは libktx / OpenCV に依存しない。利用側にサードパーティの
//  インクルードパスを強制しないため、UASTC 品質は独自 enum で表現している。
// =============================================================================

#ifndef NUDEC_PACKER_H_
#define NUDEC_PACKER_H_

#include <cstdint>
#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

namespace nudec {

// =============================================================================
//  フォーマット識別子
// =============================================================================

// マジックは 8 バイト固定。バージョンは NudecHeader::version が持つので、
// マジック側にはバージョン番号を含めない (二重管理を避けるため)。
constexpr char kNudecMagic[8] = {'N', 'U', 'D', 'E', 'C', '\0', '\0', '\0'};

constexpr uint32_t kNudecVersion   = 1;
constexpr char     kNudecExtension[] = ".nuanim";

// -----------------------------------------------------------------------------
//  UASTC エンコード品質。
//  内部で KTX_PACK_UASTC_LEVEL_* にマップされる。
// -----------------------------------------------------------------------------
enum class UastcQuality : int {
    Fastest = 0,
    Faster  = 1,
    Default = 2,
    Slower  = 3,
    Slowest = 4,
};


struct PackOptions {
    // true  : VK_FORMAT_R8G8B8A8_SRGB  
    // false : VK_FORMAT_R8G8B8A8_UNORM
    bool srgb = true;

    // --- ミップマップ ------------------------------------------------------
    bool generate_mipmaps = false;

    // --- タイル分割 --------------------------------------------------------
    // 1レイヤーの最大辺長。GL_MAX_TEXTURE_SIZE 以下に設定すること。
    // フレームがこれを超える場合、均一サイズのタイルグリッドに分割される。
    // 4 の倍数であること (UASTC は 4x4 ブロック)。
    // 実行時に glGetIntegerv(GL_MAX_TEXTURE_SIZE) で取得した値を渡すのが理想。
    uint32_t max_tile_size = 8192;

    // --- チャンク分割 ------------------------------------------------------
    // 1チャンク (= 1つの KTX2 テクスチャ配列) の最大レイヤー数。
    // GL_MAX_ARRAY_TEXTURE_LAYERS 以下にすること。GL4.5 の保証値は 2048。
    uint32_t max_array_layers = 2048;

    // 圧縮前ステージングに使ってよいメモリ量の目安 (バイト)。
    uint64_t memory_budget_bytes = 1ull << 30;  // 1 GiB

    // --- UASTC -------------------------------------------------------------
    UastcQuality uastc_quality     = UastcQuality::Default;
    bool         uastc_rdo         = true;   // Zstd の効きを良くする前処理
    float        uastc_rdo_quality = 1.0f;   // 大きいほど高圧縮・低画質

    // --- スーパーコンプレッション ------------------------------------------
    // Zstd レベル 1..22。0 で無効。UASTC 生データは 8bpp のままなので
    // 通常は有効にしておくこと。
    int zstd_level = 18;

    // --- その他 ------------------------------------------------------------
    int         thread_count = 0;  // 0 = hardware_concurrency
    std::string file_name    = std::string("sequence") + kNudecExtension;
    bool        verbose      = true;

    // 進捗コールバック (処理済みフレーム数, 総フレーム数)。空でも可。
    std::function<void(uint32_t, uint32_t)> progress;
};

// =============================================================================
//  結果情報
// =============================================================================
struct PackResult {
    std::string file_path;
    uint64_t    file_size_bytes = 0;
    uint32_t    frame_count     = 0;
    uint32_t    chunk_count     = 0;
    uint32_t    frame_width     = 0;  // 元フレームの幅
    uint32_t    frame_height    = 0;  // 元フレームの高さ
    uint32_t    tile_width      = 0;  // 1レイヤーの幅 (パディング後)
    uint32_t    tile_height     = 0;  // 1レイヤーの高さ (パディング後)
    uint32_t    tile_cols       = 0;
    uint32_t    tile_rows       = 0;
    uint32_t    layer_count     = 0;  // frame_count * tile_cols * tile_rows
    uint32_t    level_count     = 0;
};

// =============================================================================
//  NUDEC コンテナ形式 (.nuanim)
//
//  すべてリトルエンディアン。オフセットはファイル先頭からのバイト数。
//
//    +0                          NudecHeader                    (84 bytes)
//    chunk[i].offset             chunk i のバイト列 = 単体で有効な .ktx2
//                                16 バイト境界に整列
//    header.chunk_table_offset   NudecChunkEntry[chunk_count]
//    header.frame_index_offset   int32_t[frame_count]
//                                レイヤー順 -> 入力キー(元のフレーム番号)
//
//  レイヤー番号の割り当て規則:
//    tiles_per_frame = tile_cols * tile_rows
//    global_layer = frame_index * tiles_per_frame + (tile_row * tile_cols + tile_col)
//    chunk 内 local_layer = global_layer - chunk.first_layer
//
//  チャンク境界は必ずフレーム境界に一致する (1フレームのタイル群は分断されない)。
// =============================================================================

// フラグビット
constexpr uint32_t kFlagSrgb    = 1u << 0;  // vk_format が _SRGB
constexpr uint32_t kFlagMipmaps = 1u << 1;  // level_count > 1
constexpr uint32_t kFlagZstd    = 1u << 2;  // Zstd スーパーコンプレッション適用済み
constexpr uint32_t kFlagTiled   = 1u << 3;  // tile_cols * tile_rows > 1
constexpr uint32_t kFlagPadded  = 1u << 4;  // 端タイルにパディングあり

#pragma pack(push, 1)
struct NudecHeader {
    char     magic[8];            // kNudecMagic
    uint32_t version;             // kNudecVersion
    uint32_t header_size;         // sizeof(NudecHeader)
    uint32_t flags;               // kFlag*
    uint32_t vk_format;           // 37 = R8G8B8A8_UNORM, 43 = R8G8B8A8_SRGB
    uint32_t frame_count;
    uint32_t chunk_count;
    uint32_t frame_width;
    uint32_t frame_height;
    uint32_t tile_width;
    uint32_t tile_height;
    uint32_t tile_cols;
    uint32_t tile_rows;
    uint32_t level_count;
    uint32_t layer_count;
    uint32_t reserved;            // 0
    uint64_t chunk_table_offset;
    uint64_t frame_index_offset;
};

struct NudecChunkEntry {
    uint64_t offset;        　　　　// .ktx2 バイト列の開始位置
    uint64_t size;          　　　　// .ktx2 バイト列の長さ
    uint32_t first_layer;   　　　　// このチャンクが担当する global layer の先頭
    uint32_t layer_count;  　　　　 // = KTX2 側の numLayers
    uint32_t first_frame;  　　　　 // 担当フレームの先頭 (レイヤー順の index)
    uint32_t frame_count;  　　　　 // 担当フレーム数
};
#pragma pack(pop)

static_assert(sizeof(NudecHeader) == 84, "NudecHeader layout changed");
static_assert(sizeof(NudecChunkEntry) == 32, "NudecChunkEntry layout changed");

// =============================================================================
//  書き込み API
// =============================================================================

// 連番PNG を .nuanim にパックする。
// 失敗時は std::runtime_error を送出する。
PackResult PackPngSequence(const std::unordered_map<int, std::string>& input_seq,
                           const std::string& output_dir,
                           const PackOptions& opt);

// 既定オプション版。当初ご指定のシグネチャ (戻り値 void) と同じ形。
void PackPngSequence(const std::unordered_map<int, std::string>& input_seq,
                     const std::string& output_dir);

// 旧名との互換用ラッパー。新規コードでは PackPngSequence を使うこと。
// 不要なら削除して構わない。
inline void PackPngSequenceToKtx2(
    const std::unordered_map<int, std::string>& input_seq,
    const std::string& output_dir) {
    PackPngSequence(input_seq, output_dir);
}

// =============================================================================
//  読み出し API (ローダー実装用の最小限のヘルパ)
//  ---------------------------------------------------------------------------
//  ヘッダとインデックス群だけを読む。実際のチャンク本体 (.ktx2 バイト列) は
//  chunks[i].offset / .size を使って呼び出し側で読み出し、libktx の
//  ktxTexture2_CreateFromMemory に渡すこと。
// =============================================================================
struct NudecIndex {
    NudecHeader                  header{};
    std::vector<NudecChunkEntry> chunks;
    std::vector<int32_t>         frame_numbers;  // レイヤー順 -> 元フレーム番号
};

// .nuanim のヘッダ・チャンクテーブル・フレーム番号表を読み出す。
// マジック / バージョン / サイズ整合を検証し、不正なら std::runtime_error。
NudecIndex ReadNudecIndex(const std::string& path);

// 先頭バイト列が NUDEC かどうかを判定する (size >= 8 が必要)。
bool IsNudecFile(const void* first_bytes, size_t size);

// frame_index (レイヤー順の通し番号) を含むチャンクの添字を返す。
// 見つからなければ chunks.size() を返す。
size_t FindChunkForFrame(const NudecIndex& index, uint32_t frame_index);

}  // namespace nudec

#endif  // NUDEC_PACKER_H_