import re
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QFileDialog
import cv2

from shell_delta.render import time_map
from shell_delta.io.io_sdproj import IO_sdproj
from shell_delta.expression.tcl_engine import TCLEngine
from shell_delta.utils.editing_utils import EditingUtils
from shell_delta.gb_var import get_gbvar_ctx
from shell_delta.gb_var import get_gbvar_full

gb_var = get_gbvar_ctx()
gb_var_full = get_gbvar_full()

class MainWinIOMixin:

    def _show_expression_panel(self):
        self.expression_widgets.show()
        self.expression_lang_combo.show()
        self.tcl_widget.command_func_combo.clear()
        self.tcl_widget.command_func_combo.addItems(TCLEngine().get_procs())

    def read_proj(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Sequence", "", "Shell Delta proj. (*.sdproj)")
        if not filename:
            return
        IO_sdproj.load_sdproj(reading_path=filename)
        self.seq_idx = 1
        if gb_var.mata_filename is None:
            return
        self.inputting = False
        actual_img_idx = EditingUtils.get_actual_img_idx(seq_idx=self.seq_idx)
        actual_filename = EditingUtils.get_actual_filepath(img_idx=actual_img_idx)
        self.current_actual_img_idx_label.setText(str(actual_img_idx))
        new_image_path = gb_var.sequence_root_dir / actual_filename
        if not new_image_path.exists():
            new_image_path = ""
        self.current_frame_label.setText(str(self.seq_idx))
        self.gl_widget.change_image(
            new_image_path=str(new_image_path)
            )
        self.ref_gl_widget.change_image(
            new_image_path=str(new_image_path)
        )
        self.current_opened_label.setText(
            f"Working Sequence : {gb_var.sequence_root_dir / gb_var.mata_filename}"
            )
        self.ref_player.setSource(QUrl.fromLocalFile(str(gb_var.ref_path)))
        cv2_videocap = cv2.VideoCapture(str(gb_var.ref_path))
        self.ref_fps = cv2_videocap.get(cv2.CAP_PROP_FPS) if cv2_videocap.isOpened() else 0.0
        cv2_videocap.release()
        self.fps_input_field.setText(str(self.ref_fps))
        self._show_expression_panel()


    def save_proj(self):
        if gb_var.saving_path is None:
            filename, _ = QFileDialog.getOpenFileName(self, "Open Sequence", "", "Shell Delta proj. (*.sdproj)")
            if not filename:
                return
        else:
            filename = str(gb_var.saving_path)
        writing_info = {
            "base_frame_list" : EditingUtils.get_base_frames(),
            "time_map" : time_map.time_map,
            "sequence_root_dir" : str(gb_var.sequence_root_dir),
            "mata_filename" : gb_var.mata_filename,
            "first_sequence_idx" : gb_var.first_sequence_idx,
            "frame_notation_len" : gb_var.frame_notation_len,
            "ref_video_start": gb_var.ref_video_start,
            "ref_path" : str(gb_var.ref_path)
        }
        print(writing_info)
        IO_sdproj.write_sdproj(
            saving_path=filename,
            writing_info=writing_info
            )
        self._show_expression_panel()

    def open_sequence(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Sequence", "", "PNG (*.png)")
        if not filename:
            return
        gb_var.sequence_root_dir = Path(filename).resolve().parent
        matches = re.findall(r'\d+', filename)
        if len(matches) != 1:
            return
        self.gl_widget.change_image(new_image_path=filename)
        self.ref_gl_widget.change_image(new_image_path=filename)
        gb_var.frame_notation_len = len(matches[0])
        gb_var.first_sequence_idx = int(matches[0])
        sharps = '#' * gb_var.frame_notation_len
        filename = re.sub(r'\d+', sharps, filename).split("/")[-1]
        gb_var.mata_filename = filename
        self.seq_idx = gb_var.first_sequence_idx
        self.current_opened_label.setText(
            f"Working Sequence : {gb_var.sequence_root_dir / gb_var.mata_filename}"
            )
        self.current_actual_img_idx_label.setText(str(self.seq_idx))
        self.current_frame_label.setText(str(gb_var.first_sequence_idx))

        parts = [re.escape(p) for p in gb_var.mata_filename.split(sharps)]
        regex_pattern = "^" + r"(\d+)".join(parts) + "$"
        numbers = [
            m.group(1)
            for item in gb_var.sequence_root_dir.iterdir()
            if item.is_file() and (m := re.match(regex_pattern, item.name))
        ]
        for num in numbers:
            num = int(num)
            time_map.time_map[time_map.active_layer][num] = num
        gb_var.base_frame_list = EditingUtils.get_base_frames()

    def open_reference(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Sequence", "", "Video (*.mp4)")
        if not filename:
            return
        self.ref_player.setSource(QUrl.fromLocalFile(filename))
        gb_var.ref_path = filename
        cv2_videocap = cv2.VideoCapture(filename)
        self.ref_fps = cv2_videocap.get(cv2.CAP_PROP_FPS) if cv2_videocap.isOpened() else 0.0
        cv2_videocap.release()
        self.fps_input_field.setText(str(self.ref_fps))
