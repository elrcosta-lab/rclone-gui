from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class NotificationService(QObject):
    def notify(self, title: str, message: str, icon: str = "info"):
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            icon_map = {"info": QSystemTrayIcon.Information,
                        "warning": QSystemTrayIcon.Warning,
                        "error": QSystemTrayIcon.Critical,
                        "success": QSystemTrayIcon.Information}
            QApplication.instance().alert(None, 0)
        except Exception:
            pass
