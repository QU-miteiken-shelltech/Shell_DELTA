from pathlib import Path

from shell_delta.style import (
    dark_default, pure_skyblue,
    kawaii_pink, elegant_light
    )
styles = {
    "dark_default" : dark_default, 
    "pure_skyblue" : pure_skyblue,
    "kawaii_pink" : kawaii_pink, 
    "elegant_light" : elegant_light,
}
base_frame_list : list[list[int]] = [[]]
sequence_root_dir : list[Path] = [None]
mata_filename : list[str] = []
first_sequence_idx : list[int] = []
frame_notation_len : list[int] = []
active_layer: int = 0
saving_path : Path | None = None
ref_path: Path | None = None
ref_video_start: int = 0
style_script = dark_default