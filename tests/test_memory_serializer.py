import json
import math
import unittest

from src.config import AppSettings
from src.cpp_interpreter import (
    CrashInfo, ExecutionStep, MemoryRegion, StackFrame, Variable,
)
from src.memory_serializer import build_memory_dto, normalize_value, serialize_memory_state
from src.stl_containers import ContainerVariable


class MemorySerializerTests(unittest.TestCase):
    def test_empty_state_and_strict_json(self):
        settings = AppSettings(layout="split", seg_mode="standard")
        dto = build_memory_dto(None, settings, 3)
        self.assertEqual(1, dto["schemaVersion"])
        self.assertEqual(3, dto["revision"])
        self.assertIsNone(dto["step"])
        json.loads(serialize_memory_state(None, settings, 3))

    def test_normalization_is_deterministic(self):
        first = normalize_value({3: "c", 1: {"b", "a"}})
        second = normalize_value({1: {"a", "b"}, 3: "c"})
        self.assertEqual(first, second)
        self.assertEqual({"type": "float", "value": "nan"}, normalize_value(math.nan))

    def test_stack_objects_containers_and_pointer_targets(self):
        x = Variable("x", "int", 99, 0x7FFFFFF0, MemoryRegion.STACK)
        p = Variable("p", "int*", x.address, 0x7FFFFFF8, MemoryRegion.STACK, 8, 8, True)
        a = Variable("obj.a", "char", 65, 0x7FFFFFD8, MemoryRegion.STACK, 1, 1)
        b = Variable("obj.b", "double", 2.0, 0x7FFFFFE0, MemoryRegion.STACK, 8, 8)
        vector = ContainerVariable(
            "items", "vector<int>", [3, 1], 0x7FFFFFC0, MemoryRegion.STACK,
            container_kind="vector", elem_type="int", heap_data_addr=0x01000000,
            capacity=4,
        )
        frame = StackFrame("main", {"x": x, "p": p, "obj.a": a, "obj.b": b, "items": vector})
        step = ExecutionStep(
            4, "write", [frame],
            highlight_vars=["p", "x", "obj.b"],
            objects={
                "obj": {
                    "base_addr": 0x7FFFFFD8,
                    "total_size": 16,
                    "cls_name": "Sample",
                    "padding": [(0x7FFFFFD9, 7)],
                }
            },
        )
        dto = build_memory_dto(step, AppSettings(seg_mode="standard"), 1)
        frame_dto = dto["step"]["stackFrames"][0]
        self.assertEqual("main", frame_dto["functionName"])
        pointer = next(item for item in frame_dto["items"] if item.get("name") == "p")
        self.assertTrue(pointer["pointerTargetAlive"])
        self.assertEqual("0x7FFFFFF0", pointer["pointerTargetAddress"]["text"])
        obj = next(item for item in frame_dto["items"] if item["kind"] == "object")
        self.assertEqual("Sample", obj["className"])
        self.assertEqual(7, obj["padding"][0]["size"])
        self.assertTrue(obj["highlighted"])
        container = next(item for item in frame_dto["items"] if item["kind"] == "container")
        self.assertEqual("vector", container["containerKind"])
        self.assertEqual([3, 1], container["content"]["items"])

    def test_sections_heap_order_and_crash(self):
        heap = {
            0x01000000: Variable("a", "int", 1, 0x01000000, MemoryRegion.HEAP),
            0x01000008: Variable("c", "int", 3, 0x01000008, MemoryRegion.HEAP),
            0x01000004: Variable("b", "int", 2, 0x01000004, MemoryRegion.HEAP),
        }
        crash = CrashInfo("double_free", "二次释放", "重复释放", "detail", "p", 0x01000000)
        step = ExecutionStep(7, "crash", [StackFrame("main")], heap=heap, crash=crash)
        dto = build_memory_dto(
            step, AppSettings(layout="unified", seg_mode="detailed"), 4,
            ["main", "helper"],
        )
        self.assertEqual(
            [0x01000008, 0x01000004, 0x01000000],
            [item["address"]["value"] for item in dto["step"]["heap"]],
        )
        self.assertEqual(
            ["code", "literal", "data", "bss", "heap", "stack"],
            [section["key"] for section in dto["step"]["sections"]],
        )
        self.assertEqual("0x01000000", dto["step"]["crash"]["ptrValue"]["text"])
        json.loads(serialize_memory_state(step, AppSettings(seg_mode="detailed"), 4, ["main"]))


if __name__ == "__main__":
    unittest.main()
