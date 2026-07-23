"""
method_dispatch.py
成员方法调用路由器。

将 obj.method(args) 调用分发到：
  1. STLMethodHandler  — 当 obj 是 ContainerVariable 时
  2. _run_user_method  — 当 obj 是用户自定义类对象时
  3. 静默忽略           — 未知对象，不崩溃

使用方式（由 CppInterpreter 持有单例）：
    self._method_dispatcher = MethodDispatcher(self)

    # 语句形式（不关心返回值）
    self._method_dispatcher.dispatch(obj_name, method, args_str, line_index)

    # 求值形式（赋值右侧）
    val = self._method_dispatcher.dispatch_eval(obj_name, method, args_str)
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .stl_containers import ContainerVariable, STLMethodHandler

if TYPE_CHECKING:
    from .cpp_interpreter import CppInterpreter


class MethodDispatcher:

    def __init__(self, interp: "CppInterpreter"):
        self._interp = interp
        self._stl = STLMethodHandler(interp)

    # ── 语句形式：obj.method(args); ─────────────────────────

    def dispatch(self, obj_name: str, method_name: str,
                 args_str: str, line_index: int) -> None:
        """
        执行成员方法调用（语句形式，副作用为主，不关心返回值）。
        产生至少一个 snapshot。
        """
        interp = self._interp

        # 1. STL 容器变量
        var = interp._lookup_var(obj_name)
        if isinstance(var, ContainerVariable):
            self._stl.call(var, method_name, args_str, line_index)
            return

        # 2. 用户自定义类对象
        if obj_name in interp._objects:
            cls_name = interp._objects[obj_name].get("class_name", "")
            cls_info = interp._classes.get(cls_name, {})
            methods  = cls_info.get("methods", {})
            if method_name in methods:
                interp._run_user_method(
                    obj_name, cls_name, method_name,
                    methods[method_name], args_str, line_index
                )
                return
            # 未实现的成员方法，静默快照
            interp._snapshot(
                line_index,
                f"[未实现] {obj_name}.{method_name}({args_str})"
            )
            return

        # 3. 未知对象，静默（可能是 it.second 这类迭代器访问）
        # 不产生 snapshot，避免干扰

    # ── 求值形式：result = obj.method(args) ─────────────────

    def dispatch_eval(self, obj_name: str, method_name: str,
                      args_str: str) -> Any:
        """
        执行成员方法调用并返回值（赋值右侧）。
        不产生独立 snapshot（由上层的赋值快照覆盖）。
        """
        interp = self._interp

        # 1. STL 容器变量
        var = interp._lookup_var(obj_name)
        if isinstance(var, ContainerVariable):
            return self._stl.call_eval(var, method_name, args_str)

        # 2. 用户自定义类对象
        if obj_name in interp._objects:
            cls_name = interp._objects[obj_name].get("class_name", "")
            cls_info = interp._classes.get(cls_name, {})
            methods  = cls_info.get("methods", {})
            if method_name in methods:
                return interp._run_user_method_eval(
                    obj_name, cls_name, method_name,
                    methods[method_name], args_str
                )

        # 3. 未知
        return 0
