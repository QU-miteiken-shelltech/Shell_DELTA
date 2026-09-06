import numpy
import ctypes
from pathlib import Path

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QImage, QSurfaceFormat, QOpenGLContext
from PySide6.QtOpenGL import (
    QOpenGLTexture, QOpenGLShaderProgram, QOpenGLShader
)
from OpenGL import GL

MAX_LAYERS: int = 8


class OpenGLImageSingleWidget(QOpenGLWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.texture = None
        self.image_ratio = 1.0
        self.program = None
        self.vao = None
        self.vbo = None

    def initializeGL(self):
        GL.glClearColor(0, 0, 0, 1.0)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        self.program = QOpenGLShaderProgram()
        vtx_shader_path = Path(__file__).resolve().parents[1] / "shaders" / "utils" / "vertex_shader.glsl"
        frag_shader_path = Path(__file__).resolve().parents[1] / "shaders" / "utils" / "alpha_blending.glsl"
        if not vtx_shader_path.exists() or not frag_shader_path.exists():
            return
        with open(vtx_shader_path, "r", encoding="utf-8") as f:
            vertex_shader = f.read()
        with open(frag_shader_path, "r", encoding="utf-8") as f:
            fragment_shader = f.read()
        self.program.addShaderFromSourceCode(QOpenGLShader.Vertex, vertex_shader)
        self.program.addShaderFromSourceCode(QOpenGLShader.Fragment, fragment_shader)
        if not self.program.link():
            print("shader_error")
            return

        vertices = numpy.array(
            [
                -1.0, -1.0, 0.0, 1.0,
                1.0, -1.0, 1.0, 1.0,
                -1.0, 1.0, 0.0, 0.0,
                1.0, -1.0, 1.0, 1.0,
                1.0, 1.0, 1.0, 0.0,
                -1.0, 1.0, 0.0, 0.0,
            ],
            dtype=numpy.float32,
        )

        self.vao = GL.glGenVertexArrays(1)
        GL.glBindVertexArray(self.vao)
        self.vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(
            GL.GL_ARRAY_BUFFER,
            vertices.nbytes,
            vertices,
            GL.GL_STATIC_DRAW
        )
        st = 4 * 4
        GL.glVertexAttribPointer(
            0, 2,
            GL.GL_FLOAT, GL.GL_FALSE, st,
            ctypes.c_void_p(0)
        )
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(
            1, 2,
            GL.GL_FLOAT, GL.GL_FALSE, st,
            ctypes.c_void_p(8)
        )
        GL.glBindVertexArray(0)

        image_path = self.image_path if self.image_path else Path(__file__).resolve().parents[1] / "_resources" / "fallback.png"
        image = QImage(image_path)

        if not image.isNull():
            self.image_ratio = image.width() / image.height()
            texture = QOpenGLTexture(image)
            texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            self.texture = texture

    def _load_texture(self, path):
        if self.texture:
            self.texture.destroy()
            self.texture = None

        image = QImage(path)
        if not image.isNull():
            self.image_path = path
            self.image_ratio = image.width() / image.height()

            texture = QOpenGLTexture(image)
            texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            self.texture = texture

    def change_image(self,
                     new_image_path: str | Path
                     ) -> None:
        new_image_path = str(new_image_path)
        self.makeCurrent()
        print("CKPT_single ctx:", id(QOpenGLContext.currentContext()))
        self._load_texture(new_image_path)
        self.resizeGL(self.width(), self.height())
        self.doneCurrent()
        self.update()

    def resizeGL(self, w, h):
        GL.glViewport(0, 0, w, h)


    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        if not self.texture or self.program is None:
            return

        if not self.texture.isCreated() or self.texture.textureId() == 0:
            return

        self.program.bind()

        img_w, img_h = self.texture.width(), self.texture.height()
        widget_w, widget_h = max(self.width(), 1), max(self.height(), 1)
        img_aspect = img_w / img_h if img_h else 1.0
        widget_aspect = widget_w / widget_h if widget_h else 1.0
        if widget_aspect > img_aspect:
            scale_x, scale_y = img_aspect / widget_aspect, 1.0
        else:
            scale_x, scale_y = 1.0, widget_aspect / img_aspect
        self.program.setUniformValue("uScale", scale_x, scale_y)

        self.texture.bind(0)
        unit_indicies = [0] * MAX_LAYERS
        enabled_flags = [0] * MAX_LAYERS
        enabled_flags[0] = 1

        self.program.setUniformValueArray("uLayers", unit_indicies, MAX_LAYERS)
        self.program.setUniformValueArray("uLayerEnabled", enabled_flags, MAX_LAYERS)
        self.program.setUniformValue("uLayerCount", 1)
        self.program.setUniformValue("uBgColor", 0.0, 0.0, 0.0)

        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        GL.glBindVertexArray(0)

        self.texture.release()
        self.program.release()