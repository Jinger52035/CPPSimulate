"""Serialize interpreter snapshots for the embedded memory visualizer."""

from __future__ import annotations

import json
import math
from enum import Enum
from typing import Any

from .cpp_interpreter import MemoryRegion, Variable
from .stl_containers import ContainerVariable

SCHEMA_VERSION = 1
_MEMBER_COLORS = [
    "#3B6EA8", "#2E7D52", "#7B3FA0", "#8B5A00",
    "#1A6B6B", "#8B2020", "#4A5A00", "#1A4A7A",
]
_REGION_KEYS = {
    MemoryRegion.GLOBAL: "global",
    MemoryRegion.STACK: "stack",
    MemoryRegion.HEAP: "heap",
    MemoryRegion.CODE: "code",
    MemoryRegion.LITERAL: "literal",
    MemoryRegion.DATA: "data",
    MemoryRegion.BSS: "bss",
}
_SECTION_TITLES = {
    "code": "代码区 (Code)",
    "literal": "常量区 (Literals)",
    "data": "数据段 (Data)  已初始化全局",
    "bss": "BSS段  未初始化全局",
    "global": "全局区 / 静态区",
    "heap": "堆 (Heap)  ↑ 向高地址增长",
    "stack": "栈 (Stack)  ↓ 向低地址增长",
}
_SECTION_ORDER = {
    "simple": ["code", "global", "heap", "stack"],
    "standard": ["global", "heap", "stack"],
    "detailed": ["code", "literal", "data", "bss", "heap", "stack"],
}


def address_dto(value: Any) -> dict | None:
    if not isinstance(value, int):
        return None
    return {"text": f"0x{value:08X}", "value": value}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"type": "float", "value": str(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list) or isinstance(value, tuple):
        return {"type": "list", "items": [normalize_value(item) for item in value]}
    if isinstance(value, set):
        items = [normalize_value(item) for item in value]
        return {"type": "set", "items": sorted(items, key=_canonical)}
    if isinstance(value, dict):
        entries = [
            {"key": normalize_value(key), "value": normalize_value(item)}
            for key, item in value.items()
        ]
        entries.sort(key=lambda entry: _canonical(entry["key"]))
        return {"type": "map", "entries": entries}
    return {"type": "repr", "value": str(value)}


def _region_key(region: Any) -> str:
    return _REGION_KEYS.get(region, str(getattr(region, "value", region)).lower())


def _variable_dto(
    name: str,
    var: Variable | ContainerVariable,
    highlights: set[str],
    live_addresses: set[int],
    *,
    qualified_name: str | None = None,
) -> dict:
    highlighted = name in highlights or var.name in highlights
    pointer_target = address_dto(var.value) if var.is_pointer and isinstance(var.value, int) and var.value else None
    dto = {
        "kind": "container" if isinstance(var, ContainerVariable) else "variable",
        "id": f"var-{var.address:08X}-{qualified_name or name}",
        "name": name,
        "qualifiedName": qualified_name or var.name,
        "type": var.type,
        "region": _region_key(var.region),
        "value": normalize_value(var.value),
        "displayValue": var.display_value(),
        "address": address_dto(var.address),
        "size": var.size,
        "stride": var.stride,
        "isPointer": bool(var.is_pointer),
        "pointerTargetAddress": pointer_target,
        "pointerTargetAlive": bool(pointer_target and var.value in live_addresses),
        "highlighted": highlighted,
    }
    if isinstance(var, ContainerVariable):
        dto.update({
            "containerKind": var.container_kind,
            "elemType": var.elem_type,
            "mappedType": var.mapped_type,
            "heapDataAddress": address_dto(var.heap_data_addr) if var.heap_data_addr else None,
            "capacity": var.capacity,
            "content": normalize_value(var.value),
        })
    return dto


def _object_dto(
    object_name: str,
    info: dict,
    frame_variables: dict,
    highlights: set[str],
    live_addresses: set[int],
) -> dict | None:
    members = []
    prefix = object_name + "."
    for qualified_name, var in frame_variables.items():
        if not qualified_name.startswith(prefix):
            continue
        member_name = qualified_name[len(prefix):]
        members.append(
            _variable_dto(
                member_name, var, highlights, live_addresses,
                qualified_name=qualified_name,
            )
        )
    if not members:
        return None
    members.sort(key=lambda item: item["address"]["value"])
    base = int(info.get("base_addr", members[0]["address"]["value"]))
    total_size = int(info.get("total_size", 0))
    segments = []
    for index, member in enumerate(members):
        segments.append({
            "offset": member["address"]["value"] - base,
            "size": member["size"],
            "color": _MEMBER_COLORS[index % len(_MEMBER_COLORS)],
            "label": f'{member["name"]}:{member["type"]}',
        })
    padding = [
        {
            "address": address_dto(address),
            "offset": address - base,
            "size": size,
        }
        for address, size in info.get("padding", [])
    ]
    covered = set()
    for segment in segments:
        covered.update(range(segment["offset"], segment["offset"] + segment["size"]))
    explicit = set()
    for item in padding:
        explicit.update(range(item["offset"], item["offset"] + item["size"]))
    missing = sorted(set(range(total_size)) - covered - explicit)
    start = None
    previous = None
    for offset in missing + [None]:
        if start is None:
            start = offset
        elif offset is None or offset != previous + 1:
            padding.append({
                "address": address_dto(base + start),
                "offset": start,
                "size": previous - start + 1,
            })
            start = offset
        previous = offset
    padding.sort(key=lambda item: item["offset"])
    return {
        "kind": "object",
        "id": f"object-{base:08X}-{object_name}",
        "name": object_name,
        "className": info.get("cls_name", object_name),
        "baseAddress": address_dto(base),
        "totalSize": total_size,
        "members": members,
        "segments": segments,
        "padding": padding,
        "highlighted": any(member["highlighted"] for member in members),
    }


