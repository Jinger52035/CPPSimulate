"""
panels.py
内存区域面板：MemoryPanel、StackPanel、UnifiedMemoryPanel
公共的栈帧渲染逻辑在 _build_frame_widgets() 中统一维护。
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt

from .config import COLORS
from .widgets import VarCard, ObjectCard, ContainerCard
from .stl_containers import ContainerVariable


# ──────────────────────────────────────────────
# 公共工具
# ──────────────────────────────────────────────

def _make_section_header(title: str, color: str) -> QLabel:
    lbl = QLabel(f"  {title}")
    lbl.setStyleSheet(f"""
        color: {color};
        font-weight: 700;
        font-size: 11px;
        padding: 5px 10px;
        background: {COLORS['bg']};
        border-bottom: 1px solid {COLORS['separator']};
        letter-spacing: 0.3px;
    """)
    return lbl


def _make_separator() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"background: {COLORS['separator']}; max-height: 1px; margin: 2px 0;")
    return sep


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def _empty_label() -> QLabel:
    e = QLabel("(空)")
    e.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; padding: 8px 6px; font-style: italic;")
    return e


def _build_frame_widgets(frame, highlight_names: list, obj_paddings: dict) -> list:
    """
    把一个 StackFrame 里的变量转换成渲染 widget 列表（按高地址降序排列）。
    对象成员合并为 ObjectCard，普通变量渲染为 VarCard。
    返回值：[QWidget, ...]
    """
    if not frame.variables:
        lbl = QLabel("(无局部变量)")
        lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        return [lbl]

    # 收集哪些变量名属于对象成员
    obj_member_names: set = set()
    for obj_name in obj_paddings:
        for vname in frame.variables:
            if vname.startswith(obj_name + ".") or vname == obj_name:
                obj_member_names.add(vname)

    render_items = []  # (sort_addr, "obj"/"var", payload)

    for obj_name, obj_info in obj_paddings.items():
        frame_members = {
            k: v for k, v in frame.variables.items()
            if k.startswith(obj_name + ".") or k == obj_name
        }
        if not frame_members:
            continue
        members_sorted = sorted(
            [(k.split(".", 1)[1] if "." in k else k, v)
             for k, v in frame_members.items()],
            key=lambda kv: kv[1].address
        )
        render_items.append((
            obj_info["base_addr"],
            "obj",
            (obj_name, obj_info.get("cls_name", obj_name),
             members_sorted, obj_info["base_addr"], obj_info["total_size"])
        ))

    for vname, var in frame.variables.items():
        if vname not in obj_member_names:
            render_items.append((var.address, "var", (vname, var)))

    # 高地址在上 → 降序
    render_items.sort(key=lambda t: t[0], reverse=True)

    widgets = []
    for _, kind, payload in render_items:
        if kind == "obj":
            obj_name, cls_name, members_sorted, base_addr, total_size = payload
            widgets.append(ObjectCard(obj_name, cls_name, members_sorted,
                                      base_addr, total_size, highlight_names))
        else:
            vname, var = payload
            if isinstance(var, ContainerVariable):
                widgets.append(ContainerCard(var, highlight=(vname in highlight_names)))
            else:
                widgets.append(VarCard(var, highlight=(vname in highlight_names)))
    return widgets


# ──────────────────────────────────────────────
# 全局区 / 堆 通用面板
# ──────────────────────────────────────────────

class MemoryPanel(QWidget):
    """展示一个内存区域（全局/堆），高地址在上、低地址在下。"""

    def __init__(self, title: str, color: str, grow_up: bool = False):
        super().__init__()
        self._color = color
        self._grow_up = grow_up
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QLabel(f"  {title}")
        header.setStyleSheet(f"""
            color: {color};
            font-weight: 700;
            font-size: 11px;
            padding: 6px 10px;
            background: {COLORS['bg']};
            border-bottom: 1px solid {COLORS['separator']};
            letter-spacing: 0.3px;
        """)
        self._layout.addWidget(header)

        if grow_up:
            lbl = QLabel("  ↑  高地址  后分配")
            lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; padding: 3px 10px;")
            self._layout.addWidget(lbl)

        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(3)
        if grow_up:
            # 堆整体贴底；高地址块排在上方，低地址首分配块位于最下方。
            self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        else:
            self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self._cards_widget, stretch=1)

        if grow_up:
            lbl2 = QLabel("  ↓  低地址  先分配")
            lbl2.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; padding: 3px 10px;")
            self._layout.addWidget(lbl2)

        self.setStyleSheet(f"background: {COLORS['bg_panel']};")

    def refresh(self, variables: dict, highlight_names: list = None):
        highlight_names = highlight_names or []
        _clear_layout(self._cards_layout)

        if not variables:
            self._cards_layout.addWidget(_empty_label())
            return

        if self._grow_up:
            # 高地址在上、低地址在下；新分配块向上增长。
            sorted_vars = sorted(variables.items(), key=lambda kv: kv[1].address,
                                 reverse=True)
        else:
            # 全局区等：升序，低地址在上
            sorted_vars = sorted(variables.items(), key=lambda kv: kv[1].address)

        for name, var in sorted_vars:
            if isinstance(var, ContainerVariable):
                self._cards_layout.addWidget(ContainerCard(var, highlight=(name in highlight_names)))
            else:
                self._cards_layout.addWidget(VarCard(var, highlight=(name in highlight_names)))


# ──────────────────────────────────────────────
# 栈帧面板
# ──────────────────────────────────────────────

_FRAME_BOX_STYLE = f"""
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
        color: {COLORS['green_bright']};
    }}
