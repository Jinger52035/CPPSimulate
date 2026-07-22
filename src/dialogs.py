"""
dialogs.py
设置对话框 + 崩溃弹框
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QRadioButton, QButtonGroup, QWidget, QScrollArea,
)
from PyQt6.QtCore import Qt

from .config import COLORS, AppSettings


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("显示设置")
        self.setMinimumWidth(480)
        self.setMinimumHeight(440)
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['dlg_bg']};
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {COLORS['dlg_text']};
            }}
            QRadioButton {{
                background: transparent;
                border: none;
                color: {COLORS['dlg_text']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 20, 24, 20)

        # ── 布局模式
        root.addWidget(self._section_title("内存面板布局"))
        self._layout_group = QButtonGroup(self)
        self._rb_split   = self._make_radio(
            "⊞  分开多栏",
            "全局区 / 栈 / 堆 各自独立，适合对比各区域差异",
            root)
        self._rb_unified = self._make_radio(
            "☰  单竖列",
            "完整虚拟地址空间，高地址在上，适合理解整体布局",
            root)
        self._layout_group.addButton(self._rb_split,   0)
        self._layout_group.addButton(self._rb_unified, 1)

        root.addWidget(self._hline())

        # ── 内存分段粒度
        root.addWidget(self._section_title("内存分段粒度"))
        self._seg_group = QButtonGroup(self)
        self._rb_simple   = self._make_radio(
            "简单  （4段）",
            "代码区 / 全局变量 / 堆 / 栈  —  适合入门",
            root)
        self._rb_standard = self._make_radio(
            "标准  （3段）★ 默认",
            "全局区 / 堆 / 栈  —  日常教学推荐",
            root)
        self._rb_detailed = self._make_radio(
            "详细  （6段）",
            "Code / Literals / Data / BSS / Heap / Stack  —  接近真实内存布局",
            root)
        self._seg_group.addButton(self._rb_simple,   0)
        self._seg_group.addButton(self._rb_standard, 1)
        self._seg_group.addButton(self._rb_detailed, 2)

        root.addStretch()

        # ── 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(88)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_light']}; color: {COLORS['dlg_text']};
                border: 1px solid {COLORS['dlg_border']}; border-radius: 4px;
                padding: 6px 0; font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLORS['dlg_hover']}; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(88)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['dlg_accent']}; color: white;
                border: none; border-radius: 4px;
                padding: 6px 0; font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {COLORS['accent']}; }}
        """)
        ok_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

        # 回填当前设置
        (self._rb_split if settings.layout == "split" else self._rb_unified).setChecked(True)
        {"simple": self._rb_simple,
         "standard": self._rb_standard,
         "detailed": self._rb_detailed}[settings.seg_mode].setChecked(True)

        for rb in [self._rb_split, self._rb_unified,
                   self._rb_simple, self._rb_standard, self._rb_detailed]:
            rb.toggled.connect(self._refresh_radio_styles)
        self._refresh_radio_styles()

    def _refresh_radio_styles(self):
        for rb in [self._rb_split, self._rb_unified,
                   self._rb_simple, self._rb_standard, self._rb_detailed]:
            card = rb.parent()
            if card:
                if rb.isChecked():
                    card.setStyleSheet(f"""
                        QWidget#radio_card {{
                            background: {COLORS['dlg_checked']};
                            border: 2px solid {COLORS['dlg_accent']};
                            border-radius: 5px;
                        }}
                    """)
                else:
                    card.setStyleSheet(f"""
                        QWidget#radio_card {{
                            background: {COLORS['bg_panel']};
                            border: 1px solid {COLORS['dlg_border']};
                            border-radius: 5px;
                        }}
                    """)

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {COLORS['dlg_text']};
            font-weight: bold;
            font-size: 13px;
            padding-bottom: 2px;
        """)
        return lbl

    def _hline(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(f"background: {COLORS['dlg_border']}; max-height: 1px; margin: 2px 0;")
        return f

    def _make_radio(self, label: str, hint: str, parent_layout: QVBoxLayout) -> QRadioButton:
        card = QWidget()
        card.setObjectName("radio_card")
        card.setStyleSheet(f"""
            QWidget#radio_card {{
                background: {COLORS['bg_panel']};
                border: 1px solid {COLORS['dlg_border']};
                border-radius: 5px;
            }}
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 8, 14, 8)
        card_layout.setSpacing(12)

        rb = QRadioButton()
        rb.setStyleSheet("QRadioButton { background: transparent; border: none; }")
        card_layout.addWidget(rb)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(label)
        title_lbl.setStyleSheet(f"""
            color: {COLORS['dlg_text']};
            font-size: 13px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(f"""
            color: {COLORS['dlg_dim']};
            font-size: 11px;
            background: transparent;
            border: none;
        """)
        hint_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)
        text_col.addWidget(hint_lbl)
        card_layout.addLayout(text_col)
        card_layout.addStretch()

        card.mousePressEvent = lambda e, r=rb: r.setChecked(True)

        parent_layout.addWidget(card)
        return rb

    def get_settings(self) -> AppSettings:
        layout = "split" if self._rb_split.isChecked() else "unified"
        seg = "simple" if self._rb_simple.isChecked() else \
              "detailed" if self._rb_detailed.isChecked() else "standard"
        return AppSettings(layout=layout, seg_mode=seg)


# ──────────────────────────────────────────────
# 崩溃弹框
# ──────────────────────────────────────────────

_UB_BADGES = {
    "wild_ptr":      ("野指针",     "#E05555"),
    "double_free":   ("二次释放",   "#D4802A"),
    "null_deref":    ("空指针解引", "#C040C0"),
    "use_after_free":("释放后使用", "#2A7AD4"),
}


class CrashDialog(QDialog):
    """显示崩溃/未定义行为的教学弹框"""

    def __init__(self, crash, parent=None):
        super().__init__(parent)
        self.setWindowTitle("程序崩溃")
        self.setMinimumWidth(520)
        self.setMaximumWidth(640)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background: {COLORS['bg']};
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {COLORS['text']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 20)
        root.setSpacing(0)

        # ── 红色顶部 header bar
        header = QWidget()
        header.setStyleSheet("background: #8B1A1A; border: none;")
        header.setFixedHeight(64)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)

        icon_lbl = QLabel("💥")
        icon_lbl.setStyleSheet("font-size: 28px; background: transparent;")

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        t1 = QLabel("程序崩溃 / Segmentation Fault")
        t1.setStyleSheet(
            "color: #FFD0D0; font-size: 15px; font-weight: bold; background: transparent;"
        )
        t2 = QLabel(crash.title)
        t2.setStyleSheet(
            "color: #FF9090; font-size: 11px; background: transparent;"
        )
        title_col.addWidget(t1)
        title_col.addWidget(t2)

        h_layout.addWidget(icon_lbl)
        h_layout.addSpacing(12)
        h_layout.addLayout(title_col)
        h_layout.addStretch()
        root.addWidget(header)

        # ── 内容区
        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 0)
        body.setSpacing(14)

        # 崩溃类型 badge
        badge_label, badge_color = _UB_BADGES.get(
            crash.ub_type, (crash.ub_type, COLORS["border"])
        )
        badge_row = QHBoxLayout()
        badge = QLabel(f"  {badge_label}  ")
        badge.setStyleSheet(f"""
            background: {badge_color};
            color: white;
            font-size: 11px;
            font-weight: bold;
            border-radius: 4px;
            padding: 2px 4px;
        """)
        badge_row.addWidget(badge)
        badge_row.addStretch()
        body.addLayout(badge_row)

        # 原因行
        cause_lbl = QLabel(crash.cause)
        cause_lbl.setWordWrap(True)
        cause_lbl.setStyleSheet(f"""
            color: {COLORS['yellow_bright']};
            font-size: 13px;
            font-weight: 600;
            padding: 8px 12px;
            background: {COLORS['bg_panel']};
            border-left: 3px solid {COLORS['yellow']};
            border-radius: 4px;
        """)
        body.addWidget(cause_lbl)

        # 详细说明
        detail_lbl = QLabel(crash.detail)
        detail_lbl.setWordWrap(True)
        detail_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_lbl.setStyleSheet(f"""
            color: {COLORS['text']};
            font-size: 12px;
            line-height: 1.6;
            font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
            padding: 4px 0;
        """)
        body.addWidget(detail_lbl)

        # 指针信息行（如果有）
        if crash.ptr_name:
            ptr_disp = hex(crash.ptr_value) if isinstance(crash.ptr_value, int) else str(crash.ptr_value)
            info_lbl = QLabel(
                f"指针：{crash.ptr_name}   值：{ptr_disp}"
            )
            info_lbl.setStyleSheet(f"""
                color: {COLORS['text_dim']};
                font-size: 11px;
                font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
                padding: 6px 10px;
                background: {COLORS['bg_editor']};
                border-radius: 4px;
            """)
            body.addWidget(info_lbl)

        root.addLayout(body)
        root.addStretch()

        # ── 关闭按钮
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(24, 0, 24, 0)
        btn_row.addStretch()
        ok_btn = QPushButton("我知道了")
        ok_btn.setFixedWidth(110)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: #8B1A1A;
                color: #FFD0D0;
                border: 1px solid #C05050;
                border-radius: 6px;
                padding: 6px 0;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #A02020;
                color: white;
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)
