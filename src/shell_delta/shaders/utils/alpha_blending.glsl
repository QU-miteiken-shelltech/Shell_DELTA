#version 330 core
in vec2 vTex;
out vec4 FragColor;

#define MAX_LAYERS 16
uniform sampler2D uLayers[MAX_LAYERS];   
uniform int  uLayerEnabled[MAX_LAYERS]; 
uniform int  uLayerCount;             
uniform vec3 uBgColor;

vec4 over(vec4 top, vec4 bottom) {
    float outA = top.a + bottom.a * (1.0 - top.a);
    vec3 outRGB = (outA > 0.0001)
        ? (top.rgb * top.a + bottom.rgb * bottom.a * (1.0 - top.a)) / outA
        : vec3(0.0);
    return vec4(outRGB, outA);
}

vec4 sampleLayer(int idx) {
    if (idx == 0) return texture(uLayers[0], vTex);
    if (idx == 1) return texture(uLayers[1], vTex);
    if (idx == 2) return texture(uLayers[2], vTex);
    if (idx == 3) return texture(uLayers[3], vTex);
    if (idx == 4) return texture(uLayers[4], vTex);
    if (idx == 5) return texture(uLayers[5], vTex);
    if (idx == 6) return texture(uLayers[6], vTex);
    if (idx == 7) return texture(uLayers[7], vTex);
    return vec4(0.0);
}

void main() {
    vec4 accum = vec4(0.0); 
    for (int i = 0; i < uLayerCount && i < MAX_LAYERS; ++i) {
        if (uLayerEnabled[i] != 0) {
            vec4 layerColor = sampleLayer(i);
            accum = over(layerColor, accum); 
        }
    }
    vec3 finalColor = mix(uBgColor, accum.rgb, accum.a);
    FragColor = vec4(finalColor, 1.0);
}