"""


class StackPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)

        top_lbl = QLabel("高地址  ▲")
        top_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; padding: 2px 10px;")
        top_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._layout.addWidget(top_lbl)

        header = QLabel("  栈 (Stack)  ↓ 向低地址增长")
        header.setStyleSheet(f"""
            color: {COLORS['green_bright']};
            font-weight: 700;
            font-size: 11px;
            padding: 6px 10px;
            background: {COLORS['bg']};
            border-bottom: 1px solid {COLORS['separator']};
            letter-spacing: 0.3px;
        """)
        self._layout.addWidget(header)

        self._frames_widget = QWidget()
        self._frames_layout = QVBoxLayout(self._frames_widget)
        self._frames_layout.setContentsMargins(0, 0, 0, 0)
        self._frames_layout.setSpacing(6)
        self._frames_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self._frames_widget)
        self._layout.addStretch()

        bot_lbl = QLabel("▼  低地址")
        bot_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; padding: 2px 10px;")
        self._layout.addWidget(bot_lbl)

        self.setStyleSheet(f"background: {COLORS['bg_panel']};")

    def refresh(self, stack_frames: list, highlight_names: list = None,
                obj_paddings: dict = None):
        highlight_names = highlight_names or []
        obj_paddings = obj_paddings or {}
        _clear_layout(self._frames_layout)

        if not stack_frames:
            self._frames_layout.addWidget(_empty_label())
            return

        for frame in stack_frames:
            box = QGroupBox(f"  栈帧: {frame.function_name}()")
            box.setStyleSheet(_FRAME_BOX_STYLE)
            box_layout = QVBoxLayout(box)
            box_layout.setSpacing(3)
            for w in _build_frame_widgets(frame, highlight_names, obj_paddings):
                box_layout.addWidget(w)
            self._frames_layout.addWidget(box)


# ──────────────────────────────────────────────
# 单竖模式：完整内存地址空间面板
# ──────────────────────────────────────────────

class UnifiedMemoryPanel(QWidget):
    """
    单竖视图：高地址在上，低地址在下。
    区块布局随 seg_mode 动态重建。
    """

    def __init__(self):
        super().__init__()
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        self.setStyleSheet(f"background: {COLORS['bg_panel']};")
        self.setMinimumWidth(220)
        self._current_seg = None

        # 内容容器（随 seg_mode 替换）
        self._content = QWidget()
        self._outer.addWidget(self._content)

    def _rebuild_sections(self, seg_mode: str):
        """按 seg_mode 重建区块 widget，返回 section_map {key: (inner_widget, layout)}"""
        # 销毁旧内容
        old = self._content
        self._content = QWidget()
        self._content.setStyleSheet(f"background: {COLORS['bg_panel']};")
        self._outer.replaceWidget(old, self._content)
        old.deleteLater()

        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        addr_top = QLabel("  0xFFFFFFFF  高地址  ▲")
        addr_top.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; padding: 4px 10px;"
            f"font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;"
        )
        addr_top.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(addr_top)

        sections = {}   # key -> (inner_widget, inner_layout)

        def add_section(key, title, color, bg, stretch=2,
                        alignment=Qt.AlignmentFlag.AlignTop):
            layout.addWidget(_make_section_header(title, color))
            inner = QWidget()
            inner.setStyleSheet(f"background: {bg};")
            inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            cl = QVBoxLayout(inner)
            cl.setContentsMargins(6, 6, 6, 6)
            cl.setSpacing(4)
            cl.setAlignment(alignment)
            sc = QScrollArea()
            sc.setWidget(inner)
            sc.setWidgetResizable(True)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            sc.setStyleSheet(f"""
                QScrollArea {{ border: 1px solid {COLORS['border']}; border-radius: 4px;
                               background: transparent; }}
                QScrollBar:vertical {{ background: transparent; width: 6px; margin: 2px 0; }}
                QScrollBar::handle:vertical {{ background: {COLORS['border']}; border-radius: 3px; min-height: 20px; }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            """)
            layout.addWidget(sc, stretch=stretch)
            sections[key] = (inner, cl)

        if seg_mode == "simple":
            add_section("stack",  "栈 (Stack)  ↓ 向低地址增长", COLORS["green_bright"], COLORS["stack_bg"], 3)
            layout.addWidget(_make_separator())
            add_section("heap",   "堆 (Heap)  ↑ 向高地址增长",  COLORS["red"],          COLORS["heap_bg"],  2,
                        Qt.AlignmentFlag.AlignBottom)
            layout.addWidget(_make_separator())
            add_section("global", "全局变量",                    COLORS["accent"],       COLORS["global_bg"], 2)
            layout.addWidget(_make_separator())
            add_section("code",   "代码区 (Code)",               COLORS["teal"],         COLORS["bg_panel"],  1)

        elif seg_mode == "detailed":
            add_section("stack",   "栈 (Stack)  ↓ 向低地址增长",  COLORS["green_bright"], COLORS["stack_bg"],  3)
            layout.addWidget(_make_separator())
            add_section("heap",    "堆 (Heap)  ↑ 向高地址增长",   COLORS["red"],          COLORS["heap_bg"],   2,
                        Qt.AlignmentFlag.AlignBottom)
            layout.addWidget(_make_separator())
            add_section("data",    "数据段 (Data)  已初始化全局",  COLORS["accent"],       COLORS["global_bg"], 2)
            layout.addWidget(_make_separator())
            add_section("bss",     "BSS段  未初始化全局",          COLORS["yellow"],       COLORS["global_bg"], 1)
            layout.addWidget(_make_separator())
            add_section("literal", "常量区 (Literals)",            COLORS["purple"],       COLORS["bg_panel"],  1)
            layout.addWidget(_make_separator())
            add_section("code",    "代码段 (Code)",                COLORS["teal"],         COLORS["bg_panel"],  1)

        else:  # standard
            add_section("stack",  "栈 (Stack)  ↓ 向低地址增长", COLORS["green_bright"], COLORS["stack_bg"],  3)
            layout.addWidget(_make_separator())
            add_section("heap",   "堆 (Heap)  ↑ 向高地址增长",  COLORS["red"],          COLORS["heap_bg"],   2,
                        Qt.AlignmentFlag.AlignBottom)
            layout.addWidget(_make_separator())
            add_section("global", "全局区 / 静态区",             COLORS["accent"],       COLORS["global_bg"], 2)

        addr_bot = QLabel("▼  低地址  0x00000000")
        addr_bot.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; padding: 4px 10px;"
            f"font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;"
        )
        layout.addWidget(addr_bot)

        return sections

    @staticmethod
    def _cl(sections, key):
        """取某区块的 layout，不存在时返回 None"""
        entry = sections.get(key)
        return entry[1] if entry else None

    def refresh(self, step, highlight_vars: list = None, seg_mode: str = "standard"):
        from .cpp_interpreter import MemoryRegion as MR
        import re as _re
        highlight_vars = highlight_vars or []
        heap_vars    = {v.name: v for v in step.heap.values()} if step else {}
        stack_frames = step.stack_frames if step else []
        globals_all  = step.globals if step else {}
        obj_paddings = step.objects if step else {}

        # 按需重建区块
        if seg_mode != self._current_seg:
            self._sections = self._rebuild_sections(seg_mode)
            self._current_seg = seg_mode

        sections = self._sections

        # ── 栈
        cl = self._cl(sections, "stack")
        if cl is not None:
            _clear_layout(cl)
            if stack_frames:
                for frame in stack_frames:
                    box = QGroupBox(f"  栈帧: {frame.function_name}()")
                    box.setStyleSheet(_FRAME_BOX_STYLE)
                    bl = QVBoxLayout(box)
                    bl.setSpacing(3)
                    for w in _build_frame_widgets(frame, highlight_vars, obj_paddings):
                        bl.addWidget(w)
                    cl.addWidget(box)
            else:
                cl.addWidget(_empty_label())

        # ── 堆
        cl = self._cl(sections, "heap")
        if cl is not None:
            _clear_layout(cl)
            if heap_vars:
                for name, var in sorted(heap_vars.items(),
                                        key=lambda kv: kv[1].address,
                                        reverse=True):
                    cl.addWidget(VarCard(var, highlight=(name in highlight_vars)))
            else:
                cl.addWidget(_empty_label())

        # ── 全局（standard / simple）
        cl = self._cl(sections, "global")
        if cl is not None:
            _clear_layout(cl)
            if globals_all:
                for name, var in sorted(globals_all.items(), key=lambda kv: kv[1].address):
                    cl.addWidget(VarCard(var, highlight=(name in highlight_vars)))
            else:
                cl.addWidget(_empty_label())

        # ── Data 段（detailed）
        cl = self._cl(sections, "data")
        if cl is not None:
            _clear_layout(cl)
            data_vars = {n: v for n, v in globals_all.items()
                         if v.region in (MR.DATA, MR.GLOBAL) and v.value is not None}
            if data_vars:
                for name, var in sorted(data_vars.items(), key=lambda kv: kv[1].address):
                    cl.addWidget(VarCard(var, highlight=(name in highlight_vars)))
            else:
                cl.addWidget(_empty_label())

        # ── BSS 段（detailed）
        cl = self._cl(sections, "bss")
        if cl is not None:
            _clear_layout(cl)
            bss_vars = {n: v for n, v in globals_all.items()
                        if v.region == MR.BSS or v.value is None}
            if bss_vars:
                for name, var in sorted(bss_vars.items(), key=lambda kv: kv[1].address):
                    cl.addWidget(VarCard(var, highlight=(name in highlight_vars)))
            else:
                cl.addWidget(_empty_label())

        # ── 常量区（detailed）
        cl = self._cl(sections, "literal")
        if cl is not None:
            _clear_layout(cl)
            literal_vars = step.literals if step else {}
            if literal_vars:
                for name, var in literal_vars.items():
                    cl.addWidget(VarCard(var, highlight=(name in highlight_vars)))
            else:
                cl.addWidget(_empty_label())

        # ── 代码区（simple / detailed）
        cl = self._cl(sections, "code")
        if cl is not None:
            _clear_layout(cl)
            from .cpp_interpreter import Variable
            if seg_mode == "detailed":
                funcs = list(self._interpreter._functions.keys()) if hasattr(self, '_interpreter') else []
                # 代码区在 unified 里没有 interpreter 引用，显示调用栈函数名即可
                code_vars = {
                    frame.function_name: Variable(
                        name=frame.function_name + "()", type="function",
                        value="...", address=0x00401000 + i * 0x100,
                        region=MR.CODE, size=0
                    )
                    for i, frame in enumerate(stack_frames)
                }
            else:
                code_vars = {
                    frame.function_name: Variable(
                        name=frame.function_name, type="function",
                        value="...", address=0x00401000 + i * 0x100,
                        region=MR.CODE, size=0
                    )
                    for i, frame in enumerate(stack_frames)
                }
            if code_vars:
                for name, var in code_vars.items():
                    cl.addWidget(VarCard(var, highlight=(name in highlight_vars)))
            else:
                cl.addWidget(_empty_label())
