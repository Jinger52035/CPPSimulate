"""
stl_containers.py
STL 容器的数据模型（ContainerVariable）和方法模拟层（STLMethodHandler）。

设计原则：
  - ContainerVariable 继承 Variable，与现有 VarCard / StackFrame 完全兼容
  - STLMethodHandler 只操作 Python 原生数据结构，不依赖 Qt
  - 新增容器只需在 STLMethodHandler 中添加对应的 _kind_method() 方法
  - 未实现的方法不崩溃，产生一个"未实现"的快照步骤

命名约定：
  handler 方法名 = f"_{container_kind}_{method_name}"
  例：_vector_push_back、_unordered_map_find、_string_substr
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from .type_parser import ParsedType, parse_type, type_size, elem_size

if TYPE_CHECKING:
    from .cpp_interpreter import CppInterpreter, MemoryRegion


# ── ContainerVariable ────────────────────────────────────────

@dataclass
class ContainerVariable:
    """
    STL 容器的运行时表示。

    保持与 Variable 相同的核心字段（name/type/value/address/region/size/stride/is_pointer），
    使其能直接存入 StackFrame.variables 并被现有 VarCard 识别。

    额外字段记录容器特有信息，供 ContainerCard 渲染。
    """
    # ── 与 Variable 相同的核心字段 ──────────────────────────
    name:       str
    type:       str
    value:      Any          # Python 原生容器：list / dict / str / set
    address:    int
    region:     Any          # MemoryRegion
    size:       int  = 24    # 对象本体大小（不含堆数据）
    stride:     int  = 24
    is_pointer: bool = False

    # ── 容器专有字段 ─────────────────────────────────────────
    container_kind:  str = ""   # "vector" | "unordered_map" | "string" | "unordered_set"
    elem_type:       str = ""   # 元素类型字符串（K type for map）
    mapped_type:     str = ""   # value type（仅 map 使用）
    heap_data_addr:  int = 0    # 数据区在堆上的起始地址（vector/string）
    capacity:        int = 0    # 当前容量（vector/string 用）

    def display_value(self) -> str:
        """供 VarCard 显示的简短字符串"""
        if self.container_kind == "vector":
            elems = self.value or []
            preview = ", ".join(str(e) for e in elems[:6])
            suffix = ", …" if len(elems) > 6 else ""
            return f"[{preview}{suffix}]  size={len(elems)} cap={self.capacity}"

        if self.container_kind == "unordered_map":
            d = self.value or {}
            pairs = ", ".join(f"{k}:{v}" for k, v in list(d.items())[:4])
            suffix = ", …" if len(d) > 4 else ""
            return f"{{{pairs}{suffix}}}  size={len(d)}"

        if self.container_kind == "string":
            s = self.value or ""
            preview = s[:20] + ("…" if len(s) > 20 else "")
            return f'"{preview}"  len={len(s)}'

        if self.container_kind == "unordered_set":
            s = self.value or set()
            elems = ", ".join(str(e) for e in list(s)[:6])
            suffix = ", …" if len(s) > 6 else ""
            return f"{{{elems}{suffix}}}  size={len(s)}"

        return str(self.value)

    # ── 兼容 Variable.display_value 调用点 ─────────────────
    # panels.py / widgets.py 通过 var.display_value() 获取显示文本，已覆盖。


# ── STLMethodHandler ─────────────────────────────────────────

class STLMethodHandler:
    """
    所有 STL 容器的内置方法模拟。

    调用约定：
        handler = STLMethodHandler(interpreter)
        # 语句形式（产生 snapshot）
        handler.call(var, "push_back", "3", line_index)
        # 求值形式（返回 Python 值，不产生独立 snapshot）
        val = handler.call_eval(var, "size", "")
    """

    def __init__(self, interp: "CppInterpreter"):
        self._interp = interp

    # ── 分发入口 ────────────────────────────────────────────

    def call(self, var: ContainerVariable, method: str,
             args_str: str, line_index: int) -> None:
        """语句形式的方法调用，执行副作用并产生 snapshot。"""
        handler = getattr(self, f"_{var.container_kind}_{method}", None)
        if handler is None:
            self._interp._snapshot(
                line_index,
                f"[STL 未实现] {var.name}.{method}({args_str})"
            )
            return
        args = self._eval_args(args_str)
        handler(var, args, line_index, produce_snapshot=True)

    def call_eval(self, var: ContainerVariable, method: str,
                  args_str: str) -> Any:
        """求值形式的方法调用，返回 Python 值，不产生独立 snapshot。"""
        handler = getattr(self, f"_{var.container_kind}_{method}", None)
        if handler is None:
            return 0
        args = self._eval_args(args_str)
        return handler(var, args, line_index=None, produce_snapshot=False)

    def _eval_args(self, args_str: str) -> list:
        """将逗号分隔的参数字符串求值为 Python 值列表。"""
        if not args_str.strip():
            return []
        # 简单按逗号分割（不处理嵌套括号，足够应对基本 STL 方法参数）
        return [self._interp._eval_expr(a.strip())
                for a in args_str.split(",") if a.strip()]

    def _snap(self, line_index, desc, var_name=""):
        highlight = [var_name] if var_name else []
        self._interp._snapshot(line_index, desc, highlight_vars=highlight)

    # ════════════════════════════════════════════════════════
    # vector<T>
    # ════════════════════════════════════════════════════════

    def _vector_push_back(self, var, args, line_index, produce_snapshot):
        val = args[0] if args else 0
        data = var.value if var.value is not None else []
        data.append(val)
        var.value = data
        self._sync_vector_heap(var)
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.push_back({val})  →  size={len(data)}, cap={var.capacity}",
                       var.name)

    def _vector_pop_back(self, var, args, line_index, produce_snapshot):
        data = var.value if var.value is not None else []
        removed = data.pop() if data else None
        var.value = data
        self._sync_vector_heap(var)
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.pop_back()  →  移除 {removed}, size={len(data)}",
                       var.name)

    def _vector_size(self, var, args, line_index, produce_snapshot):
        return len(var.value or [])

    def _vector_empty(self, var, args, line_index, produce_snapshot):
        return 1 if not var.value else 0

    def _vector_clear(self, var, args, line_index, produce_snapshot):
        var.value = []
        var.capacity = 0
        self._sync_vector_heap(var)
        if produce_snapshot:
            self._snap(line_index, f"{var.name}.clear()  →  size=0", var.name)

    def _vector_at(self, var, args, line_index, produce_snapshot):
        idx = int(args[0]) if args else 0
        data = var.value or []
        return data[idx] if 0 <= idx < len(data) else 0

    def _vector_front(self, var, args, line_index, produce_snapshot):
        data = var.value or []
        return data[0] if data else 0

    def _vector_back(self, var, args, line_index, produce_snapshot):
        data = var.value or []
        return data[-1] if data else 0

    def _vector_resize(self, var, args, line_index, produce_snapshot):
        new_size = int(args[0]) if args else 0
        fill_val = args[1] if len(args) > 1 else 0
        data = var.value or []
        if new_size > len(data):
            data.extend([fill_val] * (new_size - len(data)))
        else:
            data = data[:new_size]
        var.value = data
        self._sync_vector_heap(var)
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.resize({new_size})  →  size={len(data)}",
                       var.name)

    def _vector_reserve(self, var, args, line_index, produce_snapshot):
        new_cap = int(args[0]) if args else 0
        if new_cap > var.capacity:
            var.capacity = new_cap
            self._sync_vector_heap(var)
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.reserve({new_cap})  →  cap={var.capacity}",
                       var.name)

    def _vector_operator_bracket(self, var, args, line_index, produce_snapshot):
        """operator[] 下标读取"""
        idx = int(args[0]) if args else 0
        data = var.value or []
        return data[idx] if 0 <= idx < len(data) else 0

    def _sync_vector_heap(self, var: ContainerVariable):
        """将 vector 元素同步到 interp._heap，供可视化用。"""
        interp = self._interp
        data = var.value or []
        parsed = parse_type(var.elem_type) if var.elem_type else None
        es = type_size(parsed) if parsed else 4

        # 扩容：简化模拟（超出时翻倍或按需分配）
        if var.capacity < len(data):
            old_cap = var.capacity
            var.capacity = max(len(data), old_cap * 2 if old_cap else 4)
            # 释放旧堆块
            if var.heap_data_addr and var.heap_data_addr in interp._heap:
                del interp._heap[var.heap_data_addr]
            var.heap_data_addr = 0

        # 分配或复用堆块
        if data and not var.heap_data_addr:
            var.heap_data_addr = interp._allocator.alloc_heap(var.capacity * es)

        if var.heap_data_addr:
            # 用一个 Variable-like 对象表示整块连续内存，ByteCells 依 stride 渲染
            from .cpp_interpreter import MemoryRegion
            hvar = interp._make_var(
                f"{var.name}.data()",
                var.elem_type or "int",
                list(data),
                var.heap_data_addr,
                MemoryRegion.HEAP,
                var.capacity * es,
            )
            hvar.stride = es
            interp._heap[var.heap_data_addr] = hvar

    # ════════════════════════════════════════════════════════
    # unordered_map<K, V>
    # ════════════════════════════════════════════════════════

    def _unordered_map_operator_bracket(self, var, args, line_index, produce_snapshot):
        """operator[] 读写（不存在时默认插入 0）"""
        k = args[0] if args else 0
        d = var.value if var.value is not None else {}
        if k not in d:
            d[k] = 0
            var.value = d
        return d.get(k, 0)

    def _unordered_map_insert(self, var, args, line_index, produce_snapshot):
        if len(args) >= 2:
            k, v = args[0], args[1]
            d = var.value if var.value is not None else {}
            d[k] = v
            var.value = d
            if produce_snapshot:
                self._snap(line_index,
                           f"{var.name}.insert({{{k}, {v}}})  →  size={len(d)}",
                           var.name)

    def _unordered_map_find(self, var, args, line_index, produce_snapshot):
        """返回迭代器模拟值：找到 → key 值，未找到 → None（代表 end()）"""
        k = args[0] if args else 0
        d = var.value or {}
        found = k in d
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.find({k})  →  {'找到' if found else 'end()'}",
                       var.name)
        # 返回 key 本身作为"非 end 迭代器"，未找到返回 None
        return k if found else None

    def _unordered_map_count(self, var, args, line_index, produce_snapshot):
        k = args[0] if args else 0
        return 1 if k in (var.value or {}) else 0

    def _unordered_map_erase(self, var, args, line_index, produce_snapshot):
        k = args[0] if args else 0
        d = var.value if var.value is not None else {}
        d.pop(k, None)
        var.value = d
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.erase({k})  →  size={len(d)}",
                       var.name)

    def _unordered_map_size(self, var, args, line_index, produce_snapshot):
        return len(var.value or {})

    def _unordered_map_empty(self, var, args, line_index, produce_snapshot):
        return 1 if not var.value else 0

    def _unordered_map_end(self, var, args, line_index, produce_snapshot):
        """返回 None 作为 end() 迭代器的模拟值"""
        return None

    # ════════════════════════════════════════════════════════
    # string
    # ════════════════════════════════════════════════════════

    def _string_size(self, var, args, line_index, produce_snapshot):
        return len(var.value or "")

    def _string_length(self, var, args, line_index, produce_snapshot):
        return len(var.value or "")

    def _string_empty(self, var, args, line_index, produce_snapshot):
        return 1 if not var.value else 0

    def _string_push_back(self, var, args, line_index, produce_snapshot):
        ch = (chr(args[0]) if isinstance(args[0], int) else str(args[0])) if args else ""
        var.value = (var.value or "") + ch
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.push_back('{ch}')  →  \"{var.value}\"",
                       var.name)

    def _string_append(self, var, args, line_index, produce_snapshot):
        s = str(args[0]) if args else ""
        var.value = (var.value or "") + s
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.append(\"{s}\")  →  \"{var.value}\"",
                       var.name)

    def _string_substr(self, var, args, line_index, produce_snapshot):
        pos = int(args[0]) if args else 0
        length = int(args[1]) if len(args) > 1 else None
        s = var.value or ""
        if length is not None:
            return s[pos:pos + length]
        return s[pos:]

    def _string_find(self, var, args, line_index, produce_snapshot):
        needle = str(args[0]) if args else ""
        s = var.value or ""
        idx = s.find(needle)
        return idx if idx >= 0 else (2 ** 32 - 1)   # npos

    def _string_at(self, var, args, line_index, produce_snapshot):
        idx = int(args[0]) if args else 0
        s = var.value or ""
        return ord(s[idx]) if 0 <= idx < len(s) else 0

    def _string_clear(self, var, args, line_index, produce_snapshot):
        var.value = ""
        if produce_snapshot:
            self._snap(line_index, f"{var.name}.clear()", var.name)

    def _string_operator_bracket(self, var, args, line_index, produce_snapshot):
        idx = int(args[0]) if args else 0
        s = var.value or ""
        return ord(s[idx]) if 0 <= idx < len(s) else 0

    # ════════════════════════════════════════════════════════
    # unordered_set<T>
    # ════════════════════════════════════════════════════════

    def _unordered_set_insert(self, var, args, line_index, produce_snapshot):
        val = args[0] if args else 0
        s = var.value if var.value is not None else set()
        s.add(val)
        var.value = s
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.insert({val})  →  size={len(s)}",
                       var.name)

    def _unordered_set_erase(self, var, args, line_index, produce_snapshot):
        val = args[0] if args else 0
        s = var.value if var.value is not None else set()
        s.discard(val)
        var.value = s
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.erase({val})  →  size={len(s)}",
                       var.name)

    def _unordered_set_count(self, var, args, line_index, produce_snapshot):
        val = args[0] if args else 0
        return 1 if val in (var.value or set()) else 0

    def _unordered_set_find(self, var, args, line_index, produce_snapshot):
        """find：找到返回元素值，未找到返回 None（end()）"""
        val = args[0] if args else 0
        s = var.value or set()
        found = val in s
        if produce_snapshot:
            self._snap(line_index,
                       f"{var.name}.find({val})  →  {'找到' if found else 'end()'}",
                       var.name)
        return val if found else None

    def _unordered_set_size(self, var, args, line_index, produce_snapshot):
        return len(var.value or set())

    def _unordered_set_empty(self, var, args, line_index, produce_snapshot):
        return 1 if not var.value else 0

    def _unordered_set_clear(self, var, args, line_index, produce_snapshot):
        var.value = set()
        if produce_snapshot:
            self._snap(line_index, f"{var.name}.clear()", var.name)

    def _unordered_set_end(self, var, args, line_index, produce_snapshot):
        return None
