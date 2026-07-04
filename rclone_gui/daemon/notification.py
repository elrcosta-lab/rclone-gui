from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


AUTOSTART_DESKTOP = """[Desktop Entry]
Type=Application
Name=Rclone GUI Daemon
Comment=Background daemon for Rclone GUI
Exec={executable} --daemon
Terminal=false
X-GNOME-Autostart-enabled=true
"""


def setup_autostart():
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop = autostart_dir / "rclone-gui-daemon.desktop"
    desktop.write_text(AUTOSTART_DESKTOP.format(executable="rclone-gui"))
    return True


def remove_autostart():
    desktop = Path.home() / ".config" / "autostart" / "rclone-gui-daemon.desktop"
    if desktop.exists():
        desktop.unlink()
    return True


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
