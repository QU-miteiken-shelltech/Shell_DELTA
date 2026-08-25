// =============================================================================
//  entry.cpp
//
//  format : 
//    nudec_pack <input_json> <output_dir> [options]
// =============================================================================

#include "nudec_pack.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>
#include <fstream>

using json = nlohmann::json;
namespace fs = std::filesystem;

namespace {

// -----------------------------------------------------------------------------
//  Help text
// -----------------------------------------------------------------------------
void PrintUsage(const char* argv0) {
    std::cout <<
"NUDEC packer - PNG sequence -> UASTC/KTX2 container (.nuanim)\n"
"\n"
"Usage:\n"
"  " << argv0 << " <input_json> <output_dir> [options]\n"
"\n"
"Frame numbering:\n"
"  The last run of digits in the file stem is used as the frame number.\n"
"    frame_0042.png      -> 42\n"
"    shot01_v2_007.png   -> 7\n"
"  Files without digits are skipped with a warning.\n"
"  Duplicate frame numbers are a fatal error.\n"
"\n"
"Options:\n"
"  -o, --out-name NAME     Output file name          (default: sequence.nuanim)\n"
"  -t, --tile-size N       Max layer edge in pixels  (default: 8192, mult. of 4)\n"
"                          Set this to your GL_MAX_TEXTURE_SIZE.\n"
"  -l, --max-layers N      Max layers per chunk      (default: 2048)\n"
"                          Set this to your GL_MAX_ARRAY_TEXTURE_LAYERS.\n"
"  -b, --budget-mb N       Staging RAM budget in MiB (default: 1024)\n"
"  -q, --quality LEVEL     fastest|faster|default|slower|slowest (default: default)\n"
"      --no-rdo            Disable UASTC RDO preprocessing\n"
"      --rdo-quality F     RDO quality scalar, higher = smaller/lossier (default: 1.0)\n"
"  -z, --zstd N            Zstd level 0..22, 0 disables (default: 18)\n"
"  -j, --threads N         Encoder threads, 0 = auto  (default: 0)\n"
"  -m, --mipmaps           Generate a full mip chain  (default: off)\n"
"      --linear            Treat input as linear data instead of sRGB\n"
"  -r, --recursive         Scan subdirectories too\n"
"  -n, --dry-run           List detected frames and exit without encoding\n"
"  -Q, --quiet             Suppress progress output\n"
"  -h, --help              Show this message\n"
"\n"
"Example:\n"
"  " << argv0 << " ./frames ./out -o walk.nuanim -t 16384 -q slower -j 16\n";
}

bool ParseInt64(const char* s, long long& out) {
    if (s == nullptr || *s == '\0') return false;
    errno = 0;
    char* end = nullptr;
    const long long v = std::strtoll(s, &end, 10);
    if (errno == ERANGE || end == s || *end != '\0') return false;
    out = v;
    return true;
}

bool ParseFloat(const char* s, float& out) {
    if (s == nullptr || *s == '\0') return false;
    errno = 0;
    char* end = nullptr;
    const double v = std::strtod(s, &end);
    if (errno == ERANGE || end == s || *end != '\0') return false;
    out = static_cast<float>(v);
    return true;
}

const char* NextArg(int argc, char** argv, int& i, const char* flag) {
    if (i + 1 >= argc) {
        std::cerr << "[error] option " << flag << " requires a value\n";
        std::exit(2);
    }
    return argv[++i];
}

std::string ToLower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

bool ParseQuality(const std::string& s, nudec::UastcQuality& out) {
    const std::string v = ToLower(s);
    if (v == "fastest") { out = nudec::UastcQuality::Fastest; return true; }
    if (v == "faster")  { out = nudec::UastcQuality::Faster;  return true; }
    if (v == "default") { out = nudec::UastcQuality::Default; return true; }
    if (v == "slower")  { out = nudec::UastcQuality::Slower;  return true; }
    if (v == "slowest") { out = nudec::UastcQuality::Slowest; return true; }
    return false;
}


bool IsPng(const fs::path& p) {
    return ToLower(p.extension().string()) == ".png";
}

// -----------------------------------------------------------------------------
//  進捗表示 (キャリッジリターンで1行を上書き)
// -----------------------------------------------------------------------------
void PrintProgress(uint32_t done, uint32_t total) {
    if (total == 0) return;
    const int width = 30;
    const int filled = static_cast<int>(static_cast<double>(done) / total * width);
    std::fprintf(stderr, "\r  [");
    for (int i = 0; i < width; ++i) std::fputc(i < filled ? '#' : '.', stderr);
    std::fprintf(stderr, "] %u/%u", done, total);
    if (done == total) std::fputc('\n', stderr);
    std::fflush(stderr);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        PrintUsage(argv[0]);
        return 2;
    }

    // ---- parse args -------------------------------------------------------
    std::string input_json;
    std::string output_dir;
    nudec::PackOptions opt;
    bool recursive = false;
    bool dry_run   = false;
    bool show_progress = true;

