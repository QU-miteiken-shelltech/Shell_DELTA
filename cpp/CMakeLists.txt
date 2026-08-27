# =============================================================================
#  NUDEC - PNG sequence -> UASTC/KTX2 container (.nuanim)
#
#  ビルド:
#    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
#    cmake --build build -j
#
#  libktx の指定方法 (上から順に試される):
#    1. -DNUDEC_FETCH_KTX=ON        KTX-Software を自動ダウンロードしてビルド
#    2. -DKTX_ROOT=<install prefix> インストール済み libktx の場所を明示
#    3. -DCMAKE_PREFIX_PATH=<path>  一般的な CMake の探索パス
#    4. 環境変数 KTX_ROOT
#    5. システム標準パス / pkg-config
#
#  nlohmann/json の指定方法 (上から順に試される):
#    1. -DNUDEC_FETCH_JSON=ON              nlohmann/json を自動ダウンロード
#    2. -DNLOHMANN_JSON_ROOT=<prefix>      展開済みヘッダの場所を明示
#    3. -DCMAKE_PREFIX_PATH=<path>         一般的な CMake の探索パス
#    4. 環境変数 NLOHMANN_JSON_ROOT
#    5. システム標準パス / pkg-config
#
#  glad (OpenGL ローダー) について:
#    configure 時に Dav1dde/glad を FetchContent で取得し、
#    glad_add_library() でローダーを生成する (Python3 + jinja2 が必要)。
#    生成される API/バージョンは -DNUDEC_GLAD_API=<spec> で変更可能
#    (既定値: "gl:core=4.6")。
#
#  その他のオプション:
#    -DNUDEC_BUILD_TOOL=OFF   CLI 実行ファイルを作らずライブラリのみビルド
#    -DOpenCV_DIR=<path>      OpenCVConfig.cmake のあるディレクトリ
# =============================================================================

cmake_minimum_required(VERSION 3.16)

# LANGUAGES に C を含めるのは必須。
# NUDEC_FETCH_KTX=ON のとき KTX-Software をこのビルドツリーに取り込むが、
# libktx の実体は大半が C で書かれている。CXX しか有効化していないと
# "No known features for C compiler" で generate 段階に失敗する。
# 手動リンクの場合は C は不要だが、有効にしていて害はない。
project(nudec
        VERSION 1.0.0
        DESCRIPTION "PNG sequence packer producing UASTC/KTX2 .nuanim containers"
        LANGUAGES C CXX)

# -----------------------------------------------------------------------------
#  グローバル設定
# -----------------------------------------------------------------------------
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    set(NUDEC_IS_TOP_LEVEL ON)
else()
    set(NUDEC_IS_TOP_LEVEL OFF)
endif()

option(NUDEC_BUILD_TOOL "Build the nudec_pack command line tool" ${NUDEC_IS_TOP_LEVEL})
option(NUDEC_FETCH_KTX  "Download and build KTX-Software via FetchContent" OFF)
option(NUDEC_FETCH_JSON "Download nlohmann/json via FetchContent" OFF)
set(NUDEC_KTX_TAG  "v4.3.2"  CACHE STRING "KTX-Software git tag used when NUDEC_FETCH_KTX=ON")
set(NUDEC_JSON_TAG "v3.11.3" CACHE STRING "nlohmann/json git tag used when NUDEC_FETCH_JSON=ON")

# nlohmann_json::nlohmann_json というインポートターゲット名が安定して提供され
# 始めたのが 3.2.0。これより古いものは find_package で見つかってもターゲットが
# 無いか名前が違うため、最低ラインとして扱う。
set(NUDEC_JSON_MIN_VERSION 3.2.0)

