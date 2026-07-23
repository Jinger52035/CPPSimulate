# C++ 执行可视化教学工具

**C++ Execution Visualizer — An interactive teaching tool for memory layout**

---

## 简介 / Overview

一个基于 PyQt6 的桌面应用，将 C++ 代码的逐步执行过程可视化为内存布局图。
每一步都能清晰看到栈帧的创建与销毁、堆内存的分配与释放、全局变量的存储区域，以及各类指针错误引发的崩溃现象。

A PyQt6 desktop application that visualizes the step-by-step execution of C++ code as an interactive memory layout diagram.  
Each step shows stack frame creation and teardown, heap allocation and deallocation, global variable storage regions, and crash behavior triggered by common pointer errors.

---

## 功能特性 / Features

| 功能 | Feature |
|------|---------|
| 逐步执行，单步 / 自动播放 | Step-by-step and auto-play execution |
| 栈帧层叠展示，含参数绑定 | Stacked frame display with parameter binding |
| 堆内存动态分配可视化 | Heap allocation visualization |
| 字节格子图（ByteCells） | Byte-level memory cell widget |
| 结构体内存对齐与 padding | Struct layout with padding visualization |
| 指针地址双向追踪 | Pointer-to-address cross-referencing |
| 全局 / 数据段 / BSS / 常量区 | Global / Data / BSS / Literals segments |
| 三种内存分段粒度（简单/标准/详细） | Three segmentation modes (simple/standard/detailed) |
| 分栏布局 / 统一虚拟地址空间布局 | Split-panel and unified address space layouts |
| **崩溃模拟**：野指针 / 二次释放 / 空指针解引用 | **Crash simulation**: wild ptr / double free / null deref |
| 20 个内置源码示例：19 个课程示例 + LeetCode 递归示例 | 20 built-in source examples: 19 curriculum lessons + recursively discovered LeetCode examples |
| 可加载外部 `.cpp` 文件 | Load external `.cpp` files |

---

## 崩溃模拟 / Crash Simulation

当代码触发以下未定义行为时，工具会**暂停执行**并弹出崩溃弹框，展示崩溃原因和修复建议：

When the following undefined behaviors are triggered, the tool **halts execution** and shows a crash dialog with cause explanation and fix suggestions:

- **野指针 Wild Pointer** — `delete` an uninitialized pointer
- **二次释放 Double Free** — `delete` the same address twice
- **空指针解引用 Null Dereference** — write through a `nullptr`
- **释放后使用 Use After Free** — write through a pointer after `delete`

---

## 内置示例 / Built-in Examples

示例编号是稳定 ID；界面中的组内顺序按知识依赖组织。Example numbers are stable IDs; lessons are ordered by prerequisites in the UI.

| 学习阶段 / Stage | 推荐顺序 | 内容 / Topics |
|------------------|----------|---------------|
| 语言基础 / Language Basics | 01, 02 | 基本变量与类型；for 循环累加 |
| 函数、作用域与调用栈 / Functions, Scope & Stack | 03, 08, 07 | 函数调用；变量遮蔽；递归栈帧 |
| 指针与动态内存 / Pointers & Dynamic Memory | 06, 10, 04, 11, 13 | 地址与解引用；参数传递；new/delete；堆数组与增长方向 |
| 对象、生命周期与布局 / Objects & Layout | 05, 12, 09 | 类实例；构造析构顺序；内存对齐与 padding |
| 进程内存模型 / Process Memory Model | 14 | Data、BSS 与常量区 |
| 内存安全错误 / Memory Safety | 15, 16, 17 | 野指针；二次释放；空指针解引用 |
| STL 与算法 / STL & Algorithms | 18, 19 | vector；unordered_map 与 Two Sum |

LeetCode 是独立的默认顶层分组，不属于第 8 个课程阶段。工具会递归镜像 `examples/leetcode` 的目录层级，并自动计入 `.cpp`、`.h`、`.cxx`、`.cc` 源码文件；不支持的文件和没有源码后代的目录会被忽略。

