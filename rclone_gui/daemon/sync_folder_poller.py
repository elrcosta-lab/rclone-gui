from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class SyncFolderPoller(QObject):
    time_to_sync = Signal()

    def __init__(self, interval_seconds: int = 300, parent=None):
        super().__init__(parent)
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_tick)
        self._interval = interval_seconds * 1000
        self._suppressed = False

    def start(self):
        self._timer.start(self._interval)

    def stop(self):
        self._timer.stop()

    def is_running(self) -> bool:
        return self._timer.isActive()

    def set_suppressed(self, suppressed: bool):
        self._suppressed = suppressed

    def _on_tick(self):
        if not self._suppressed:
            self.time_to_sync.emit()
