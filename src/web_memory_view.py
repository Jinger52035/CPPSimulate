"""Embedded local web view for the memory visualization UI."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from .memory_serializer import serialize_memory_state
from .web_bridge import MemoryWebBridge

try:
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineCore import (
        QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_IMPORT_ERROR = None
except ImportError as exc:
    QWebChannel = None
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineSettings = None
    QWebEngineView = None
    WEBENGINE_IMPORT_ERROR = exc


class RestrictedWebPage(QWebEnginePage if QWebEnginePage else object):
    def __init__(self, profile, resource_root: Path, parent=None):
        if QWebEnginePage:
            super().__init__(profile, parent)
        self._resource_root = resource_root.resolve()

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if url.scheme() == "about" and url.toString() == "about:blank":
            return True
        if url.scheme() != "file":
            return False
        try:
            candidate = Path(url.toLocalFile()).resolve()
            candidate.relative_to(self._resource_root)
            return True
        except (OSError, ValueError):
            return False

    def createWindow(self, _window_type):
        return None


class WebMemoryView(QWidget):
    readyChanged = pyqtSignal(bool)
    errorOccurred = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._revision = 0
        self._last_step = None
        self._function_names = []
        self._stack = QStackedWidget(self)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._loading = QLabel("正在加载内存可视化界面...")
        self._loading.setObjectName("memoryLoading")
        self._loading.setWordWrap(True)
        self._loading.setStyleSheet(
            "QLabel#memoryLoading { padding: 24px; color: #768390; "
            "background: #1C2128; border: 1px solid #30363D; font-size: 13px; }"
        )
        self._stack.addWidget(self._loading)
        self._error_page, self._error_label = self._build_error_page()
        self._stack.addWidget(self._error_page)

        initial_state = serialize_memory_state(None, settings, self._revision)
        self._bridge = MemoryWebBridge(initial_state, self)
        self._bridge.readyChanged.connect(self._on_ready_changed)
        self._bridge.errorReported.connect(self._show_error)
        self._view = None
        self._profile = None
        self._page = None
        self._channel = None
        self._resource_root = self._resolve_resource_root()
        self._initialize_webengine()

    def _build_error_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch()
        page.setObjectName("memoryErrorPage")
        page.setStyleSheet(
            "QWidget#memoryErrorPage { background: #1C2128; border: 1px solid #30363D; }"
        )
        title = QLabel("内存可视化页面加载失败")
        title.setStyleSheet(
            "color: #FFAAA5; background: #30262A; border: 1px solid #713535; "
            "border-left: 3px solid #E5534B; border-radius: 5px; "
            "padding: 10px 12px; font-size: 15px; font-weight: 600;"
        )
        label = QLabel()
        label.setWordWrap(True)
        label.setStyleSheet("color: #ADBAC7; padding: 12px 0; line-height: 1.5;")
        retry = QPushButton("重试加载")
        retry.setStyleSheet(
            "QPushButton { background: #343B45; color: #CDD9E5; border: 1px solid #444C56; "
            "border-radius: 5px; padding: 6px 12px; font-weight: 600; } "
            "QPushButton:hover { background: #373E47; } "
            "QPushButton:focus { border: 2px solid #539BF5; }"
        )
        retry.clicked.connect(self.retry_load)
        layout.addWidget(title)
        layout.addWidget(label)
        layout.addWidget(retry)
        layout.addStretch()
        return page, label

    @staticmethod
    def _resolve_resource_root() -> Path:
        if hasattr(sys, "_MEIPASS"):
            bundled = Path(sys._MEIPASS) / "src" / "web"
            if bundled.exists():
                return bundled
        return Path(__file__).resolve().parent / "web"

    def _initialize_webengine(self):
        if WEBENGINE_IMPORT_ERROR is not None:
            self._show_error(
                "缺少 PyQt6-WebEngine。请运行 python -m pip install -r requirements.txt\n"
                f"{WEBENGINE_IMPORT_ERROR}"
            )
            return
        required = ["index.html", "styles.css", "app.js"]
        missing = [name for name in required if not (self._resource_root / name).is_file()]
        if missing:
            self._show_error(f"缺少 Web 资源: {', '.join(missing)}\n目录: {self._resource_root}")
            return

        self._profile = QWebEngineProfile(self)
        self._profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self._profile.downloadRequested.connect(lambda item: item.cancel())
        self._page = RestrictedWebPage(self._profile, self._resource_root, self)
        settings = self._page.settings()
        attrs = QWebEngineSettings.WebAttribute
        toggles = {
            "JavascriptEnabled": True,
            "LocalContentCanAccessFileUrls": True,
            "LocalContentCanAccessRemoteUrls": False,
            "JavascriptCanOpenWindows": False,
            "JavascriptCanAccessClipboard": False,
            "PluginsEnabled": False,
            "FullScreenSupportEnabled": False,
            "PdfViewerEnabled": False,
            "LocalStorageEnabled": False,
        }
        for name, enabled in toggles.items():
            if hasattr(attrs, name):
                settings.setAttribute(getattr(attrs, name), enabled)

        self._channel = QWebChannel(self._page)
        self._channel.registerObject("memoryBridge", self._bridge)
        self._page.setWebChannel(self._channel)
        self._view = QWebEngineView()
        self._view.setPage(self._page)
        self._view.loadFinished.connect(self._on_load_finished)
        self._page.renderProcessTerminated.connect(self._on_render_process_terminated)
        self._stack.addWidget(self._view)
        self._stack.setCurrentWidget(self._loading)
        self._view.setUrl(QUrl.fromLocalFile(str(self._resource_root / "index.html")))

    def set_state(self, step, settings, function_names=()) -> None:
        self._last_step = step
        self._settings = settings
        self._function_names = list(function_names)
        self._revision += 1
        state = serialize_memory_state(
            step, settings, self._revision, self._function_names
        )
        self._bridge.update_state(state)

    def retry_load(self) -> None:
        if self._view is None:
            self._initialize_webengine()
            return
        self._bridge.reset_ready()
        self._stack.setCurrentWidget(self._loading)
        self._view.reload()

    def _on_load_finished(self, succeeded: bool) -> None:
        if not succeeded:
            self._show_error(f"无法加载本地页面: {self._resource_root / 'index.html'}")

    def _on_ready_changed(self, ready: bool) -> None:
        if ready and self._view is not None:
            self._stack.setCurrentWidget(self._view)
        self.readyChanged.emit(ready)

    def _on_render_process_terminated(self, status, exit_code: int) -> None:
        self._show_error(f"WebEngine 渲染进程已终止: {status.name}, code={exit_code}")

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._stack.setCurrentWidget(self._error_page)
        self.errorOccurred.emit(message)
