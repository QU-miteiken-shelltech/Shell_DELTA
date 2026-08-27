#include "nudec_pack.h"

#include <ktx.h>
#include <glad/gl.h>

#include <cstdint>
#include <array>
#include <fstream>
#include <vector>
#include <stdexcept>

constexpr std::array<char, 8> MAGIC = {'N', 'U', 'D', 'E', 'C', '\0', '\0', '\0'};
constexpr int32_t VERSION = 1;
constexpr size_t HEADER_SIZE = sizeof(nudec::NudecHeader);
constexpr size_t CHUNK_SIZE = sizeof(nudec::NudecChunkEntry);
constexpr std::array<uint8_t, 12> KTX2_MAGIC = {
    0xAB, 0x4B, 0x54, 0x58, 0x20, 0x32,
    0x30, 0xBB, 0x0D, 0x0A, 0x1A, 0x0A
};
constexpr size_t COPY_BUF = 8 * 1024 * 1024;

nudec::NudecHeader ReadHeader(std::ifstream& f);

bool VerifyKtx2(
    std::ifstream& f, 
    nudec::NudecChunkEntry c
);

std::vector<uint8_t> LoadKtxChunk(
    std::ifstream& f, 
    nudec::NudecChunkEntry c
);

GLuint KtxToGLTexture(const std::vector<uint8_t>& ktx_raw);