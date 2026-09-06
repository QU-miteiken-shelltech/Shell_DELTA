#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aTex;

out vec2 vTex;

uniform vec2 uScale;

void main() {
    gl_Position = vec4(aPos * uScale, 0.0, 1.0);
    vTex = aTex;
}
