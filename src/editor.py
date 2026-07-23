"""
editor.py
带行号的 C++ 代码编辑器
"""

from PyQt6.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
from PyQt6.QtGui import QFont, QColor, QPalette, QTextCharFormat, QTextCursor, QPainter
from PyQt6.QtCore import Qt, QRect, QSize

from .config import COLORS


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor._line_number_width(), 0)

    def paintEvent(self, event):
        self._editor._paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self._line_area = LineNumberArea(self)
        self._highlighted_line = -1
        self._error_lines: set = set()

        font = QFont("JetBrains Mono", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        # 回退到常见等宽字体
        font.setFamilies(["JetBrains Mono", "Cascadia Code", "Consolas", "Courier New"])
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self._update_line_area_width(0)

        p = self.palette()
        p.setColor(QPalette.ColorRole.Base, QColor(COLORS["bg_editor"]))
        p.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
        p.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["selection_bg"]))
        p.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["text_select"]))
        self.setPalette(p)
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {COLORS['canvas']};
                color: {COLORS['fg_muted']};
                border: 1px solid {COLORS['border_muted']};
                border-radius: 5px;
                padding: 2px;
                selection-background-color: {COLORS['accent_muted']};
                selection-color: {COLORS['text_select']};
            }}
            QPlainTextEdit:focus {{
                border-color: {COLORS['border_focus']};
            }}
        """)

    def _line_number_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_area_width(self, _):
        self.setViewportMargins(self._line_number_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(),
                                          self._line_number_width(), cr.height()))

    def _paint_line_numbers(self, event):
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(COLORS["bg_light"]))

        # 右侧 1px 分割线
        painter.setPen(QColor(COLORS["separator"]))
        painter.drawLine(self._line_area.width() - 1, event.rect().top(),
                         self._line_area.width() - 1, event.rect().bottom())

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        font = self.font()
        font.setPointSize(10)
        painter.setFont(font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                num_str = str(block_num + 1)
                if block_num == self._highlighted_line:
                    painter.fillRect(0, top, self._line_area.width() - 1,
                                     self.fontMetrics().height(),
                                     QColor(COLORS["highlight_line"]))
                    painter.setPen(QColor(COLORS["yellow"]))
                else:
                    painter.setPen(QColor(COLORS["text_dim"]))
                painter.drawText(0, top, self._line_area.width() - 8,
                                 self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, num_str)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_num += 1

    def highlight_line(self, line_index: int):
        """高亮第 line_index 行（0-based）"""
        self._highlighted_line = line_index
        self._line_area.update()

        cursor = QTextCursor(self.document().findBlockByNumber(line_index))
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

        extra = []
        if line_index >= 0:
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(COLORS["highlight_line"]))
            sel.format.setProperty(
                sel.format.Property.FullWidthSelection, True)  # type: ignore
            sel.cursor = cursor
            extra.append(sel)
        self.setExtraSelections(extra)  # type: ignore

    def clear_highlight(self):
        self._highlighted_line = -1
        self._line_area.update()
        self.setExtraSelections([])  # type: ignore
