"""
type_parser.py
模板类型字符串解析工具。
将 C++ 类型字符串（含模板）解析为 ParsedType 结构化对象。

支持：
  parse_type("int")                      → ParsedType("int", [])
  parse_type("int*")                     → ParsedType("int", [], is_pointer=True)
  parse_type("vector<int>")              → ParsedType("vector", [ParsedType("int", [])])
  parse_type("unordered_map<int,int>")   → ParsedType("unordered_map", [...])
  parse_type("vector<vector<int>>")      → 嵌套模板
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ── STL 容器识别集合 ─────────────────────────────────────────
STL_CONTAINERS = {"vector", "unordered_map", "string", "unordered_set"}

BASIC_TYPES = {
    "int", "float", "double", "char", "bool", "long", "short",
}


# ── 数据结构 ─────────────────────────────────────────────────

@dataclass
class ParsedType:
    base: str                           # "vector" / "int" / "unordered_map" …
    params: list = field(default_factory=list)  # list[ParsedType]，模板参数
    is_pointer: bool = False
    raw: str = ""                       # 原始字符串，调试用

    @property
    def is_template(self) -> bool:
        return len(self.params) > 0

    @property
    def is_stl_container(self) -> bool:
        return self.base in STL_CONTAINERS

    @property
    def is_basic(self) -> bool:
        return self.base in BASIC_TYPES

    def elem_type(self) -> Optional["ParsedType"]:
        """vector/set 的元素类型，map 的 key 类型"""
        return self.params[0] if self.params else None

    def mapped_type(self) -> Optional["ParsedType"]:
        """unordered_map 的 value 类型"""
        return self.params[1] if len(self.params) > 1 else None

    def __repr__(self) -> str:
        if self.params:
            inner = ", ".join(repr(p) for p in self.params)
            return f"ParsedType({self.base!r}, [{inner}])"
        return f"ParsedType({self.base!r})"


# ── 解析函数 ─────────────────────────────────────────────────

def parse_type(type_str: str) -> ParsedType:
    """
    将 C++ 类型字符串解析为 ParsedType 树。

    >>> parse_type("int")
    ParsedType('int')
    >>> parse_type("vector<int>")
    ParsedType('vector', [ParsedType('int')])
    >>> parse_type("unordered_map<int, string>")
    ParsedType('unordered_map', [ParsedType('int'), ParsedType('string')])
    """
    type_str = type_str.strip()
    if not type_str:
        return ParsedType(base="int", raw=type_str)

    # 处理指针后缀
    is_ptr = type_str.endswith("*")
    if is_ptr:
        type_str = type_str[:-1].strip()

    # 处理引用后缀（C++ 引用，模拟时忽略，当值传递处理）
    is_ref = type_str.endswith("&")
    if is_ref:
        type_str = type_str[:-1].strip()

    # 去掉 const 前缀
    if type_str.startswith("const "):
        type_str = type_str[6:].strip()

    # 匹配模板类型：base<inner>
    m = re.match(r'^(\w+)\s*<(.+)>$', type_str)
    if m:
        base = m.group(1).strip()
        inner = m.group(2).strip()
        params = [parse_type(p) for p in _split_template_params(inner)]
        return ParsedType(base=base, params=params, is_pointer=is_ptr, raw=type_str)

    # 普通类型
    return ParsedType(base=type_str, params=[], is_pointer=is_ptr, raw=type_str)


def _split_template_params(s: str) -> list:
    """
    正确处理嵌套模板参数分割，不被嵌套 <> 内的逗号干扰。

    "int, string"           → ["int", "string"]
    "vector<int>, int"      → ["vector<int>", "int"]
    "map<int,int>, vector<string>"  → ["map<int,int>", "vector<string>"]
    """
    parts = []
    depth = 0
    current: list = []

    for ch in s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1

        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)

    if current:
        parts.append("".join(current).strip())

    return [p for p in parts if p]


# ── 类型大小 ─────────────────────────────────────────────────

# 模拟 sizeof，基础类型参考 x86-64 ABI
_BASIC_SIZES = {
    "int":    4,
    "float":  4,
    "double": 8,
    "char":   1,
    "bool":   1,
    "long":   8,
    "short":  2,
    "void":   0,
}

# STL 容器对象本体大小（不含堆数据区）
# vector<T>        = {T* data, size_t size, size_t capacity} = 3 × 8 = 24
# string           = 约 32 字节（SSO 实现）
# unordered_map    ≈ 56 字节（libstdc++ 实现）
# unordered_set    ≈ 56 字节
_CONTAINER_SIZES = {
    "vector":        24,
    "string":        32,
    "unordered_map": 56,
    "unordered_set": 56,
}


def type_size(parsed: ParsedType) -> int:
    """
    返回类型的模拟 sizeof（字节数）。

    指针类型统一返回 8（x86-64）。
    容器对象本体大小不含堆数据区。
    """
    if parsed.is_pointer:
        return 8
    if parsed.base in _CONTAINER_SIZES:
        return _CONTAINER_SIZES[parsed.base]
    return _BASIC_SIZES.get(parsed.base, 4)


def elem_size(parsed: ParsedType) -> int:
    """
    返回容器元素的大小。
    vector<int> → 4，vector<double> → 8，unordered_map<int,int> → 8（pair）
    """
    if parsed.base == "unordered_map":
        # key_size + value_size（粗略，不含 hash 桶开销）
        k = type_size(parsed.params[0]) if parsed.params else 4
        v = type_size(parsed.params[1]) if len(parsed.params) > 1 else 4
        return k + v
    et = parsed.elem_type()
    return type_size(et) if et else 4


# ── 辅助：判断字符串是否为 STL 容器类型声明 ─────────────────

# 预编译正则，供外部模块快速判断
_CONTAINER_DECL_RE = re.compile(
    r'^(?:vector|unordered_map|unordered_set)\s*<[^>]+>|string$'
)


def is_container_type(type_str: str) -> bool:
    """
    判断类型字符串是否为受支持的 STL 容器类型。

    >>> is_container_type("vector<int>")
    True
    >>> is_container_type("int")
    False
    """
    return bool(_CONTAINER_DECL_RE.match(type_str.strip()))
