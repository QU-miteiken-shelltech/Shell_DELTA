import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader, QOpenGLVertexArrayObject, QOpenGLBuffer
from PySide6.QtGui import QSurfaceFormat
import ctypes

# 共通の頂点シェーダー（全画面の四角形を描画）
VERTEX_SHADER = """
#version 330 core
in vec2 position;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}
"""

# 初期状態のフラグメントシェーダー（青色）
INITIAL_FRAGMENT_SHADER = """
#version 330 core
out vec4 fragColor;
void main() {
    fragColor = vec4(0.0, 0.4, 0.8, 1.0); // 青
}
"""

# ボタンを押したときに適用する新しいフラグメントシェーダーコード (x: str)
NEW_FRAGMENT_SHADER = """
#version 330 core
out vec4 fragColor;
uniform float u_time; // 時間に応じて色が変化するシェーダー
void main() {
    // 時間で赤〜黄に変化させる
    float r = abs(sin(u_time));
    float g = abs(cos(u_time));
    fragColor = vec4(r, g, 0.2, 1.0);
}
"""

# 全画面を覆う三角形ストリップ用の頂点データ (x, y)
QUAD_VERTICES = [
    -1.0, -1.0,
     1.0, -1.0,
    -1.0,  1.0,
     1.0,  1.0,
]


class ShaderWidget(QOpenGLWidget):
    """
    修正点:
    - QOpenGLFunctions の多重継承をやめ、self.context().functions() を使う
      (PySide6での多重継承はクラッシュしやすいため)
    - initializeGL 内では makeCurrent/doneCurrent を呼ばない
      (Qtがすでにコンテキストをcurrentにしているため、doneCurrentを呼ぶと
       以降のpaintGLでコンテキスト状態がおかしくなりセグフォの原因になる)
    - 実際に頂点を描画するようVAO/VBOとglDrawArraysを追加
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shader_program = None
        self.time_val = 0.0
        self.gl = None  # initializeGLで設定するGL関数セット
        self.vao = None
        self.vbo = None

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(16)  # 約60FPS

    def update_animation(self):
        self.time_val += 0.05
        self.update()

    def initializeGL(self):
        # 多重継承の代わりにコンテキストから関数セットを取得する
        self.gl = self.context().functions()

        # VAO/VBOを準備して、実際に描画できるようにする
        self.vao = QOpenGLVertexArrayObject(self)
        self.vao.create()
        self.vao.bind()

        self.vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        self.vbo.create()
        self.vbo.bind()
        vertex_array_type = ctypes.c_float * len(QUAD_VERTICES)
        self.vbo.allocate(vertex_array_type(*QUAD_VERTICES), len(QUAD_VERTICES) * 4)

        self.vao.release()

        # ここでは initializeGL から呼ぶので makeCurrent/doneCurrent はしない
        self._build_shader(INITIAL_FRAGMENT_SHADER, need_context_switch=False)

    def set_fragment_shader_from_source(self, fragment_source: str):
        """外部(ボタンクリックなど)から呼ばれる想定。ここではコンテキストを
        明示的にcurrentにする必要がある。"""
        self._build_shader(fragment_source, need_context_switch=True)

    def _build_shader(self, fragment_source: str, need_context_switch: bool):
        if need_context_switch:
            self.makeCurrent()

        new_program = QOpenGLShaderProgram(self)

        if not new_program.addShaderFromSourceCode(QOpenGLShader.Vertex, VERTEX_SHADER):
            print("Vertex shader error:", new_program.log())
            if need_context_switch:
                self.doneCurrent()
            return

        if not new_program.addShaderFromSourceCode(QOpenGLShader.Fragment, fragment_source):
            print("Fragment shader compilation error:", new_program.log())
            if need_context_switch:
                self.doneCurrent()
            return

        if not new_program.link():
            print("Shader link error:", new_program.log())
            if need_context_switch:
                self.doneCurrent()
            return

        self.shader_program = new_program

        if need_context_switch:
            self.doneCurrent()

        self.update()

    def resizeGL(self, w, h):
        self.gl.glViewport(0, 0, w, h)

    def paintGL(self):
        self.gl.glClearColor(0.1, 0.1, 0.1, 1.0)
        self.gl.glClear(0x00004000)  # GL_COLOR_BUFFER_BIT

        if self.shader_program and self.shader_program.isLinked():
            self.shader_program.bind()
            self.shader_program.setUniformValue("u_time", self.time_val)

            self.vao.bind()
            self.vbo.bind()
            self.shader_program.enableAttributeArray(0)
            self.shader_program.setAttributeBuffer(0, 0x1406, 0, 2, 0)  # GL_FLOAT
            self.gl.glDrawArrays(0x0005, 0, 4)  # GL_TRIANGLE_STRIP

            self.shader_program.disableAttributeArray(0)
            self.vao.release()
            self.shader_program.release()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shader Switcher Example")
        self.resize(600, 400)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        self.opengl_widget = ShaderWidget()
        layout.addWidget(self.opengl_widget)

        self.button = QPushButton("シェーダーを動的に変更 (アニメーション化)")
        self.button.clicked.connect(self.change_shader)
        layout.addWidget(self.button)

        self.setCentralWidget(central_widget)

    def change_shader(self):
        self.opengl_widget.set_fragment_shader_from_source(NEW_FRAGMENT_SHADER)
        self.button.setEnabled(False)


if __name__ == "__main__":
    # OpenGL 3.3 Core Profile を明示的に要求(環境によっては必須)
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())