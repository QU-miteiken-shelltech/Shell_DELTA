from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from shell_delta import gb_var
from shell_delta.ui.main_win.main_win_ui import MainWinUIMixin
from shell_delta.ui.main_win.main_win_io import MainWinIOMixin
from shell_delta.ui.main_win.main_win_playback import MainWinPlaybackMixin
from shell_delta.ui.main_win.main_win_events import MainWinEventsMixin


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

        gb_var.frame_notation_len = 0
        self.is_on_main_window = True
        self.inputting = False
        self.seq_idx = 0
        self.ref_seq_idx = 0
        self.ref_frame_offset = 0

        self._init_ui()
