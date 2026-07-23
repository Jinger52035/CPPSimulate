"""Minimal QWebChannel bridge for the memory visualizer."""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

CLIENT_VERSION = "1"


class MemoryWebBridge(QObject):
    stateChanged = pyqtSignal(str)
    readyChanged = pyqtSignal(bool)
    errorReported = pyqtSignal(str)

    def __init__(self, initial_state: str, parent=None):
        super().__init__(parent)
        self._latest_state = initial_state
        self._ready = False
        self._client_version = ""

    @property
    def is_ready(self) -> bool:
        return self._ready

    def update_state(self, state_json: str) -> None:
        self._latest_state = state_json
        if self._ready:
            self.stateChanged.emit(state_json)

    def reset_ready(self) -> None:
        if self._ready:
            self._ready = False
            self.readyChanged.emit(False)

    @pyqtSlot(str)
    def ready(self, client_version: str) -> None:
        self._client_version = client_version
        compatible = client_version == CLIENT_VERSION
        if not compatible:
            self.errorReported.emit(
                f"可视化协议版本不兼容: desktop={CLIENT_VERSION}, web={client_version}"
            )
            return
        if not self._ready:
            self._ready = True
            self.readyChanged.emit(True)

    @pyqtSlot(result=str)
    def getInitialState(self) -> str:
        return self._latest_state

    @pyqtSlot(str, str)
    def reportError(self, phase: str, message: str) -> None:
        safe_phase = (phase or "frontend")[:40]
        safe_message = (message or "未知错误")[:1000]
        self.errorReported.emit(f"{safe_phase}: {safe_message}")
