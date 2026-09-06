import json
from pathlib import Path

from PySide6.QtCore import QTimer, QStringListModel
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, 
    QComboBox, QDialog, QLineEdit,
    QLabel, QCompleter
)
from shell_delta.ui.expression_editor import ExpressionEditor
from shell_delta.render import time_map
from shell_delta.expression.tcl_engine import TCLEngine
from shell_delta.expression.cel_engine import CELEngine
from shell_delta.io.io_sdproj import IO_sdproj
from shell_delta import gb_var as gb_var_script
from shell_delta import gb_var as gb_var_global

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class TCLExpressionWidget(QWidget):
    def __init__(self):
        super().__init__()
        lo = QHBoxLayout()
        self.command_func_combo = QComboBox()
        self.command_func_combo.setFixedWidth(300)
        lo.addWidget(self.command_func_combo)
        self.exec_btn = QPushButton("Run Expression")
        self.exec_btn.clicked.connect(self.run_expression)
        lo.addWidget(self.exec_btn)
        self.edit_btn = QPushButton("Edit Expression")
        self.edit_btn.clicked.connect(self.edit_expresion)
        lo.addWidget(self.edit_btn)

        lo.addStretch
        self.from_word_label = QLabel("loop over frames")
        lo.addWidget(self.from_word_label)
        self.run_from_input = QLineEdit("0")
        self.run_from_input.setValidator(QIntValidator())
        lo.addWidget(self.run_from_input)
        self.to_word_label = QLabel(" ~ ")
        lo.addWidget(self.to_word_label)
        self.run_to_input = QLineEdit("1")
        self.run_to_input.setValidator(QIntValidator())
        lo.addWidget(self.run_to_input)
        self.setLayout(lo)

    def edit_expresion(self):
            expression_edit = ExpressionEditor().exec()
            if expression_edit == QDialog.Accepted:
                self.command_func_combo.clear()
                self.command_func_combo.addItems(TCLEngine().get_procs())
    
    def run_expression(self):
        func_name = self.command_func_combo.currentText()
        from_frame = int(self.run_from_input.text())
        to_frame = int(self.run_to_input.text())
        arguements = {
            "frame" : frame,
            "seq_count" : len(gb_var.base_frame_list),
            "loop_count" : to_frame - from_frame + 1,
            "cframe" : int(time_map.time_map[time_map.active_layer].get(frame, frame))
        }
        for frame in range(from_frame, to_frame+1):
            tcl_rtn = TCLEngine().run_tcl(
                func_name=func_name,
                **arguements
            )
            if int(tcl_rtn) in gb_var.base_frame_list:
                time_map.time_map[time_map.active_layer][frame] = int(tcl_rtn)
            else:
                continue
        self.exec_btn.setStyleSheet(f"color : {gb_var_global.style_script.MAIN_WIN_SUCCESS} ;")
        self.exec_btn.setText("Executed")
        self.exec_btn.setEnabled(False)
        IO_sdproj.write_sdproj(
            saving_path=gb_var.saving_path,
            writing_info={"time_map" : time_map.time_map}
        )
        QTimer().singleShot(
            2000, 
            lambda: self._recover_btn(
                btn=self.exec_btn,
                original_text="Run Expression")
            )

    def _recover_btn(self, 
                        btn: QPushButton,
                        original_text: str
                        ):
        btn.setStyleSheet(f"color : {gb_var_global.style_script.MAIN_WIN_TEXT} ;")
        btn.setText(original_text)
        btn.setEnabled(True)


class CELExpressionWidget(QWidget):
    def __init__(self):
        super().__init__()
        lo = QHBoxLayout()
        self.cel_input = QLineEdit()
        self.cel_input.setPlaceholderText("CEL expression ...")
        self.cel_input.setFixedWidth(220)
        lo.addWidget(self.cel_input)
        if not (Path(__file__).resolve().parents[1] / "_resources/expression_presets.json").exists():
            raise Exception
        with open (Path(__file__).resolve().parents[1] / "_resources/expression_presets.json", 
                   "r", encoding="utf-8") as f:
            self.presets = json.load(f)
        preset_completer = QCompleter()
        preset_completer.setModel(QStringListModel(self.presets))
        preset_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.cel_input.setCompleter(preset_completer)
        self.cel_input.editingFinished.connect(self.complete_presets)

        self.exec_btn = QPushButton("Run Expression")
        self.exec_btn.clicked.connect(self.run_expression)
        lo.addWidget(self.exec_btn)

        lo.addStretch
        self.from_word_label = QLabel("loop over frames")
        lo.addWidget(self.from_word_label)
        self.run_from_input = QLineEdit("0")
        self.run_from_input.setValidator(QIntValidator())
        lo.addWidget(self.run_from_input)
        self.to_word_label = QLabel(" ~ ")
        lo.addWidget(self.to_word_label)
        self.run_to_input = QLineEdit("1")
        self.run_to_input.setValidator(QIntValidator())
        lo.addWidget(self.run_to_input)
        self.setLayout(lo)

    def run_expression(self):
        from_frame = int(self.run_from_input.text())
        to_frame = int(self.run_to_input.text())
        cel_engine = CELEngine(
            cel_expression=self.cel_input.text().strip()
        )
        for frame in range(from_frame, to_frame+1):
            cel_rtn = cel_engine.run_cel(
                data={
                    "frame" : frame,
                    "seq_count" : len(gb_var.base_frame_list),
                    "loop_count" : to_frame - from_frame + 1,
                    "cframe" : int(time_map.time_map[time_map.active_layer].get(frame, frame))
                }
            )
            if int(cel_rtn) in gb_var.base_frame_list:
                time_map.time_map[time_map.active_layer][frame] = int(cel_rtn)
            else:
                continue
        self.exec_btn.setStyleSheet(f"color : {gb_var_global.style_script.MAIN_WIN_SUCCESS} ;")
        self.exec_btn.setText("Executed")
        self.exec_btn.setEnabled(False)
        IO_sdproj.write_sdproj(
            saving_path=gb_var.saving_path,
            writing_info={"time_map" : time_map.time_map}
        )
        QTimer().singleShot(
            2000, 
            lambda: self._recover_btn(
                btn=self.exec_btn,
                original_text="Run Expression")
            )

    def complete_presets(self):
        if not self.cel_input.text().startswith("$"):
            return
        preset_used = self.cel_input.text()
        self.cel_input.setText(self.presets.get(preset_used, ""))

    def _recover_btn(self, 
                        btn: QPushButton,
                        original_text: str
                        ):
        btn.setStyleSheet(f"color : {gb_var_global.style_script.MAIN_WIN_TEXT} ;")
        btn.setText(original_text)
        btn.setEnabled(True)