from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPlainTextEdit,
    QPushButton, QHBoxLayout, QFileDialog
)

from shell_delta import gb_var as gb_var_script
from shell_delta import gb_var as gb_var_global
from shell_delta.io.io_sdproj import IO_sdproj

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class ExpressionEditor(QDialog):
    def __init__(self):
        super().__init__()
        self.resize(600,390)

        dialog_lo = QVBoxLayout()
        dialog_lo.setSpacing(10)
        dialog_lo.setContentsMargins(16, 16, 16, 16)

        self.scripting_area = QPlainTextEdit()
        self.scripting_area.setPlaceholderText("Custom Expression")
        self.set_expression()
        dialog_lo.addWidget(self.scripting_area)

        btn_lo = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.save_expression)
        btn_lo.addWidget(save_btn)
        open_tcl_btn = QPushButton("Load TCL")
        open_tcl_btn.clicked.connect(self.load_tcl_script)
        btn_lo.addWidget(open_tcl_btn)
        dialog_lo.addLayout(btn_lo)

        self.setStyleSheet(gb_var_global.style_script.EXP_EDITOR_STYLESHEET)
        self.setLayout(dialog_lo)

    def load_tcl_script(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open TCL Script", "", "TCL Script (*.tcl)")
        if not filename:
            return
        with open(filename, "r", encoding="utf-8") as f:
            expression_content = f.read()
        self.scripting_area.setPlainText(expression_content)

    def save_expression(self):
        saving_path = gb_var.saving_path
        if saving_path is None:
            self.reject()
            return
        IO_sdproj.write_sdproj(
            saving_path=str(saving_path),
            writing_info={"expression" : self.scripting_area.toPlainText()}
        )
        self.accept()

    def set_expression(self):
        saving_path = gb_var.saving_path
        if saving_path is None:
            self.reject()
            return
        current_expression = IO_sdproj.read_sdproj(
            reading_path=str(saving_path),
            reading_attr="expression"
        )
        if current_expression is not None:
            self.scripting_area.setPlainText(current_expression)