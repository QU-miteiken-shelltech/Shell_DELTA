from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

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

IS_CONFIGED: bool = False

@dataclass
class GBVar:
    base_frame_list : list[list[int]] = field(default_factory=lambda: [[]])
    sequence_root_dir : list[Path] = field(default_factory=list)
    mata_filename : list[str] = field(default_factory=list)
    first_sequence_idx : list[int] = field(default_factory=list)
    frame_notation_len : list[int] = field(default_factory=list)
    saving_path : Path | None = None
    ref_path: Path | None = None
    ref_video_start: int = 0
    style_script: Any = dark_default

    _instance: Optional["GBVar"] = None

    @classmethod
    def get_instance(cls, 
                     init_data: Optional[Dict[str, Any]] = None
                     ) -> "GBVar":
        global IS_CONFIGED
        if cls._instance is None:
            if init_data is None:
                init_data = {}
            cls._instance = cls(**init_data)
            IS_CONFIGED = True
        return cls._instance

    def __post_init__(self):
        GBVar_CTX.get_instance().initialize()


@dataclass
class GBVar_CTX:
    base_frame_list : list[int] = field(default_factory=list)
    sequence_root_dir : Path | None = None
    mata_filename : str | None = None
    first_sequence_idx : int = 0
    frame_notation_len : int = 0
    active_layer: int = 0
    saving_path : Path | None = None
    ref_path: Path | None = None
    ref_video_start: int = 0
    style_script: Any = dark_default

    _instance: Optional["GBVar_CTX"] = None

    @classmethod
    def get_instance(cls) -> "GBVar_CTX":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def write_to_main(self, active_layer: int):
        gbvar = GBVar.get_instance()
        gbvar.base_frame_list[active_layer] = self.base_frame_list
        gbvar.sequence_root_dir[active_layer] = self.sequence_root_dir
        gbvar.mata_filename[active_layer] = self.mata_filename
        gbvar.first_sequence_idx[active_layer] = self.first_sequence_idx
        gbvar.frame_notation_len[active_layer] = self.frame_notation_len

    def switch_layer(self, active_layer: int):
        gbvar = GBVar.get_instance()
        self.write_to_main(active_layer=active_layer)
        self.active_layer = active_layer
        self.base_frame_list = gbvar.base_frame_list[active_layer]
        self.sequence_root_dir = gbvar.sequence_root_dir[active_layer]
        self.mata_filename = gbvar.mata_filename[active_layer]
        self.first_sequence_idx = gbvar.first_sequence_idx[active_layer]
        self.frame_notation_len = gbvar.frame_notation_len[active_layer]

    def initialize(self):
        gbvar = GBVar.get_instance()
        self.switch_layer(active_layer=0)
        self.saving_path = gbvar.saving_path
        self.ref_path = gbvar.ref_path
        self.ref_video_start = gbvar.ref_video_start
        self.style_script = gbvar.style_script

def get_gbvar_full(init_data: Optional[Dict[str, Any]]=None):
    if not IS_CONFIGED and init_data is None:
        print("Unconfiged")
        return
    return GBVar.get_instance(init_data=init_data)

def get_gbvar_ctx():
    if not IS_CONFIGED:
        print("Unconfiged")
        return
    return GBVar_CTX.get_instance()

