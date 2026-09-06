"""
opengl.py の OpenGLImageWidget から、シェーダー読み込み〜複数テクスチャの
アルファブレンド描画までの「OpenGL構成そのもの」だけを取り出した最小テスト。

business logic (time_map, gb_var, EditingUtils, RAMバッファ機構など) は
すべて削除している。

使い方:
    python3 test.py <画像パスA> <画像パスB> <画像パスC>
"""

import sys
import ctypes
import numpy
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QImage, QSurfaceFormat
from PySide6.QtOpenGL import (
    QOpenGLTexture, QOpenGLShaderProgram, QOpenGLShader
)
from OpenGL import GL

MAX_LAYERS: int = 8

# シェーダーパスはご指定の絶対パスをそのままハードコード
VERTEX_SHADER_PATH = "/Users/shiinaayame/Documents/ShellDelta/src/shell_delta/shaders/utils/vertex_shader.glsl"
FRAGMENT_SHADER_PATH = "/Users/shiinaayame/Documents/ShellDelta/src/shell_delta/shaders/utils/alpha_blending.glsl"


class TestGLWidget(QOpenGLWidget):
    def __init__(self, image_paths: list[str], parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.texture: list[QOpenGLTexture] = []
        self.image_ratio = 1.0
        self.program = None
        self.vao = None
        self.vbo = None
        # NOTE: QSurfaceFormatの指定はmain()側でQApplication生成前に
        # setDefaultFormat()として行う方針に変更したため、ここでの
        # self.setFormat(fmt)は削除した(役割が重複するため)。

    def initializeGL(self):
        GL.glClearColor(0, 0, 0, 1.0)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        # --- シェーダーのロード & リンク ---
        self.program = QOpenGLShaderProgram()

        vtx_path = Path(VERTEX_SHADER_PATH)
        frag_path = Path(FRAGMENT_SHADER_PATH)
        if not vtx_path.exists() or not frag_path.exists():
            print(f"[ERROR] shader file not found: "
                  f"{vtx_path} exists={vtx_path.exists()}, "
                  f"{frag_path} exists={frag_path.exists()}")
            return

        with open(vtx_path, "r", encoding="utf-8") as f:
            vertex_shader = f.read()
        with open(frag_path, "r", encoding="utf-8") as f:
            fragment_shader = f.read()

        self.program.addShaderFromSourceCode(QOpenGLShader.Vertex, vertex_shader)
        self.program.addShaderFromSourceCode(QOpenGLShader.Fragment, fragment_shader)
        if not self.program.link():
            print("[ERROR] shader link failed:", self.program.log())
            return

        # --- フルスクリーン矩形のVAO/VBO ---
        vertices = numpy.array(
            [
                -1.0, -1.0, 0.0, 1.0,
                 1.0, -1.0, 1.0, 1.0,
                -1.0,  1.0, 0.0, 0.0,
                 1.0, -1.0, 1.0, 1.0,
                 1.0,  1.0, 1.0, 0.0,
                -1.0,  1.0, 0.0, 0.0,
            ],
            dtype=numpy.float32,
        )

        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        self.vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_STATIC_DRAW)

        stride = 4 * 4
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, stride, ctypes.c_void_p(8))
        GL.glEnableVertexAttribArray(1)
        GL.glBindVertexArray(0)

        # --- コマンドライン引数の画像を全てロード ---
        self.texture = []
        for i, p in enumerate(self.image_paths):
            image = QImage(p)
            if image.isNull():
                print(f"[WARN] failed to load image[{i}]: {p}")
                continue
            if i == 0:
                self.image_ratio = image.width() / image.height()
            texture = QOpenGLTexture(image)
            texture.create()
            texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            self.texture.append(texture)

        print(f"[INFO] loaded {len(self.texture)} / {len(self.image_paths)} textures")

    def resizeGL(self, w, h):
        GL.glViewport(0, 0, w, h)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        if not self.texture or self.program is None:
            return

        self.program.bind()

        widget_w, widget_h = max(self.width(), 1), max(self.height(), 1)
        widget_aspect = widget_w / widget_h if widget_h else 1.0
        img_aspect = self.image_ratio if self.image_ratio else 1.0
        if widget_aspect > img_aspect:
            scale_x, scale_y = img_aspect / widget_aspect, 1.0
        else:
            scale_x, scale_y = 1.0, widget_aspect / img_aspect
        self.program.setUniformValue("uScale", scale_x, scale_y)

        n = min(len(self.texture), MAX_LAYERS)

        for t in self.texture:
            if not t.isCreated() or t.textureId() == 0:
                print("[ERROR] a texture is invalid, aborting paint")
                return

        unit_indices = []
        enabled_flags = []
        for i in range(MAX_LAYERS):
            if i < n:
                self.texture[i].bind(i)
                unit_indices.append(i)
                enabled_flags.append(1)
            else:
                unit_indices.append(0)
                enabled_flags.append(0)

        self.program.setUniformValueArray("uLayers", unit_indices, MAX_LAYERS)
        self.program.setUniformValueArray("uLayerEnabled", enabled_flags, MAX_LAYERS)
        self.program.setUniformValue("uLayerCount", n)
        self.program.setUniformValue("uBgColor", 0.0, 0.0, 0.0)

        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        GL.glBindVertexArray(0)

        for i in range(n):
            self.texture[i].release()
        self.program.release()


class MainWindow(QMainWindow):
    """TestGLWidgetを子ウィジェットとして持つだけのシンプルなラッパー。
    今回の検証観点(単体トップレベル表示 vs 子ウィジェット表示)を
    切り分けるためだけに追加したもので、それ以外の機能は持たない。
    """

    def __init__(self, image_paths: list[str]):
        super().__init__()
        self.setWindowTitle("OpenGL Layer Blend Test")

        central = QWidget()
        layout = QVBoxLayout(central)

        self.gl_widget = TestGLWidget(image_paths)
        layout.addWidget(self.gl_widget, 1)

        self.setCentralWidget(central)
        self.resize(800, 600)


def main():
    if len(sys.argv) < 2:
        print("usage: python3 test.py <image1> [image2] [image3] ...")
        sys.exit(1)

    image_paths = sys.argv[1:]
    for p in image_paths:
        if not Path(p).exists():
            print(f"[ERROR] file not found: {p}")
            sys.exit(1)

    # QApplicationを生成する前にアプリ全体のデフォルトフォーマットとして設定する。
    # (ウィジェット単位のsetFormat()ではなく、こちらに一本化した)
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    window = MainWindow(image_paths)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()