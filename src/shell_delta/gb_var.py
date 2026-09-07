from pathlib import Path
from dataclasses import dataclass, field, fields
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
style_script: Any = dark_default

IS_CONFIGED: bool = False
MAX_LAYER: int = 8

class SequenceList(list):
    def __getitem__(self, index):
        layer_order = get_gbvar_full().layer_order
        if isinstance(index, slice):
            return super().__getitem__()
        return [super().__getitem__(layer_order[i]) for i in layer_order[index]]

    def __setitem__(self, index, value):
        layer_order = get_gbvar_full().layer_order
        super().__setitem__(layer_order[index], value)

@dataclass
class GBVar:
    base_frame_list : list[list[int]] = field(default_factory=lambda: SequenceList([[]]))
    sequence_root_dir : list[Path] = field(default_factory=SequenceList)
    mata_filename : list[str] = field(default_factory=SequenceList)
    first_sequence_idx : list[int] = field(default_factory=SequenceList)
    frame_notation_len : list[int] = field(default_factory=SequenceList)
    saving_path : Path | None = None
    ref_path: Path | None = None
    ref_video_start: int = 0
    layer_order: list[int] = field(default_factory=list)

    _instance: Optional["GBVar"] = None

    @classmethod
    def get_instance(cls) -> "GBVar":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __post_init__(self):
        self.layer_order = [i for i in range(0, MAX_LAYER)]

    def initialize(self, 
                   init_data: Optional[Dict[str, Any]]):
        global IS_CONFIGED
        valid_fields = {f.name for f in fields(self)}
        for k, v in init_data.items():
            if k in valid_fields:
                setattr(self, k, v)
            else:
                raise KeyError(f"Key : {k} not exist, so initilization failed")
        IS_CONFIGED = True
        GBVar_CTX.get_instance().initialize()

    def __getattribute__(self, name):
        global IS_CONFIGED
        if name in ("__dict__", "__class__", "__dataclass_fields__") or name.startswith("_"):
            return super().__getattribute__(name)
        attr = super().__getattribute__(name)
        if callable(attr):
            return attr
        if not IS_CONFIGED:
            raise KeyError(f"Unconfiged yet: cannot access '{name}'")
        
        return attr


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

    _instance: Optional["GBVar_CTX"] = None

    @classmethod
    def get_instance(cls) -> "GBVar_CTX":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __getattribute__(self, name):
        global IS_CONFIGED
        if name in ("__dict__", "__class__", "__dataclass_fields__") or name.startswith("_"):
            return super().__getattribute__(name)
        
        attr = super().__getattribute__(name)
        if callable(attr):
            return attr

        if not IS_CONFIGED:
            raise KeyError(f"Unconfiged yet: cannot access '{name}'")
        
        return attr

    def write_to_main(self, active_layer: int):
        gbvar = GBVar.get_instance()
        gbvar.base_frame_list[active_layer] = self.base_frame_list
        gbvar.sequence_root_dir[active_layer] = self.sequence_root_dir
        gbvar.mata_filename[active_layer] = self.mata_filename
        gbvar.first_sequence_idx[active_layer] = self.first_sequence_idx
        gbvar.frame_notation_len[active_layer] = self.frame_notation_len

    def switch_layer(self, 
                     active_layer: int, 
                     do_write_back: bool=True):
        gbvar = GBVar.get_instance()
        if do_write_back:
            self.write_to_main(active_layer=self.active_layer)
        self.active_layer = active_layer
        self.base_frame_list = gbvar.base_frame_list[active_layer]
        self.sequence_root_dir = gbvar.sequence_root_dir[active_layer]
        self.mata_filename = gbvar.mata_filename[active_layer]
        self.first_sequence_idx = gbvar.first_sequence_idx[active_layer]
        self.frame_notation_len = gbvar.frame_notation_len[active_layer]

    def initialize(self):
        gbvar = GBVar.get_instance()
        self.switch_layer(active_layer=0, do_write_back=False)
        self.saving_path = gbvar.saving_path
        self.ref_path = gbvar.ref_path
        self.ref_video_start = gbvar.ref_video_start

def get_gbvar_full():
    return GBVar.get_instance()

def get_gbvar_ctx():
    return GBVar_CTX.get_instance()