import unittest

from PyQt6.QtCore import QCoreApplication

from src.web_bridge import MemoryWebBridge


class WebBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_ready_cache_and_updates(self):
        bridge = MemoryWebBridge('{"revision":0}')
        emitted = []
        readiness = []
        bridge.stateChanged.connect(emitted.append)
        bridge.readyChanged.connect(readiness.append)
        bridge.update_state('{"revision":1}')
        self.assertEqual([], emitted)
        self.assertEqual('{"revision":1}', bridge.getInitialState())
        bridge.ready("1")
        self.assertEqual([True], readiness)
        bridge.update_state('{"revision":2}')
        self.assertEqual(['{"revision":2}'], emitted)
        bridge.reset_ready()
        self.assertEqual([True, False], readiness)

    def test_incompatible_version_and_error_truncation(self):
        bridge = MemoryWebBridge("{}")
        errors = []
        bridge.errorReported.connect(errors.append)
        bridge.ready("2")
        self.assertFalse(bridge.is_ready)
        self.assertIn("不兼容", errors[-1])
        bridge.reportError("render", "x" * 1200)
        self.assertLessEqual(len(errors[-1]), 1008)


if __name__ == "__main__":
    unittest.main()
