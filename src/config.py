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
    # ── 基础背景层次（GitHub Dark Dimmed 风格）─
    "bg":          "#22272E",   # 主窗口背景
    "bg_editor":   "#1C2128",   # 编辑器背景（最暗）
    "bg_light":    "#2D333B",   # 侧边栏/工具栏
    "bg_panel":    "#2D333B",   # 内存面板
    "bg_card":     "#373E47",   # 卡片背景
    "bg_input":    "#3D444D",   # 悬停/输入框

    # ── 边框与分割线 ──────────────────────────
    "border":      "#444C56",   # 普通边框
    "border_focus":"#539BF5",   # 聚焦蓝
    "separator":   "#30363D",   # 细分割线

    # ── 文字层次 ──────────────────────────────
    "text":        "#ADBAC7",   # 正文
    "text_bright": "#CDD9E5",   # 标题/变量名
    "text_dim":    "#636E7B",   # 辅助/注释
    "text_select": "#FFFFFF",

    # ── 语法高亮（GitHub Dark 配色）───────────
    "syn_keyword": "#F47067",   # 关键字：珊瑚红
    "syn_string":  "#96D0FF",   # 字符串：冰蓝
    "syn_number":  "#6CB6FF",   # 数字：天蓝
    "syn_comment": "#545D68",   # 注释：暗灰
    "syn_preproc": "#F69D50",   # 预处理：琥珀
    "syn_const":   "#DCBDFB",   # 常量/宏：薰衣草紫

    # ── 品牌/强调色 ───────────────────────────
    "accent":      "#539BF5",   # 主蓝（GitHub blue）
    "accent_dim":  "#2660A4",   # 深蓝（按下）
    "accent_bg":   "#1B3A5C",   # 蓝色背景层

    # ── 语义色 ────────────────────────────────
    "green":       "#57AB5A",   # 成功绿
    "green_bright":"#6BC46D",   # 亮绿（栈帧标题）
    "green_bg":    "#1B3A1F",   # 绿色背景层（栈区）
    "yellow":      "#C69026",   # 警告黄
    "yellow_bright":"#DAAA3F",  # 亮黄（高亮变量）
    "yellow_bg":   "#2E2A05",   # 黄色背景层
    "red":         "#E5534B",   # 错误红
    "red_bright":  "#FF8080",   # 亮红
    "red_bg":      "#3A1A1A",   # 红色背景层（堆区）
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