LeetCode is a separate default top-level group, not an eighth curriculum stage. The tree recursively mirrors `examples/leetcode` and discovers `.cpp`, `.h`, `.cxx`, and `.cc` files automatically; unsupported files and branches without source descendants are omitted.

---

## 环境要求 / Requirements

- Python 3.11+
- PyQt6 6.11+
- PyQt6-WebEngine 6.11+

```bash
pip install -r requirements.txt
```

---

## 运行 / Run

```bash
python run.py
```

### 运行测试 / Run Tests

`tests/` 保存应用的自动化回归测试，不参与桌面程序运行。测试覆盖：

- `test_main_window_web.py`：示例树、工具栏、示例加载和 Web 内存界面联动。
- `test_memory_serializer.py`：执行快照到 JSON DTO 的结构、地址和序列化稳定性。
- `test_web_bridge.py`：Python 与嵌入式 HTML 页面之间的 QWebChannel 状态桥接。
- `test_web_memory_view.py`：内存布局、分段模式、指针高亮、崩溃状态和 CSP 安全约束。

在项目根目录执行：

```bash
PYTHONPATH="." python -m unittest discover -s tests -p "test_*.py"
```

Windows PowerShell 可使用：

```powershell
$env:PYTHONPATH = "."
python -m unittest discover -s tests -p "test_*.py"
```

---

## 使用方法 / Usage

1. 在左侧分组示例树中展开学习阶段并选择示例，或在 File 栏点击「打开」加载自己的 `.cpp` 文件  
   Expand a learning stage in the grouped example tree, or use **Open** in the File bar to load your own `.cpp` file

2. 点击工具栏的运行图标解析代码  
   Click the Run icon in the toolbar to parse the code

3. 点击单步图标逐步执行，右侧内存面板实时更新  
   Click the Step icon to advance; the memory panels update in real time

4. 点击自动播放图标开始或暂停，用速度滑块调节间隔  
   Click the Auto icon to play or pause; use the speed slider to adjust interval

5. 点击 **⚙ 设置** 切换内存分段粒度与布局模式  
   Click **⚙ Settings** to change segmentation granularity and layout mode

6. 遇到崩溃示例时，执行到问题行会自动弹出崩溃说明弹框  
   On crash examples, a dialog appears automatically at the offending line

---

## 项目结构 / Project Structure

```
C++/
├── run.py                  # 启动入口 / Entry point
├── requirements.txt
├── README.md
├── FIXES_2026-07-23.md     # 当日修复记录 / Daily fix notes
├── tests/                  # 自动化回归测试 / Automated regression tests
│   ├── test_main_window_web.py
│   ├── test_memory_serializer.py
│   ├── test_web_bridge.py
│   └── test_web_memory_view.py
├── examples/               # 按知识进程分组的 C++ 示例
│   ├── 01_language_basics/
│   ├── 02_functions_scope_stack/
│   ├── 03_pointers_dynamic_memory/
│   ├── 04_objects_layout/
│   ├── 05_memory_model/
│   ├── 06_memory_safety/
│   ├── 07_stl_algorithms/
│   └── leetcode/           # 默认递归分组 / Default recursive group
│       └── array/
│           └── 0001.cpp
└── src/
    ├── main_window.py      # 主窗口 UI / Main window
    ├── cpp_interpreter.py  # 模拟执行引擎 / Execution engine
    ├── memory_serializer.py # 执行快照 JSON DTO / Snapshot serializer
    ├── web_bridge.py       # QWebChannel 通信桥 / Web channel bridge
    ├── web_memory_view.py  # 内嵌 WebEngine 容器 / Embedded web host
    ├── web/                # HTML/CSS/JS 内存界面 / Web memory UI
    ├── panels.py           # 旧版 Qt 内存面板（迁移对照）/ Legacy panels
    ├── widgets.py          # 旧版 Qt 内存组件（迁移对照）/ Legacy widgets
    ├── dialogs.py          # 设置弹框 / 崩溃弹框 / Dialogs
    ├── editor.py           # 代码编辑器 / Code editor
    ├── highlighter.py      # C++ 语法高亮 / Syntax highlighter
    └── config.py           # 颜色主题 / 设置 / Theme and settings
```