    std::vector<std::string> positional;

    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];

        if (a == "-h" || a == "--help") {
            PrintUsage(argv[0]);
            return 0;
        } else if (a == "-o" || a == "--out-name") {
            opt.file_name = NextArg(argc, argv, i, a.c_str());
        } else if (a == "-t" || a == "--tile-size") {
            long long v = 0;
            if (!ParseInt64(NextArg(argc, argv, i, a.c_str()), v) || v < 4 || v % 4 != 0) {
                std::cerr << "[error] --tile-size must be a multiple of 4 and >= 4\n";
                return 2;
            }
            opt.max_tile_size = static_cast<uint32_t>(v);
        } else if (a == "-l" || a == "--max-layers") {
            long long v = 0;
            if (!ParseInt64(NextArg(argc, argv, i, a.c_str()), v) || v < 1) {
                std::cerr << "[error] --max-layers must be >= 1\n";
                return 2;
            }
            opt.max_array_layers = static_cast<uint32_t>(v);
        } else if (a == "-b" || a == "--budget-mb") {
            long long v = 0;
            if (!ParseInt64(NextArg(argc, argv, i, a.c_str()), v) || v < 1) {
                std::cerr << "[error] --budget-mb must be >= 1\n";
                return 2;
            }
            opt.memory_budget_bytes = static_cast<uint64_t>(v) * 1024ull * 1024ull;
        } else if (a == "-q" || a == "--quality") {
            const char* v = NextArg(argc, argv, i, a.c_str());
            if (!ParseQuality(v, opt.uastc_quality)) {
                std::cerr << "[error] unknown quality '" << v
                          << "' (fastest|faster|default|slower|slowest)\n";
                return 2;
            }
        } else if (a == "--no-rdo") {
            opt.uastc_rdo = false;
        } else if (a == "--rdo-quality") {
            float v = 0.0f;
            if (!ParseFloat(NextArg(argc, argv, i, a.c_str()), v) || v <= 0.0f) {
                std::cerr << "[error] --rdo-quality must be a positive number\n";
                return 2;
            }
            opt.uastc_rdo_quality = v;
        } else if (a == "-z" || a == "--zstd") {
            long long v = 0;
            if (!ParseInt64(NextArg(argc, argv, i, a.c_str()), v) || v < 0 || v > 22) {
                std::cerr << "[error] --zstd must be in 0..22\n";
                return 2;
            }
            opt.zstd_level = static_cast<int>(v);
        } else if (a == "-j" || a == "--threads") {
            long long v = 0;
            if (!ParseInt64(NextArg(argc, argv, i, a.c_str()), v) || v < 0) {
                std::cerr << "[error] --threads must be >= 0\n";
                return 2;
            }
            opt.thread_count = static_cast<int>(v);
        } else if (a == "-m" || a == "--mipmaps") {
            opt.generate_mipmaps = true;
        } else if (a == "--linear") {
            opt.srgb = false;
        } else if (a == "-r" || a == "--recursive") {
            recursive = true;
        } else if (a == "-n" || a == "--dry-run") {
            dry_run = true;
        } else if (a == "-Q" || a == "--quiet") {
            opt.verbose   = false;
            show_progress = false;
        } else if (!a.empty() && a[0] == '-') {
            std::cerr << "[error] unknown option: " << a << "\n";
            return 2;
        } else {
            positional.push_back(a);
        }
    }

    if (positional.size() != 2) {
        std::cerr << "[error] expected exactly 2 positional arguments "
                     "(<input_json> <output_dir>), got "
                  << positional.size() << "\n\n";
        PrintUsage(argv[0]);
        return 2;
    }
    input_json  = positional[0];
    output_dir = positional[1];

    if (fs::path(opt.file_name).extension().empty()) {
        opt.file_name += nudec::kNudecExtension;
    }

    try {
        std::ifstream file(input_json);
        if (!file.is_open()) {
            std::cerr << "ファイルを開けませんでした。" << std::endl;
            return 1;
        }

        json j;
        try{
            file >> j;
        } catch (const json::parse_error& e) {
            std::cerr << "JSONのパースエラー: " << e.what() << std::endl;
            return 1;
        }

        std::unordered_map<int, std::string> input_seq;
        for (const auto& [key, value] : j.items()) {
            try {
                input_seq.emplace(std::stoi(key), value.get<std::string>());
            } catch (const std::invalid_argument&) {
                std::cerr << "non-numeric key skipped: " << key << "\n";
            }
        }

        std::cout << "JSONの型チェック: " 
          << (j.is_object() ? "Object (OK)" : "Not Object (Error)") << std::endl;


        if (input_seq.empty()) {
            std::cerr << "[error] no usable PNG files found in " << input_json << "\n";
            return 1;
        }


        if (dry_run) {
            std::cout << "[nudec] dry run - layer order:\n";
            uint32_t layer = 0;
            for (const auto& kv : input_seq) {
                std::cout << "  layer " << layer++ << "  frame " << kv.first
                          << "  " << kv.second << "\n";
            }
            std::cout << "[nudec] dry run complete; nothing was written.\n";
            return 0;
        }

        if (show_progress) {
            opt.progress = &PrintProgress;
        }

        const nudec::PackResult r =
            nudec::PackPngSequence(input_seq, output_dir, opt);

        if (opt.verbose) {
            const double src_mb =
                static_cast<double>(r.frame_width) * r.frame_height * 4.0 *
                r.frame_count / (1024.0 * 1024.0);
            const double out_mb =
                static_cast<double>(r.file_size_bytes) / (1024.0 * 1024.0);

            std::cout << "\n"
                      << "  file        : " << r.file_path        << "\n"
                      << "  frames      : " << r.frame_count      << "\n"
                      << "  frame size  : " << r.frame_width << "x" << r.frame_height << "\n"
                      << "  tile grid   : " << r.tile_cols << "x" << r.tile_rows
                      << " (" << r.tile_width << "x" << r.tile_height << " each)\n"
                      << "  layers      : " << r.layer_count      << "\n"
                      << "  mip levels  : " << r.level_count      << "\n"
                      << "  chunks      : " << r.chunk_count      << "\n"
                      << "  size        : " << out_mb << " MiB\n"
                      << "  vs raw RGBA : " << src_mb << " MiB ("
                      << (src_mb > 0.0 ? out_mb / src_mb * 100.0 : 0.0) << "%)\n";
        }
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "\n[error] " << e.what() << "\n";
        return 1;
    }
}