from PySide6.QtWidgets import(
    QDialog, QFileDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox
)
from PySide6.QtGui import QIntValidator, QDoubleValidator

from shell_delta.render import render_formats
from shell_delta.render.render import RenderVideo
from shell_delta.gb_var import get_gbvar_ctx
from shell_delta.gb_var import get_gbvar_full
from shell_delta import gb_var as gb_var_global

gb_var = get_gbvar_ctx()
gb_var_full = get_gbvar_full()

class RenderDialog(QDialog):
    def __init__(self, 
                 fps: float):
        super().__init__()
        dialog_lo = QVBoxLayout()
        dialog_lo.setSpacing(10)
        dialog_lo.setContentsMargins(16, 16, 16, 16)
        self.fps = fps

        codec_lo = QHBoxLayout()
        codec_lo.addWidget(QLabel("Codec"))
        self.codec_type_combo = QComboBox()
        self.codec_type_combo.addItems([n for n in render_formats.codec_type_list])
        codec_lo.addWidget(self.codec_type_combo)
        dialog_lo.addLayout(codec_lo)

        container_lo = QHBoxLayout()
        container_lo.addWidget(QLabel("Container"))
        self.container_type_combo = QComboBox()
        self.container_type_combo.addItems([n for n in render_formats.container_type_list])
        container_lo.addWidget(self.container_type_combo)
        dialog_lo.addLayout(container_lo)

        fps_lo = QHBoxLayout()
        fps_lo.addWidget(QLabel("FPS"))
        self.fps_input = QLineEdit(str(self.fps))
        self.fps_input.setValidator(QDoubleValidator())
        fps_lo.addWidget(self.fps_input)
        dialog_lo.addLayout(fps_lo)

        size_lo = QHBoxLayout()
        size_lo.addWidget(QLabel("Size"))
        self.size_x_input = QLineEdit("1920")
        self.size_x_input.setValidator(QIntValidator())
        size_lo.addWidget(self.size_x_input)
        size_lo.addWidget(QLabel("X"))
        self.size_y_input = QLineEdit("1080")
        self.size_y_input.setValidator(QIntValidator())
        size_lo.addWidget(self.size_y_input)
        dialog_lo.addLayout(size_lo)

        range_lo = QHBoxLayout()
        range_lo.addWidget(QLabel("Export Range"))
        self.export_from_input = QLineEdit("0")
        self.export_from_input.setValidator(QIntValidator())
        range_lo.addWidget(self.export_from_input)
        range_lo.addWidget(QLabel("~"))
        self.export_to_input = QLineEdit("1")
        self.export_to_input.setValidator(QIntValidator())
        range_lo.addWidget(self.export_to_input)
        dialog_lo.addLayout(range_lo)

        name_lo = QHBoxLayout()
        name_lo.addWidget(QLabel("Video Name"))
        self.video_name_input = QLineEdit()
        name_lo.addWidget(self.video_name_input)
        dialog_lo.addLayout(name_lo)

        dir_lo = QHBoxLayout()
        dir_lo.addWidget(QLabel("Directory"))
        self.video_dir_input = QLineEdit()
        dir_lo.addWidget(self.video_dir_input)
        browse_file_btn = QPushButton("Browse")
        browse_file_btn.clicked.connect(self.browse_file)
        dir_lo.addWidget(browse_file_btn)
        dialog_lo.addLayout(dir_lo)

        dialog_lo.addStretch
        render_btn = QPushButton("Render")
        render_btn.setObjectName("primaryButton")
        render_btn.clicked.connect(self.send_to_render)
        dialog_lo.addWidget(render_btn)

        self.setStyleSheet(gb_var_global.style_script.REND_DIALOG_STYLESHEET)
        self.setLayout(dialog_lo)

    def browse_file(self):
        dir_selected = QFileDialog.getExistingDirectory(self, "Select a Directory")
        if not dir_selected:
            return
        self.video_dir_input.setText(dir_selected)

    def send_to_render(self):
        codec_4cc=render_formats.codec_type_list[self.codec_type_combo.currentText()]
        container_extension=render_formats.container_type_list[self.container_type_combo.currentText()]
        saving_dir = self.video_dir_input.text().rstrip("/")
        video_name = self.video_name_input.text()
        video_size = (int(self.size_x_input.text()), int(self.size_y_input.text()))
        export_range = (int(self.export_from_input.text()), int(self.export_to_input.text()))
        if not (saving_dir and video_name):
            return
        render_video = RenderVideo(
            codec_type=codec_4cc,
            saving_path=f"{saving_dir}/{video_name}{container_extension}",
            fps=float(self.fps_input.text()),
            size=video_size,
            export_range=export_range
        )
        render_video.compose_video()
        self.accept()