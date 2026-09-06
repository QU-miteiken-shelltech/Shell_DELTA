import gc
import numpy
import ctypes
from pathlib import Path

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QImage, QSurfaceFormat, QOpenGLContext
from PySide6.QtOpenGL import (
    QOpenGLTexture, QOpenGLShaderProgram, QOpenGLShader
)
from OpenGL import GL

from shell_delta.render import time_map
from shell_delta import gb_var as gb_var_script
from shell_delta.utils.editing_utils import EditingUtils

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

MAX_LAYERS : int = 8

class OpenGLImageWidget(QOpenGLWidget):
    def __init__(self, image_path: list, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.texture = []
        self.image_ratio = 1.0 
        self.program = None
        self.vao = None
        self.vbo = None

        self.ram_img_buffer: list[dict[str, tuple[QOpenGLTexture, float]]] = []

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
        GL.glEnableVertexAttribArray(1)
        GL.glBindVertexArray(0)

        image_path = self.image_path if self.image_path else Path(__file__).resolve().parents[1] / "_resources" / "fallback.png"
        image = QImage(image_path)
        
        if not image.isNull():
            self.image_ratio = image.width() / image.height()
            texture = QOpenGLTexture(image)
            texture.create()
            texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            self.texture = [texture]

    def _load_textures(self, paths) -> list[QOpenGLTexture]:
        if self.texture:
            for i in range(0, len(self.texture)):
                self.texture[i].destroy()
            self.texture = []

        textures = []
        self.image_path = paths
        for p in paths:
            image = QImage(p)
            if image.isNull():
                continue
            self.image_ratio = image.width() / image.height()
            texture = QOpenGLTexture(image)
            texture.create()
            texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            textures.append(texture)
        return textures

    def change_image(self, 
                     new_image_paths: list[str] | list[Path]
                     ) -> None:
        if self.ram_img_buffer:
            self.change_image_onram(next_image_paths=new_image_paths)
            return
        new_image_paths = [str(x) for x in new_image_paths]
        self.makeCurrent()
        print("CKPT_normal ctx:", id(QOpenGLContext.currentContext()))

        self.texture = self._load_textures(paths=new_image_paths)
        self.resizeGL(self.width(), self.height())
        self.doneCurrent()
        self.update()        

    def send_img_to_buffer(self):
        if self.ram_img_buffer:
            return
        self.makeCurrent()
        img_idx_list = []
        for time_map_i in time_map.time_map:
            img_idx_list.append(list(set([int(v) for _, v in time_map_i.items()])))
        img_file_path_list = []
        for idx in range(0, len(img_idx_list)):
            img_idx_list_i = img_idx_list[idx]
            img_file_path_list.append([
                str(gb_var_full.sequence_root_dir[idx] / EditingUtils.get_actual_filepath(img_idx=i, layer=idx)) 
                for i in img_idx_list_i
            ])

        self.ram_img_buffer = []
        for i in range(0, len(img_idx_list)):
            ram_img_buffer_i = {}
            j = 0
            for img_file_path in img_file_path_list[i][j]:
                image = QImage(img_file_path)
                if not image.isNull():
                    asp_ratio = image.width() / image.height()
                    texture = QOpenGLTexture(image)
                    texture.create()
                    texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
                    texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
                    ram_img_buffer_i[img_file_path] = (texture, asp_ratio)
            self.ram_img_buffer.append(ram_img_buffer_i)
        self.doneCurrent()


    def change_image_onram(self,
                           next_image_paths: list[str] | list[Path]
                           ) -> None:
        if not self.ram_img_buffer:
            return
        print(next_image_paths)
        print("*****")
        next_image_paths = [str(x) for x in next_image_paths]
        try:
            self.texture = []
            for ram_img_buffer_i in self.ram_img_buffer:
                buf = ram_img_buffer_i.get(
                    next_image_paths, 
                    str(Path(__file__).resolve().parents[1] / "_resources" / "fallback.png")
                )
                self.texture.append(buf[0])
                self.image_ratio = buf[1]
            self.update()
        except:
            pass

    def release_buffer(self):
        if not self.ram_img_buffer:
            return
        self.ram_img_buffer.clear()
        self.ram_img_buffer = []
        gc.collect()
        try:
            import platform
            import ctypes
            if platform.system() == "Linux":
                ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass


    def resizeGL(self, w, h):
        GL.glViewport(0, 0, w, h)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        if not self.texture:
            return
        
        self.program.bind()

        img_w, img_h = self.texture[0].width(), self.texture[0].height()
        widget_w, widget_h = max(self.width(), 1), max(self.height(), 1)
        img_aspect = img_w / img_h if img_h else 1.0
        widget_aspect = widget_w / widget_h if widget_h else 1.0
        if widget_aspect > img_aspect:
            scale_x, scale_y = img_aspect / widget_aspect, 1.0
        else:
            scale_x, scale_y = 1.0, widget_aspect / img_aspect
        self.program.setUniformValue("uScale", scale_x, scale_y)

        n = min(len(self.texture), MAX_LAYERS)

        for t in self.texture:
            if not t.isCreated() or t.textureId() == 0:
                self.release_buffer()
                return

        unit_indicies = []
        enabled_flags = []
        for i in range(MAX_LAYERS):
            if i < n:
                self.texture[i].bind(i)
                unit_indicies.append(i)
                enabled_flags.append(1)
            else:
                unit_indicies.append(0)
                enabled_flags.append(0)

        self.program.setUniformValueArray("uLayers", unit_indicies, MAX_LAYERS)
        self.program.setUniformValueArray("uLayerEnabled", enabled_flags, MAX_LAYERS)
        self.program.setUniformValue("uLayerCount", n)
        self.program.setUniformValue("uBgColor", 0.0, 0.0, 0.0)

        GL.glBindVertexArray(self.vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        GL.glBindVertexArray(0)

        for i in range(n):
            self.texture[i].release()
        self.program.release()



