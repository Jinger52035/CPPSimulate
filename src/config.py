"""
config.py
全局颜色主题与应用设置数据类
"""

from dataclasses import dataclass


# ──────────────────────────────────────────────
# 应用设置
# ──────────────────────────────────────────────

@dataclass
class AppSettings:
    layout:   str = "split"     # "split" | "unified"
    seg_mode: str = "standard"  # "simple" | "standard" | "detailed"


# ──────────────────────────────────────────────
# 调色板
# ──────────────────────────────────────────────

COLORS = {
    # ── Primer / GitHub Dark Dimmed 语义令牌 ───
    "canvas":       "#1C2128",
    "surface":      "#22272E",
    "surface_subtle":"#2D333B",
    "surface_raised":"#343B45",
    "surface_hover": "#373E47",
    "surface_pressed": "#3D444D",
    "border_muted": "#30363D",
    "border":       "#444C56",
    "border_focus": "#539BF5",
    "fg_default":   "#CDD9E5",
    "fg_muted":     "#ADBAC7",
    "fg_subtle":    "#768390",
    "accent":       "#539BF5",
    "accent_hover": "#6CB6FF",
    "accent_pressed": "#4184E4",
    "accent_muted": "#1B3A5C",
    "danger":       "#E5534B",
    "danger_fg":    "#FFAAA5",
    "danger_bg":    "#30262A",
    "danger_border":"#713535",

    # ── 旧组件兼容别名 ──────────────────────────
    "bg":          "#22272E",
    "bg_editor":   "#1C2128",
    "bg_light":    "#2D333B",
    "bg_panel":    "#2D333B",
    "bg_card":     "#343B45",
    "bg_input":    "#3D444D",
    "separator":   "#30363D",
    "text":        "#ADBAC7",
    "text_bright": "#CDD9E5",
    "text_dim":    "#768390",
    "text_select": "#FFFFFF",

    # ── 语法高亮（GitHub Dark 配色）───────────
    "syn_keyword": "#F47067",   # 关键字：珊瑚红
    "syn_string":  "#96D0FF",   # 字符串：冰蓝
    "syn_number":  "#6CB6FF",   # 数字：天蓝
    "syn_comment": "#545D68",   # 注释：暗灰
    "syn_preproc": "#F69D50",   # 预处理：琥珀
    "syn_const":   "#DCBDFB",   # 常量/宏：薰衣草紫

    # ── 品牌/强调色 ───────────────────────────
    "accent_dim":  "#4184E4",   # 深蓝（按下）
    "accent_bg":   "#1B3A5C",   # 蓝色背景层

    # ── 语义色 ────────────────────────────────
    "green":       "#57AB5A",   # 成功绿
    "green_bright":"#6BC46D",   # 亮绿（栈帧标题）
    "green_bg":    "#1B3A1F",   # 绿色背景层（栈区）
    "yellow":      "#C69026",   # 警告黄
    "yellow_bright":"#DAAA3F",  # 亮黄（高亮变量）
    "yellow_bg":   "#2E2A05",   # 黄色背景层
    "red":         "#E5534B",   # 错误红
    "red_bright":  "#FFAAA5",   # 亮红
    "red_bg":      "#30262A",   # subtle danger 背景
    "purple":      "#DCBDFB",   # 紫（类型）
    "purple_bg":   "#2A1F3D",   # 紫色背景层
    "teal":        "#39C5CF",   # 青（代码段）
    "orange":      "#F69D50",   # 橙

    # ── 内存区域背景 ──────────────────────────
    "stack_bg":    "#1E2D20",   # 栈区
    "heap_bg":     "#2D1E1E",   # 堆区
    "global_bg":   "#1E1E2D",   # 全局区

    # ── 编辑器 ────────────────────────────────
    "highlight_line": "#2A3A2A",  # 执行行背景
    "selection_bg":   "#1B3A5C",  # 选中背景

    # ── 设置对话框 ────────────────────────────
    "dlg_bg":      "#2D333B",
    "dlg_text":    "#CDD9E5",
    "dlg_border":  "#444C56",
    "dlg_accent":  "#539BF5",
    "dlg_dim":     "#636E7B",
    "dlg_hover":   "#373E47",
    "dlg_checked": "#1B3A5C",
}
