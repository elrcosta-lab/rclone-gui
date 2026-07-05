from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QApplication


class TrayManager(QObject):
    show_window_requested = Signal()
    sync_folder_triggered = Signal(int)
    quit_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._mount_submenu: Optional[QMenu] = None
        self._sync_folder_submenu: Optional[QMenu] = None
        self._status = "ok"  # ok, busy, error

    def setup(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False

        icon = self._create_icon()
        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("Rclone GUI — Iniciando...")
        self._build_menu()
        self.tray.show()
        return True

    def _create_icon(self) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(self._status_color())
        return QIcon(pixmap)

    def _status_color(self):
        from PySide6.QtGui import QColor
        return {"ok": QColor(76, 175, 80), "busy": QColor(255, 193, 7),
                "error": QColor(244, 67, 54)}.get(self._status, QColor(128, 128, 128))

    def _build_menu(self):
        self._menu = QMenu()

        open_action = QAction("Abrir Rclone GUI", self._menu)
        open_action.triggered.connect(self.show_window_requested.emit)
        self._menu.addAction(open_action)

        self._menu.addSeparator()

        self._mount_submenu = QMenu("Montagens", self._menu)
        self._menu.addMenu(self._mount_submenu)
        self._update_mount_menu([])

        self._sync_folder_submenu = QMenu("Sync Folders", self._menu)
        self._menu.addMenu(self._sync_folder_submenu)
        self._update_sync_folder_menu([])

        self._menu.addSeparator()

        quit_action = QAction("Sair", self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)

        self.tray.setContextMenu(self._menu)

    def _update_mount_menu(self, mounts: list[str]):
        self._mount_submenu.clear()
        if not mounts:
            self._mount_submenu.addAction("Nenhuma montagem ativa")
        else:
            for m in mounts:
                self._mount_submenu.addAction(f"Abrir {m}")

    def _update_sync_folder_menu(self, folders: list[tuple[int, str, str]]):
        self._sync_folder_submenu.clear()
        if not folders:
            self._sync_folder_submenu.addAction("Nenhuma pasta configurada")
        else:
            for fid, name, status in folders:
                label = f"{'🟢' if status == 'active' else '🔴'} {name}"
                act = self._sync_folder_submenu.addAction(label)
                act.setData(fid)
                act.triggered.connect(
                    lambda checked, fid=fid: self.sync_folder_triggered.emit(fid)
                )

    def set_sync_folders(self, folders: list[tuple[int, str, str]]):
        self._update_sync_folder_menu(folders)

    def set_status(self, status: str, message: str = ""):
        self._status = status
        if self.tray:
            self.tray.setIcon(self._create_icon())
            self.tray.setToolTip(f"Rclone GUI — {message or status}")

    def set_mounts(self, mounts: list[str]):
        self._update_mount_menu(mounts)

    def cleanup(self):
        if self.tray:
            self.tray.hide()
            self.tray = None
