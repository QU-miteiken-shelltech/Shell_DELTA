import sys
import ctypes
from pathlib import Path

import numpy as np
import OpenGL.GL as gl

from PySide6.QtGui import QImage, QSurfaceFormat
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QMessageBox,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture

MAX_LAYERS = 16

class GLWidget(QOpenGLWidget):
    """GLSLでA/Bの合成を行うOpenGL描画ウィジェット"""

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = paths
        # self.path_a = path_a
        # self.path_b = path_b
        self.show_idx = 0

        self.program = None
        self.tex = []
        # self.tex_a = None
        # self.tex_b = None
        self.vao = None
        self.vbo = None

        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        self.setFormat(fmt)

    def set_show_b(self):
        self.show_idx += 1
        self.update()

    def load_texture(self, path: str) -> QOpenGLTexture:
        img = QImage(path)
        if img.isNull():
            raise RuntimeError(f"画像を読み込めませんでした: {path}")
        img = img.convertToFormat(QImage.Format_RGBA8888)

        tex = QOpenGLTexture(QOpenGLTexture.Target2D)
        tex.setData(img)
        tex.setMinificationFilter(QOpenGLTexture.Linear)
        tex.setMagnificationFilter(QOpenGLTexture.Linear)
        tex.setWrapMode(QOpenGLTexture.ClampToEdge)
        return tex

    def initializeGL(self):
        gl.glClearColor(0.15, 0.15, 0.15, 1.0)

        self.program = QOpenGLShaderProgram()
        vtx_shader_path = Path("/Users/shiinaayame/Documents/ShellDelta/src/shell_delta/shaders/utils/vertex_shader.glsl")
        frag_shader_path = Path("/Users/shiinaayame/Documents/ShellDelta/src/shell_delta/shaders/utils/alpha_blending.glsl")
        if not vtx_shader_path.exists() or not frag_shader_path.exists():
            return
        with open(vtx_shader_path, "r", encoding="utf-8") as f:
            vertex_shader = f.read()
        with open(frag_shader_path, "r", encoding="utf-8") as f:
            fragment_shader = f.read()
        self.program.addShaderFromSourceCode(QOpenGLShader.Vertex, vertex_shader)
        self.program.addShaderFromSourceCode(QOpenGLShader.Fragment, fragment_shader)
        if not self.program.link():
            QMessageBox.critical(self, "シェーダエラー", self.program.log())
            QApplication.instance().quit()
            return

        vertices = np.array(
            [
                -1.0, -1.0, 0.0, 1.0,
                 1.0, -1.0, 1.0, 1.0,
                -1.0,  1.0, 0.0, 0.0,
                 1.0, -1.0, 1.0, 1.0,
                 1.0,  1.0, 1.0, 0.0,
                -1.0,  1.0, 0.0, 0.0,
            ],
            dtype=np.float32,
        )

        self.vao = gl.glGenVertexArrays(1)
        gl.glBindVertexArray(self.vao)

        self.vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)

        stride = 4 * 4  # 4 floats * 4 bytes
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))
        gl.glEnableVertexAttribArray(1)

        gl.glBindVertexArray(0)

        # --- テクスチャ読み込み ---
        try:
            for p in self.paths:
                self.tex.append(self.load_texture(p))
        except RuntimeError as e:
            QMessageBox.critical(self, "エラー", str(e))
            QApplication.instance().quit()

    def resizeGL(self, w, h):
        gl.glViewport(0, 0, max(w, 1), max(h, 1))

    def paintGL(self):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        self.program.bind()

        if self.tex:
            img_w, img_h = self.tex[0].width(), self.tex[0].height()
            widget_w, widget_h = max(self.width(), 1), max(self.height(), 1)
            img_aspect = img_w / img_h if img_h else 1.0
            widget_aspect = widget_w / widget_h if widget_h else 1.0
            if widget_aspect > img_aspect:
                scale_x, scale_y = img_aspect / widget_aspect, 1.0
            else:
                scale_x, scale_y = 1.0, widget_aspect / img_aspect
        else:
            scale_x, scale_y = 1.0, 1.0
        self.program.setUniformValue("uScale", scale_x, scale_y)

        n = min(len(self.tex), MAX_LAYERS)  # self.textures: QOpenGLTextureのリスト

        unit_indices = []
        enabled_flags = []
        for i in range(MAX_LAYERS):
            if i < n:
                self.tex[i].bind(i)          # テクスチャユニット i にバインド(アクティブユニット切替も自動)
                unit_indices.append(i)
                enabled_flags.append(1 if self.show_idx >= i else 0)
            else:
                unit_indices.append(0)            # 未使用分はダミーで0番を指すだけ(enabled=0なので実際は参照されない)
                enabled_flags.append(0)

        self.program.setUniformValueArray("uLayers", unit_indices, MAX_LAYERS)
        self.program.setUniformValueArray("uLayerEnabled", enabled_flags, MAX_LAYERS)
        self.program.setUniformValue("uLayerCount", n)
        self.program.setUniformValue("uBgColor", 0.15, 0.15, 0.15)

        gl.glBindVertexArray(self.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 6)
        gl.glBindVertexArray(0)

        for i in range(n):
            self.tex[i].release()
        self.program.release()


class MainWindow(QMainWindow):
    def __init__(self, paths):
        super().__init__()
        self.setWindowTitle("GLSL Alpha Blend Sample ")

        central = QWidget()
        layout = QVBoxLayout(central)

        self.gl_widget = GLWidget(paths=paths)
        layout.addWidget(self.gl_widget, 1)

        self.button = QPushButton("画像Bを重ねる (OFF)")
        self.button.setCheckable(True)
        self.button.toggled.connect(self.on_toggle_b)
        layout.addWidget(self.button)

        self.setCentralWidget(central)
        self.resize(800, 600)

    def on_toggle_b(self):
        self.gl_widget.set_show_b()
        self.button.setText(f"SHOW IDX : {self.gl_widget.show_idx}")


def main():

    paths = []
    for i in range(1, len(sys.argv)):
        paths.append(sys.argv[i])

    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    window = MainWindow(paths=paths)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()