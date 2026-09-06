from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPushButton, QDialog
from PySide6.QtMultimedia import QVideoFrame
import psutil

from shell_delta.ui.render_dialog import RenderDialog
from shell_delta.utils.editing_utils import EditingUtils
from shell_delta import gb_var as gb_var_script
from shell_delta import gb_var as gb_var_global

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class MainWinPlaybackMixin:

    def play_sequence(self):
        if not self.gl_widget.ram_img_buffer:
            print("buffering")
            self.gl_widget.send_img_to_buffer()
        mem = round(psutil.virtual_memory().percent)
        self.release_buff_btn.setText(f"Release Buff. ({mem}%)")
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        if self.ref_player.position() == 0:
            self.ref_player.setPosition(gb_var.ref_video_start)
            print(gb_var.ref_video_start)
            self.ref_frame_offset = int((gb_var.ref_video_start / 1000.0) * self.ref_fps)
        self.ref_player.play()
        self.back_to_start_btn.setEnabled(False)

    def pause_sequence(self, arrived_idx):
        self.ref_player.pause()
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.back_to_start_btn.setEnabled(True)

    def back_to_start(self):
        self.ref_player.setPosition(0)

    def release_buffer(self):
        if self.gl_widget.ram_img_buffer:
            self.gl_widget.release_buffer()
            mem = round(psutil.virtual_memory().percent)
            self.release_buff_btn.setText(f"Release Buff. ({mem}%)")

    def on_finished(self):
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)

    def ref_video_proceed(self, frame: QVideoFrame):
        if not frame.isValid() or gb_var.mata_filename is None:
            return
        current_frame = int(round((frame.startTime() / 1000000.0) * self.ref_fps))
        current_frame -= self.ref_frame_offset
        self.seq_idx = current_frame
        self.current_frame_label.setText(str(self.seq_idx))
        next_image_paths = []
        for l in range(0, len(gb_var_full.first_sequence_idx)):
            actual_img_idx = EditingUtils.get_actual_img_idx(seq_idx=self.seq_idx, layer=l)
            actual_filename = EditingUtils.get_actual_filepath(img_idx=actual_img_idx, layer=l)
            self.current_actual_img_idx_label.setText(str(actual_img_idx))
            next_image_path = gb_var.sequence_root_dir / actual_filename
            if not next_image_path.exists():
                next_image_path = str(Path(__file__).resolve().parents[2] / "_resources" / "fallback.png")
            next_image_paths.append(str(next_image_path))
        self.gl_widget.change_image_onram(
            next_image_paths=next_image_paths
        )


    def render_sequence(self):
        render_dialog_call = RenderDialog(fps=int(self.fps_input_field.text())).exec()
        if render_dialog_call == QDialog.Accepted:
            self.render_btn.setStyleSheet(f"color : {gb_var_global.style_script.MAIN_WIN_SUCCESS} ;")
            self.render_btn.setText("Rendered")
            self.render_btn.setEnabled(False)
            QTimer().singleShot(
                2000,
                lambda: self._recover_btn(
                    btn=self.render_btn,
                    original_text="Render")
                )

    def switch_expression_lang(self):
        lang = self.expression_lang_combo.currentText()
        if lang == "TCL":
            self.expression_widgets.setCurrentIndex(0)
        elif lang == "CEL":
            self.expression_widgets.setCurrentIndex(1)
        else:
            self.expression_widgets.setCurrentIndex(0)


    def _recover_btn(self,
                     btn: QPushButton,
                     original_text: str
                     ):
        btn.setStyleSheet(f"color : {gb_var_global.style_script.MAIN_WIN_TEXT} ;")
        btn.setText(original_text)
        btn.setEnabled(True)