# 単一構成ジェネレータでビルドタイプ未指定なら Release を既定にする。
# UASTC エンコードは Debug ビルドだと桁違いに遅くなるため。
get_property(_is_multi_config GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
if(NOT _is_multi_config AND NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
    message(STATUS "[nudec] CMAKE_BUILD_TYPE not set; defaulting to Release")
endif()

# -----------------------------------------------------------------------------
#  依存: OpenCV
# -----------------------------------------------------------------------------
find_package(OpenCV REQUIRED COMPONENTS core imgcodecs imgproc)
message(STATUS "[nudec] OpenCV ${OpenCV_VERSION} : ${OpenCV_INCLUDE_DIRS}")

# =============================================================================
#  依存: libktx (KTX-Software)
#
#  KTX_FEATURE_WRITE=ON かつ Basis エンコーダ有効でビルドされたものが必要。
#  読み込み専用ビルドだと ktxTexture2_CompressBasisEx が未定義参照になるため、
#  この CMakeLists では configure 時に実際にリンクして検証する。
# =============================================================================
set(NUDEC_KTX_TARGET "")
set(NUDEC_KTX_SOURCE "")
set(NUDEC_KTX_SKIP_VERIFY OFF)

# --- 手段 1: FetchContent で自動ビルド ----------------------------------------
if(NUDEC_FETCH_KTX)
    message(STATUS "[nudec] NUDEC_FETCH_KTX=ON : fetching KTX-Software ${NUDEC_KTX_TAG}")
    include(FetchContent)

    # KTX-Software 側のビルドを必要最小限に絞る (ツール/テスト/ドキュメントは不要)
    set(KTX_FEATURE_TESTS          OFF CACHE BOOL "" FORCE)
    set(KTX_FEATURE_TOOLS          OFF CACHE BOOL "" FORCE)
    set(KTX_FEATURE_DOC            OFF CACHE BOOL "" FORCE)
    set(KTX_FEATURE_LOADTEST_APPS  OFF CACHE BOOL "" FORCE)
    set(KTX_FEATURE_STATIC_LIBRARY ON  CACHE BOOL "" FORCE)
    set(KTX_FEATURE_WRITE          ON  CACHE BOOL "" FORCE)

    FetchContent_Declare(ktx_software
        GIT_REPOSITORY https://github.com/KhronosGroup/KTX-Software.git
        GIT_TAG        ${NUDEC_KTX_TAG}
        GIT_SHALLOW    TRUE)
    FetchContent_MakeAvailable(ktx_software)

    foreach(_cand ktx KTX::ktx)
        if(TARGET ${_cand})
            set(NUDEC_KTX_TARGET ${_cand})
            break()
        endif()
    endforeach()

    if(NOT NUDEC_KTX_TARGET)
        message(FATAL_ERROR
            "[nudec] FetchContent succeeded but no 'ktx' target was created.\n"
            "  The KTX-Software target name may have changed in ${NUDEC_KTX_TAG}.")
    endif()
    set(NUDEC_KTX_SOURCE "FetchContent (${NUDEC_KTX_TAG})")
    # まだビルドされていないターゲットには try_compile できないので検証は省略する
    set(NUDEC_KTX_SKIP_VERIFY ON)
endif()

# --- 手段 2: CMake パッケージコンフィグ ---------------------------------------
# KTX-Software はバージョンによって config 名 / ターゲット名が異なりうるため
# 候補を総当たりする。
if(NOT NUDEC_KTX_TARGET)
    foreach(_pkg Ktx KTX ktx)
        find_package(${_pkg} CONFIG QUIET)
    endforeach()

    foreach(_cand KTX::ktx KTX::libktx Ktx::ktx ktx::ktx ktx)
        if(TARGET ${_cand})
            set(NUDEC_KTX_TARGET ${_cand})
            set(NUDEC_KTX_SOURCE "CMake package config (target ${_cand})")
            break()
        endif()
    endforeach()
endif()

# --- 手段 3: pkg-config --------------------------------------------------------
if(NOT NUDEC_KTX_TARGET)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        foreach(_mod ktx libktx)
            if(NOT NUDEC_KTX_TARGET)
                pkg_check_modules(PC_KTX QUIET IMPORTED_TARGET ${_mod})
                if(TARGET PkgConfig::PC_KTX)
                    set(NUDEC_KTX_TARGET PkgConfig::PC_KTX)
                    set(NUDEC_KTX_SOURCE "pkg-config (${_mod})")
                endif()
            endif()
        endforeach()
    endif()
endif()

# --- 手段 4: 手動探索 ----------------------------------------------------------
# インストール済みレイアウトに加え、「ビルドしたが install していない」
# ソースツリーのレイアウトも拾えるようパスサフィックスを増やしてある。
if(NOT NUDEC_KTX_TARGET)
    set(_ktx_hints
        ${KTX_ROOT} $ENV{KTX_ROOT}
        ${KTX_DIR}  $ENV{KTX_DIR}
        ${CMAKE_PREFIX_PATH}
        /usr /usr/local /opt/homebrew /opt/local
        "$ENV{ProgramFiles}/KTX-Software"
        "$ENV{ProgramW6432}/KTX-Software")

    find_path(KTX_INCLUDE_DIR
              NAMES ktx.h
              HINTS ${_ktx_hints}
              PATH_SUFFIXES include include/ktx include/KTX)

    find_library(KTX_LIBRARY
                 NAMES ktx libktx
                 HINTS ${_ktx_hints}
                 PATH_SUFFIXES lib lib64 lib/x64
                               build build/Release build/Debug build/lib)

    if(KTX_INCLUDE_DIR AND KTX_LIBRARY)
        add_library(ktx_imported UNKNOWN IMPORTED)
        set_target_properties(ktx_imported PROPERTIES
            IMPORTED_LOCATION "${KTX_LIBRARY}"
            INTERFACE_INCLUDE_DIRECTORIES "${KTX_INCLUDE_DIR}")
        set(NUDEC_KTX_TARGET ktx_imported)
        set(NUDEC_KTX_SOURCE "manual search (${KTX_LIBRARY})")
    endif()
endif()

# --- どれも駄目だった場合: 何を探したかを全部出す ------------------------------
if(NOT NUDEC_KTX_TARGET)
    message(STATUS "[nudec] --- libktx search report ---")
    message(STATUS "[nudec]   KTX_ROOT (cache) : ${KTX_ROOT}")
    message(STATUS "[nudec]   KTX_ROOT (env)   : $ENV{KTX_ROOT}")
    message(STATUS "[nudec]   CMAKE_PREFIX_PATH: ${CMAKE_PREFIX_PATH}")
    message(STATUS "[nudec]   ktx.h found at   : ${KTX_INCLUDE_DIR}")
    message(STATUS "[nudec]   library found at : ${KTX_LIBRARY}")
    message(STATUS "[nudec] -------------------------------")
    message(FATAL_ERROR
        "[nudec] libktx not found.\n"
        "\n"
        "  Pick one of the following:\n"
        "\n"
        "  (a) Let CMake build it for you (requires network access):\n"
        "        cmake -S . -B build -DNUDEC_FETCH_KTX=ON\n"
        "\n"
        "  (b) Point at an existing install:\n"
        "        cmake -S . -B build -DKTX_ROOT=/path/to/prefix\n"
        "      The prefix must contain include/ktx.h and lib/libktx.*\n"
        "\n"
        "  (c) Point at an un-installed KTX-Software source tree:\n"
        "        cmake -S . -B build -DKTX_ROOT=/path/to/KTX-Software\n"
        "      (its include/ and build/ subdirectories are searched too)\n"
        "\n"
        "  (d) Build and install KTX-Software manually - see README.\n"
        "\n"
        "  NOTE: the library must be built with KTX_FEATURE_WRITE=ON.\n"
        "        Distro packages are often read-only builds and will not work.")
endif()

message(STATUS "[nudec] libktx: ${NUDEC_KTX_SOURCE}")

# --- 書き込み(Basis エンコーダ)対応の検証 --------------------------------------
# ここで落としておかないと、リンク段階で ktxTexture2_CompressBasisEx が
# 未定義参照になるまで気づけない。
if(NOT NUDEC_KTX_SKIP_VERIFY)
    include(CheckCXXSourceCompiles)
    set(CMAKE_REQUIRED_LIBRARIES ${NUDEC_KTX_TARGET})
    check_cxx_source_compiles("
        #include <ktx.h>
        int main() {
            ktxBasisParams p{};
            p.structSize = sizeof(p);
            p.uastc = KTX_TRUE;
            ktxTexture2* t = nullptr;
            (void)ktxTexture2_CompressBasisEx(t, &p);
            (void)ktxTexture2_DeflateZstd(t, 18);
            return 0;
        }" NUDEC_KTX_HAS_WRITE)
    unset(CMAKE_REQUIRED_LIBRARIES)

    if(NOT NUDEC_KTX_HAS_WRITE)
        message(FATAL_ERROR
            "[nudec] The libktx found at:\n"
            "          ${NUDEC_KTX_SOURCE}\n"
            "        does not provide the Basis/UASTC writer API.\n"
            "        It was most likely built with KTX_FEATURE_WRITE=OFF\n"
            "        (a read-only build), or Zstd support is missing.\n"
            "\n"
            "        Rebuild KTX-Software with -DKTX_FEATURE_WRITE=ON, or use\n"
            "        -DNUDEC_FETCH_KTX=ON to have CMake build a correct one.")
    endif()
    message(STATUS "[nudec] libktx write/UASTC support: OK")
endif()

# =============================================================================
#  依存: nlohmann/json
#
#  ヘッダオンリーなのでリンク対象のバイナリは無いが、
#  「include path が通っているか」「3.x 系か」は configure 時に確認しておく。
#  2.x 系は API が別物 (nlohmann::json::parse のシグネチャ等) なので、
#  コンパイルエラーで初めて気づく事態を避ける。
# =============================================================================
set(NUDEC_JSON_TARGET "")
set(NUDEC_JSON_SOURCE "")
set(NUDEC_JSON_SKIP_VERIFY OFF)

# --- 手段 1: FetchContent で自動取得 ------------------------------------------
if(NUDEC_FETCH_JSON)
    message(STATUS "[nudec] NUDEC_FETCH_JSON=ON : fetching nlohmann/json ${NUDEC_JSON_TAG}")
    include(FetchContent)

    # json 側のテストと install ルールは不要。
    # JSON_Install=ON のままだと、こちらの install(EXPORT) と衝突しうる。
    set(JSON_BuildTests OFF CACHE INTERNAL "")
    set(JSON_Install    OFF CACHE INTERNAL "")

    FetchContent_Declare(nlohmann_json
        GIT_REPOSITORY https://github.com/nlohmann/json.git
        GIT_TAG        ${NUDEC_JSON_TAG}
        GIT_SHALLOW    TRUE)
    FetchContent_MakeAvailable(nlohmann_json)

    foreach(_cand nlohmann_json::nlohmann_json nlohmann_json)
        if(TARGET ${_cand})
            set(NUDEC_JSON_TARGET ${_cand})
            break()
        endif()
    endforeach()

    if(NOT NUDEC_JSON_TARGET)
        message(FATAL_ERROR
            "[nudec] FetchContent succeeded but no 'nlohmann_json' target was created.\n"
            "  The target name may have changed in ${NUDEC_JSON_TAG}.")
    endif()
    set(NUDEC_JSON_SOURCE "FetchContent (${NUDEC_JSON_TAG})")
    # libktx と同じ理由: 自プロジェクト内のターゲットは try_compile から参照できない
    set(NUDEC_JSON_SKIP_VERIFY ON)
endif()

# --- 手段 2: CMake パッケージコンフィグ ---------------------------------------
if(NOT NUDEC_JSON_TARGET)
    find_package(nlohmann_json ${NUDEC_JSON_MIN_VERSION} CONFIG QUIET)

    foreach(_cand nlohmann_json::nlohmann_json nlohmann_json)
        if(TARGET ${_cand})
            set(NUDEC_JSON_TARGET ${_cand})
            set(NUDEC_JSON_SOURCE "CMake package config (target ${_cand}, version ${nlohmann_json_VERSION})")
            break()
        endif()
    endforeach()
endif()

# --- 手段 3: pkg-config --------------------------------------------------------
if(NOT NUDEC_JSON_TARGET)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        foreach(_mod nlohmann_json nlohmann-json)
            if(NOT NUDEC_JSON_TARGET)
                pkg_check_modules(PC_JSON QUIET IMPORTED_TARGET ${_mod})
                if(TARGET PkgConfig::PC_JSON)
                    set(NUDEC_JSON_TARGET PkgConfig::PC_JSON)
                    set(NUDEC_JSON_SOURCE "pkg-config (${_mod})")
                endif()
            endif()
        endforeach()
    endif()
endif()

# --- 手段 4: 手動探索 ----------------------------------------------------------
# インストール済みの include/nlohmann/json.hpp に加え、
# GitHub のリリース zip をそのまま置いた場合の single_include/ も拾う。
if(NOT NUDEC_JSON_TARGET)
    set(_json_hints
        ${NLOHMANN_JSON_ROOT} $ENV{NLOHMANN_JSON_ROOT}
        ${JSON_ROOT}          $ENV{JSON_ROOT}
        ${CMAKE_PREFIX_PATH}
        ${CMAKE_CURRENT_SOURCE_DIR}/third_party/json
        ${CMAKE_CURRENT_SOURCE_DIR}/external/json
        /usr /usr/local /opt/homebrew /opt/local)

    find_path(NLOHMANN_JSON_INCLUDE_DIR
              NAMES nlohmann/json.hpp
              HINTS ${_json_hints}
              PATH_SUFFIXES include single_include
                            include/nlohmann_json)

    if(NLOHMANN_JSON_INCLUDE_DIR)
        # ヘッダオンリーなので INTERFACE ライブラリで十分
        add_library(nlohmann_json_imported INTERFACE IMPORTED)
        set_target_properties(nlohmann_json_imported PROPERTIES
            INTERFACE_INCLUDE_DIRECTORIES "${NLOHMANN_JSON_INCLUDE_DIR}")
        set(NUDEC_JSON_TARGET nlohmann_json_imported)
        set(NUDEC_JSON_SOURCE "manual search (${NLOHMANN_JSON_INCLUDE_DIR})")
    endif()
endif()

# --- どれも駄目だった場合 ------------------------------------------------------
if(NOT NUDEC_JSON_TARGET)
    message(STATUS "[nudec] --- nlohmann/json search report ---")
    message(STATUS "[nudec]   NLOHMANN_JSON_ROOT (cache) : ${NLOHMANN_JSON_ROOT}")
    message(STATUS "[nudec]   NLOHMANN_JSON_ROOT (env)   : $ENV{NLOHMANN_JSON_ROOT}")
    message(STATUS "[nudec]   CMAKE_PREFIX_PATH          : ${CMAKE_PREFIX_PATH}")
    message(STATUS "[nudec]   nlohmann/json.hpp found at : ${NLOHMANN_JSON_INCLUDE_DIR}")
    message(STATUS "[nudec] ------------------------------------")
    message(FATAL_ERROR
        "[nudec] nlohmann/json (>= ${NUDEC_JSON_MIN_VERSION}) not found.\n"
        "\n"
        "  Pick one of the following:\n"
        "\n"
        "  (a) Let CMake download it (requires network access):\n"
        "        cmake -S . -B build -DNUDEC_FETCH_JSON=ON\n"
        "\n"
        "  (b) Install it from your package manager, e.g.\n"
        "        apt install nlohmann-json3-dev\n"
        "        brew install nlohmann-json\n"
        "        vcpkg install nlohmann-json\n"
        "\n"
        "  (c) Point at an unpacked release archive:\n"
        "        cmake -S . -B build -DNLOHMANN_JSON_ROOT=/path/to/json\n"
        "      The path must contain include/nlohmann/json.hpp or\n"
        "      single_include/nlohmann/json.hpp\n"
        "\n"
        "  (d) Drop the headers into third_party/json/ or external/json/\n"
        "      next to this CMakeLists.txt - those are searched automatically.")
endif()

message(STATUS "[nudec] nlohmann/json: ${NUDEC_JSON_SOURCE}")

# --- 3.x 系であることの検証 ----------------------------------------------------
# nlohmann/json は C++11 で足りるため、標準規格の指定なしでこのチェックは通る。
if(NOT NUDEC_JSON_SKIP_VERIFY)
    include(CheckCXXSourceCompiles)
    set(CMAKE_REQUIRED_LIBRARIES ${NUDEC_JSON_TARGET})
    check_cxx_source_compiles("
        #include <nlohmann/json.hpp>
        static_assert(NLOHMANN_JSON_VERSION_MAJOR >= 3,
                      \"nudec requires nlohmann/json 3.x or newer\");
        int main() {
            nlohmann::json j;
            j[\"frames\"] = 0;
            j[\"format\"] = \"UASTC\";
            return j.dump().empty() ? 1 : 0;
        }" NUDEC_JSON_USABLE)
    unset(CMAKE_REQUIRED_LIBRARIES)

    if(NOT NUDEC_JSON_USABLE)
        message(FATAL_ERROR
            "[nudec] The nlohmann/json found at:\n"
            "          ${NUDEC_JSON_SOURCE}\n"
            "        could not be compiled against.\n"
            "        It is most likely a 2.x release (the include path was\n"
            "        <json.hpp>, not <nlohmann/json.hpp>) or an incomplete copy.\n"
            "\n"
            "        Install ${NUDEC_JSON_MIN_VERSION} or newer, or use\n"
            "        -DNUDEC_FETCH_JSON=ON to have CMake download a correct one.")
    endif()
    message(STATUS "[nudec] nlohmann/json usable: OK")
endif()

# =============================================================================
#  依存: glad (OpenGL ローダー)
#
#  glad は通常のプリビルド配布物ではなく、必要な API/バージョンに応じて
#  ソースをその場で生成するツールである。ここでは Dav1dde/glad の CMake
#  統合 (glad_add_library) を使い、configure 時に OpenGL ローダーを
#  生成してターゲット化する。
#
#  注意:
#    - configure 時に Python3 (+ jinja2) がビルドマシンに必要
#      (glad の生成スクリプトが Python 製のため)。
#    - ネットワークアクセスが必要 (FetchContent で Dav1dde/glad を取得)。
#    - 生成される API/プロファイルは NUDEC_GLAD_API で変更できる。
#      例: "gl:compat=3.3", "gl:core=4.1" 等。
# =============================================================================
set(NUDEC_GLAD_TAG "v2.0.6"      CACHE STRING "Dav1dde/glad git tag used to fetch the loader generator")
set(NUDEC_GLAD_API "gl:core=4.6" CACHE STRING "glad API spec passed to glad_add_library, e.g. gl:core=4.6")

include(FetchContent)
message(STATUS "[nudec] fetching glad loader generator (Dav1dde/glad ${NUDEC_GLAD_TAG})")
FetchContent_Declare(glad_generator
    GIT_REPOSITORY https://github.com/Dav1dde/glad.git
    GIT_TAG        ${NUDEC_GLAD_TAG}
    GIT_SHALLOW    TRUE
    SOURCE_SUBDIR  cmake)  # Dav1dde/glad のCMake統合(GladConfig.cmake, glad_add_library())は
                           # リポジトリ直下ではなく cmake/ の下にあるため、
                           # FetchContent が自動 add_subdirectory する対象をここで明示する。
FetchContent_MakeAvailable(glad_generator)

if(NOT COMMAND glad_add_library)
    message(FATAL_ERROR
        "[nudec] glad_add_library() is not available after fetching "
        "Dav1dde/glad ${NUDEC_GLAD_TAG}.\n"
        "  This usually means Python 3 (and the 'jinja2' package) is not\n"
        "  available on this machine - glad's generator is written in Python\n"
        "  and CMake invokes it during configure.\n"
        "\n"
        "  Install Python 3 and run: pip install jinja2\n"
        "  then re-run cmake configure.")
endif()

# STATIC ライブラリとして生成する。ターゲット名は nudec_glad。
glad_add_library(nudec_glad STATIC API ${NUDEC_GLAD_API})

set(NUDEC_GLAD_TARGET nudec_glad)
message(STATUS "[nudec] glad: generated via Dav1dde/glad ${NUDEC_GLAD_TAG}, API '${NUDEC_GLAD_API}'")

# =============================================================================
#  ライブラリ本体
#
#  nlohmann/json と OpenCV は PRIVATE でリンクする。
#  nudec_pack.h は標準ライブラリにしか依存しない設計なので、利用側に
#  これらの include path は伝播しない。
#
#  一方 libktx と glad は PUBLIC でリンクする。
#  公開ヘッダ nudec_decode.h が <ktx.h> / <glad/glad.h> を直接 include
#  しており、これを利用する側 (nudec::nudec をリンクする側) にも
#  同じヘッダが見える必要があるため。
# =============================================================================
# ソースが揃っているかを先に確認する。
# add_library が出す "Cannot find source file" は原因が分かりにくいため、
# 何をどこに置くべきかを明示したメッセージに差し替える。
foreach(_src nudec_pack.cpp nudec_pack.h nudec_decode.cpp nudec_decode.h)
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${_src}")
        message(FATAL_ERROR
            "[nudec] missing source file: ${_src}\n"
            "  Expected directory layout:\n"
            "    ${CMAKE_CURRENT_SOURCE_DIR}/\n"
            "      CMakeLists.txt\n"
            "      nudec_pack.h\n"
            "      nudec_pack.cpp\n"
            "      nudec_decode.h\n"
            "      nudec_decode.cpp\n"
            "      entry.cpp        (only needed when NUDEC_BUILD_TOOL=ON)\n")
    endif()
endforeach()

if(NUDEC_BUILD_TOOL AND NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/entry.cpp")
    message(FATAL_ERROR
        "[nudec] missing entry.cpp (required when NUDEC_BUILD_TOOL=ON).\n"
        "  Place it next to CMakeLists.txt, or configure with "
        "-DNUDEC_BUILD_TOOL=OFF to build the library only.")
endif()

add_library(nudec STATIC
    nudec_pack.cpp
    nudec_pack.h
    nudec_decode.cpp
    nudec_decode.h)

add_library(nudec::nudec ALIAS nudec)

target_include_directories(nudec
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
        $<INSTALL_INTERFACE:include>)

target_link_libraries(nudec
    PUBLIC
        ${NUDEC_KTX_TARGET}
        ${NUDEC_GLAD_TARGET}
    PRIVATE
        ${NUDEC_JSON_TARGET}
        ${OpenCV_LIBS})

# std::filesystem: GCC 8 系は libstdc++fs の明示リンクが必要
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 9.0)
    target_link_libraries(nudec PUBLIC stdc++fs)
endif()

set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
target_link_libraries(nudec PRIVATE Threads::Threads)

if(MSVC)
    target_compile_options(nudec PRIVATE /W4 /utf-8 /permissive-)
else()
    target_compile_options(nudec PRIVATE -Wall -Wextra -Wpedantic)
endif()

# -----------------------------------------------------------------------------
#  CLI 実行ファイル
# -----------------------------------------------------------------------------
if(NUDEC_BUILD_TOOL)
    add_executable(nudec_pack entry.cpp)
    target_link_libraries(nudec_pack PRIVATE nudec)

    # CLI 側でも引数やプリセットを JSON で受けたい場合があるため、
    # json だけは実行ファイルにも直接見せておく (ヘッダオンリーなのでコスト無し)。
    # 不要なら次の 1 行を削除してよい。
    target_link_libraries(nudec_pack PRIVATE ${NUDEC_JSON_TARGET})

    if(MSVC)
        target_compile_options(nudec_pack PRIVATE /W4 /utf-8 /permissive-)
    else()
        target_compile_options(nudec_pack PRIVATE -Wall -Wextra -Wpedantic)
    endif()

    set_target_properties(nudec_pack PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
endif()

# -----------------------------------------------------------------------------
#  インストール
# -----------------------------------------------------------------------------
include(GNUInstallDirs)

install(TARGETS nudec
        EXPORT nudecTargets
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES nudec_pack.h nudec_decode.h
        DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

if(NUDEC_BUILD_TOOL)
    install(TARGETS nudec_pack RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()

message(STATUS "[nudec] build type : ${CMAKE_BUILD_TYPE}")
message(STATUS "[nudec] build tool : ${NUDEC_BUILD_TOOL}")
message(STATUS "[nudec] libktx     : ${NUDEC_KTX_SOURCE}")
message(STATUS "[nudec] json       : ${NUDEC_JSON_SOURCE}")
message(STATUS "[nudec] glad       : Dav1dde/glad ${NUDEC_GLAD_TAG}, API '${NUDEC_GLAD_API}'")