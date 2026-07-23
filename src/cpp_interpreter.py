"""
cpp_interpreter.py
一个简化的 C++ 执行模拟引擎，支持基本语句的逐步执行
支持：变量声明/赋值、算术运算、if/else、for/while 循环、
      简单函数定义与调用、cout 输出、new/delete（堆内存模拟）
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from .type_parser import (
    parse_type as _parse_type,
    type_size as _template_type_size,
    is_container_type as _is_container_type,
)
from .stl_containers import ContainerVariable, STLMethodHandler


# ──────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────

class MemoryRegion(Enum):
    # 简单/标准模式
    GLOBAL  = "全局区"
    STACK   = "栈 (Stack)"
    HEAP    = "堆 (Heap)"
    # 详细模式细分
    CODE    = "代码段 (Code)"
    LITERAL = "常量区 (Literals)"
    DATA    = "数据段 (Data)"       # 已初始化全局/静态
    BSS     = "BSS段 (未初始化)"    # 未初始化全局/静态


@dataclass
class Variable:
    name: str
    type: str
    value: Any
    address: int          # 模拟地址
    region: MemoryRegion
    size: int = 4         # 真实字节数（char=1, int=4, double=8）
    stride: int = 4       # 对齐后实际占用槽宽（含 padding）
    is_pointer: bool = False

    def display_value(self):
        if self.value is None:
            return "未初始化"
        if self.is_pointer:
            if self.value == 0:
                return "nullptr"
            return hex(self.value)
        if self.type == "char" and isinstance(self.value, int):
            return f"'{chr(self.value)}' ({self.value})"
        return str(self.value)


@dataclass
class StackFrame:
    function_name: str
    variables: dict = field(default_factory=dict)   # name -> Variable
    return_line: Optional[int] = None
    objects: list = field(default_factory=list)      # 本帧创建的对象名列表（析构用）

    def __str__(self):
        return self.function_name


@dataclass
class CrashInfo:
    """崩溃/未定义行为信息，附加在导致崩溃的执行步骤上"""
    ub_type: str      # "wild_ptr" | "double_free" | "null_deref" | "use_after_free"
    title: str        # 崩溃类型标题，如 "野指针崩溃"
    cause: str        # 一句话原因
    detail: str       # 详细说明（原理 + 危害）
    ptr_name: str = ""
    ptr_value: Any = None


@dataclass
class ExecutionStep:
    """单步执行的快照"""
    line_index: int
    description: str
    stack_frames: list
    heap: dict = field(default_factory=dict)
    globals: dict = field(default_factory=dict)
    output: str = ""
    highlight_vars: list = field(default_factory=list)
    # obj_name -> {base_addr, total_size, padding: [(addr, nbytes)]}
    objects: dict = field(default_factory=dict)
    # 源码中出现过的字符串字面量 {str -> Variable}
    literals: dict = field(default_factory=dict)
    # 崩溃信息：非 None 表示此步骤触发了崩溃/UB
    crash: "CrashInfo | None" = None


# ──────────────────────────────────────────────
# 地址分配器（纯模拟）
# ──────────────────────────────────────────────

class AddressAllocator:
    GLOBAL_BASE = 0x00400000
    STACK_BASE  = 0x7FFF0000
    HEAP_BASE   = 0x01000000

    def __init__(self):
        self._global_ptr = self.GLOBAL_BASE
        self._stack_ptr  = self.STACK_BASE
        self._heap_ptr   = self.HEAP_BASE

    @staticmethod
    def _align_up(value: int, align: int) -> int:
        return (value + align - 1) & ~(align - 1)

    @staticmethod
    def _stride(size: int) -> int:
        """x86-64 ABI 自然对齐：stride = size，最大 8B"""
        if size <= 1:  return 1   # char, bool
        if size <= 2:  return 2   # short
        if size <= 4:  return 4   # int, float
        return 8                  # double, long, pointer

    def alloc_global(self, size=4):
        align = min(self._stride(size), 8)
        self._global_ptr = self._align_up(self._global_ptr, align)
        addr = self._global_ptr
        self._global_ptr += self._stride(size)
        return addr

    def alloc_stack(self, size=4):
        """栈向低地址增长，按类型自然对齐"""
        stride = self._stride(size)
        self._stack_ptr -= stride
        # 向下对齐到 stride 边界（处理跨类型时的 padding）
        self._stack_ptr = self._stack_ptr & ~(stride - 1)
        return self._stack_ptr

    def alloc_heap(self, size=4):
        align = min(self._stride(size), 8)
        self._heap_ptr = self._align_up(self._heap_ptr, align)
        addr = self._heap_ptr
        self._heap_ptr += size   # 堆按真实大小步进，不强制 padding
        return addr

    def reset_stack(self):
        self._stack_ptr = self.STACK_BASE


# ──────────────────────────────────────────────
# 词法预处理
# ──────────────────────────────────────────────

TYPE_SIZES = {
    "int": 4, "float": 4, "double": 8,
    "char": 1, "bool": 1, "long": 8,
    "short": 2, "string": 32,
}
BASIC_TYPES = set(TYPE_SIZES.keys())


def get_type_size(ctype: str) -> int:
    ctype = ctype.strip().rstrip("*")
    return TYPE_SIZES.get(ctype, 4)


def is_pointer_type(ctype: str) -> bool:
    return "*" in ctype


# ──────────────────────────────────────────────
# 主解析器 / 模拟器
# ──────────────────────────────────────────────

class CppInterpreter:
    """
    解析并逐步"执行"一段简化 C++ 代码。
    不是真正的编译器，而是教学级别的状态机模拟。
    """

    def __init__(self):
        self.reset()

    # ── 公开接口 ──────────────────────────────

    @staticmethod
    def _make_var(name, ctype, value, address, region, size, is_pointer=False) -> "Variable":
        """创建 Variable，自动计算对齐 stride。"""
        stride = AddressAllocator._stride(size)
        return Variable(name=name, type=ctype, value=value,
                        address=address, region=region,
                        size=size, stride=stride, is_pointer=is_pointer)

    def load(self, source: str):
        """加载源代码并预解析，准备执行"""
        self.reset()
        self.source_lines = source.splitlines()
        self._preparse()
        self._scan_literals()   # 预扫描字符串字面量

    def _scan_literals(self):
        """扫描源码中所有字符串字面量，建立常量区映射 {str: Variable}"""
        seen = {}
        addr = 0x00402000
        for line in self.source_lines:
            for m in re.finditer(r'"([^"]*)"', line):
                s = m.group(1)
                if s not in seen:
                    var = self._make_var(
                        f'"{s}"', "const char*", s,
                        addr, MemoryRegion.LITERAL, len(s) + 1
                    )
                    seen[s] = var
                    addr += ((len(s) + 1 + 3) & ~3)   # 4字节对齐
        self._literals = seen

    def reset(self):
        self.source_lines: list[str] = []
        self.steps: list[ExecutionStep] = []
        self.current_step = -1

        self._allocator = AddressAllocator()
        self._globals: dict[str, Variable] = {}
        self._heap: dict[int, Variable] = {}
        self._call_stack: list[StackFrame] = []
        self._output = ""
        self._functions: dict[str, dict] = {}  # name -> {params, body_start, body_end}
        self._classes: dict[str, dict] = {}    # class_name -> {members, ctor, dtor}
        self._objects: dict[str, dict] = {}    # obj_name -> {class_name, members: {name->Variable}}
        self._steps_built = False
        self._literals: dict = {}   # 源码字符串字面量常量区
        self._freed_addrs: set = set()  # 已 delete 的堆地址（用于检测 double-free）
        self._crashed: bool = False     # 一旦崩溃，停止继续生成步骤
        # 成员方法分发器（延迟初始化，避免循环引用）
        self._method_dispatcher = None

    def build_steps(self):
        """一次性生成所有执行步骤（教学用途，离线计算）"""
        if self._steps_built:
            return
        self._steps_built = True
        # 延迟导入避免循环依赖
        from .method_dispatch import MethodDispatcher
        self._method_dispatcher = MethodDispatcher(self)
        # 先执行全局语句（全局变量初始化），再显式调用 main
        self._execute_lines(self.source_lines, scope="global")
        if "main" in self._functions:
            self._call_function("main", "", 0)

    def total_steps(self) -> int:
        return len(self.steps)

    def get_step(self, index: int) -> Optional[ExecutionStep]:
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    # ── 内部预解析 ────────────────────────────

    def _preparse(self):
        """扫描函数定义和 class 定义，建立查找表"""
        lines = self.source_lines
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()

            # ── class 定义
            m_class = re.match(r'^class\s+(\w+)\s*\{?', stripped)
            if m_class:
                class_name = m_class.group(1)
                class_info = {
                    "members": [],      # [(type, name)]
                    "ctor": None,       # {params_str, lines, body_start}
                    "dtor": None,       # {lines, body_start}
                    "methods": {},
                }
                # 找 class 体
                depth = 0
                class_body = []
                j = i
                while j < len(lines):
                    depth += lines[j].count("{") - lines[j].count("}")
                    class_body.append(lines[j])
                    j += 1
                    if depth == 0 and len(class_body) > 1:
                        break
                # 解析 class 体内容
                self._parse_class_body(class_name, class_body, i, class_info)
                self._classes[class_name] = class_info
                i = j
                continue

            # ── 普通函数定义
            m = re.match(
                r'^\s*((?:\w[\w\s]*?)(?:\s*<[^>]*>)?(?:\s*\*)?)\s+(\w+)\s*\(([^)]*)\)\s*\{?\s*$',
                lines[i]
            )
            if m:
                ret_type = m.group(1).strip()
                fname    = m.group(2).strip()
                params   = m.group(3).strip()
                if fname not in ("if", "while", "for", "else") and ret_type not in ("if",):
                    body_start = i
                    depth = 0
                    for j in range(i, len(lines)):
                        depth += lines[j].count("{") - lines[j].count("}")
                        if depth == 0 and j > i:
                            self._functions[fname] = {
                                "ret_type": ret_type,
                                "params_str": params,
                                "body_start": body_start,
                                "body_end": j,
                                "lines": lines[body_start:j+1],
                            }
                            break
                    i = self._functions.get(fname, {}).get("body_end", i) + 1
                    continue
            i += 1

    def _parse_class_body(self, class_name: str, body_lines: list, file_offset: int, info: dict):
        """解析 class 体：提取成员变量、构造函数、析构函数"""
        i = 0
        while i < len(body_lines):
            s = body_lines[i].strip()
            # 跳过 access specifiers / 空行 / 注释
            if not s or s in ("public:", "private:", "protected:", "{", "}") \
                    or s.startswith("//") or s.startswith("class"):
                i += 1
                continue

            # 构造函数：ClassName(params) {
            m_ctor = re.match(rf'^{class_name}\s*\(([^)]*)\)\s*\{{?', s)
            if m_ctor:
                params_str = m_ctor.group(1).strip()
                depth = 0
                ctor_lines = []
                j = i
                while j < len(body_lines):
                    depth += body_lines[j].count("{") - body_lines[j].count("}")
                    ctor_lines.append(body_lines[j])
                    j += 1
                    if depth == 0 and len(ctor_lines) > 1:
                        break
                info["ctor"] = {
                    "params_str": params_str,
                    "lines": ctor_lines,
                    "body_start": file_offset + i,
                }
                i = j
                continue

            # 析构函数：~ClassName() {
            m_dtor = re.match(rf'^~{class_name}\s*\(\s*\)\s*\{{?', s)
            if m_dtor:
                depth = 0
                dtor_lines = []
                j = i
                while j < len(body_lines):
                    depth += body_lines[j].count("{") - body_lines[j].count("}")
                    dtor_lines.append(body_lines[j])
                    j += 1
                    if depth == 0 and len(dtor_lines) > 1:
                        break
                info["dtor"] = {
                    "lines": dtor_lines,
                    "body_start": file_offset + i,
                }
                i = j
                continue

            # 成员方法：ret_type method_name(params) { ... }
            m_method = re.match(
                r'^\s*((?:\w[\w\s]*?)(?:\s*<[^>]*>)?(?:\s*\*)?)\s+(\w+)\s*\(([^)]*)\)\s*\{?\s*$',
                s
            )
            if m_method:
                mret  = m_method.group(1).strip()
                mname = m_method.group(2).strip()
                # 排除构造/析构函数（已在上面处理）、关键字
                if mname not in (class_name, f"~{class_name}") \
                        and mret not in ("if", "while", "for", "else"):
                    # 收集方法体
                    depth = 0
                    method_lines = []
                    j = i
                    while j < len(body_lines):
                        depth += body_lines[j].count("{") - body_lines[j].count("}")
                        method_lines.append(body_lines[j])
                        j += 1
                        if depth == 0 and len(method_lines) > 1:
                            break
                    info["methods"][mname] = {
                        "ret_type":   mret,
                        "params_str": m_method.group(3).strip(),
                        "lines":      method_lines,
                        "body_start": file_offset + i,
                    }
                    i = j
                    continue

            # 成员变量声明（非函数）：type name;
            m_member = re.match(
                r'^(?:int|float|double|char|bool|long|short)\s+(\w+)\s*;', s
            )
            if m_member:
                parts = s.rstrip(";").split()
                if len(parts) >= 2:
                    info["members"].append((parts[0], parts[1]))
                i += 1
                continue

            i += 1

    # ── 执行引擎 ──────────────────────────────

    def _snapshot(self, line_index: int, description: str,
                  highlight_vars=None,
                  crash: "CrashInfo | None" = None) -> "ExecutionStep":
        """生成当前状态快照"""
        import copy
        # 提取 objects 的 padding/layout 信息（轻量拷贝，不含 Variable 对象）
        obj_snap = {
            name: {
                "base_addr":  obj.get("base_addr", 0),
                "total_size": obj.get("total_size", 0),
                "cls_name":   obj.get("class_name", name),
                "padding":    list(obj.get("padding") or []),
            }
            for name, obj in self._objects.items()
        }
        step = ExecutionStep(
            line_index=line_index,
            description=description,
            stack_frames=copy.deepcopy(self._call_stack),
            heap=copy.deepcopy(self._heap),
            globals=copy.deepcopy(self._globals),
            output=self._output,
            highlight_vars=highlight_vars or [],
            objects=obj_snap,
            literals=dict(self._literals),   # 常量区：整个执行过程不变
            crash=crash,
        )
        self.steps.append(step)
        return step

    def _current_frame(self) -> Optional[StackFrame]:
        return self._call_stack[-1] if self._call_stack else None

    def _lookup_var(self, name: str) -> Optional[Variable]:
        """从当前帧到全局依次查找变量"""
        for frame in reversed(self._call_stack):
            if name in frame.variables:
                return frame.variables[name]
        if name in self._globals:
            return self._globals[name]
        return None

    def _set_var(self, name: str, value):
        """修改变量值"""
        for frame in reversed(self._call_stack):
            if name in frame.variables:
                frame.variables[name].value = value
                return
        if name in self._globals:
            self._globals[name].value = value

    def _lookup_var_by_address(self, address: int) -> Optional[Variable]:
        """按模拟地址查找当前仍存活的栈或全局变量。"""
        for frame in reversed(self._call_stack):
            for var in frame.variables.values():
                if var.address == address:
                    return var
        for var in self._globals.values():
            if var.address == address:
                return var
        return None

    def _execute_lines(self, lines: list[str], scope: str = "global",
                       line_offset: int = 0, local_frame: StackFrame = None):
        """
        逐行解析执行。
        line_offset: 该段代码在原始文件中的起始行号（用于高亮）
        """
        i = 0
        while i < len(lines):
            if self._crashed:
                break
            raw = lines[i]
            stripped = raw.strip()
            real_line = line_offset + i

            # 跳过空行、纯注释、预处理指令、纯括号
            if (not stripped or stripped.startswith("//")
                    or stripped.startswith("#")
                    or stripped in ("{", "}")):
                i += 1
                continue

            # ── 函数定义（在 global 执行时跳过函数体）
            if scope == "global":
                m_func = re.match(
                    r'^\s*(\w[\w\s\*]*?)\s+(\w+)\s*\(([^)]*)\)\s*\{?\s*$', stripped
                )
                if m_func:
                    fname = m_func.group(2).strip()
                    if fname not in ("if", "while", "for") and fname in self._functions:
                        # 跳过整个函数体
                        depth = 0
                        while i < len(lines):
                            depth += lines[i].count("{") - lines[i].count("}")
                            i += 1
                            if depth == 0:
                                break
                        continue

                # 跳过 class 定义体
                m_cls = re.match(r'^class\s+(\w+)', stripped)
                if m_cls and m_cls.group(1) in self._classes:
                    depth = 0
                    while i < len(lines):
                        depth += lines[i].count("{") - lines[i].count("}")
                        i += 1
                        if depth == 0:
                            break
                    continue

            # ── main 函数入口（已由 build_steps 统一调用，此处跳过）
            if re.match(r'^\s*int\s+main\s*\(', stripped):
                i += 1
                continue

            # ── return 语句
            if stripped.startswith("return"):
                val_str = re.sub(r'^return\s*', '', stripped).rstrip(";").strip()
                val = self._eval_expr(val_str) if val_str else None
                self._snapshot(real_line, f"return {val_str}  →  值={val}")
                # 析构本帧所有对象（逆序）
                if self._call_stack:
                    for obj_name in reversed(self._call_stack[-1].objects[:]):
                        self._destroy_object(obj_name, real_line)
                    self._call_stack.pop()
                i += 1
                continue

            # ── cout 输出（先替换 obj.member 再解析）
            if "cout" in stripped:
                output = self._parse_cout(stripped)
                self._output += output
                self._snapshot(real_line, f"输出: {repr(output)}")
                i += 1
                continue

            # ── 对象声明：ClassName obj(args);  或  ClassName obj;
            m_obj = re.match(
                r'^(\w+)\s+(\w+)\s*(?:\(([^)]*)\))?\s*;?$', stripped
            )
            if m_obj:
                cls_name  = m_obj.group(1)
                obj_name  = m_obj.group(2)
                args_str  = (m_obj.group(3) or "").strip()
                if cls_name in self._classes:
                    self._instantiate_object(cls_name, obj_name, args_str, real_line)
                    i += 1
                    continue

            # ── obj.member = value
            m_dot_assign = re.match(r'^(\w+)\.(\w+)\s*=\s*(.+);?$', stripped)
            if m_dot_assign:
                obj_n, mem_n, rhs_str = m_dot_assign.groups()
                rhs = self._eval_expr(rhs_str.rstrip(";"))
                if obj_n in self._objects:
                    mems = self._objects[obj_n]["members"]
                    if mem_n in mems:
                        old = mems[mem_n].value
                        mems[mem_n].value = rhs
                        # 同步栈帧里的 variable（按 obj_name.member 存储）
                        self._sync_obj_to_frame(obj_n)
                        self._snapshot(real_line,
                                       f"{obj_n}.{mem_n} = {rhs}  (旧值: {old})",
                                       highlight_vars=[f"{obj_n}.{mem_n}"])
                i += 1
                continue

            # ── 变量声明（含初始化）—— 先检测是否是 new 声明
            decl = self._try_parse_declaration(stripped)
            if decl:
                ctype, name, init_str_raw = decl
                # 检测 new 表达式
                m_new_init = re.match(
                    r'^new\s+(\w+)(\[\s*(\d+)\s*\])?$',
                    (init_str_raw or "").strip()
                )
                if m_new_init:
                    # 先创建指针变量
                    ptr_size = 8
                    if not self._call_stack:
                        addr = self._allocator.alloc_global(ptr_size)
                        region = MemoryRegion.DATA   # new 初始化，归 DATA
                        store = self._globals
                    else:
                        addr = self._allocator.alloc_stack(ptr_size)
                        region = MemoryRegion.STACK
                        store = self._current_frame().variables
                    alloc_type = m_new_init.group(1)
                    arr_size = int(m_new_init.group(3)) if m_new_init.group(3) else 1
                    elem_size  = get_type_size(alloc_type)
                    total_size = elem_size * arr_size
                    heap_addr = self._allocator.alloc_heap(total_size)
                    hvar = self._make_var(f"*{name}", alloc_type, 0,
                                         heap_addr, MemoryRegion.HEAP, total_size)
                    hvar.stride = elem_size   # stride = 单元素大小，ByteCells 用此计算格数
                    self._heap[heap_addr] = hvar
                    var = self._make_var(name, ctype, heap_addr,
                                        addr, region, ptr_size, is_pointer=True)
                    store[name] = var
                    desc = (f"声明 {ctype} {name} = new {alloc_type}"
                            + (f"[{arr_size}]" if arr_size > 1 else "")
                            + f"  指针@{hex(addr)} → 堆@{hex(heap_addr)}")
                    self._snapshot(real_line, desc, highlight_vars=[name])
                    i += 1
                    continue

                size = 8 if is_pointer_type(ctype) else get_type_size(ctype)
                if scope == "global" or not self._call_stack:
                    addr = self._allocator.alloc_global(size)
                    # 详细模式区分：有初始值 → DATA，无初始值 → BSS
                    region = MemoryRegion.DATA if init_str_raw else MemoryRegion.BSS
                    # 同时保留 GLOBAL 兼容标记（UI 层按需取用）
                    store = self._globals
                else:
                    addr = self._allocator.alloc_stack(size)
                    region = MemoryRegion.STACK
                    store = self._current_frame().variables

                # auto 类型：求值后存为普通变量
                if ctype == "auto":
                    init_val = self._eval_expr(init_str_raw, real_line) if init_str_raw else None
                    # 使用 "auto" 作为类型名，size 固定 8（保守）
                    addr_auto = self._allocator.alloc_stack(8)
                    region_auto = MemoryRegion.STACK
                    if scope == "global" or not self._call_stack:
                        addr_auto = self._allocator.alloc_global(8)
                        region_auto = MemoryRegion.DATA if init_str_raw else MemoryRegion.BSS
                        store = self._globals
                    else:
                        store = self._current_frame().variables
                    var = self._make_var(name, "auto", init_val,
                                        addr_auto, region_auto, 8)
                    store[name] = var
                    self._snapshot(real_line,
                                   f"auto {name} = {init_val}",
                                   highlight_vars=[name])
                    i += 1
                    continue

                # STL 容器类型：创建 ContainerVariable
                if _is_container_type(ctype):
                    var = self._make_container_var(name, ctype, addr, region)
                    # 处理花括号初始化：vector<int> v = {1,2,3}
                    if init_str_raw:
                        self._init_container_from_str(var, init_str_raw.strip())
                    store[name] = var
                    desc = (f"声明 {ctype} {name}  "
                            f"[地址: {hex(addr)}, 大小: {var.size}B]")
                    self._snapshot(real_line, desc, highlight_vars=[name])
                    i += 1
                    continue

                init_val = self._eval_expr(init_str_raw, real_line) if init_str_raw else None
                var = self._make_var(name, ctype, init_val,
                                     addr, region, size,
                                     is_pointer=is_pointer_type(ctype))
                store[name] = var
                desc = (f"声明 {ctype} {name}"
                        + (f" = {init_val}" if init_val is not None else " (未初始化)")
                        + f"  [地址: {hex(addr)}, 大小: {size}B, 区域: {region.value}]")
                self._snapshot(real_line, desc, highlight_vars=[name])
                i += 1
                continue

            # ── 容器下标赋值：varname[key] = value
            m_subscript_assign = re.match(r'^(\w+)\[(.+)\]\s*=\s*(.+?)\s*;?$', stripped)
            if m_subscript_assign:
                cname = m_subscript_assign.group(1)
                key_str = m_subscript_assign.group(2).strip()
                val_str = m_subscript_assign.group(3).strip()
                cvar = self._lookup_var(cname)
                if isinstance(cvar, ContainerVariable) and self._method_dispatcher:
                    key = self._eval_expr(key_str)
                    val = self._eval_expr(val_str)
                    from .stl_containers import STLMethodHandler
                    stl = STLMethodHandler(self)
                    # 更新容器字典值
                    if cvar.container_kind == "unordered_map":
                        d = cvar.value if cvar.value is not None else {}
                        d[key] = val
                        cvar.value = d
                        self._snapshot(real_line,
                                       f"{cname}[{key}] = {val}  →  size={len(d)}",
                                       highlight_vars=[cname])
                    elif cvar.container_kind == "vector":
                        data = cvar.value or []
                        if 0 <= int(key) < len(data):
                            data[int(key)] = val
                            cvar.value = data
                            stl._sync_vector_heap(cvar)
                            self._snapshot(real_line,
                                           f"{cname}[{key}] = {val}",
                                           highlight_vars=[cname])
                    i += 1
                    continue

            # ── 赋值语句（含复合赋值）
            assign = self._try_parse_assignment(stripped)
            if assign:
                name, op, rhs_str = assign
                rhs = self._eval_expr(rhs_str)
                var = self._lookup_var(name)
                if var:
                    old = var.value
                    if op == "=":
                        new_val = rhs
                    elif op == "+=": new_val = (old or 0) + rhs
                    elif op == "-=": new_val = (old or 0) - rhs
                    elif op == "*=": new_val = (old or 0) * rhs
                    elif op == "/=": new_val = (old or 1) / rhs
                    else: new_val = rhs
                    self._set_var(name, new_val)
                    self._snapshot(real_line,
                                   f"{name} {op} {rhs_str}  →  {name} = {new_val}  (旧值: {old})",
                                   highlight_vars=[name])
                i += 1
                continue

            # ── ++/-- 自增自减
            if re.match(r'^\w+\s*(\+\+|--)\s*;', stripped) or re.match(r'^(\+\+|--)\s*\w+\s*;', stripped):
                m = re.match(r'^(\w+)\s*(\+\+|--)', stripped) or re.match(r'^(\+\+|--)\s*(\w+)', stripped)
                if m:
                    groups = m.groups()
                    if groups[0] in ("++", "--"):
                        op, name = groups[0], groups[1]
                    else:
                        name, op = groups[0], groups[1]
                    var = self._lookup_var(name)
                    if var:
                        old = var.value or 0
                        new_val = old + (1 if op == "++" else -1)
                        self._set_var(name, new_val)
                        self._snapshot(real_line,
                                       f"{name}{op}  →  {name} = {new_val}  (旧值: {old})",
                                       highlight_vars=[name])
                i += 1
                continue

            # ── new（堆内存分配）—— 单独赋值形式 ptr = new T
            m_new = re.match(r'^(\w+)\s*=\s*new\s+(\w+)(\[\s*(\d+)\s*\])?', stripped)
            if m_new:
                ptr_name = m_new.group(1)
                alloc_type = m_new.group(2)
                arr_size = int(m_new.group(4)) if m_new.group(4) else 1
                elem_size  = get_type_size(alloc_type)
                total_size = elem_size * arr_size
                heap_addr = self._allocator.alloc_heap(total_size)
                hvar = self._make_var(f"*{ptr_name}", alloc_type, 0,
                                     heap_addr, MemoryRegion.HEAP, total_size)
                hvar.stride = elem_size   # stride = 单元素大小
                self._heap[heap_addr] = hvar
                self._set_var(ptr_name, heap_addr)
                self._snapshot(real_line,
                               f"new {alloc_type}[{arr_size}] → 堆地址 {hex(heap_addr)}, {total_size}B",
                               highlight_vars=[ptr_name])
                i += 1
                continue

            # ── delete
            m_del = re.match(r'delete\s*(\[\])?\s*(\w+)', stripped)
            if m_del:
                ptr_name = m_del.group(2)
                var = self._lookup_var(ptr_name)

                if var and var.is_pointer:
                    ptr_val = var.value
                    is_arr  = bool(m_del.group(1))

                    # ── 崩溃检测：野指针（从未初始化或指向非堆）
                    if ptr_val is None:
                        crash = CrashInfo(
                            ub_type="wild_ptr",
                            title="野指针崩溃  (Wild Pointer)",
                            cause=f"delete {ptr_name}：指针从未被初始化，值不确定",
                            detail=(
                                "此指针从未被 new 赋值，内部存的是'垃圾地址'。\n"
                                "对随机地址调用 delete，操作系统无法识别该内存块，\n"
                                "导致堆管理结构损坏，程序立即崩溃（Segmentation Fault）。\n\n"
                                "修复：使用前务必初始化指针，如\n"
                                "  int* p = nullptr;  或  int* p = new int;"
                            ),
                            ptr_name=ptr_name,
                            ptr_value=ptr_val,
                        )
                        self._snapshot(real_line,
                                       f"CRASH: delete {ptr_name} — 野指针，值未定义",
                                       highlight_vars=[ptr_name], crash=crash)
                        self._crashed = True
                        break

                    # ── 崩溃检测：double free（地址已被释放过）
                    if ptr_val in self._freed_addrs:
                        crash = CrashInfo(
                            ub_type="double_free",
                            title="二次释放崩溃  (Double Free)",
                            cause=f"delete {ptr_name}：该地址 {hex(ptr_val)} 已经被 delete 过一次",
                            detail=(
                                f"指针 {ptr_name} 指向的地址 {hex(ptr_val)} 在之前已经释放。\n"
                                "二次 delete 同一地址会破坏堆的元数据链表，\n"
                                "导致程序崩溃，或在某些平台上引发安全漏洞（CVE 级别）。\n\n"
                                "修复：delete 后立即将指针置为 nullptr：\n"
                                f"  delete {ptr_name};  {ptr_name} = nullptr;\n"
                                "再次 delete nullptr 是安全的（无操作）。"
                            ),
                            ptr_name=ptr_name,
                            ptr_value=ptr_val,
                        )
                        self._snapshot(real_line,
                                       f"CRASH: delete {ptr_name} — double free @ {hex(ptr_val)}",
                                       highlight_vars=[ptr_name], crash=crash)
                        self._crashed = True
                        break

                    # ── 崩溃检测：指针指向非堆区域（野指针/错误地址）
                    if ptr_val != 0 and ptr_val not in self._heap:
                        crash = CrashInfo(
                            ub_type="wild_ptr",
                            title="野指针崩溃  (Wild Pointer)",
                            cause=f"delete {ptr_name}：指针值 {hex(ptr_val)} 不是有效的堆地址",
                            detail=(
                                f"指针 {ptr_name} 的值 {hex(ptr_val)} 并不来自 new，\n"
                                "可能指向栈变量、全局变量或随机地址。\n"
                                "delete 非堆内存是未定义行为，通常立即崩溃。\n\n"
                                "修复：只对 new 返回的地址调用 delete。"
                            ),
                            ptr_name=ptr_name,
                            ptr_value=ptr_val,
                        )
                        self._snapshot(real_line,
                                       f"CRASH: delete {ptr_name} — 地址 {hex(ptr_val)} 非堆",
                                       highlight_vars=[ptr_name], crash=crash)
                        self._crashed = True
                        break

                    # ── 正常 delete
                    if ptr_val in self._heap:
                        self._freed_addrs.add(ptr_val)    # 记录已释放地址
                        del self._heap[ptr_val]
                        # 保留原地址值（悬空指针状态），便于教学展示
                        # 在显示层 display_value 会仍然显示旧地址
                        self._snapshot(real_line,
                                       f"delete{'[]' if is_arr else ''} {ptr_name} "
                                       f"→ 释放堆内存 {hex(ptr_val)}，{ptr_name} 变为悬空指针",
                                       highlight_vars=[ptr_name])
                    elif ptr_val == 0:
                        # delete nullptr 是合法的无操作
                        self._snapshot(real_line,
                                       f"delete nullptr（合法无操作，无内存释放）",
                                       highlight_vars=[ptr_name])
                i += 1
                continue

            # ── *ptr = value（解引用赋值，含空指针/悬空指针检测）
            m_deref_assign = re.match(r'^\*(\w+)\s*=\s*(.+?)\s*;?\s*$', stripped)
            if m_deref_assign:
                ptr_name = m_deref_assign.group(1)
                rhs_str  = m_deref_assign.group(2).rstrip(";")
                var = self._lookup_var(ptr_name)

                if var and var.is_pointer:
                    ptr_val = var.value

                    # ── 空指针解引用崩溃
                    if ptr_val == 0 or ptr_val is None:
                        crash = CrashInfo(
                            ub_type="null_deref",
                            title="空指针解引用  (Null Pointer Dereference)",
                            cause=f"*{ptr_name}：指针为 nullptr（地址 0），无法写入",
                            detail=(
                                f"指针 {ptr_name} 的值为 nullptr（0x0）。\n"
                                "地址 0 是操作系统保留的'零页'，任何读写都会触发\n"
                                "Segmentation Fault（段错误），程序立即终止。\n\n"
                                "修复：在解引用前检查指针是否为 nullptr：\n"
                                f"  if ({ptr_name} != nullptr) {{ *{ptr_name} = ...; }}"
                            ),
                            ptr_name=ptr_name,
                            ptr_value=ptr_val,
                        )
                        self._snapshot(real_line,
                                       f"CRASH: *{ptr_name} — 空指针解引用（nullptr）",
                                       highlight_vars=[ptr_name], crash=crash)
                        self._crashed = True
                        i += 1
                        continue

                    # ── use-after-free 崩溃
                    if ptr_val in self._freed_addrs:
                        crash = CrashInfo(
                            ub_type="use_after_free",
                            title="释放后使用  (Use After Free)",
                            cause=f"*{ptr_name}：地址 {hex(ptr_val)} 已被 delete，内存已归还堆",
                            detail=(
                                f"指针 {ptr_name} 指向的地址 {hex(ptr_val)} 已经被 delete 释放。\n"
                                "该内存可能已被重新分配给其他变量，写入会产生数据污染，\n"
                                "或者触发堆保护机制导致程序崩溃。\n"
                                "这是常见的高危安全漏洞（CWE-416）。\n\n"
                                "修复：delete 后立即将指针置为 nullptr。"
                            ),
                            ptr_name=ptr_name,
                            ptr_value=ptr_val,
                        )
                        self._snapshot(real_line,
                                       f"CRASH: *{ptr_name} — use-after-free @ {hex(ptr_val)}",
                                       highlight_vars=[ptr_name], crash=crash)
                        self._crashed = True
                        i += 1
                        continue

                    # ── 正常解引用写入
                    rhs = self._eval_expr(rhs_str)
                    target = self._heap.get(ptr_val)
                    target_region = "堆"
                    if target is None:
                        target = self._lookup_var_by_address(ptr_val)
                        target_region = "栈" if target and target.region == MemoryRegion.STACK else "全局区"
                    if target is not None:
                        target.value = rhs
                        self._snapshot(real_line,
                                       f"*{ptr_name} = {rhs}  ({target_region}@{hex(ptr_val)})",
                                       highlight_vars=[ptr_name, target.name])
                i += 1
                continue

            # ── if / else if / else
            m_if = re.match(r'^(else\s+)?if\s*\((.+)\)\s*\{?\s*$', stripped)
            if m_if or stripped == "else{" or stripped == "else {" or re.match(r'^else\s*\{?\s*$', stripped):
                cond_str = m_if.group(2).strip() if m_if and m_if.group(2) else "true"
                cond_val = bool(self._eval_expr(cond_str)) if cond_str != "true" else True
                self._snapshot(real_line,
                               f"if ({cond_str})  →  条件为 {'真' if cond_val else '假'}")
                # 收集 if 块
                block_lines, after = self._collect_block(lines, i)
                if cond_val:
                    self._execute_lines(block_lines, scope, line_offset + i + 1, local_frame)
                i = after
                continue

            # ── for 循环
            m_for = re.match(r'^for\s*\((.+?);(.+?);(.+?)\)\s*\{?\s*$', stripped)
            if m_for:
                init_s  = m_for.group(1).strip()
                cond_s  = m_for.group(2).strip()
                incr_s  = m_for.group(3).strip()
                block_lines, after = self._collect_block(lines, i)
                # 执行 init
                self._execute_lines([init_s + ";"], scope, real_line, local_frame)
                iteration = 0
                MAX_ITER = 200
                while True:
                    cond_val = bool(self._eval_expr(cond_s))
                    self._snapshot(real_line,
                                   f"for 循环 第{iteration+1}次 条件 ({cond_s}) = {'真' if cond_val else '假'}")
                    if not cond_val or iteration >= MAX_ITER:
                        break
                    self._execute_lines(block_lines, scope, line_offset + i + 1, local_frame)
                    self._execute_lines([incr_s + ";"], scope, real_line, local_frame)
                    iteration += 1
                i = after
                continue

            # ── while 循环
            m_while = re.match(r'^while\s*\((.+)\)\s*\{?\s*$', stripped)
            if m_while:
                cond_s = m_while.group(1).strip()
                block_lines, after = self._collect_block(lines, i)
                iteration = 0
                MAX_ITER = 200
                while True:
                    cond_val = bool(self._eval_expr(cond_s))
                    self._snapshot(real_line,
                                   f"while ({cond_s}) = {'真' if cond_val else '假'}")
                    if not cond_val or iteration >= MAX_ITER:
                        break
                    self._execute_lines(block_lines, scope, line_offset + i + 1, local_frame)
                    iteration += 1
                i = after
                continue

            # ── 成员方法调用语句：obj.method(args);
            m_method_stmt = re.match(r'^(\w+)\.(\w+)\s*\(([^)]*)\)\s*;?$', stripped)
            if m_method_stmt:
                if self._method_dispatcher:
                    self._method_dispatcher.dispatch(
                        m_method_stmt.group(1),
                        m_method_stmt.group(2),
                        m_method_stmt.group(3).strip(),
                        real_line
                    )
                i += 1
                continue

            # ── 函数调用语句（非赋值）
            m_call = re.match(r'^(\w+)\s*\(([^)]*)\)\s*;', stripped)
            if m_call:
                fname = m_call.group(1)
                args_str = m_call.group(2)
                if fname in self._functions:
                    self._call_function(fname, args_str, real_line)
                i += 1
                continue

            i += 1

    def _collect_block(self, lines, start_i):
        """从 start_i 行收集到匹配的 } ，返回(块内容行列表, 下一行索引)"""
        i = start_i
        depth = 0
        block = []
        first = True
        while i < len(lines):
            line = lines[i]
            opens  = line.count("{")
            closes = line.count("}")
            if first:
                depth += opens - closes
                first = False
                if depth <= 0:  # 单行 if
                    i += 1
                    return block, i
                i += 1
                continue
            depth += opens - closes
            if depth <= 0:
                i += 1
                break
            block.append(line)
            i += 1
        return block, i

    def _call_function(self, fname: str, args_str: str, call_line: int):
        """执行一次函数调用"""
        finfo = self._functions.get(fname)
        if not finfo:
            return

        frame = StackFrame(fname, return_line=call_line)
        self._call_stack.append(frame)

        # 绑定参数
        param_decls = [p.strip() for p in finfo["params_str"].split(",") if p.strip()]
        arg_vals    = [a.strip() for a in args_str.split(",") if a.strip()]
        highlight = []
        for pdecl, aval_str in zip(param_decls, arg_vals):
            parts = pdecl.split()
            if len(parts) >= 2:
                ptype = " ".join(parts[:-1])
                pname = parts[-1].lstrip("*&")
                pval  = self._eval_expr(aval_str)
                addr  = self._allocator.alloc_stack(get_type_size(ptype))
                frame.variables[pname] = self._make_var(
                    pname, ptype, pval, addr, MemoryRegion.STACK,
                    get_type_size(ptype)
                )
                highlight.append(pname)

        self._snapshot(call_line,
                       f"调用 {fname}({args_str})，创建栈帧，绑定参数",
                       highlight_vars=highlight)

        # 执行函数体（跳过第一行定义行）
        body_lines = finfo["lines"][1:]
        self._execute_lines(body_lines, "function",
                            finfo["body_start"] + 1, frame)

        # 析构本帧所有对象（逆序，后创建先析构）
        if self._call_stack and self._call_stack[-1].function_name == fname:
            for obj_name in reversed(self._call_stack[-1].objects):
                self._destroy_object(obj_name, finfo["body_start"])
            self._call_stack.pop()
        self._snapshot(call_line, f"{fname}() 执行完毕，栈帧弹出")

    # ── 表达式求值 ────────────────────────────

    def _eval_expr(self, expr: str, call_line: Optional[int] = None) -> Any:
        """求值简单表达式，替换变量后用 eval。"""
        if expr is None or expr.strip() == "":
            return None
        expr = expr.strip().rstrip(";")

        # 取地址：&varname → 返回该变量的模拟地址
        m_addr = re.match(r'^&(\w+)$', expr)
        if m_addr:
            v = self._lookup_var(m_addr.group(1))
            return v.address if v else 0

        # 解引用读取：*varname → 返回指针指向的值
        m_deref = re.match(r'^\*(\w+)$', expr)
        if m_deref:
            v = self._lookup_var(m_deref.group(1))
            if v:
                target = self._heap.get(v.value)
                if target is None:
                    target = self._lookup_var_by_address(v.value)
                if target is not None:
                    return target.value
            return 0

        # 字符串字面量
        m_str = re.match(r'^"(.*)"$', expr)
        if m_str:
            return m_str.group(1)

        # 字符字面量
        m_char = re.match(r"^'(.)'$", expr)
        if m_char:
            return ord(m_char.group(1))

        # bool
        if expr == "true":  return True
        if expr == "false": return False
        if expr == "nullptr": return None

        # 成员方法调用：obj.method(args)（赋值右侧求值形式）
        m_dot_call = re.match(r'^(\w+)\.(\w+)\s*\(([^)]*)\)$', expr)
        if m_dot_call:
            if self._method_dispatcher:
                return self._method_dispatcher.dispatch_eval(
                    m_dot_call.group(1),
                    m_dot_call.group(2),
                    m_dot_call.group(3).strip()
                )

        # 下标操作符：varname[expr]
        m_subscript = re.match(r'^(\w+)\[(.+)\]$', expr)
        if m_subscript:
            vname = m_subscript.group(1)
            idx_expr = m_subscript.group(2).strip()
            idx = self._eval_expr(idx_expr)
            var = self._lookup_var(vname)
            if isinstance(var, ContainerVariable) and self._method_dispatcher:
                return self._method_dispatcher.dispatch_eval(
                    vname, "operator_bracket", str(idx)
                )
            # 普通指针数组下标（原有逻辑）
            if var and var.is_pointer and var.value in self._heap:
                hvar = self._heap[var.value]
                if isinstance(hvar.value, list):
                    try:
                        return hvar.value[int(idx)]
                    except (IndexError, TypeError):
                        return 0

        # 内联函数调用（用于赋值右值，如 multiply(4, 5)）
        m_call = re.match(r'^(\w+)\s*\(([^)]*)\)$', expr)
        if m_call:
            fname = m_call.group(1)
            args_str = m_call.group(2).strip()
            if fname in self._functions:
                return self._eval_function_call(fname, args_str, call_line)

        # 替换变量为其当前值（含 obj.member 形式）
        def replace_var(m):
            vname = m.group(0)
            # obj.member 由外层正则已拆分，这里处理普通变量名
            v = self._lookup_var(vname)
            if v is not None and v.value is not None:
                return str(v.value)
            return vname

        # 先替换 obj.member → 值
        def replace_dot(m):
            obj_n, mem_n = m.group(1), m.group(2)
            # 检查是否是 ContainerVariable 的属性访问（不是方法调用）
            var = self._lookup_var(obj_n)
            if isinstance(var, ContainerVariable):
                # 支持 .size / .empty 等无括号属性（不常见，防御性处理）
                return m.group(0)   # 留给后续 eval 处理
            obj_info = self._objects.get(obj_n, {})
            mems = obj_info.get("members", {})
            if mem_n in mems and mems[mem_n].value is not None:
                return str(mems[mem_n].value)
            return m.group(0)

        # 先替换表达式中内嵌的 obj.method() 调用（如 it != hashtable.end()）
        def replace_method_call(m):
            obj_n  = m.group(1)
            meth_n = m.group(2)
            args_s = m.group(3).strip()
            if self._method_dispatcher:
                val = self._method_dispatcher.dispatch_eval(obj_n, meth_n, args_s)
                if val is None:
                    return "None"
                return str(val)
            return m.group(0)

        expr = re.sub(r'\b(\w+)\.(\w+)\s*\(([^)]*)\)', replace_method_call, expr)

        subst = re.sub(r'\b(\w+)\.(\w+)\b', replace_dot, expr)
        subst = re.sub(r'\b[a-zA-Z_]\w*\b', replace_var, subst)

        # 替换 C++ 逻辑运算符（!= 必须先保护，防止 ! 被替换破坏 !=）
        subst = subst.replace("!=", "___NEQ___")
        subst = subst.replace("&&", " and ").replace("||", " or ")
        # 单独的 ! 替换为 not（仅在非 = 之前的情况）
        subst = re.sub(r'!(?!=)', " not ", subst)
        subst = subst.replace("___NEQ___", "!=")

        try:
            result = eval(subst, {"__builtins__": {}, "None": None, "True": True, "False": False})
            return result
        except Exception as e:
            print(f"[EVAL ERROR] expr={expr!r}  subst={subst!r}  {type(e).__name__}: {e}")
            return 0

    def _eval_function_call(self, fname: str, args_str: str,
                            call_line: Optional[int] = None) -> Any:
        """
        求值一个函数调用，记录步骤，返回返回值。
        用于赋值右侧的函数调用（如 int r = add(x, y)）。
        """
        finfo = self._functions.get(fname)
        if not finfo:
            return 0

        # 实参必须在调用者作用域中完成求值，再压入被调用者栈帧。
        arg_strs = [a.strip() for a in args_str.split(",") if a.strip()]
        arg_vals = [self._eval_expr(arg, call_line) for arg in arg_strs]
        snapshot_line = call_line if call_line is not None else finfo["body_start"]
        frame = StackFrame(fname, return_line=snapshot_line)
        self._call_stack.append(frame)

        # 绑定参数
        param_decls = [p.strip() for p in finfo["params_str"].split(",") if p.strip()]
        highlight = []
        for pdecl, pval in zip(param_decls, arg_vals):
            parts = pdecl.split()
            if len(parts) >= 2:
                ptype = " ".join(parts[:-1])
                pname = parts[-1].lstrip("*&")
                addr  = self._allocator.alloc_stack(get_type_size(ptype))
                frame.variables[pname] = self._make_var(
                    pname, ptype, pval, addr, MemoryRegion.STACK,
                    get_type_size(ptype)
                )
                highlight.append(pname)

        self._snapshot(snapshot_line,
                       f"调用 {fname}({args_str})，创建栈帧，绑定参数",
                       highlight_vars=highlight)

        return_val = self._execute_function_body(finfo)

        if self._call_stack and self._call_stack[-1] is frame:
            for obj_name in reversed(frame.objects):
                self._destroy_object(obj_name, snapshot_line)
            self._call_stack.pop()
        self._snapshot(snapshot_line,
                       f"{fname}() 执行完毕，栈帧弹出，返回值={return_val}")
        return return_val

    def _execute_function_body(self, finfo: dict, line_offset: int = None) -> Any:
        """执行需要返回值的函数体，并返回 return 语句的值。"""
        lines = finfo["lines"][1:]  # 跳过函数定义行
        returned, return_val = self._execute_function_block(
            lines, finfo["body_start"] + 1
        )
        return return_val if returned else 0

    def _execute_function_block(self, lines: list[str], line_offset: int) -> tuple[bool, Any]:
        """执行函数内的代码块，并把 return 状态传播到整个当前函数。"""
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            real_line = line_offset + i

            if not stripped or stripped.startswith("//") or stripped in ("{", "}"):
                i += 1
                continue

            m_if = re.match(r'^if\s*\((.+)\)\s*\{?\s*$', stripped)
            if m_if:
                cond_str = m_if.group(1).strip()
                cond_val = bool(self._eval_expr(cond_str, real_line))
                self._snapshot(real_line,
                               f"if ({cond_str})  →  条件为 {'真' if cond_val else '假'}")
                block_lines, after = self._collect_block(lines, i)
                if cond_val:
                    returned, return_val = self._execute_function_block(
                        block_lines, real_line + 1
                    )
                    if returned:
                        return True, return_val
                i = after
                continue

            if stripped.startswith("return"):
                val_str = re.sub(r'^return\s*', '', stripped).rstrip(";").strip()
                return_val = self._eval_expr(val_str, real_line) if val_str else 0
                self._snapshot(real_line, f"return {val_str}  →  值={return_val}")
                return True, return_val

            if "cout" in stripped:
                output = self._parse_cout(stripped)
                self._output += output
                self._snapshot(real_line, f"输出: {repr(output)}")
                i += 1
                continue

            decl = self._try_parse_declaration(stripped)
            if decl:
                ctype, name, init_str_raw = decl
                size = get_type_size(ctype)
                init_val = self._eval_expr(init_str_raw, real_line) if init_str_raw else None
                addr = self._allocator.alloc_stack(size)
                var = self._make_var(name, ctype, init_val,
                                     addr, MemoryRegion.STACK, size)
                if self._call_stack:
                    self._call_stack[-1].variables[name] = var
                desc = (f"声明 {ctype} {name}"
                        + (f" = {init_val}" if init_val is not None else " (未初始化)")
                        + f"  [地址: {hex(addr)}, 大小: {size}B]")
                self._snapshot(real_line, desc, highlight_vars=[name])
                i += 1
                continue

            assign = self._try_parse_assignment(stripped)
            if assign:
                name, op, rhs_str = assign
                rhs = self._eval_expr(rhs_str, real_line)
                var = self._lookup_var(name)
                if var:
                    old = var.value
                    if op == "=":   new_val = rhs
                    elif op == "+=": new_val = (old or 0) + rhs
                    elif op == "-=": new_val = (old or 0) - rhs
                    elif op == "*=": new_val = (old or 0) * rhs
                    elif op == "/=": new_val = (old or 1) / rhs
                    else: new_val = rhs
                    self._set_var(name, new_val)
                    self._snapshot(real_line,
                                   f"{name} {op} {rhs_str}  →  {name} = {new_val}  (旧值: {old})",
                                   highlight_vars=[name])
                i += 1
                continue

            if re.match(r'^\w+\s*(\+\+|--)\s*;', stripped):
                m = re.match(r'^(\w+)\s*(\+\+|--)', stripped)
                if m:
                    name, op = m.group(1), m.group(2)
                    var = self._lookup_var(name)
                    if var:
                        old = var.value or 0
                        new_val = old + (1 if op == "++" else -1)
                        self._set_var(name, new_val)
                        self._snapshot(real_line, f"{name}{op}  →  {name}={new_val}",
                                       highlight_vars=[name])
                i += 1
                continue

            i += 1
        return False, 0

    # ── 对象实例化与销毁 ──────────────────────────

    @staticmethod
    def _calc_struct_layout(members: list) -> tuple:
        """
        按 C++ struct layout 规则计算每个成员的 offset 和总大小。
        members: [(type, name), ...]
        返回: ([(type, name, offset, size)], total_size)
        """
        layout = []
        offset = 0
        max_align = 1
        for mtype, mname in members:
            sz    = get_type_size(mtype)
            align = AddressAllocator._stride(sz)   # 对齐要求 = stride
            max_align = max(max_align, align)
            # 向上对齐到 align 边界
            if offset % align != 0:
                offset += align - (offset % align)  # padding
            layout.append((mtype, mname, offset, sz))
            offset += sz
        # 结构体总大小向最大对齐数取整
        if offset % max_align != 0:
            offset += max_align - (offset % max_align)
        return layout, offset

    def _instantiate_object(self, cls_name: str, obj_name: str,
                             args_str: str, line_index: int):
        """在当前栈帧创建对象，按 struct layout 分配成员地址"""
        info = self._classes[cls_name]

        # 计算 struct 内部 layout
        layout, total_size = self._calc_struct_layout(info["members"])

        # 在栈上分配整块空间（按结构体总大小，对齐到最大成员对齐数）
        max_align = max((AddressAllocator._stride(sz) for _, _, _, sz in layout), default=1)
        self._allocator._stack_ptr -= total_size
        self._allocator._stack_ptr = (self._allocator._stack_ptr
                                      & ~(max_align - 1))
        base_addr = self._allocator._stack_ptr

        members: dict[str, Variable] = {}
        highlight = []
        pad_bytes = []   # 记录 padding 位置用于描述

        prev_end = 0
        for mtype, mname, offset, sz in layout:
            pad = offset - prev_end
            if pad > 0:
                pad_bytes.append((base_addr + prev_end, pad))
            addr = base_addr + offset
            var  = self._make_var(f"{obj_name}.{mname}", mtype, None,
                                  addr, MemoryRegion.STACK, sz)
            members[mname] = var
            if self._call_stack:
                self._call_stack[-1].variables[f"{obj_name}.{mname}"] = var
            highlight.append(f"{obj_name}.{mname}")
            prev_end = offset + sz

        self._objects[obj_name] = {
            "class_name": cls_name,
            "members": members,
            "base_addr": base_addr,
            "total_size": total_size,
            "padding": pad_bytes,   # [(addr, nbytes), ...]
        }

        if self._call_stack:
            self._call_stack[-1].objects.append(obj_name)

        pad_desc = ""
        if pad_bytes:
            pads = ", ".join(f"{n}B@{hex(a)}" for a, n in pad_bytes)
            pad_desc = f"  [padding: {pads}]"
        self._snapshot(line_index,
                       f"构造 {cls_name} {obj_name}  共{total_size}B"
                       f"  基址{hex(base_addr)}{pad_desc}",
                       highlight_vars=highlight)

        # 执行构造函数体
        ctor = info.get("ctor")
        if ctor:
            self._run_ctor_dtor(obj_name, cls_name, ctor, args_str, line_index, is_ctor=True)

    def _run_ctor_dtor(self, obj_name: str, cls_name: str,
                       func_info: dict, args_str: str,
                       call_line: int, is_ctor: bool):
        """执行构造函数或析构函数体"""
        fname = cls_name if is_ctor else f"~{cls_name}"
        frame = StackFrame(f"{fname}()")
        self._call_stack.append(frame)

        # 绑定构造函数参数
        if is_ctor and args_str:
            param_decls = [p.strip() for p in func_info["params_str"].split(",") if p.strip()]
            arg_strs    = [a.strip() for a in args_str.split(",") if a.strip()]
            for pdecl, aval_str in zip(param_decls, arg_strs):
                parts = pdecl.split()
                if len(parts) >= 2:
                    ptype = parts[0]
                    pname = parts[-1].lstrip("*&")
                    pval  = self._eval_expr(aval_str)
                    addr  = self._allocator.alloc_stack(get_type_size(ptype))
                    frame.variables[pname] = self._make_var(
                        pname, ptype, pval, addr, MemoryRegion.STACK, get_type_size(ptype))

        body_lines = func_info["lines"][1:]   # 跳过函数定义行
        body_start = func_info["body_start"] + 1

        for j, raw in enumerate(body_lines):
            s = raw.strip()
            real_line = body_start + j
            if not s or s in ("{", "}") or s.startswith("//"):
                continue

            if "cout" in s:
                output = self._parse_cout_with_obj(s, obj_name)
                self._output += output
                self._snapshot(real_line, f"输出: {repr(output)}")
                continue

            # 成员赋值：member = expr  （构造函数内不带 obj. 前缀）
            m_assign = re.match(r'^(\w+)\s*=\s*(.+);?$', s)
            if m_assign:
                lhs, rhs_str = m_assign.group(1), m_assign.group(2).rstrip(";")
                obj_members = self._objects.get(obj_name, {}).get("members", {})
                if lhs in obj_members:
                    rhs = self._eval_expr_with_obj(rhs_str, obj_name, frame)
                    old = obj_members[lhs].value
                    obj_members[lhs].value = rhs
                    key = f"{obj_name}.{lhs}"
                    # 同步到所有栈帧
                    for fr in self._call_stack:
                        if key in fr.variables:
                            fr.variables[key].value = rhs
                    self._snapshot(real_line,
                                   f"{obj_name}.{lhs} = {rhs}  (旧值: {old})",
                                   highlight_vars=[key])
                elif lhs in frame.variables:
                    rhs = self._eval_expr_with_obj(rhs_str, obj_name, frame)
                    frame.variables[lhs].value = rhs
                    self._snapshot(real_line,
                                   f"{lhs} = {rhs}", highlight_vars=[lhs])

        if self._call_stack and self._call_stack[-1].function_name == f"{fname}()":
            self._call_stack.pop()
        action = "构造完毕" if is_ctor else "析构完毕"
        self._snapshot(call_line, f"{cls_name}::{fname}()  {action}，栈帧弹出")

    def _destroy_object(self, obj_name: str, line_index: int):
        """触发析构函数，清理对象"""
        if obj_name not in self._objects:
            return
        obj = self._objects[obj_name]
        cls_name = obj["class_name"]
        info = self._classes.get(cls_name, {})
        highlight = [f"{obj_name}.{m}" for m in obj["members"]]
        self._snapshot(line_index,
                       f"作用域结束，析构 {cls_name} {obj_name}",
                       highlight_vars=highlight)
        dtor = info.get("dtor")
        if dtor:
            self._run_ctor_dtor(obj_name, cls_name, dtor, "", line_index, is_ctor=False)
        # 从栈帧移除成员变量
        for fr in self._call_stack:
            for mname in list(fr.variables.keys()):
                if mname.startswith(f"{obj_name}."):
                    del fr.variables[mname]
        del self._objects[obj_name]

    def _sync_obj_to_frame(self, obj_name: str):
        """把 _objects 里的成员值同步回栈帧变量"""
        if obj_name not in self._objects:
            return
        mems = self._objects[obj_name]["members"]
        for fr in self._call_stack:
            for mname, var in mems.items():
                key = f"{obj_name}.{mname}"
                if key in fr.variables:
                    fr.variables[key].value = var.value

    def _eval_expr_with_obj(self, expr: str, obj_name: str, frame: StackFrame) -> Any:
        """求值时先把参数帧局部变量和对象成员都代入"""
        expr = expr.strip().rstrip(";")
        # 先代入参数帧里的局部变量
        def replace_var(m):
            vname = m.group(0)
            if vname in frame.variables and frame.variables[vname].value is not None:
                return str(frame.variables[vname].value)
            # 对象成员（不带前缀）
            obj_members = self._objects.get(obj_name, {}).get("members", {})
            if vname in obj_members and obj_members[vname].value is not None:
                return str(obj_members[vname].value)
            v = self._lookup_var(vname)
            if v is not None and v.value is not None:
                return str(v.value)
            return vname
        subst = re.sub(r'\b[a-zA-Z_]\w*\b', replace_var, expr)
        subst = subst.replace("&&", " and ").replace("||", " or ")
        try:
            return eval(subst, {"__builtins__": {}})
        except Exception as e:
            print(f"[EVAL_OBJ ERROR] expr={expr!r}  subst={subst!r}  {type(e).__name__}: {e}")
            return 0

    def _parse_cout_with_obj(self, line: str, obj_name: str) -> str:
        """解析 cout，成员变量不带 obj. 前缀时也能正确输出"""
        parts = re.split(r'<<', line)
        result = ""
        for part in parts[1:]:
            part = part.strip().rstrip(";").strip()
            if part in ("endl", '"\\n"'):
                result += "\n"
            elif part.startswith('"') and part.endswith('"'):
                result += part[1:-1]
            else:
                # 尝试带 obj. 前缀
                full = f"{obj_name}.{part}" if "." not in part else part
                obj_members = self._objects.get(obj_name, {}).get("members", {})
                bare = part.split(".")[-1] if "." in part else part
                if bare in obj_members:
                    var = obj_members[bare]
                    if var.type == "char" and isinstance(var.value, int):
                        result += chr(var.value)
                    else:
                        result += str(var.value) if var.value is not None else part
                else:
                    v = self._lookup_var(part)
                    if v is not None and v.value is not None:
                        if v.type == "char" and isinstance(v.value, int):
                            result += chr(v.value)
                        else:
                            result += str(v.value)
                    else:
                        result += part
        return result

    def _try_parse_declaration(self, line: str):
        """
        尝试解析变量声明，返回 (type, name, init_str_raw) 或 None
        init_str_raw 是未求值的原始右值字符串，由调用方决定如何处理。
        支持：int x; int x = 5; float* p = new float; int* p = nullptr;
        """
        line = line.rstrip(";").strip()
        # 匹配：type[*] name [= expr]
        m = re.match(
            r'^((?:' + '|'.join(BASIC_TYPES) + r')(?:\s*\*)?)\s+(\w+)'
            r'(?:\s*=\s*(.+))?$',
            line
        )
        if m:
            ctype = m.group(1).strip()
            name  = m.group(2).strip()
            init_raw = m.group(3)  # 原始字符串，不求值
            return ctype, name, init_raw

        # 新增：模板容器类型 vector<T>, unordered_map<K,V>, unordered_set<T>, string
        # 也处理 auto 关键字（简化处理，不做类型推断）
        m2 = re.match(
            r'^((?:vector|unordered_map|unordered_set)\s*<[^>]+>|string)\s+(\w+)'
            r'(?:\s*=\s*(.+))?$',
            line
        )
        if m2:
            return m2.group(1).strip(), m2.group(2).strip(), m2.group(3)

        # auto 声明：auto it = xxx; — 忽略类型推断，直接求值
        m_auto = re.match(r'^auto\s+(\w+)\s*=\s*(.+)$', line)
        if m_auto:
            # 使用 "auto" 作为占位类型名
            return "auto", m_auto.group(1).strip(), m_auto.group(2).strip()

        return None

    def _try_parse_assignment(self, line: str):
        """
        尝试解析赋值，返回 (name, op, rhs) 或 None
        支持：x = ...; x += ...; x -= ...; etc.
        """
        line = line.rstrip(";").strip()
        m = re.match(r'^(\w+)\s*(\+\+|--|[+\-*/]?=)\s*(.+)?$', line)
        if m:
            name = m.group(1)
            op   = m.group(2)
            rhs  = m.group(3) or ""
            # 确保左边是已知变量，不是新声明
            if op in ("=", "+=", "-=", "*=", "/=") and self._lookup_var(name):
                return name, op, rhs
        return None

    def _parse_cout(self, line: str) -> str:
        """解析 cout << ... << endl; 输出结果"""
        # 提取 << 之间的内容
        parts = re.split(r'<<', line)
        result = ""
        for part in parts[1:]:
            part = part.strip().rstrip(";")
            if "endl" in part or "\\n" in part:
                result += "\n"
                continue
            # 字符串字面量
            m_str = re.match(r'^"(.*)"$', part)
            if m_str:
                result += m_str.group(1)
                continue
            # 字符字面量
            m_char = re.match(r"^'(.)'$", part)
            if m_char:
                result += m_char.group(1)
                continue
            # 变量（查类型决定是否转字符）
            vname = part.strip()
            v = self._lookup_var(vname)
            if v is not None and v.value is not None:
                if v.type == "char" and isinstance(v.value, int):
                    result += chr(v.value)
                else:
                    result += str(v.value)
            else:
                val = self._eval_expr(vname)
                if val is not None:
                    result += str(val)
        return result

    # ── STL 容器工厂方法 ──────────────────────

    def _make_container_var(self, name: str, type_str: str,
                            addr: int, region) -> ContainerVariable:
        """根据类型字符串创建 ContainerVariable，初始化默认 Python 容器值。"""
        parsed = _parse_type(type_str)
        size   = _template_type_size(parsed)
        stride = size

        kind       = parsed.base
        elem_t     = parsed.params[0].raw if parsed.params else ""
        mapped_t   = parsed.params[1].raw if len(parsed.params) > 1 else ""

        default_value: Any
        if kind == "vector":
            default_value = []
        elif kind == "unordered_map":
            default_value = {}
        elif kind == "string":
            default_value = ""
        elif kind == "unordered_set":
            default_value = set()
        else:
            default_value = None

        return ContainerVariable(
            name=name,
            type=type_str,
            value=default_value,
            address=addr,
            region=region,
            size=size,
            stride=stride,
            container_kind=kind,
            elem_type=elem_t,
            mapped_type=mapped_t,
        )

    def _init_container_from_str(self, var: ContainerVariable, init_str: str):
        """
        从初始化字符串填充容器值。
        支持花括号列表：{1, 2, 3}
        """
        s = init_str.strip()
        if not s:
            return
        if s.startswith("{") and s.endswith("}"):
            s = s[1:-1].strip()
        if not s:
            return

        parts = [p.strip() for p in s.split(",") if p.strip()]
        if var.container_kind == "vector":
            var.value = [self._eval_expr(p) for p in parts]
            stl = STLMethodHandler(self)
            stl._sync_vector_heap(var)
        elif var.container_kind == "unordered_set":
            var.value = set(self._eval_expr(p) for p in parts)

    # ── 用户自定义类方法执行 ─────────────────

    def _run_user_method(self, obj_name: str, cls_name: str,
                         method_name: str, minfo: dict,
                         args_str: str, line_index: int) -> None:
        """执行用户自定义类的成员方法（语句形式）。"""
        frame = StackFrame(f"{cls_name}::{method_name}")
        self._call_stack.append(frame)

        param_decls = [p.strip() for p in minfo["params_str"].split(",") if p.strip()]
        arg_vals    = [a.strip() for a in args_str.split(",") if a.strip()]
        highlight   = []
        for pdecl, aval_str in zip(param_decls, arg_vals):
            parts = pdecl.split()
            if len(parts) >= 2:
                ptype = " ".join(parts[:-1])
                pname = parts[-1].lstrip("*&")
                # 检查实参是否是 ContainerVariable（引用传参，保留类型信息）
                src_var = self._lookup_var(aval_str.strip())
                if isinstance(src_var, ContainerVariable):
                    import copy
                    alias = copy.copy(src_var)
                    alias.name = pname
                    frame.variables[pname] = alias
                    highlight.append(pname)
                    continue
                pval  = self._eval_expr(aval_str)
                addr  = self._allocator.alloc_stack(get_type_size(ptype))
                frame.variables[pname] = self._make_var(
                    pname, ptype, pval, addr, MemoryRegion.STACK,
                    get_type_size(ptype)
                )
                highlight.append(pname)

        # 将 this 对象的成员变量暴露到帧中（隐式 this）
        obj_info = self._objects.get(obj_name, {})
        for mname_m, mvar in obj_info.get("members", {}).items():
            frame.variables[mname_m] = mvar

        self._snapshot(line_index,
                       f"调用 {obj_name}.{method_name}({args_str})，进入方法体",
                       highlight_vars=highlight)

        body_lines = minfo["lines"][1:]
        self._execute_lines(body_lines, "function", minfo["body_start"] + 1, frame)

        if (self._call_stack
                and self._call_stack[-1].function_name == f"{cls_name}::{method_name}"):
            self._call_stack.pop()
        self._snapshot(line_index, f"{obj_name}.{method_name}() 执行完毕，栈帧弹出")

    def _run_user_method_eval(self, obj_name: str, cls_name: str,
                              method_name: str, minfo: dict,
                              args_str: str) -> Any:
        """执行用户自定义类的成员方法并返回值（求值形式）。"""
        frame = StackFrame(f"{cls_name}::{method_name}")
        self._call_stack.append(frame)

        param_decls = [p.strip() for p in minfo["params_str"].split(",") if p.strip()]
        arg_vals    = [a.strip() for a in args_str.split(",") if a.strip()]
        for pdecl, aval_str in zip(param_decls, arg_vals):
            parts = pdecl.split()
            if len(parts) >= 2:
                ptype = " ".join(parts[:-1])
                pname = parts[-1].lstrip("*&")
                pval  = self._eval_expr(aval_str)
                addr  = self._allocator.alloc_stack(get_type_size(ptype))
                frame.variables[pname] = self._make_var(
                    pname, ptype, pval, addr, MemoryRegion.STACK,
                    get_type_size(ptype)
                )

        obj_info = self._objects.get(obj_name, {})
        for mname_m, mvar in obj_info.get("members", {}).items():
            frame.variables[mname_m] = mvar

        self._snapshot(minfo["body_start"],
                       f"调用 {obj_name}.{method_name}({args_str})")

        return_val = self._execute_function_body(minfo, minfo["body_start"])

        if (self._call_stack
                and self._call_stack[-1].function_name == f"{cls_name}::{method_name}"):
            self._call_stack.pop()
        self._snapshot(minfo["body_start"],
                       f"{obj_name}.{method_name}() 返回 {return_val}")
        return return_val