#include "nudec_pack.h"
#include "nudec_decode.h"

#include <glad/gl.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <ktx.h>

#include <cstdint>
#include <cstring>
#include <array>
#include <fstream>
#include <vector>
#include <stdexcept>

namespace py = pybind11;

static std::array<GLuint, 2> texture_buffer{};
static nudec::NudecHeader nudec_header;
static std::vector<nudec::NudecChunkEntry> chunk_entries;
static std::string nuanim_path;

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

std::vector<nudec::NudecChunkEntry> ReadChunkEntries(
    std::ifstream&f, nudec::NudecHeader header
){
    f.seekg(header.chunk_table_offset, std::ios::beg);
    std::vector<nudec::NudecChunkEntry> chunk_entries{};
    chunk_entries.resize(header.chunk_count);
    f.read(reinterpret_cast<char*>(chunk_entries.data()), CHUNK_SIZE * header.chunk_count);
    return chunk_entries;
}

std::vector<uint8_t> LoadKtxChunk(std::ifstream& f, nudec::NudecChunkEntry c){
    f.seekg(c.offset, std::ios::beg);
    std::array<uint8_t, 12> magic{};
    f.read(reinterpret_cast<char*>(magic.data()), KTX2_MAGIC.size());
    bool is_verified = (magic == KTX2_MAGIC);
    if (!is_verified){
        throw std::runtime_error("KTX2 format verification failed");
    }

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

std::array<GLuint, 2> InitTextureBuffer(const std::string& path){
    glDeleteTextures(1, &texture_buffer[0]);
    glDeleteTextures(1, &texture_buffer[1]);
    nuanim_path = path;
    std::ifstream ifs(nuanim_path, std::ios::binary);
    if (!ifs){
        throw std::runtime_error("File loading error");
    }

    nudec_header = ReadHeader(ifs);
    chunk_entries = ReadChunkEntries(ifs, nudec_header);
    for (int i = 0; i < 2; ++i){
        nudec::NudecChunkEntry chunk_entry = chunk_entries[i % chunk_entries.size()];
        std::vector<uint8_t> ktx_raw = LoadKtxChunk(ifs, chunk_entry);
        GLuint gl_tex_id = KtxToGLTexture(ktx_raw);
        texture_buffer[i % texture_buffer.size()] = gl_tex_id;
    }
    return texture_buffer;
}

std::array<GLuint, 2> UpdateTextureBuffer(const int chunk_idx){
    if (chunk_idx > chunk_entries.size() - 1 || chunk_entries.size() == 0){
        throw std::runtime_error("Chunk index out of range");
    }
    std::ifstream ifs(nuanim_path, std::ios::binary);
    if (!ifs){
        throw std::runtime_error("File loading error");
    }
    glDeleteTextures(1, &texture_buffer[0]);
    texture_buffer[0] = texture_buffer[1];
    nudec::NudecChunkEntry chunk_entry = chunk_entries[chunk_idx % chunk_entries.size()];
    std::vector<uint8_t> ktx_raw = LoadKtxChunk(ifs, chunk_entries);
    GLuint gl_tex_id = KtxToGLTexture(ktx_raw);
    texture_buffer[1] = gl_tex_id;

    return texture_buffer;
}