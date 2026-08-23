from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu

from shell_delta.render import time_map
from shell_delta.utils.editing_utils import EditingUtils
from shell_delta import gb_var


class MainWinEventsMixin:

    def move_sequence(self,
                      is_foward: bool=True,
                      is_increment: bool=True,
                      increment_step: int=1
                      ):
        if gb_var.mata_filename is None:
            return
        self.inputting = False
        if self.is_on_main_window:
            if is_increment:
                self.seq_idx += increment_step if is_foward else -increment_step
            else:
                self.seq_idx = int(self.current_frame_label.text())
            actual_img_idx = EditingUtils.get_actual_img_idx(seq_idx=self.seq_idx)
            actual_filename = EditingUtils.get_actual_filepath(img_idx=actual_img_idx)
            self.current_actual_img_idx_label.setText(str(actual_img_idx))
            self.current_frame_label.setText(str(self.seq_idx))
        else:
            if is_increment:
                self.ref_seq_idx += increment_step if is_foward else -increment_step
            else:
                self.ref_seq_idx = int(self.current_frame_label.text())
            self.ref_seq_idx_label.setText(str(self.ref_seq_idx))
            actual_filename = EditingUtils.get_actual_filepath(img_idx=self.ref_seq_idx)
        new_image_path = gb_var.sequence_root_dir / actual_filename
        if not new_image_path.exists():
            new_image_path = ""
        if self.is_on_main_window:
            self.gl_widget.change_image(
                new_image_path=str(new_image_path)
            )
        else:
            self.ref_gl_widget.change_image(
                new_image_path=str(new_image_path)
            )

    def ref_ctx_menu(self, pos):
        menu = QMenu(self.ref_video_widget)
        action_01 = menu.addAction("Mark as Start")
        action_01.triggered.connect(
            lambda: setattr(gb_var, 'ref_video_start', int(self.ref_player.position()))
        )
        action_02 = menu.addAction("Reset Starting Point")
        action_02.triggered.connect(
            lambda: setattr(gb_var, 'ref_video_start', 0)
        )


        menu.exec_(self.ref_video_widget.mapToGlobal(pos))


    def keyPressEvent(self, event):
        _move_seq_keys = [
            Qt.Key.Key_Right,
            Qt.Key.Key_Left
        ]
        _num_keys = {
            Qt.Key.Key_0 : 0,
            Qt.Key.Key_1 : 1,
            Qt.Key.Key_2 : 2,
            Qt.Key.Key_3 : 3,
            Qt.Key.Key_4 : 4,
            Qt.Key.Key_5 : 5,
            Qt.Key.Key_6 : 6,
            Qt.Key.Key_7 : 7,
            Qt.Key.Key_8 : 8,
            Qt.Key.Key_9 : 9
        }
        pressed = event.key()
        modifier = event.modifiers()
        if pressed == Qt.Key.Key_Return:
            if not self.inputting:
                return
            self.inputting = False
            time_map.time_map[self.seq_idx] = int(self.input_frame_num_str)
            actual_filename = EditingUtils.get_actual_filepath(img_idx=time_map.time_map[self.seq_idx])
            designated_image_path = gb_var.sequence_root_dir / actual_filename
            if not designated_image_path.exists():
                designated_image_path = ""
            self.input_frame_num_str = ""
            self.gl_widget.change_image(new_image_path=designated_image_path)
        elif pressed in _move_seq_keys:
            if pressed == Qt.Key.Key_Right:
                if (modifier & Qt.KeyboardModifier.ShiftModifier):
                    self.move_sequence(is_foward=True, is_increment=True, increment_step=10)
                else:
                    self.move_sequence(is_foward=True)
            elif pressed == Qt.Key.Key_Left:
                if (modifier & Qt.KeyboardModifier.ShiftModifier):
                    self.move_sequence(is_foward=False, is_increment=True, increment_step=10)
                else:
                    self.move_sequence(is_foward=False)
        elif pressed in _num_keys:
            if gb_var.mata_filename is None:
                return
            if not self.inputting:
                self.inputting = True
                self.input_frame_num_str = ""
            self.input_frame_num_str += str(_num_keys[pressed])
            self.current_actual_img_idx_label.setText(self.input_frame_num_str)

    def mouseMoveEvent(self, event):
        widget_on = QApplication.widgetAt(event.globalPosition().toPoint())
        if widget_on != self.ref_gl_widget:
            self.is_on_main_window = True
            self.ref_seq_idx_label.setStyleSheet("color : white ;")
        else:
            self.is_on_main_window = False
            self.ref_seq_idx_label.setStyleSheet("color : green ;")
