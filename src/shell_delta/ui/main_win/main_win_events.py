from PySide6.QtWidgets import QMenu

from shell_delta.utils.editing_utils import EditingUtils
from shell_delta import gb_var as gb_var_script

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

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
                new_image_paths=str(new_image_path)
            )
        else:
            self.ref_gl_widget.change_image(
                new_image_paths=str(new_image_path)
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

