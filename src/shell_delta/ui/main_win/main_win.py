from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QApplication

from shell_delta import gb_var as gb_var_script
from shell_delta.render import time_map
from shell_delta.utils.editing_utils import EditingUtils
from shell_delta.ui.main_win.main_win_ui import MainWinUIMixin
from shell_delta.ui.main_win.main_win_io import MainWinIOMixin
from shell_delta.ui.main_win.main_win_playback import MainWinPlaybackMixin
from shell_delta.ui.main_win.main_win_events import MainWinEventsMixin
 
gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class MainUserUi(QWidget, 
                 MainWinUIMixin, 
                 MainWinIOMixin, 
                 MainWinPlaybackMixin, 
                 MainWinEventsMixin
                 ):
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        gb_var_full.frame_notation_len = 0
        self.is_on_main_window = True
        self.inputting = False
        self.seq_idx = 0
        self.ref_seq_idx = 0
        self.ref_frame_offset = 0

        self._init_ui()

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
            time_map.time_map[time_map.active_layer][self.seq_idx] = int(self.input_frame_num_str)
            actual_filename = EditingUtils.get_actual_filepath(
                img_idx=time_map.time_map[time_map.active_layer][self.seq_idx], 
                layer=time_map.active_layer
            )
            designated_image_path = gb_var.sequence_root_dir / actual_filename
            if not designated_image_path.exists():
                designated_image_path = str(Path(__file__).resolve().parents[2] / "_resources" / "fallback.png")
            self.input_frame_num_str = ""
            self.gl_widget.change_image(new_image_paths=designated_image_path)
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