---

## 界面架构 / UI Architecture

核心内存可视化使用本地 HTML/CSS/JavaScript 重写，并通过 `QWebEngineView` 嵌入 PyQt6 桌面窗口。Python 解释器仍是唯一执行状态来源，`QWebChannel` 只向页面发送当前步骤的版本化 JSON 快照；编辑器、工具栏、自动播放、文件对话框、设置和崩溃教学弹框继续由原生 Qt 控制。页面不依赖网络、CDN 或 Node.js 构建工具。

The core memory visualization is implemented with local HTML/CSS/JavaScript embedded in the PyQt6 window through `QWebEngineView`. Python remains the sole execution-state authority, while `QWebChannel` sends a versioned JSON snapshot of the current step. The editor, desktop controls, playback, file dialogs, settings, and crash dialogs remain native Qt components.

---

## 内存分段粒度 / Segmentation Modes

| 模式 | 分区 | Mode | Segments |
|------|------|------|----------|
| 简单 | 代码区 / 全局 / 堆 / 栈 | Simple | Code / Global / Heap / Stack |
| 标准 | 全局区 / 堆 / 栈 | Standard | Global / Heap / Stack |
| 详细 | Code / Literals / Data / BSS / Heap / Stack | Detailed | Code / Literals / Data / BSS / Heap / Stack |

详细模式采用 **2 行 × 3 列** 布局，上行为只读区（代码/常量/数据段），下行为运行时区（BSS/堆/栈）。

In detailed mode, the layout is **2 rows × 3 columns**: the top row shows read-only regions (Code / Literals / Data), and the bottom row shows runtime regions (BSS / Heap / Stack).

---

## 修复记录 / Fix Notes

2026-07-23 的详细修复记录已单独整理到 [`FIXES_2026-07-23.md`](FIXES_2026-07-23.md)，包括：

- 指针解引用修改栈变量。
- 示例 07 递归执行与多层栈帧展示。
- 小屏幕下 split 多栏整体横向滚动适配。
- unified 与 split 堆内存向高地址增长的展示方向。
- 修复原因、代码范围和验证结果。

---

## 支持的 C++ 子集 / Supported C++ Subset

| 特性 | 支持 | Feature | Supported |
|------|------|---------|-----------|
| 基本类型 int/float/double/char/bool | ✓ | Basic types | ✓ |
| 指针类型 int* / float* | ✓ | Pointer types | ✓ |
| 变量赋值、复合赋值 +=/-=/*= | ✓ | Assignment and compound assignment | ✓ |
| 自增/自减 ++/-- | ✓ | Increment/decrement | ✓ |
| for / while 循环 | ✓ | Loops | ✓ |
| if / else | ✓ | Conditionals | ✓ |
| 函数定义与调用 | ✓ | Function definition and calls | ✓ |
| 递归（有限深度） | ✓ | Recursion (bounded depth) | ✓ |
| new / delete / delete[] | ✓ | Dynamic memory | ✓ |
| class / struct，含构造/析构 | ✓ | Classes with ctor/dtor | ✓ |
| cout 输出 | ✓ | cout output | ✓ |
| 全局变量 / 静态变量 | ✓ | Global variables | ✓ |
| 崩溃/UB 检测 | ✓ | Crash / UB detection | ✓ |

---

## 地址模型 / Address Model

模拟 x86-64 小端序，地址为教学演示用虚构值：

Simulates x86-64 little-endian; addresses are illustrative, not real:

| 区域 | 基址 | Region | Base |
|------|------|--------|------|
| 代码段 | `0x00401000` ↑ | Code | `0x00401000` ↑ |
| 常量区 | `0x00402000` ↑ | Literals | `0x00402000` ↑ |
| 全局/数据段 | `0x00400000` ↑ | Global / Data | `0x00400000` ↑ |
| 堆 | `0x01000000` ↑ | Heap | `0x01000000` ↑ |
| 栈 | `0x7FFF0000` ↓ | Stack | `0x7FFF0000` ↓ |
