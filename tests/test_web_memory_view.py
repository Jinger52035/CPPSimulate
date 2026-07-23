import json
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from src.config import AppSettings
from src.cpp_interpreter import CrashInfo, ExecutionStep, MemoryRegion, StackFrame, Variable
from src.web_memory_view import WebMemoryView


class WebMemoryViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def wait_until(self, predicate, timeout=10000):
        loop = QEventLoop()
        timer = QTimer()
        timer.setInterval(25)
        deadline = QTimer()
        deadline.setSingleShot(True)
        result = {"ok": False}

        def check():
            if predicate():
                result["ok"] = True
                loop.quit()

        timer.timeout.connect(check)
        deadline.timeout.connect(loop.quit)
        timer.start()
        deadline.start(timeout)
        check()
        if not result["ok"]:
            loop.exec()
        timer.stop()
        return result["ok"]

    def run_js(self, page, source):
        result = {"done": False, "value": None}
        page.runJavaScript(source, lambda value: result.update(done=True, value=value))
        self.assertTrue(self.wait_until(lambda: result["done"]))
        return result["value"]

    def test_load_state_and_layout_switch(self):
        settings = AppSettings(layout="split", seg_mode="standard")
        view = WebMemoryView(settings)
        view.resize(700, 500)
        view.show()
        errors = []
        view.errorOccurred.connect(errors.append)
        self.assertTrue(self.wait_until(lambda: view._bridge.is_ready), errors)

        variable = Variable("x", "int", 42, 0x7FFFFFF0, MemoryRegion.STACK)
        step = ExecutionStep(1, "declare x", [StackFrame("main", {"x": variable})])
        view.set_state(step, settings, ["main"])
        revision = view._revision
        self.assertTrue(self.wait_until(lambda: self.run_js(view._page, "document.querySelector('.visualizer')?.dataset.revision") == str(revision)))
        self.assertEqual("3", self.run_js(view._page, "String(document.querySelectorAll('.memory-section').length)"))
        self.assertEqual("1", self.run_js(view._page, "String(document.querySelectorAll('.workspace-header').length)"))
        self.assertEqual("Memory", self.run_js(view._page, "document.querySelector('.workspace-title')?.textContent"))
        self.assertEqual("Line 2", self.run_js(view._page, "document.querySelector('.workspace-step')?.textContent"))
        self.assertEqual(f"rev {revision}", self.run_js(view._page, "document.querySelector('.workspace-revision')?.textContent"))
        self.assertEqual("3", self.run_js(view._page, "String(document.querySelectorAll('.section-count').length)"))
        self.assertEqual("1", self.run_js(view._page, "document.querySelector('[data-section=\"stack\"] .section-count')?.textContent"))
        self.assertEqual("main", self.run_js(view._page, "document.querySelector('.stack-frame')?.dataset.frameId.split('-').slice(2).join('-')"))

        expected_sections = {"simple": "4", "standard": "3", "detailed": "6"}
        for layout in ("split", "unified"):
            for mode in ("simple", "standard", "detailed"):
                current = AppSettings(layout=layout, seg_mode=mode)
                view.set_state(step, current, ["main", "helper"])
                revision = view._revision
                self.assertTrue(self.wait_until(lambda: self.run_js(view._page, "document.querySelector('.visualizer')?.dataset.revision") == str(revision)))
                self.assertEqual(layout, self.run_js(view._page, "document.querySelector('.visualizer')?.dataset.layout"))
                self.assertEqual(mode, self.run_js(view._page, "document.querySelector('.visualizer')?.dataset.segMode"))
                self.assertEqual(layout.title(), self.run_js(view._page, "document.querySelector('.layout-label')?.textContent"))
                self.assertEqual(mode.title(), self.run_js(view._page, "document.querySelector('.mode-label')?.textContent"))
                self.assertEqual(expected_sections[mode], self.run_js(view._page, "String(document.querySelectorAll('.memory-section').length)"))
                self.assertEqual(expected_sections[mode], self.run_js(view._page, "String(document.querySelectorAll('.section-count').length)"))
        self.assertEqual("1", self.run_js(view._page, "String(document.querySelectorAll('.address-axis').length)"))
        self.assertFalse(errors)
        view.close()

    def test_static_web_security_contract(self):
        web_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "web")
        with open(os.path.join(web_root, "app.js"), encoding="utf-8") as source:
            app_js = source.read()
        with open(os.path.join(web_root, "index.html"), encoding="utf-8") as source:
            index_html = source.read()
        self.assertNotIn("innerHTML", app_js)
        self.assertNotIn("eval(", app_js)
        self.assertIn("default-src 'none'", index_html)
        self.assertIn("connect-src 'none'", index_html)
        self.assertNotIn("https://", index_html)
        self.assertNotIn("http://", index_html)

    def test_visual_states_pointer_crash_and_narrow_layout(self):
        settings = AppSettings(layout="split", seg_mode="standard")
        view = WebMemoryView(settings)
        view.resize(420, 520)
        view.show()
        self.assertTrue(self.wait_until(lambda: view._bridge.is_ready))

        target = Variable("x", "int", 99, 0x7FFFFFF0, MemoryRegion.STACK)
        pointer = Variable("p", "int*", target.address, 0x7FFFFFF8, MemoryRegion.STACK, 8, 8, True)
        caller = StackFrame("main", {"x": target, "p": pointer})
        callee = StackFrame("factorial", {"n": Variable("n", "int", 1, 0x7FFFFFE0, MemoryRegion.STACK)})
        crash = CrashInfo("null_deref", "空指针解引用", "指针没有有效目标", "写入空地址会触发未定义行为。", "p", 0)
        step = ExecutionStep(3, "pointer state", [caller, callee], highlight_vars=["p"], crash=crash)
        view.set_state(step, settings, ["main", "factorial"])
        revision = view._revision
        self.assertTrue(self.wait_until(lambda: self.run_js(view._page, "document.querySelector('.visualizer')?.dataset.revision") == str(revision)))

        self.assertEqual("1", self.run_js(view._page, "String(document.querySelectorAll('.stack-frame.is-current').length)"))
        self.assertEqual("true", self.run_js(view._page, "document.querySelector('.stack-frame.is-current')?.getAttribute('aria-current')"))
        self.assertEqual("0x7FFFFFF0", self.run_js(view._page, "document.querySelector('[data-name=\"p\"]')?.dataset.pointerTarget"))
        self.assertEqual("0", self.run_js(view._page, "String(document.querySelector('[data-name=\"p\"]')?.tabIndex)"))
        self.run_js(view._page, "document.querySelector('[data-name=\"p\"]')?.dispatchEvent(new FocusEvent('focus')); true")
        self.assertEqual("1", self.run_js(view._page, "String(document.querySelectorAll('.pointer-target-active').length)"))
        self.run_js(view._page, "document.querySelector('[data-name=\"p\"]')?.dispatchEvent(new FocusEvent('blur')); true")
        self.assertEqual("0", self.run_js(view._page, "String(document.querySelectorAll('.pointer-target-active').length)"))
        self.assertEqual("空指针解引用", self.run_js(view._page, "document.querySelector('.crash-title')?.childNodes[0]?.textContent"))
        self.assertEqual("p = 0x00000000", self.run_js(view._page, "document.querySelector('.crash-pointer')?.textContent.trim()"))
        self.assertEqual("true", self.run_js(view._page, "String(document.querySelector('.memory-scroll').scrollWidth > document.querySelector('.memory-scroll').clientWidth)"))
        self.assertEqual("0", self.run_js(view._page, "String(document.querySelectorAll('.variable-card').length - document.querySelectorAll('.variable-card[data-address][data-kind][data-name]').length)"))
        view.close()


if __name__ == "__main__":
    unittest.main()
