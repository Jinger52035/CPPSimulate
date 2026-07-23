import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu")

from PyQt6.QtCore import QEventLoop, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from src.main_window import EXAMPLE_CURRICULUM, MainWindow


class MainWindowWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def wait_until(self, predicate, timeout=10000):
        loop = QEventLoop()
        poll = QTimer()
        poll.setInterval(25)
        deadline = QTimer()
        deadline.setSingleShot(True)
        done = {"value": False}

        def check():
            if predicate():
                done["value"] = True
                loop.quit()

        poll.timeout.connect(check)
        deadline.timeout.connect(loop.quit)
        poll.start()
        deadline.start(timeout)
        check()
        if not done["value"]:
            loop.exec()
        poll.stop()
        return done["value"]

    def test_examples_and_toolbar_component_contract(self):
        window = MainWindow()
        self.assertEqual(8, window._file_list.topLevelItemCount())
        self.assertEqual("20", window._example_count.text())
        expected_counts = [2, 3, 5, 3, 1, 3, 2]
        leaf_paths = []
        for group_index, (directory, label, filenames) in enumerate(EXAMPLE_CURRICULUM):
            group = window._file_list.topLevelItem(group_index)
            self.assertEqual(label, group.text(0))
            self.assertTrue(group.isExpanded())
            self.assertFalse(group.flags() & Qt.ItemFlag.ItemIsSelectable)
            self.assertIsNone(group.data(0, Qt.ItemDataRole.UserRole))
            self.assertEqual(expected_counts[group_index], group.childCount())
            self.assertEqual(len(filenames), group.childCount())
            for child_index, filename in enumerate(filenames):
                item = group.child(child_index)
                path = Path(item.data(0, Qt.ItemDataRole.UserRole))
                self.assertTrue(path.is_file())
                self.assertEqual(directory, path.parent.name)
                self.assertEqual(filename, path.name)
                self.assertTrue(item.text(0).startswith(filename.split("_", 1)[0] + "  "))
                leaf_paths.append(path)

        leetcode = window._file_list.topLevelItem(7)
        self.assertEqual("LeetCode", leetcode.text(0))
        self.assertTrue(leetcode.isExpanded())
        self.assertFalse(leetcode.flags() & Qt.ItemFlag.ItemIsSelectable)
        self.assertIsNone(leetcode.data(0, Qt.ItemDataRole.UserRole))
        array = leetcode.child(0)
        self.assertEqual("array", array.text(0))
        self.assertTrue(array.isExpanded())
        self.assertFalse(array.flags() & Qt.ItemFlag.ItemIsSelectable)
        self.assertIsNone(array.data(0, Qt.ItemDataRole.UserRole))
        leetcode_file = array.child(0)
        self.assertEqual("0001", leetcode_file.text(0))
        leetcode_path = Path(leetcode_file.data(0, Qt.ItemDataRole.UserRole))
        self.assertEqual(Path("leetcode/array/0001.cpp"), leetcode_path.relative_to(Path(window._examples_dir)))
        leaf_paths.append(leetcode_path)

        self.assertEqual(20, len(leaf_paths))
        self.assertEqual(20, len(set(leaf_paths)))

        expected = {
            "openButton": "secondary",
            "runButton": "primary",
            "previousButton": "secondary",
            "stepButton": "secondary",
            "autoButton": "toggle",
            "resetButton": "quiet",
            "settingsButton": "quiet",
        }
        buttons = {button.objectName(): button for button in window.findChildren(QPushButton)}
        for name, variant in expected.items():
            self.assertIn(name, buttons)
            self.assertEqual(variant, buttons[name].property("variant"))

        icon_only = ["runButton", "previousButton", "stepButton", "autoButton", "resetButton"]
        for name in icon_only:
            button = buttons[name]
            self.assertEqual("", button.text())
            self.assertTrue(button.property("iconOnly"))
            self.assertFalse(button.icon().isNull())
            self.assertTrue(button.toolTip())
            self.assertTrue(button.accessibleName())

        file_bar = window.findChild(QWidget, "fileBar")
        self.assertIsNotNone(file_bar)
        self.assertIs(buttons["openButton"].parentWidget(), file_bar)
        self.assertFalse(buttons["openButton"].icon().isNull())

        auto = buttons["autoButton"]
        self.assertFalse(auto.isChecked())
        self.assertEqual("自动播放", auto.accessibleName())
        auto.setChecked(True)
        self.assertEqual("暂停自动播放", auto.accessibleName())
        window._reset()
        self.assertFalse(auto.isChecked())
        self.assertEqual("自动播放", auto.accessibleName())
        window.close()

    def test_native_execution_updates_web_memory(self):
        window = MainWindow()
        window.resize(960, 620)
        window.show()
        self.assertTrue(self.wait_until(lambda: window._memory_view._bridge.is_ready))
        self.assertGreater(window._memory_view.width(), 0)
        self.assertGreater(window._memory_view.height(), 0)
        pointer_group = window._file_list.topLevelItem(2)
        pointer_example = pointer_group.child(0)
        source = Path(pointer_example.data(0, Qt.ItemDataRole.UserRole))
        self.assertEqual("06_pointer_address.cpp", source.name)
        window._on_example_clicked(pointer_example, 0)
        self.assertEqual(source.read_text(encoding="utf-8"), window._editor.toPlainText())
        window._run_code()
        self.assertGreater(window._interpreter.total_steps(), 0)
        while window._current_step + 1 < window._interpreter.total_steps():
            window._step_forward()
        self.assertIn("x after *p=99: 99", window._output_box.toPlainText())
        expected_revision = window._memory_view._revision
        rendered = {"value": None}
        window._memory_view._page.runJavaScript(
            "document.querySelector('.visualizer')?.dataset.revision",
            lambda value: rendered.update(value=value),
        )
        self.assertTrue(self.wait_until(lambda: rendered["value"] == str(expected_revision)))
        window.close()


if __name__ == "__main__":
    unittest.main()
