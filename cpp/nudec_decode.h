#include "nudec_pack.h"

#include <cstdint>
#include <array>
#include <fstream>
#include <stdexcept>

constexpr std::array<char, 8> MAGIC = {'N', 'U', 'D', 'E', 'C', '\0', '\0', '\0'};
constexpr int32_t VERSION = 1;
constexpr size_t HEADER_SIZE = sizeof(NudecHeader);
constexpr size_t CHUNK_SIZE = sizeof(NudecChunkEntry);
constexpr std::array<uint8_t, 12> KTX2_MAGIC = {
    0xAB, 0x4B, 0x54, 0x58, 0x20, 0x32,
    0x30, 0xBB, 0x0D, 0x0A, 0x1A, 0x0A
};
constexpr size_t COPY_BUF = 8 * 1024 * 1024;

NudecHeader ReadHeader(std::ifstream& f){
    f.seekg(0, std::ios::beg);
    if (!f){
        throw std::runtime_error("Seeking failed");
    }
    NudecHeader header{};
    f.read(reinterpret_cast<char*>(&header), HEADER_SIZE);
    if (f.gcount() < static_cast<std::streamsize>(HEADER_SIZE)){
        throw std::runtime_error("File too short");
    }

    if (std::memcmp(header.magic, MAGIC.data(), MAGIC.size()) != 0) {
        throw std::runtime_error("Invalid NUDEC");
    }
    if (header.version != VERSION){
        throw std::runtime_error("Unsupported NUDEC version");
    }
    if (header.headersize != HEADER_SIZE){
        throw std::runtime_error("Header size unmatch");
    }

    return header;
}

bool VerifyKtx2(std::ifstream& f, NudecChunkEntry c){
    f.seekg(c.offset, std::ios::beg);
    std::array<uint8_t, 12> magic{};
    f.read(reinterpret_cast<char*>(magic.data()), KTX2_MAGIC.size());
    bool is_varified = (magic == KTX2_MAGIC);
    return is_varified;
}