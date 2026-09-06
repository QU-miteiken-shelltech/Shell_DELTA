import json
from pathlib import Path
from typing import Any

from shell_delta.gb_var import get_gbvar_ctx
from shell_delta.gb_var import get_gbvar_full
from shell_delta.render import time_map

gb_var = get_gbvar_ctx()
gb_var_full = get_gbvar_full()

class IO_sdproj:
    def __init__(self):
        pass

    @classmethod
    def write_sdproj(cls, 
                    saving_path: str,
                    writing_info: dict
                    ) -> None:
        if not str(saving_path).endswith(".sdproj"):
            if "." in saving_path:
                saving_path_split = saving_path.split(".")
                saving_path_split.pop(-1)
                saving_path = "".join(saving_path_split)
            saving_path += ".sdproj"
        if saving_path is not None and Path(saving_path).exists():
            with open(saving_path, "r", encoding="utf-8") as f:
                current_sdproj = json.load(f)
            for writing_attr in writing_info:
                current_sdproj[writing_attr] = writing_info[writing_attr]
        else:
            current_sdproj = writing_info
        with open(saving_path, "w", encoding="utf-8") as f:
            json.dump(current_sdproj, f, indent=3, ensure_ascii=False)
        gb_var.saving_path = Path(saving_path)

    @classmethod
    def load_sdproj(cls,
                   reading_path: str
                   ) -> None:
        if reading_path is None or not Path(reading_path).exists():
            return
        with open(reading_path, "r", encoding="utf-8") as f:
            current_sdproj = json.load(f)
        current_time_map = current_sdproj.get("time_map", [])
        for time_map_i in current_time_map:
            time_map.time_map.append({int(k) : int(v) for k, v in time_map_i.items()})
        gb_var.base_frame_list = [int(i) for i in current_sdproj.get("base_frame_list", [])]
        gb_var.sequence_root_dir = Path(current_sdproj["sequence_root_dir"]) if "sequence_root_dir" in current_sdproj else None
        gb_var.mata_filename = current_sdproj.get("mata_filename", None)
        gb_var.first_sequence_idx = current_sdproj.get("first_sequence_idx", 0)
        gb_var.frame_notation_len = current_sdproj.get("frame_notation_len", 0)
        gb_var.ref_video_start = current_sdproj.get("ref_video_start", 0)
        ref_path = current_sdproj.get("ref_path", None)
        gb_var.ref_path = Path(ref_path) if ref_path is not None else None
        gb_var.saving_path = Path(reading_path)

    @classmethod
    def read_sdproj(cls,
                   reading_path: str,
                   reading_attr: str
                   ) -> Any:
        if reading_path is None or not Path(reading_path).exists():
            return
        with open(reading_path, "r", encoding="utf-8") as f:
            current_sdproj = json.load(f)
        return current_sdproj.get(reading_attr, None)


        