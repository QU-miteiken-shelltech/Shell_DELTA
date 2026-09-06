from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QStackedWidget
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QDoubleValidator, QIntValidator
import psutil

from shell_delta.ui.opengl import OpenGLImageWidget
from shell_delta.ui.expression_widgets import TCLExpressionWidget, CELExpressionWidget
from shell_delta.gb_var import get_gbvar_ctx
from shell_delta.gb_var import get_gbvar_full
from shell_delta import gb_var as gb_var_global

gb_var = get_gbvar_ctx()
gb_var_full = get_gbvar_full()

class MainWinUIMixin:
    def _init_ui(self):
        main_lo = QVBoxLayout()
        main_lo.setSpacing(10)
        main_lo.setContentsMargins(16, 16, 16, 16)

        io_lo = QHBoxLayout()
        read_btn = QPushButton("Read Sequence")
        read_btn.clicked.connect(self.open_sequence)
        io_lo.addWidget(read_btn)
        read_ref_btn = QPushButton("Read Ref")
        read_ref_btn.clicked.connect(self.open_reference)
        io_lo.addWidget(read_ref_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_proj)
        io_lo.addWidget(save_btn)
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self.read_proj)
        io_lo.addWidget(open_btn)
        main_lo.addLayout(io_lo)

        labels_lo = QHBoxLayout()
        self.current_actual_img_idx_label = QLabel("----")
        self.current_actual_img_idx_label.setFixedWidth(50)
        self.current_actual_img_idx_label.setAlignment(Qt.AlignCenter)
        self.current_actual_img_idx_label.setStyleSheet(
            f"border: 1px solid {gb_var_global.style_script.MAIN_WIN_ACCENT}; border-radius: 6px; "
            f"background-color: {gb_var_global.style_script.MAIN_WIN_PANEL}; color: {gb_var_global.style_script.MAIN_WIN_TEXT}; font-weight: 600;"
        )
        labels_lo.addWidget(self.current_actual_img_idx_label)
        self.current_opened_label = QLabel("Working Sequence : None")
        labels_lo.addWidget(self.current_opened_label)
        main_lo.addLayout(labels_lo)

        graphics_lo = QHBoxLayout()
        self.gl_widget = OpenGLImageWidget("")
        graphics_lo.addWidget(self.gl_widget, stretch=2)

        self.ref_player = QMediaPlayer()
        self.ref_fps = 0.0
        graphics_sublo = QVBoxLayout()
        self.ref_video_widget = QVideoWidget()
        graphics_sublo.addWidget(self.ref_video_widget)
        self.ref_player.setVideoOutput(self.ref_video_widget)
        self.ref_audio_widget = QAudioOutput()
        self.ref_player.setAudioOutput(self.ref_audio_widget)
        self.ref_player.videoSink().videoFrameChanged.connect(self.ref_video_proceed)

        self.ref_video_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ref_video_widget.customContextMenuRequested.connect(self.ref_ctx_menu)

        self.ref_gl_widget = OpenGLImageWidget("")
        self.ref_gl_widget.setObjectName("RefOpenGLWidget")
        graphics_sublo.addWidget(self.ref_gl_widget)
        graphics_lo.addLayout(graphics_sublo, stretch=1)
        main_lo.addLayout(graphics_lo, 6)
        self.ref_seq_idx_label = QLabel("--", self.ref_gl_widget)
        self.ref_seq_idx_label.setStyleSheet("color : white ;")
        self.ref_seq_idx_label.move(15, 10)
        self.ref_seq_idx_label.setFixedWidth(30)

        btn_lo = QHBoxLayout()
        prev_btn = QPushButton("Previous")
        prev_btn.clicked.connect(lambda: self.move_sequence(is_foward=False))
        self.current_frame_label = QLineEdit("0")
        self.current_frame_label.setValidator(QIntValidator())
        self.current_frame_label.setAlignment(Qt.AlignCenter)
        self.current_frame_label.setFixedWidth(60)
        self.current_frame_label.editingFinished.connect(
            lambda: self.move_sequence(is_foward=True, is_increment=False)
        )
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.move_sequence(is_foward=True))
        btn_lo.addWidget(prev_btn)
        btn_lo.addWidget(self.current_frame_label)
        btn_lo.addWidget(next_btn)
        main_lo.addLayout(btn_lo, 2)

        video_lo = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("primaryButton")
        self.play_btn.clicked.connect(self.play_sequence)
        video_lo.addWidget(self.play_btn)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_sequence)
        self.pause_btn.setEnabled(False)
        video_lo.addWidget(self.pause_btn)
        self.back_to_start_btn = QPushButton("Back")
        self.back_to_start_btn.clicked.connect(self.back_to_start)
        video_lo.addWidget(self.back_to_start_btn)
        mem = round(psutil.virtual_memory().percent)
        self.release_buff_btn = QPushButton(f"Release Buff. ({mem}%)")
        self.release_buff_btn.clicked.connect(self.release_buffer)
        video_lo.addWidget(self.release_buff_btn)
        self.render_btn = QPushButton("Render")
        self.render_btn.setObjectName("primaryButton")
        self.render_btn.clicked.connect(self.render_sequence)
        video_lo.addWidget(self.render_btn)
        video_lo.addSpacing

        fps_input_lo = QHBoxLayout()
        fps_label = QLabel("FPS : ")
        fps_label.setFixedWidth(60)
        fps_label.setAlignment(Qt.AlignRight)
        fps_input_lo.addWidget(fps_label)
        self.fps_input_field = QLineEdit("30.0")
        self.fps_input_field.setValidator(QDoubleValidator())
        self.fps_input_field.setFixedWidth(60)
        fps_input_lo.addWidget(self.fps_input_field)
        video_lo.addLayout(fps_input_lo)
        main_lo.addLayout(video_lo, 1)

        expression_lo = QHBoxLayout()
        self.expression_lang_combo = QComboBox()
        self.expression_lang_combo.setFixedWidth(80)
        self.expression_lang_combo.addItems(["TCL", "CEL", "GLSL", "Python"])
        self.expression_lang_combo.setCurrentText("TCL")
        self.expression_lang_combo.currentIndexChanged.connect(self.switch_expression_lang)
        expression_lo.addWidget(self.expression_lang_combo)

        self.expression_widgets = QStackedWidget()
        self.tcl_widget = TCLExpressionWidget()
        self.expression_widgets.addWidget(self.tcl_widget)
        self.cel_widget = CELExpressionWidget()
        self.expression_widgets.addWidget(self.cel_widget)
        expression_lo.addWidget(self.expression_widgets)
        self.expression_widgets.setCurrentIndex(0)
        main_lo.addLayout(expression_lo)

        self.expression_widgets.hide()
        self.expression_lang_combo.hide()

        self.setStyleSheet(gb_var_global.style_script.MAIN_WIN_STYLESHEET)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setLayout(main_lo)

    