def _stack_frames(step, highlights: set[str], live_addresses: set[int]) -> list[dict]:
    result = []
    for frame_index, frame in enumerate(step.stack_frames):
        object_names = {
            object_name for object_name in step.objects
            if any(name.startswith(object_name + ".") for name in frame.variables)
        }
        items = []
        for object_name in object_names:
            obj = _object_dto(
                object_name, step.objects[object_name], frame.variables,
                highlights, live_addresses,
            )
            if obj:
                items.append(obj)
        for name, var in frame.variables.items():
            if any(name.startswith(object_name + ".") for object_name in object_names):
                continue
            items.append(_variable_dto(name, var, highlights, live_addresses))
        items.sort(
            key=lambda item: (
                item.get("baseAddress") or item.get("address") or {"value": -1}
            )["value"],
            reverse=True,
        )
        result.append({
            "id": f"frame-{frame_index}-{frame.function_name}",
            "functionName": frame.function_name,
            "returnLine": frame.return_line,
            "items": items,
        })
    return result


def _variable_list(variables: dict, highlights: set[str], live_addresses: set[int], reverse=False) -> list:
    items = [
        _variable_dto(name, var, highlights, live_addresses)
        for name, var in variables.items()
    ]
    items.sort(key=lambda item: item["address"]["value"], reverse=reverse)
    return items


def _crash_dto(crash) -> dict | None:
    if crash is None:
        return None
    return {
        "ubType": crash.ub_type,
        "title": crash.title,
        "cause": crash.cause,
        "detail": crash.detail,
        "ptrName": crash.ptr_name,
        "ptrValue": address_dto(crash.ptr_value) if isinstance(crash.ptr_value, int) else normalize_value(crash.ptr_value),
    }


def build_memory_dto(step, settings, revision: int, function_names=()) -> dict:
    seg_mode = settings.seg_mode if settings.seg_mode in _SECTION_ORDER else "standard"
    layout = settings.layout if settings.layout in ("split", "unified") else "split"
    envelope = {
        "schemaVersion": SCHEMA_VERSION,
        "revision": revision,
        "render": {"layout": layout, "segMode": seg_mode},
        "environment": {
            "architecture": "x86-64",
            "endianness": "little",
            "stackGrowth": "down",
            "heapGrowth": "up",
            "byteSizes": {"char": 1, "short": 2, "int": 4, "float": 4, "double": 8, "long": 8, "pointer": 8},
        },
        "step": None,
    }
    if step is None:
        return envelope

    highlights = set(step.highlight_vars or [])
    all_vars = list(step.heap.values()) + list(step.globals.values())
    for frame in step.stack_frames:
        all_vars.extend(frame.variables.values())
    live_addresses = {var.address for var in all_vars}
    heap_named = {var.name: var for var in step.heap.values()}
    globals_all = step.globals
    code_names = (
        list(function_names) if seg_mode == "detailed"
        else [frame.function_name for frame in step.stack_frames]
    )
    code_variables = {
        name: Variable(
            name=name + ("()" if seg_mode == "detailed" else ""),
            type="function",
            value="compiled" if seg_mode == "detailed" else "...",
            address=0x00401000 + index * 0x100,
            region=MemoryRegion.CODE,
            size=0,
            stride=0,
        )
        for index, name in enumerate(code_names)
    }
    data_vars = {
        name: var for name, var in globals_all.items()
        if var.region in (MemoryRegion.DATA, MemoryRegion.GLOBAL) and var.value is not None
    }
    bss_vars = {
        name: var for name, var in globals_all.items()
        if var.region == MemoryRegion.BSS or var.value is None
    }
    stack_frames = _stack_frames(step, highlights, live_addresses)
    section_items = {
        "code": _variable_list(code_variables, highlights, live_addresses),
        "literal": _variable_list(step.literals, highlights, live_addresses),
        "data": _variable_list(data_vars, highlights, live_addresses),
        "bss": _variable_list(bss_vars, highlights, live_addresses),
        "global": _variable_list(globals_all, highlights, live_addresses),
        "heap": _variable_list(heap_named, highlights, live_addresses, reverse=True),
        "stack": stack_frames,
    }
    sections = [
        {"key": key, "title": _SECTION_TITLES[key], "items": section_items[key]}
        for key in _SECTION_ORDER[seg_mode]
    ]
    envelope["step"] = {
        "lineIndex": step.line_index,
        "description": step.description,
        "output": step.output,
        "highlightVars": list(step.highlight_vars or []),
        "stackFrames": stack_frames,
        "heap": section_items["heap"],
        "globals": section_items["global"],
        "literals": section_items["literal"],
        "objects": list(step.objects.keys()),
        "crash": _crash_dto(step.crash),
        "sections": sections,
    }
    return envelope


def serialize_memory_state(step, settings, revision: int, function_names=()) -> str:
    return json.dumps(
        build_memory_dto(step, settings, revision, function_names),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
