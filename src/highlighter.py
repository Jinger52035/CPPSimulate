"""
highlighter.py
C++ 代码语法高亮（QSyntaxHighlighter）
"""

import re
from PyQt6.QtGui import QColor, QTextCharFormat, QSyntaxHighlighter

from .config import COLORS


class CppHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        def fmt(color, bold=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(700)
            return f

        keywords = (
            "int|float|double|char|bool|void|long|short|unsigned|"
            "return|if|else|for|while|do|break|continue|"
            "new|delete|nullptr|true|false|const|static|"
            "include|define|cout|cin|endl|string|using|namespace|std"
        )
        self._rules += [
            (re.compile(r'\b(' + keywords + r')\b'), fmt(COLORS["syn_keyword"], True)),
            (re.compile(r'"[^"]*"'),                 fmt(COLORS["syn_string"])),
            (re.compile(r"'[^']*'"),                 fmt(COLORS["syn_string"])),
            (re.compile(r'//[^\n]*'),                fmt(COLORS["syn_comment"])),
            (re.compile(r'\b\d+\.?\d*\b'),           fmt(COLORS["syn_number"])),
            (re.compile(r'#\w+'),                    fmt(COLORS["syn_preproc"])),
            (re.compile(r'\b[A-Z_][A-Z0-9_]+\b'),   fmt(COLORS["syn_const"])),
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
