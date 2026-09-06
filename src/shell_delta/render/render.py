from pathlib import Path

import cv2

from shell_delta.render import time_map
from shell_delta.utils.editing_utils import EditingUtils
from shell_delta import gb_var as gb_var_script

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class RenderVideo:
    def __init__(self,
                 codec_type: str,
                 saving_path: str,
                 fps: float,
                 size: tuple[int, int],
                 export_range: tuple[int, int]
                 ) -> None:
        self.codec_type = codec_type
        self.saving_path = saving_path
        self.fps = fps
        self.size = size
        self.export_range = export_range

    def get_video_writer(self) -> cv2.VideoWriter:
        fourcc_codec = cv2.VideoWriter_fourcc(*self.codec_type)
        writer = cv2.VideoWriter(self.saving_path, fourcc_codec, self.fps, self.size)
        return writer

    def compose_video(self):
        time_map_dict = time_map.time_map
        writer = self.get_video_writer()
        idx_to_use = 0
        for i in range (self.export_range[0], self.export_range[1]+1):
            idx_to_use = i if int(i) in time_map_dict or str(i) in time_map_dict else idx_to_use
            actual_filename = EditingUtils.get_actual_filepath(img_idx=idx_to_use)
            image_path = str(gb_var.sequence_root_dir / actual_filename)
            if not Path(image_path).exists():
                image_path = str(Path(__file__).resolve().parents[1] / "_resources/fallback.png")
            frame = cv2.imread(image_path)
            writer.write(frame)
        writer.release()


