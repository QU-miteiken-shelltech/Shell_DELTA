#include "nudec_pack.h"
#include "nudec_decode.h"

#include <ktx.h>
#include <glad/gl.h>

#include <cstdint>
#include <cstring>
#include <array>
#include <fstream>
#include <vector>
#include <stdexcept>

nudec::NudecHeader ReadHeader(std::ifstream& f){
    f.seekg(0, std::ios::beg);
    if (!f){
        throw std::runtime_error("Seeking failed");
    }
    nudec::NudecHeader header{};
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
    if (header.header_size != HEADER_SIZE){
        throw std::runtime_error("Header size unmatch");
    }

    return header;
}

bool VerifyKtx2(std::ifstream& f, nudec::NudecChunkEntry c){
    f.seekg(c.offset, std::ios::beg);
    std::array<uint8_t, 12> magic{};
    f.read(reinterpret_cast<char*>(magic.data()), KTX2_MAGIC.size());
    bool is_varified = (magic == KTX2_MAGIC);
    return is_varified;
}

std::vector<uint8_t> LoadKtxChunk(std::ifstream& f, nudec::NudecChunkEntry c){
    f.seekg(c.offset, std::ios::beg);
    std::vector<uint8_t> ktx_raw(c.size);
    f.read(reinterpret_cast<char*>(ktx_raw.data()), c.size);
    return ktx_raw;
}

GLuint KtxToGLTexture(const std::vector<uint8_t>& ktx_raw){
    ktxTexture2* tex = nullptr;

    KTX_error_code result = ktxTexture2_CreateFromMemory(
        ktx_raw.data(),
        ktx_raw.size(),
        KTX_TEXTURE_CREATE_LOAD_IMAGE_DATA_BIT,
        &tex
    );
    if (result != KTX_SUCCESS){
        throw std::runtime_error("Loading KTX failed" + std::to_string(result));
    }
    if (ktxTexture2_NeedsTranscoding(tex)){
        result = ktxTexture2_TranscodeBasis(tex, KTX_TTF_BC7_RGBA, 0);
        if (result != KTX_SUCCESS){
            ktxTexture_Destroy(ktxTexture(tex));
            throw std::runtime_error("Trascode basis failed" + std::to_string(result));
        }
    }

    GLuint gl_tex_id = 0;
    GLenum gl_target, gl_error;
    result = ktxTexture_GLUpload(
        ktxTexture(tex),
        &gl_tex_id,
        &gl_target,
        &gl_error
    );
    ktxTexture_Destroy(ktxTexture(tex));
    if (result != KTX_SUCCESS){
        throw std::runtime_error(
            "GL Uploading failed " + std::to_string(result) + " and GL error " + std::to_string(gl_error)
        );
    }

    return gl_tex_id;
}