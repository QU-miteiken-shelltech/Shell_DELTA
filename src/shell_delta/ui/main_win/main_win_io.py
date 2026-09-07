import re
from pathlib import Path
from dataclasses import dataclass, asdict

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import QFileDialog
import cv2

from shell_delta.render import time_map
from shell_delta.io.io_sdproj import IO_sdproj
from shell_delta.expression.tcl_engine import TCLEngine
from shell_delta.utils.editing_utils import EditingUtils
from shell_delta import gb_var as gb_var_script

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

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
        if not gb_var_full.mata_filename:
            return
        self.inputting = False
        new_image_paths = []
        for l in range(0, len(gb_var_full.first_sequence_idx)):
            actual_img_idx = EditingUtils.get_actual_img_idx(seq_idx=self.seq_idx, layer=l)
            actual_filename = EditingUtils.get_actual_filepath(img_idx=actual_img_idx, layer=l)
            self.current_actual_img_idx_label.setText(str(actual_img_idx))
            new_image_path = gb_var_full.sequence_root_dir[l] / actual_filename
            if not new_image_path.exists():
                new_image_path = str(Path(__file__).resolve().parents[2] / "_resources" / "fallback.png")
            new_image_paths.append(str(new_image_path))
        self.current_frame_label.setText(str(self.seq_idx))
        self.gl_widget.change_image(
            new_image_paths=new_image_paths
            )

        actual_img_idx = EditingUtils.get_actual_img_idx(seq_idx=self.seq_idx, layer=0)
        actual_filename = EditingUtils.get_actual_filepath(img_idx=actual_img_idx, layer=0)
        new_image_path = gb_var.sequence_root_dir / actual_filename
        if not new_image_path.exists():
            new_image_path = str(Path(__file__).resolve().parents[2] / "_resources" / "fallback.png")
        self.ref_gl_widget.change_image(
            new_image_path=new_image_path
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
        self.layer_list.clear()
        self.layer_list.addItems([str(i) for i in range(0, len(new_image_paths))])
        self.layer_list.setCurrentRow(0)
        for i in range(0, self.layer_list.count()):
            item = self.layer_list.item(i)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

    def save_proj(self):
        if gb_var.saving_path is None:
            filename, _ = QFileDialog.getOpenFileName(self, "Open Sequence", "", "Shell Delta proj. (*.sdproj)")
            if not filename:
                return
        else:
            filename = str(gb_var.saving_path)
        active_layer = gb_var.active_layer
        gb_var.write_to_main(active_layer=active_layer)
        writing_info = {
            "base_frame_list" : [EditingUtils.get_base_frames(layer=l) for l in range(0, len(gb_var_full.first_sequence_idx))],
            "time_map" : time_map.time_map,
            "sequence_root_dir" : [str(x) for x in gb_var_full.sequence_root_dir],
            "mata_filename" : gb_var_full.mata_filename,
            "first_sequence_idx" : gb_var_full.first_sequence_idx,
            "frame_notation_len" : gb_var_full.frame_notation_len,
            "ref_video_start": gb_var_full.ref_video_start,
            "ref_path" : str(gb_var_full.ref_path)
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
        self.gl_widget.change_image(new_image_paths=filename)
        self.ref_gl_widget.change_image(new_image_paths=filename)
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
            time_map.time_map[gb_var.active_layer][num] = num
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
