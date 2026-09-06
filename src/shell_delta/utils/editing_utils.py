import re
from pathlib import Path

from shell_delta.render import time_map
from shell_delta import gb_var as gb_var_script

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class EditingUtils:
    @classmethod
    def get_actual_img_idx(cls,
                           seq_idx: int,
                           layer: int
                           ) -> int:
        actual_img_idx = time_map.time_map[layer].get(seq_idx, None)
        if actual_img_idx is not None:
            return actual_img_idx
        checking_idx = seq_idx - 1
        while actual_img_idx is None and checking_idx >= 0:
            actual_img_idx = time_map.time_map[layer].get(checking_idx, None)
            checking_idx -= 1
        return actual_img_idx if actual_img_idx is not None else -1

    @classmethod
    def get_actual_filepath(cls,
                            img_idx: int,
                            layer: int
                            ) -> str:
        actual_filename = gb_var_full.mata_filename[layer].replace(
            '#' * gb_var_full.frame_notation_len[layer], 
            f"{img_idx:0{gb_var_full.frame_notation_len[layer]}d}"
            )
        return actual_filename

    @classmethod
    def get_base_frames(cls,
                        layer: int
                        ) -> list[int]:
        root_dir = Path(gb_var_full.sequence_root_dir[layer])
        if root_dir is None or not root_dir.exists():
            return
        escaped_template = re.escape(gb_var_full.mata_filename[layer])
        regex_pattern = re.sub(r"#+", r"(\\d+)", escaped_template)
        compiled_regex = re.compile(f"^{regex_pattern}$")
        glob_pattern = re.sub(r"#+", "*", gb_var_full.mata_filename[layer])
        base_frames = []
        for file_path in root_dir.glob(glob_pattern):
            match = compiled_regex.match(file_path.name)
            if match:
                base_frames.append(int(match.group(1)))
        return base_frames