from __future__ import annotations

import os

from PySide6.QtCore import QObject, QTimer, Signal
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self._callback(event.src_path)


class SyncFolderWatcher(QObject):
    changes_detected = Signal()
    _change_requested = Signal()

    def __init__(self, watch_path: str, debounce_seconds: int = 5,
                 ignore_patterns: list[str] = None, parent=None):
        super().__init__(parent)
        self._path = watch_path
        self._debounce_ms = debounce_seconds * 1000
        self._observer = Observer()
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounced_change)
        self._change_requested.connect(self._restart_timer)
        self._ignore_patterns = ignore_patterns or [
            ".~lock", ".rclonelck", ".binaysynclck"
        ]
        self._handler = _DebouncedHandler(self._on_file_event)
        self._running = False

    def _on_file_event(self, src_path: str):
        name = os.path.basename(src_path)
        for pattern in self._ignore_patterns:
            if pattern.startswith(".") and name.startswith("."):
                return
            if pattern in name:
                return
        self._change_requested.emit()

    def _restart_timer(self):
        self._debounce_timer.start(self._debounce_ms)

    def _on_debounced_change(self):
        self.changes_detected.emit()

    def start(self):
        if self._running:
            return
        self._observer.schedule(self._handler, self._path, recursive=True)
        self._observer.start()
        self._running = True

    def stop(self):
        self._debounce_timer.stop()
        if self._running:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._running = False

    def is_running(self) -> bool:
        return self._running
