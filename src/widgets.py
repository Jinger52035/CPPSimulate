"""
widgets.py
内存可视化基础小组件：字节格子、变量卡片、对象卡片
"""

from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtCore import Qt

from .cpp_interpreter import MemoryRegion
from .config import COLORS


# ──────────────────────────────────────────────
# 字节格子
# ──────────────────────────────────────────────

class ByteCells(QWidget):
    """将变量字节可视化为小格子，每格 = 1 字节。
    每行最多 4 格，行数按 size 自动计算。
    int=1行4格；double/ptr=2行4格；int[5]=5行4格。"""

    CELL_W  = 7
    CELL_H  = 10
    GAP     = 1
    ROW_W   = 4   # 每行固定 4 格

    def __init__(self, size: int, stride: int, base_addr: int, fill_color: str, parent=None):
        super().__init__(parent)
        stride      = max(stride, 1)
        self._cols  = self.ROW_W
        self._rows  = max(1, (size + self.ROW_W - 1) // self.ROW_W)
        self._total = size
        self._stride = stride   # 用于在行之间绘制元素分隔线
        self._color = QColor(fill_color)

        w = self._cols * (self.CELL_W + self.GAP) - self.GAP
        h = self._rows * (self.CELL_H + self.GAP) - self.GAP
        self.setFixedSize(w, h)
        elem_count = size // stride
        self.setToolTip(
            f"地址: {hex(base_addr)} ~ {hex(base_addr + size - 1)}\n"
            f"大小: {size} 字节  步长: {stride}B"
            + (f"  元素: {elem_count}" if elem_count > 1 else "")
        )

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        fill        = self._color
        border      = self._color.darker(160)
        elem_border = self._color.darker(220)   # 元素边界加深
        for i in range(self._total):
            col = i % self._cols
            row = i // self._cols
            x = col * (self.CELL_W + self.GAP)
            y = row * (self.CELL_H + self.GAP)
            p.fillRect(x, y, self.CELL_W, self.CELL_H, fill)
            # 每隔 stride 字节是一个元素边界，用深色线区分
            at_elem_boundary = (i % self._stride == 0) and i > 0
            p.setPen(elem_border if at_elem_boundary else border)
            p.drawRect(x, y, self.CELL_W - 1, self.CELL_H - 1)
        p.end()


class StructCells(QWidget):
    """
    把整个 struct/class 的内存画成连续格子，每行 4 格。
    segments: [(offset, size, color, label), ...]  — 成员片段
    total_size: struct 总字节数（含 padding）
    base_addr: struct 基址
    """

    CELL_W  = 9
    CELL_H  = 13
    GAP     = 1
    ROW_CAP = 4

    def __init__(self, segments: list, total_size: int, base_addr: int, parent=None):
        super().__init__(parent)
        self._segments  = segments
        self._total     = min(total_size, 32)
        self._base      = base_addr

        cols = min(self._total, self.ROW_CAP)
        rows = (self._total + self.ROW_CAP - 1) // self.ROW_CAP
        self.setFixedSize(cols * (self.CELL_W + self.GAP) - self.GAP,
                          rows * (self.CELL_H + self.GAP) - self.GAP)

        tip_lines = [f"struct  {total_size}B  基址 {hex(base_addr)}"]
        for offset, size, _, label in segments:
            tip_lines.append(f"  +{offset}  {label}  {size}B  {hex(base_addr+offset)}")
        self.setToolTip("\n".join(tip_lines))

    def paintEvent(self, _event):
        CW, CH, G = self.CELL_W, self.CELL_H, self.GAP
        colors = [QColor("#2A2A3A")] * self._total   # 默认 padding 灰
        for offset, size, color, _ in self._segments:
            c = QColor(color)
            for b in range(size):
                idx = offset + b
                if idx < self._total:
                    colors[idx] = c

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for i, c in enumerate(colors):
            col = i % self.ROW_CAP
            row = i // self.ROW_CAP
            x = col * (CW + G)
            y = row * (CH + G)
            p.fillRect(x, y, CW, CH, c)
            p.setPen(c.darker(160))
            p.drawRect(x, y, CW - 1, CH - 1)
        p.end()


# ──────────────────────────────────────────────
# 成员颜色池
# ──────────────────────────────────────────────

_MEMBER_COLORS = ["#3B6EA8", "#2E7D52", "#7B3FA0", "#8B5A00",
                  "#1A6B6B", "#8B2020", "#4A5A00", "#1A4A7A"]


# ──────────────────────────────────────────────
# 变量卡片
# ──────────────────────────────────────────────

class VarCard(QFrame):
    def __init__(self, var, highlight=False):
        super().__init__()
        self.setFrameShape(QFrame.Shape.NoFrame)

        region_colors = {
            MemoryRegion.GLOBAL: (COLORS["global_bg"], COLORS["accent"]),
            MemoryRegion.STACK:  (COLORS["stack_bg"],  COLORS["green_bright"]),
            MemoryRegion.HEAP:   (COLORS["heap_bg"],   COLORS["red"]),
        }
        bg, accent = region_colors.get(var.region, (COLORS["bg_panel"], COLORS["border"]))
        left_color = COLORS["yellow"] if highlight else accent

        self.setStyleSheet(f"""
            VarCard {{
                background-color: {bg};
                border-left: 3px solid {left_color};
                border-top: 1px solid {COLORS['separator']};
                border-right: 1px solid {COLORS['separator']};
                border-bottom: 1px solid {COLORS['separator']};
                border-radius: 4px;
                margin: 2px 4px;
            }}
            VarCard:hover {{
                border-top-color: {COLORS['border']};
                border-right-color: {COLORS['border']};
                border-bottom-color: {COLORS['border']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(2)

        cells = ByteCells(var.size, var.stride, var.address,
                          COLORS["yellow"] if highlight else accent)
        is_array = (var.size > var.stride and var.stride > 0)

        # Top row: type badge + name + = + value
        row = QHBoxLayout()
        row.setSpacing(6)

        type_lbl = QLabel(var.type + ("[]" if is_array else ""))
        type_lbl.setStyleSheet(f"""
            color: {COLORS['purple']};
            background: {COLORS['purple_bg']};
            font-size: 10px;
            font-style: italic;
            padding: 1px 5px;
            border-radius: 3px;
        """)

        name_lbl = QLabel(var.name)
        name_lbl.setStyleSheet(
            f"color: {COLORS['yellow_bright'] if highlight else COLORS['text_bright']};"
            f"font-weight: 600; font-size: 12px; background: transparent;"
        )

        row.addWidget(type_lbl)
        row.addWidget(name_lbl)

        if not is_array:
            eq_lbl = QLabel("=")
            eq_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; background: transparent;")
            val_lbl = QLabel(var.display_value())
            val_lbl.setStyleSheet(
                f"color: {COLORS['syn_number']}; font-size: 12px; font-weight: 600; background: transparent;"
            )
            row.addWidget(eq_lbl)
            row.addWidget(val_lbl)

        row.addStretch()
        row.addWidget(cells, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(row)

        if is_array:
            n_elem = var.size // max(var.stride, 1)
            size_lbl = QLabel(f"{n_elem} × {var.stride}B = {var.size}B")
            size_lbl.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 10px; background: transparent;"
            )
            layout.addWidget(size_lbl)

        # Address sub-line
        addr_lbl = QLabel(hex(var.address))
        addr_lbl.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 9px; background: transparent;"
            f"font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;"
        )
        layout.addWidget(addr_lbl)


# ──────────────────────────────────────────────
# 对象卡片（struct/class 实例）
# ──────────────────────────────────────────────

class ObjectCard(QFrame):
    """展示一个 struct/class 实例，成员合并在一张卡片内"""

    def __init__(self, obj_name: str, cls_name: str,
                 members_sorted: list,   # [(name, Variable), ...] 按地址升序
                 base_addr: int, total_size: int,
                 highlight_names: list = None):
        super().__init__()
        highlight_names = highlight_names or []
        self.setFrameShape(QFrame.Shape.NoFrame)
        highlighted = any(n in highlight_names for n, _ in members_sorted)
        left_color = COLORS["yellow"] if highlighted else COLORS["green_bright"]
        self.setStyleSheet(f"""
            ObjectCard {{
                background: {COLORS['stack_bg']};
                border-left: 3px solid {left_color};
                border-top: 1px solid {COLORS['separator']};
                border-right: 1px solid {COLORS['separator']};
                border-bottom: 1px solid {COLORS['separator']};
                border-radius: 4px;
                margin: 2px 4px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(4)

        # 标题行
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        cls_lbl = QLabel(cls_name)
        cls_lbl.setStyleSheet(f"""
            color: {COLORS['purple']};
            background: {COLORS['purple_bg']};
            font-size: 10px;
            font-style: italic;
            padding: 1px 5px;
            border-radius: 3px;
        """)
        name_lbl = QLabel(obj_name)
        name_lbl.setStyleSheet(
            f"color: {COLORS['text_bright']}; font-weight: 600; font-size: 12px; background: transparent;"
        )
        size_lbl = QLabel(f"{total_size}B  ·  {hex(base_addr)}")
        size_lbl.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 9px; background: transparent;"
            f"font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;"
        )
        title_row.addWidget(cls_lbl)
        title_row.addWidget(name_lbl)
        title_row.addStretch()
        title_row.addWidget(size_lbl)
        root.addLayout(title_row)

        # StructCells
        segments = []
        for i, (mname, var) in enumerate(members_sorted):
            offset = var.address - base_addr
            color  = _MEMBER_COLORS[i % len(_MEMBER_COLORS)]
            segments.append((offset, var.size, color, f"{mname}:{var.type}"))

        cells = StructCells(segments, total_size, base_addr)
        root.addWidget(cells)

        # 成员列表
        for i, (mname, var) in enumerate(members_sorted):
            color = _MEMBER_COLORS[i % len(_MEMBER_COLORS)]
            row = QHBoxLayout()
            row.setSpacing(5)

            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 8px; background: transparent;")
            type_lbl = QLabel(var.type)
            type_lbl.setStyleSheet(
                f"color: {COLORS['purple']}; font-size: 10px; font-style: italic; background: transparent;"
            )
            mname_lbl = QLabel(mname)
            hl = mname in highlight_names or f"{obj_name}.{mname}" in highlight_names
            mname_lbl.setStyleSheet(
                f"color: {COLORS['yellow_bright'] if hl else COLORS['text_bright']}; "
                f"font-size: 11px; font-weight: {'600' if hl else 'normal'}; background: transparent;"
            )
            eq_lbl = QLabel("=")
            eq_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; background: transparent;")
            val_lbl = QLabel(var.display_value())
            val_lbl.setStyleSheet(
                f"color: {COLORS['syn_number']}; font-size: 11px; font-weight: 600; background: transparent;"
            )
            addr_lbl = QLabel(hex(var.address))
            addr_lbl.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 9px; background: transparent;"
                f"font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;"
            )

            row.addWidget(dot)
            row.addWidget(type_lbl)
            row.addWidget(mname_lbl)
            row.addWidget(eq_lbl)
            row.addWidget(val_lbl)
            row.addStretch()
            row.addWidget(addr_lbl)
            root.addLayout(row)
