"""
main_window.py
主窗口：负责 UI 组装与事件处理，不含任何业务/渲染逻辑。
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QPlainTextEdit, QPushButton, QLabel,
    QFileDialog, QScrollArea, QStackedWidget, QDialog,
    QToolBar, QSlider, QListWidget, QListWidgetItem,
)
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt, QTimer

from .cpp_interpreter import CppInterpreter, ExecutionStep, MemoryRegion, Variable
from .config import COLORS, AppSettings
from .editor import CodeEditor
from .highlighter import CppHighlighter
from .panels import MemoryPanel, StackPanel, UnifiedMemoryPanel
from .dialogs import SettingsDialog, CrashDialog


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
        self.setMinimumSize(1280, 780)
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
                background-color: {COLORS['bg_card']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_input']};
                border-color: {COLORS['border_focus']};
                color: {COLORS['text_bright']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['accent_bg']};
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
            }}
            QPushButton:checked {{
                background-color: {COLORS['accent_bg']};
                color: {COLORS['accent']};
                border-color: {COLORS['accent']};
                font-weight: bold;
            }}
            QPushButton:disabled {{
                color: {COLORS['text_dim']};
                border-color: {COLORS['separator']};
                background-color: transparent;
            }}
            QSplitter::handle {{
                background: {COLORS['separator']};
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
                color: {COLORS['green_bright']};
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
        """)

    # ── UI 构建 ───────────────────────────────

    def _build_ui(self):
        # 工具栏
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(__import__('PyQt6.QtCore', fromlist=['QSize']).QSize(16, 16))
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

        open_btn = QPushButton("打开")
        open_btn.setToolTip("打开 C++ 文件")
        open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(open_btn)
        toolbar.addSeparator()

        self._run_btn = QPushButton("▶  运行")
        self._run_btn.setToolTip("解析并准备执行步骤")
        self._run_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent_bg']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']};
                border-radius: 6px;
                padding: 4px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {COLORS['accent']};
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background: {COLORS['accent_dim']};
                color: #FFFFFF;
            }}
        """)
        self._run_btn.clicked.connect(self._run_code)
        toolbar.addWidget(self._run_btn)

        self._prev_btn = QPushButton("← 上一步")
        self._prev_btn.setToolTip("回退到上一步")
        self._prev_btn.clicked.connect(self._step_back)
        self._prev_btn.setEnabled(False)
        toolbar.addWidget(self._prev_btn)

        self._step_btn = QPushButton("单步 →")
        self._step_btn.setToolTip("执行下一步")
        self._step_btn.clicked.connect(self._step_forward)
        self._step_btn.setEnabled(False)
        toolbar.addWidget(self._step_btn)

        self._auto_btn = QPushButton("▶▶ 自动")
        self._auto_btn.setToolTip("自动步进播放")
        self._auto_btn.setCheckable(True)
        self._auto_btn.clicked.connect(self._toggle_auto)
        toolbar.addWidget(self._auto_btn)

        self._reset_btn = QPushButton("重置")
        self._reset_btn.setToolTip("重置到初始状态")
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
                border-color: {COLORS['text_bright']};
                background: {COLORS['accent']};
            }}
        """)
        toolbar.addWidget(self._speed_slider)

        toolbar.addSeparator()

        settings_btn = QPushButton("⚙  设置")
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
        left_widget.setMinimumWidth(420)
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

        file_hdr = QLabel("  EXAMPLES")
        file_hdr.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 8px 10px 7px 10px;
            border-bottom: 1px solid {COLORS['separator']};
            background: {COLORS['bg_light']};
        """)
        file_layout.addWidget(file_hdr)

        self._file_list = QListWidget()
        self._file_list.setStyleSheet(f"""
            QListWidget {{
                background: {COLORS['bg_light']};
                border: none;
                outline: none;
                font-size: 12px;
                color: {COLORS['text']};
                padding: 4px 0;
            }}
            QListWidget::item {{
                padding: 6px 12px;
                border-radius: 0;
            }}
            QListWidget::item:selected {{
                background: {COLORS['accent_bg']};
                color: {COLORS['accent']};
                border-left: 2px solid {COLORS['accent']};
                padding-left: 10px;
            }}
            QListWidget::item:hover:!selected {{
                background: {COLORS['bg_card']};
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

        code_label = QLabel("SOURCE")
        code_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 2px 0;
        """)
        editor_layout.addWidget(code_label)

        self._editor = CodeEditor()
        self._editor.setReadOnly(False)
        CppHighlighter(self._editor.document())
        editor_layout.addWidget(self._editor, stretch=4)

        desc_label = QLabel("EXECUTION")
        desc_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 2px 0;
        """)
        editor_layout.addWidget(desc_label)

        self._desc_box = QLabel("点击「运行」开始解析代码")
        self._desc_box.setWordWrap(True)
        self._desc_box.setStyleSheet(f"""
            background: {COLORS['bg_panel']};
            color: {COLORS['yellow_bright']};
            border: 1px solid {COLORS['border']};
            border-left: 3px solid {COLORS['yellow']};
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 12px;
            min-height: 44px;
        """)
        editor_layout.addWidget(self._desc_box)

        out_label = QLabel("OUTPUT")
        out_label.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 2px 0;
        """)
        editor_layout.addWidget(out_label)

        self._output_box = QPlainTextEdit()
        self._output_box.setReadOnly(True)
        self._output_box.setMaximumHeight(84)
        self._output_box.setStyleSheet(f"""
            background: {COLORS['bg_editor']};
            color: {COLORS['green_bright']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
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
        # 初始 seg_mode=standard → 3列 × 300px
        right_widget.setMinimumWidth(900)

        env_bar = QLabel(
            "  x86-64 · 小端序 · 栈↓低地址    "
            "char=1B  short=2B  int/float=4B  double/long/ptr=8B  自然对齐"
        )
        env_bar.setStyleSheet(f"""
            background: {COLORS['bg']};
            color: {COLORS['text_dim']};
            font-size: 10px;
            font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
            padding: 4px 10px;
            border-bottom: 1px solid {COLORS['separator']};
        """)
        right_layout.addWidget(env_bar)

        self._mem_stack = QStackedWidget()

        split_page = self._build_split_page(self._settings.seg_mode)
        self._mem_stack.addWidget(split_page)   # index 0

        self._unified_panel = UnifiedMemoryPanel()
        self._mem_stack.addWidget(self._unified_panel)   # index 1

        right_layout.addWidget(self._mem_stack)
        splitter.addWidget(right_widget)
        splitter.setSizes([500, 780])

        main_layout.addWidget(splitter)

    def _build_split_page(self, seg_mode: str) -> QWidget:
        """构建分开多栏页面，同时更新各面板引用。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        spl = QSplitter(Qt.Orientation.Horizontal)
        spl.setHandleWidth(4)
        spl.setStyleSheet(f"QSplitter::handle {{ background: {COLORS['border']}; }}")

        def add_scroll(panel, min_w=300):
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setWidget(panel)
            sc.setMinimumWidth(min_w)
            spl.addWidget(sc)

        if seg_mode == "simple":
            self._code_panel   = MemoryPanel("代码区 (Code)", COLORS["teal"])
            self._global_panel = MemoryPanel("全局变量", COLORS["accent"])
            self._heap_panel   = MemoryPanel("堆 (Heap)", COLORS["red"], grow_up=True)
            self._stack_panel  = StackPanel()
            add_scroll(self._code_panel)
            add_scroll(self._global_panel)
            add_scroll(self._heap_panel)
            add_scroll(self._stack_panel)
            spl.setSizes([300, 300, 300, 300])

        elif seg_mode == "detailed":
            self._code_panel    = MemoryPanel("代码段 (Code)",      COLORS["teal"])
            self._literal_panel = MemoryPanel("常量区 (Literals)",  COLORS["purple"])
            self._data_panel    = MemoryPanel("数据段 (Data)  已初始化全局", COLORS["accent"])
            self._bss_panel     = MemoryPanel("BSS段  未初始化全局",  COLORS["yellow"])
            self._heap_panel    = MemoryPanel("堆 (Heap)",           COLORS["red"], grow_up=True)
            self._stack_panel   = StackPanel()

            # 上行：代码段 / 常量区 / 数据段
            top_spl = QSplitter(Qt.Orientation.Horizontal)
            top_spl.setHandleWidth(4)
            top_spl.setStyleSheet(f"QSplitter::handle {{ background: {COLORS['border']}; }}")
            for p in [self._code_panel, self._literal_panel, self._data_panel]:
                sc = QScrollArea()
                sc.setWidgetResizable(True)
                sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                sc.setWidget(p)
                sc.setMinimumWidth(300)
                top_spl.addWidget(sc)
            top_spl.setSizes([300, 300, 300])

            # 下行：BSS / 堆 / 栈
            bot_spl = QSplitter(Qt.Orientation.Horizontal)
            bot_spl.setHandleWidth(4)
            bot_spl.setStyleSheet(f"QSplitter::handle {{ background: {COLORS['border']}; }}")
            for p in [self._bss_panel, self._heap_panel, self._stack_panel]:
                sc = QScrollArea()
                sc.setWidgetResizable(True)
                sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                sc.setWidget(p)
                sc.setMinimumWidth(300)
                bot_spl.addWidget(sc)
            bot_spl.setSizes([300, 300, 300])

            # 垂直 splitter 组合上下两行
            v_spl = QSplitter(Qt.Orientation.Vertical)
            v_spl.setHandleWidth(4)
            v_spl.setStyleSheet(f"QSplitter::handle {{ background: {COLORS['border']}; }}")
            v_spl.addWidget(top_spl)
            v_spl.addWidget(bot_spl)
            v_spl.setSizes([1, 1])

            layout.addWidget(v_spl)
            return page

        else:  # standard
            self._global_panel = MemoryPanel("全局区 / 静态区", COLORS["accent"])
            self._heap_panel   = MemoryPanel("堆 (Heap)", COLORS["red"], grow_up=True)
            self._stack_panel  = StackPanel()
            add_scroll(self._global_panel)
            add_scroll(self._heap_panel)
            add_scroll(self._stack_panel)
            spl.setSizes([300, 300, 300])

        layout.addWidget(spl)
        return page

    # ── 事件处理 ──────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings(dlg.get_settings())

    def _apply_settings(self, new_settings: AppSettings):
        seg_changed    = new_settings.seg_mode != self._settings.seg_mode
        layout_changed = new_settings.layout   != self._settings.layout
        self._settings = new_settings

        if seg_changed:
            old_widget = self._mem_stack.widget(0)
            new_page   = self._build_split_page(new_settings.seg_mode)
            self._mem_stack.insertWidget(0, new_page)
            self._mem_stack.removeWidget(old_widget)
            old_widget.deleteLater()
            # 根据列数重新设置右侧最小宽度
            min_w = {"simple": 1200, "standard": 900, "detailed": 1800}
            self._right_widget.setMinimumWidth(min_w.get(new_settings.seg_mode, 900))

        is_unified = new_settings.layout == "unified"
        self._mem_stack.setCurrentIndex(1 if is_unified else 0)

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

        # 崩溃步骤用红色样式，普通步骤恢复默认
        if step.crash:
            self._desc_box.setStyleSheet(f"""
                background: #3A0000;
                color: #FF9090;
                border: 1px solid #8B1A1A;
                border-left: 3px solid #E05555;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 12px;
                min-height: 44px;
            """)
        else:
            self._desc_box.setStyleSheet(f"""
                background: {COLORS['bg_panel']};
                color: {COLORS['yellow_bright']};
                border: 1px solid {COLORS['border']};
                border-left: 3px solid {COLORS['yellow']};
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 12px;
                min-height: 44px;
            """)

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

    def _refresh_memory(self, step: ExecutionStep):
        import re
        seg          = self._settings.seg_mode
        highlight    = step.highlight_vars if step else []
        heap_named   = {v.name: v for v in step.heap.values()} if step else {}
        stack_frames = step.stack_frames if step else []
        globals_all  = step.globals if step else {}
        obj_pads     = step.objects if step else {}

        if seg == "simple":
            code_vars = {
                frame.function_name: Variable(
                    name=frame.function_name, type="function",
                    value="...", address=0x00401000 + i * 0x100,
                    region=MemoryRegion.CODE, size=0
                )
                for i, frame in enumerate(stack_frames)
            }
            self._code_panel.refresh(code_vars, highlight)
            self._global_panel.refresh(globals_all, highlight)
            self._heap_panel.refresh(heap_named, highlight)
            self._stack_panel.refresh(stack_frames, highlight, obj_pads)

        elif seg == "detailed":
            funcs = list(self._interpreter._functions.keys())
            code_vars = {
                fname: Variable(
                    name=fname + "()", type="function",
                    value="compiled", address=0x00401000 + i * 0x100,
                    region=MemoryRegion.CODE, size=0
                )
                for i, fname in enumerate(funcs)
            }
            self._code_panel.refresh(code_vars, highlight)

            literal_vars = step.literals if step else {}
            self._literal_panel.refresh(literal_vars, highlight)

            data_vars = {n: v for n, v in globals_all.items()
                         if v.region in (MemoryRegion.DATA, MemoryRegion.GLOBAL)
                         and v.value is not None}
            bss_vars  = {n: v for n, v in globals_all.items()
                         if v.region == MemoryRegion.BSS or v.value is None}
            self._data_panel.refresh(data_vars, highlight)
            self._bss_panel.refresh(bss_vars, highlight)
            self._heap_panel.refresh(heap_named, highlight)
            self._stack_panel.refresh(stack_frames, highlight, obj_pads)

        else:  # standard
            self._global_panel.refresh(globals_all, highlight)
            self._heap_panel.refresh(heap_named, highlight)
            self._stack_panel.refresh(stack_frames, highlight, obj_pads)

        self._unified_panel.refresh(step, highlight, seg)

    # ── 示例文件列表 ──────────────────────────

    def _load_examples(self):
        """扫描 examples/ 目录，填充文件列表"""
        self._file_list.clear()
        if not os.path.isdir(self._examples_dir):
            return
        files = sorted(f for f in os.listdir(self._examples_dir) if f.endswith(".cpp"))
        for fname in files:
            # 提取注释首行作为标题（// 示例N：...）
            fpath = os.path.join(self._examples_dir, fname)
            title = fname
            try:
                with open(fpath, encoding="utf-8") as f:
                    first = f.readline().strip()
                    if first.startswith("//"):
                        title = first.lstrip("/ ").strip()
            except OSError:
                pass
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, fpath)
            item.setToolTip(fname)
            self._file_list.addItem(item)

    def _on_example_clicked(self, item: QListWidgetItem):
        fpath = item.data(Qt.ItemDataRole.UserRole)
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
