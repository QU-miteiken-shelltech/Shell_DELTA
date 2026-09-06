import gc
from pathlib import Path

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QImage
from PySide6.QtOpenGL import QOpenGLTexture
from OpenGL import GL

from shell_delta.render import time_map
from shell_delta import gb_var as gb_var_script
from shell_delta.utils.editing_utils import EditingUtils

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class OpenGLImageWidget(QOpenGLWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.texture = None
        self.image_ratio = 1.0 
        self.ram_img_buffer: dict[str, tuple[QOpenGLTexture, float]] = {}

    def initializeGL(self):
        GL.glClearColor(0, 0, 0, 1.0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        image = QImage(self.image_path).mirrored()
        
        if not image.isNull():
            # 画像の縦横比を保存
            self.image_ratio = image.width() / image.height()
            
            self.texture = QOpenGLTexture(image)
            self.texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            self.texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)

    def _load_texture(self, path):
        """画像ファイルを読み込み、QOpenGLTexture を生成する内部関数"""
        # 古いテクスチャが存在する場合は破棄してメモリ開放
        if self.texture:
            self.texture.destroy()
            self.texture = None

        image = QImage(path).mirrored()
        if not image.isNull():
            self.image_path = path
            self.image_ratio = image.width() / image.height()

            # 新しいテクスチャを作成
            self.texture = QOpenGLTexture(image)
            self.texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            self.texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)

    def change_image(self, 
                     new_image_path: str | Path
                     ) -> None:
        if self.ram_img_buffer:
            self.change_image_onram(next_image_path=new_image_path)
            return
        new_image_path = str(new_image_path)
        self.makeCurrent()
        self._load_texture(new_image_path)
        self.resizeGL(self.width(), self.height())
        self.doneCurrent()
        self.update()

    def send_img_to_buffer(self):
        if self.ram_img_buffer:
            return
        img_idx_list = []
        for time_map_i in time_map.time_map:
            img_idx_list.append(list(set([int(v) for _, v in time_map_i.items()])))
        img_file_path_list = []
        for idx in range(0, len(img_idx_list)):
            img_idx_list_i = img_idx_list[idx]
            img_file_path_list.append([
                str(gb_var.sequence_root_dir / EditingUtils.get_actual_filepath(img_idx=i)) 
                for i in img_idx_list_i
            ])
        self.ram_img_buffer = {}
        i = 0
        for img_file_path in img_file_path_list[i]:
            image = QImage(img_file_path).mirrored()
            if not image.isNull():
                asp_ratio = image.width() / image.height()
                texture = QOpenGLTexture(image)
                texture.setMinificationFilter(QOpenGLTexture.Filter.Linear)
                texture.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
                self.ram_img_buffer[img_file_path] = (texture, asp_ratio)


    def change_image_onram(self,
                           next_image_path: str | Path
                           ) -> None:
        if not self.ram_img_buffer:
            return
        next_image_path = str(next_image_path)
        try:
            buf = self.ram_img_buffer.get(next_image_path, "")
            self.texture = buf[0]
            self.image_ratio = buf[1]
            self.update()
        except:
            print(next_image_path)
            pass

    def release_buffer(self):
        if not self.ram_img_buffer:
            return
        self.ram_img_buffer.clear()
        self.ram_img_buffer = {}
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
        
        # 投影行列を設定してアスペクト比を補正
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        
        widget_ratio = w / h if h != 0 else 1.0

        # ウィンドウと画像の縦横比を比較し、描画範囲 (glOrtho) を調整
        if widget_ratio > self.image_ratio:
            # ウィンドウの方が横長：左右に余白を作る
            factor = widget_ratio / self.image_ratio
            GL.glOrtho(-factor, factor, -1.0, 1.0, -1.0, 1.0)
        else:
            # ウィンドウの方が縦長：上下に余白を作る
            factor = self.image_ratio / widget_ratio
            GL.glOrtho(-1.0, 1.0, -factor, factor, -1.0, 1.0)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        if not self.texture:
            return

        if not self.texture.isCreated() or self.texture.textureId() == 0:
            self.release_buffer()
            self.send_img_to_buffer()
            return
        self.texture.bind()

        # -1.0 〜 1.0 の正方形の矩形を描画（resizeGL の glOrtho 側で比率を吸収）
        GL.glBegin(GL.GL_QUADS)
        
        GL.glTexCoord2f(0.0, 0.0)
        GL.glVertex2f(-1.0, -1.0)

        GL.glTexCoord2f(1.0, 0.0)
        GL.glVertex2f(1.0, -1.0)

        GL.glTexCoord2f(1.0, 1.0)
        GL.glVertex2f(1.0, 1.0)

        GL.glTexCoord2f(0.0, 1.0)
        GL.glVertex2f(-1.0, 1.0)

        GL.glEnd()

        self.texture.release()


