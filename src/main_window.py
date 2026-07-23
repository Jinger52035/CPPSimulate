"""
main_window.py
主窗口：负责 UI 组装与事件处理，不含任何业务/渲染逻辑。
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QPlainTextEdit, QPushButton, QLabel,
    QFileDialog, QDialog, QStyle,
    QToolBar, QSlider, QTreeWidget, QTreeWidgetItem,
)
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt, QTimer, QSize

from .cpp_interpreter import CppInterpreter, ExecutionStep
from .config import COLORS, AppSettings
from .editor import CodeEditor
from .highlighter import CppHighlighter
from .web_memory_view import WebMemoryView
from .dialogs import SettingsDialog, CrashDialog


EXAMPLE_CURRICULUM = (
    ("01_language_basics", "语言基础", (
        "01_variables.cpp", "02_loop.cpp",
    )),
    ("02_functions_scope_stack", "函数、作用域与调用栈", (
        "03_function_stack.cpp", "08_scope.cpp", "07_recursion.cpp",
    )),
    ("03_pointers_dynamic_memory", "指针与动态内存", (
        "06_pointer_address.cpp", "10_swap.cpp", "04_heap_memory.cpp",
        "11_array_heap.cpp", "13_heap_growth.cpp",
    )),
    ("04_objects_layout", "对象、生命周期与布局", (
        "05_class_object.cpp", "12_multiple_objects.cpp", "09_struct_padding.cpp",
    )),
    ("05_memory_model", "进程内存模型", (
        "14_memory_segments.cpp",
    )),
    ("06_memory_safety", "内存安全错误", (
        "15_wild_pointer.cpp", "16_double_free.cpp", "17_null_deref.cpp",
    )),
    ("07_stl_algorithms", "STL 与算法", (
        "18_vector_basic.cpp", "19_unordered_map.cpp",
    )),
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._interpreter = CppInterpreter()
        self._current_step = -1
        self._auto_timer = QTimer()
        self._auto_timer.timeout.connect(self._auto_next)
        self._auto_speed = 800
        self._settings = AppSettings()

        # examples 目录：和本文件同级的上层目录下的 examples/
        self._examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples"
        )

        self.setWindowTitle("C++ 执行可视化教学工具")
        self.setMinimumSize(960, 620)
        self._apply_global_style()
        self._build_ui()
        self._load_examples()
        self._load_demo()

    # ── 样式 ──────────────────────────────────

    def _apply_global_style(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {COLORS['bg']};
                color: {COLORS['text']};
                font-family: 'Segoe UI', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
                font-size: 13px;
            }}
            QToolBar {{
                background-color: {COLORS['bg_light']};
                border-bottom: 1px solid {COLORS['separator']};
                padding: 4px 8px;
                spacing: 4px;
            }}
            QStatusBar {{
                background: {COLORS['bg_light']};
                color: {COLORS['text_dim']};
                border-top: 1px solid {COLORS['separator']};
                font-size: 11px;
                padding: 0 8px;
            }}
            QPushButton {{
                min-height: 26px;
                background-color: {COLORS['surface_raised']};
                color: {COLORS['fg_default']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 0 11px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
            }}
            QPushButton[iconOnly="true"] {{
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
            }}
            QPushButton[iconOnly="true"]:focus {{
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['border']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['surface_pressed']};
            }}
            QPushButton:focus {{
                border: 2px solid {COLORS['border_focus']};
                padding: 0 10px;
            }}
            QPushButton[variant="primary"] {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border-color: {COLORS['accent']};
            }}
            QPushButton[variant="primary"]:hover {{
                background-color: {COLORS['accent_hover']};
                border-color: {COLORS['accent_hover']};
            }}
            QPushButton[variant="primary"]:pressed {{
                background-color: {COLORS['accent_pressed']};
                border-color: {COLORS['accent_pressed']};
            }}
            QPushButton[variant="toggle"]:checked {{
                background-color: {COLORS['accent_muted']};
                color: #96D0FF;
                border-color: {COLORS['accent']};
            }}
            QPushButton[variant="quiet"] {{
                background-color: transparent;
                border-color: transparent;
                color: {COLORS['fg_muted']};
            }}
            QPushButton[variant="quiet"]:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['fg_default']};
            }}
            QPushButton:disabled {{
                color: {COLORS['fg_subtle']};
                border-color: {COLORS['border_muted']};
                background-color: transparent;
            }}
            QSplitter::handle {{
                background: {COLORS['separator']};
            }}
            QSplitter::handle:hover {{
                background: {COLORS['border']};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['text_dim']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                margin: 0 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {COLORS['border']};
                border-radius: 4px;
                min-width: 24px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
            QToolTip {{
                background: {COLORS['bg_card']};
                color: {COLORS['text_bright']};
                border: 1px solid {COLORS['border']};
                padding: 5px 8px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QGroupBox {{
                color: {COLORS['text_bright']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                margin-top: 12px;
                font-weight: 600;
                font-size: 11px;
                background: {COLORS['stack_bg']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background: {COLORS['stack_bg']};
            }}
            QLabel#executionPanel {{
                min-height: 44px;
                padding: 8px 12px;
                background: {COLORS['surface_subtle']};
                color: {COLORS['fg_muted']};
                border: 1px solid {COLORS['border_muted']};
                border-left: 3px solid {COLORS['accent']};
                border-radius: 5px;
                font-size: 12px;
            }}
            QLabel#executionPanel[danger="true"] {{
                background: {COLORS['danger_bg']};
                color: {COLORS['danger_fg']};
                border-color: {COLORS['danger_border']};
                border-left-color: {COLORS['danger']};
            }}
        """)

    # ── UI 构建 ───────────────────────────────

    def _build_ui(self):
        # 工具栏
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background: {COLORS['bg_light']};
                border-bottom: 1px solid {COLORS['separator']};
                padding: 5px 10px;
                spacing: 4px;
            }}
            QToolBar::separator {{
                background: {COLORS['border']};
                width: 1px;
                margin: 4px 6px;
            }}
        """)

        # App title chip
        app_title = QLabel("C++ 执行可视化")
        app_title.setStyleSheet(f"""
            color: {COLORS['text_bright']};
            font-size: 13px;
            font-weight: 600;
            padding: 0 12px 0 4px;
            letter-spacing: 0.3px;
        """)
        toolbar.addWidget(app_title)
        toolbar.addSeparator()

        standard_icons = QStyle.StandardPixmap
        self._auto_play_icon = self.style().standardIcon(standard_icons.SP_MediaPlay)
        self._auto_pause_icon = self.style().standardIcon(standard_icons.SP_MediaPause)

        def configure_icon_button(button, name, variant, icon, tooltip, accessible_name):
            button.setObjectName(name)
            button.setProperty("variant", variant)
            button.setProperty("iconOnly", True)
            button.setIcon(icon)
            button.setIconSize(QSize(16, 16))
            button.setToolTip(tooltip)
            button.setAccessibleName(accessible_name)
            button.setAccessibleDescription(tooltip)

        self._run_btn = QPushButton()
        configure_icon_button(
            self._run_btn, "runButton", "primary",
            self.style().standardIcon(standard_icons.SP_MediaPlay),
            "解析并准备执行步骤", "运行",
        )
        self._run_btn.clicked.connect(self._run_code)
        toolbar.addWidget(self._run_btn)

        self._prev_btn = QPushButton()
        configure_icon_button(
            self._prev_btn, "previousButton", "secondary",
            self.style().standardIcon(standard_icons.SP_MediaSkipBackward),
            "回退到上一步", "上一步",
        )
        self._prev_btn.clicked.connect(self._step_back)
        self._prev_btn.setEnabled(False)
        toolbar.addWidget(self._prev_btn)

        self._step_btn = QPushButton()
        configure_icon_button(
            self._step_btn, "stepButton", "secondary",
            self.style().standardIcon(standard_icons.SP_MediaSkipForward),
            "执行下一步", "单步执行",
        )
        self._step_btn.clicked.connect(self._step_forward)
        self._step_btn.setEnabled(False)
        toolbar.addWidget(self._step_btn)

        self._auto_btn = QPushButton()
        configure_icon_button(
            self._auto_btn, "autoButton", "toggle", self._auto_play_icon,
            "自动步进播放", "自动播放",
        )
        self._auto_btn.setCheckable(True)
        self._auto_btn.toggled.connect(self._sync_auto_button_state)
        self._auto_btn.clicked.connect(self._toggle_auto)
        toolbar.addWidget(self._auto_btn)

        self._reset_btn = QPushButton()
        configure_icon_button(
            self._reset_btn, "resetButton", "quiet",
            self.style().standardIcon(standard_icons.SP_BrowserReload),
            "重置到初始状态", "重置",
        )
        self._reset_btn.clicked.connect(self._reset)
        self._reset_btn.setEnabled(False)
        toolbar.addWidget(self._reset_btn)

        toolbar.addSeparator()
        speed_lbl = QLabel("速度")
        speed_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; padding: 0 4px 0 2px;")
        toolbar.addWidget(speed_lbl)

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(100, 2000)
        self._speed_slider.setValue(800)
        self._speed_slider.setFixedWidth(100)
        self._speed_slider.setInvertedAppearance(True)
        self._speed_slider.valueChanged.connect(self._on_speed_change)
        self._speed_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: {COLORS['bg_card']};
                border-radius: 2px;
                margin: 0;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLORS['accent']};
                border-radius: 2px;
            }}
            QSlider::add-page:horizontal {{
                background: {COLORS['border']};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px;
                height: 12px;
                margin: -4px 0;
                background: #FFFFFF;
                border-radius: 6px;
                border: 2px solid {COLORS['accent']};
            }}
            QSlider::handle:horizontal:hover {{
                border-color: {COLORS['accent_hover']};
                background: {COLORS['accent_hover']};
            }}
            QSlider:focus {{
                border: 1px solid {COLORS['border_focus']};
                border-radius: 5px;
            }}
        """)
        toolbar.addWidget(self._speed_slider)

        toolbar.addSeparator()

        settings_btn = QPushButton("⚙ 设置")
        settings_btn.setObjectName("settingsButton")
        settings_btn.setProperty("variant", "quiet")
        settings_btn.clicked.connect(self._open_settings)
        settings_btn.setToolTip("内存面板布局与分段粒度设置")
        toolbar.addWidget(settings_btn)

        self.addToolBar(toolbar)

        # 状态栏
        self._status_bar = self.statusBar()
        self._step_label = QLabel("未运行")
        self._step_label.setStyleSheet(f"""
            color: {COLORS['accent']};
            font-size: 11px;
            font-weight: 600;
            padding: 0 6px;
        """)
        self._status_bar.addPermanentWidget(self._step_label)

        # 中央区域
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {COLORS['border']}; }}")

        # 左侧：文件列表 + 编辑器区（水平 Splitter）
        left_widget = QWidget()
        left_widget.setMinimumWidth(360)
        left_outer = QHBoxLayout(left_widget)
        left_outer.setContentsMargins(0, 0, 0, 0)
        left_outer.setSpacing(0)

        # ── 文件列表面板
        file_panel = QWidget()
        file_panel.setFixedWidth(180)
        file_panel.setStyleSheet(f"""
            background: {COLORS['bg_light']};
            border-right: 1px solid {COLORS['separator']};
        """)
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(0)

        file_bar = QWidget()
        file_bar.setObjectName("fileBar")
        file_bar.setStyleSheet(f"""
            QWidget#fileBar {{
                background: {COLORS['surface']};
                border-bottom: 1px solid {COLORS['border_muted']};
            }}
        """)
        file_bar_layout = QHBoxLayout(file_bar)
        file_bar_layout.setContentsMargins(10, 6, 8, 6)
        file_bar_layout.setSpacing(6)
        file_label = QLabel("File")
        file_label.setStyleSheet(
            f"color: {COLORS['fg_default']}; font-size: 12px; font-weight: 600;"
        )
        open_btn = QPushButton("打开")
        open_btn.setObjectName("openButton")
        open_btn.setProperty("variant", "secondary")
        open_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        open_btn.setIconSize(QSize(14, 14))
        open_btn.setToolTip("打开 C++ 文件")
        open_btn.setAccessibleName("打开文件")
        open_btn.setAccessibleDescription("打开 C++ 文件")
        open_btn.clicked.connect(self._open_file)
        file_bar_layout.addWidget(file_label)
        file_bar_layout.addStretch()
        file_bar_layout.addWidget(open_btn)
        file_layout.addWidget(file_bar)

        file_header = QWidget()
        file_header.setObjectName("examplesHeader")
        file_header.setStyleSheet(f"""
            QWidget#examplesHeader {{
                background: {COLORS['surface_subtle']};
                border-bottom: 1px solid {COLORS['border_muted']};
            }}
        """)
        file_header_layout = QHBoxLayout(file_header)
        file_header_layout.setContentsMargins(10, 7, 8, 7)
        file_header_layout.setSpacing(6)
        file_hdr = QLabel("Examples")
        file_hdr.setStyleSheet(f"color: {COLORS['fg_default']}; font-size: 12px; font-weight: 600;")
        self._example_count = QLabel("0")
        self._example_count.setObjectName("examplesCount")
        self._example_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._example_count.setStyleSheet(f"""
            QLabel#examplesCount {{
                min-width: 22px;
                color: {COLORS['fg_subtle']};
                background: {COLORS['surface_raised']};
                border: 1px solid {COLORS['border_muted']};
                border-radius: 8px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: 600;
            }}
        """)
        file_header_layout.addWidget(file_hdr)
        file_header_layout.addStretch()
        file_header_layout.addWidget(self._example_count)
        file_layout.addWidget(file_header)

        self._file_list = QTreeWidget()
        self._file_list.setHeaderHidden(True)
        self._file_list.setRootIsDecorated(True)
        self._file_list.setIndentation(12)
        self._file_list.setUniformRowHeights(True)
        self._file_list.setStyleSheet(f"""
            QTreeWidget {{
                background: {COLORS['surface_subtle']};
                border: 1px solid transparent;
                outline: none;
                font-size: 12px;
                color: {COLORS['fg_muted']};
                padding: 4px;
            }}
            QTreeWidget:focus {{
                border-color: {COLORS['border_focus']};
            }}
            QTreeWidget::item {{
                min-height: 27px;
                padding: 0 4px;
                border: 1px solid transparent;
                border-radius: 4px;
            }}
            QTreeWidget::item:has-children {{
                color: {COLORS['fg_default']};
                font-weight: 600;
            }}
            QTreeWidget::item:selected {{
                background: {COLORS['accent_muted']};
                color: {COLORS['fg_default']};
                border-color: #315F8C;
            }}
            QTreeWidget::item:hover:!selected {{
                background: {COLORS['surface_hover']};
                color: {COLORS['fg_default']};
            }}
            QTreeWidget::branch {{
                background: transparent;
            }}
        """)
        self._file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._file_list.itemClicked.connect(self._on_example_clicked)
        file_layout.addWidget(self._file_list)
        left_outer.addWidget(file_panel)

        # ── 编辑器区（编辑器 + 说明 + 输出）
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(10, 0, 0, 0)
        editor_layout.setSpacing(6)

        code_label = QLabel("Source")
        code_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: 11px;
            font-weight: 600;
            padding: 2px 0;
        """)
        editor_layout.addWidget(code_label)

        self._editor = CodeEditor()
        self._editor.setReadOnly(False)
        CppHighlighter(self._editor.document())
        editor_layout.addWidget(self._editor, stretch=4)

        desc_label = QLabel("Execution")
        desc_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: 11px;
            font-weight: 600;
            padding: 2px 0;
        """)
        editor_layout.addWidget(desc_label)

        self._desc_box = QLabel("点击「运行」开始解析代码")
        self._desc_box.setObjectName("executionPanel")
        self._desc_box.setProperty("danger", False)
        self._desc_box.setWordWrap(True)
        editor_layout.addWidget(self._desc_box)

        out_label = QLabel("Output")
        out_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: 11px;
            font-weight: 600;
            padding: 2px 0;
        """)
        editor_layout.addWidget(out_label)

        self._output_box = QPlainTextEdit()
        self._output_box.setReadOnly(True)
        self._output_box.setMaximumHeight(84)
        self._output_box.setStyleSheet(f"""
            background: {COLORS['canvas']};
            color: #78C980;
            border: 1px solid {COLORS['border_muted']};
            border-radius: 5px;
            font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
            font-size: 12px;
            padding: 4px 6px;
        """)
        editor_layout.addWidget(self._output_box)

        left_outer.addWidget(editor_widget, stretch=1)

        splitter.addWidget(left_widget)

        # 右侧：内存可视化区
        right_widget = QWidget()
        self._right_widget = right_widget
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        # 多栏内容在内部横向滚动，右侧 viewport 本身允许收缩。
        right_widget.setMinimumWidth(0)

        self._memory_view = WebMemoryView(self._settings)
        self._memory_view.errorOccurred.connect(self._on_memory_view_error)
        right_layout.addWidget(self._memory_view)
        splitter.addWidget(right_widget)
        splitter.setSizes([500, 780])

        main_layout.addWidget(splitter)

    # ── 事件处理 ──────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings(dlg.get_settings())

    def _apply_settings(self, new_settings: AppSettings):
        self._settings = new_settings
        step = self._interpreter.get_step(self._current_step) if self._current_step >= 0 else None
        self._refresh_memory(step)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 C++ 文件", "", "C++ Files (*.cpp *.h *.cxx *.cc);;All Files (*)"
        )
        if path:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            self._editor.setPlainText(code)
            self._reset()
            self._status_bar.showMessage(f"已加载: {path}")

    def _run_code(self):
        code = self._editor.toPlainText()
        if not code.strip():
            self._status_bar.showMessage("代码为空")
            return
        self._interpreter.load(code)
        self._interpreter.build_steps()
        total = self._interpreter.total_steps()
        if total == 0:
            self._desc_box.setText("未能解析出任何执行步骤。请检查代码是否包含 main 函数。")
            self._status_bar.showMessage("解析完成，0 步")
            return
        self._current_step = -1
        self._step_btn.setEnabled(True)
        self._prev_btn.setEnabled(False)
        self._reset_btn.setEnabled(True)
        self._step_label.setText(f"0 / {total}")
        self._desc_box.setText(f"解析完成，共 {total} 个执行步骤。点击「单步」开始。")
        self._status_bar.showMessage(f"解析完成，共 {total} 步")
        self._refresh_memory(None)

    def _step_forward(self):
        total = self._interpreter.total_steps()
        if self._current_step + 1 >= total:
            self._auto_timer.stop()
            self._auto_btn.setChecked(False)
            self._desc_box.setText("✓ 执行完毕")
            return
        self._current_step += 1
        self._show_step(self._current_step)
        self._prev_btn.setEnabled(self._current_step > 0)

    def _step_back(self):
        if self._current_step <= 0:
            return
        self._current_step -= 1
        self._show_step(self._current_step)
        self._prev_btn.setEnabled(self._current_step > 0)

    def _sync_auto_button_state(self, checked: bool):
        if checked:
            self._auto_btn.setIcon(self._auto_pause_icon)
            self._auto_btn.setAccessibleName("暂停自动播放")
            self._auto_btn.setToolTip("暂停自动步进")
        else:
            self._auto_btn.setIcon(self._auto_play_icon)
            self._auto_btn.setAccessibleName("自动播放")
            self._auto_btn.setToolTip("自动步进播放")

    def _toggle_auto(self, checked):
        if checked:
            self._auto_timer.start(self._auto_speed)
        else:
            self._auto_timer.stop()

    def _auto_next(self):
        total = self._interpreter.total_steps()
        if self._current_step + 1 >= total:
            self._auto_timer.stop()
            self._auto_btn.setChecked(False)
            self._desc_box.setText("✓ 执行完毕")
            return
        self._step_forward()

    def _reset(self):
        self._auto_timer.stop()
        self._auto_btn.setChecked(False)
        self._interpreter.reset()
        self._current_step = -1
        self._step_btn.setEnabled(False)
        self._prev_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)
        self._step_label.setText("未运行")
        self._desc_box.setProperty("danger", False)
        self._desc_box.style().unpolish(self._desc_box)
        self._desc_box.style().polish(self._desc_box)
        self._desc_box.setText("点击「运行」开始解析代码")
        self._editor.clear_highlight()
        self._output_box.clear()
        self._refresh_memory(None)

    def _on_speed_change(self, value):
        self._auto_speed = value
        if self._auto_timer.isActive():
            self._auto_timer.setInterval(value)

    # ── 步骤展示 ──────────────────────────────

    def _show_step(self, index: int):
        step = self._interpreter.get_step(index)
        if step is None:
            return
        total = self._interpreter.total_steps()
        self._step_label.setText(f"步骤 {index + 1} / {total}")
        self._editor.highlight_line(step.line_index)

        self._desc_box.setProperty("danger", bool(step.crash))
        self._desc_box.style().unpolish(self._desc_box)
        self._desc_box.style().polish(self._desc_box)

        self._desc_box.setText(f"第 {step.line_index + 1} 行 → {step.description}")
        if step.output:
            self._output_box.setPlainText(step.output)
        self._refresh_memory(step)

        # 崩溃步骤：弹出教学弹框，并禁用继续前进
        if step.crash:
            self._step_btn.setEnabled(False)
            self._auto_timer.stop()
            self._auto_btn.setChecked(False)
            dlg = CrashDialog(step.crash, self)
            dlg.exec()

    def _refresh_memory(self, step: ExecutionStep | None):
        self._memory_view.set_state(
            step,
            self._settings,
            list(self._interpreter._functions.keys()),
        )

    def _on_memory_view_error(self, message: str):
        self._auto_timer.stop()
        self._auto_btn.setChecked(False)
        self._status_bar.showMessage(f"内存可视化错误: {message}")

    # ── 示例文件列表 ──────────────────────────

    _SOURCE_SUFFIXES = {".cpp", ".h", ".cxx", ".cc"}

    def _create_example_directory_item(self, label: str, relative_path: str):
        item = QTreeWidgetItem([label])
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        item.setData(0, Qt.ItemDataRole.UserRole, None)
        item.setToolTip(0, relative_path)
        return item

    def _example_display_label(self, path: str) -> str:
        source_path = os.fspath(path)
        stem = os.path.splitext(os.path.basename(source_path))[0]
        title = ""
        try:
            with open(source_path, encoding="utf-8") as source:
                first = source.readline().strip()
                if first.startswith("//"):
                    title = first.lstrip("/ ").strip()
        except OSError:
            pass
        if title:
            if "：" in title:
                title = title.split("：", 1)[1].strip()
            elif ":" in title:
                title = title.split(":", 1)[1].strip()
        if not title or title == stem:
            return stem
        lesson_id = stem.split("_", 1)[0]
        return f"{lesson_id}  {title}"

    def _create_example_file_item(self, path: str):
        fpath = os.path.abspath(os.fspath(path))
        item = QTreeWidgetItem([self._example_display_label(fpath)])
        item.setData(0, Qt.ItemDataRole.UserRole, fpath)
        relative = os.path.relpath(fpath, self._examples_dir)
        item.setToolTip(0, relative)
        return item

    def _add_recursive_example_directory(self, parent, path: str) -> int:
        entries = []
        try:
            entries = list(os.scandir(path))
        except OSError:
            return 0
        entries.sort(key=lambda entry: (not entry.is_dir(follow_symlinks=False), entry.name.lower(), entry.name))
        count = 0
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if os.path.islink(entry.path):
                    continue
                directory_count = self._count_supported_sources(entry.path)
                if not directory_count:
                    continue
                child = self._create_example_directory_item(
                    entry.name, os.path.relpath(entry.path, self._examples_dir)
                )
                parent.addChild(child)
                child.setExpanded(True)
                count += self._add_recursive_example_directory(child, entry.path)
            elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(tuple(self._SOURCE_SUFFIXES)):
                parent.addChild(self._create_example_file_item(entry.path))
                count += 1
        return count

    def _count_supported_sources(self, path: str) -> int:
        count = 0
        try:
            entries = os.scandir(path)
        except OSError:
            return 0
        with entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    if not os.path.islink(entry.path):
                        count += self._count_supported_sources(entry.path)
                elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(tuple(self._SOURCE_SUFFIXES)):
                    count += 1
        return count

    def _load_examples(self):
        """按课程清单和 LeetCode 磁盘层级填充分组示例树。"""
        self._file_list.clear()
        self._example_count.setText("0")
        if not os.path.isdir(self._examples_dir):
            return

        example_count = 0
        for directory, label, filenames in EXAMPLE_CURRICULUM:
            group = self._create_example_directory_item(label, directory)
            self._file_list.addTopLevelItem(group)
            for filename in filenames:
                fpath = os.path.join(self._examples_dir, directory, filename)
                if not os.path.isfile(fpath):
                    continue
                group.addChild(self._create_example_file_item(fpath))
                example_count += 1
            group.setExpanded(True)

        leetcode_root = os.path.join(self._examples_dir, "leetcode")
        if os.path.isdir(leetcode_root) and not os.path.islink(leetcode_root):
            leetcode_count = self._count_supported_sources(leetcode_root)
            if leetcode_count:
                leetcode_group = self._create_example_directory_item("LeetCode", "leetcode")
                self._file_list.addTopLevelItem(leetcode_group)
                leetcode_group.setExpanded(True)
                example_count += self._add_recursive_example_directory(leetcode_group, leetcode_root)

        self._example_count.setText(str(example_count))

    def _on_example_clicked(self, item: QTreeWidgetItem, _column: int = 0):
        fpath = item.data(0, Qt.ItemDataRole.UserRole)
        if not fpath:
            return
        try:
            with open(fpath, encoding="utf-8", errors="replace") as f:
                code = f.read()
        except OSError:
            return
        self._editor.setPlainText(code)
        self._reset()
        self._status_bar.showMessage(f"已加载: {os.path.basename(fpath)}")

    # ── 示例代码 ──────────────────────────────

    def _load_demo(self):
        demo = r"""#include <iostream>
using namespace std;

int globalVar = 100;

int add(int a, int b) {
    int result = a + b;
    return result;
}

int main() {
    // 基本变量
    int x = 5;
    int y = 3;
    float pi = 3.14;
    char ch = 'A';

    // 运算
    int sum = add(x, y);
    x += 10;

    // 循环
    int total = 0;
    for (int i = 0; i < 3; i++) {
        total += i;
    }

    // 输出
    cout << "sum = " << sum << endl;
    cout << "total = " << total << endl;

    // 堆内存
    int* ptr = new int;
    *ptr = 42;
    delete ptr;

    return 0;
}
"""
        self._editor.setPlainText(demo)


# ──────────────────────────────────────────────
# 入口函数
# ──────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("C++ 执行可视化")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
