from __future__ import annotations

import os
import signal
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .db.database import Database
from .gui.main_window import MainWindow
from .services.job_service import JobService
from .services.rclone_service import RcloneService
from .services.sync_folder_service import SyncFolderService
from .daemon.daemon_app import RCDManager, Scheduler
from .daemon.sync_folder_manager import SyncFolderManager
from .daemon.tray_manager import TrayManager


class RcloneGUI:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Rclone GUI")
        self.app.setOrganizationName("rclone-gui")
        self.app.setQuitOnLastWindowClosed(False)

        self.db = Database.get_instance()
        self.db.connect()
        self.rclone = RcloneService()
        self.job_service = JobService(self.db)
        self.sync_folder_service = SyncFolderService(self.db)
        self.sync_manager = SyncFolderManager(self.sync_folder_service)
        self.scheduler = Scheduler(self.job_service)
        self.rcd = RCDManager(
            port=self.db.get_config("rcd_port", 5572),
            user=self.db.get_config("rcd_user", "rgui"),
            password=self.db.get_config("rcd_pass_hash", ""),
        )
        self.tray = TrayManager()
        self._window: Optional[MainWindow] = None

    def start(self):
        self.rcd.start()
        self.sync_manager.start_all()

        self._heartbeat = QTimer()
        self._heartbeat.timeout.connect(self._heartbeat_tick)
        self._heartbeat.start(30000)

        self.tray.setup()
        self.tray.show_window_requested.connect(self._open_window)
        self.tray.sync_folder_triggered.connect(self._sync_folder)
        self.tray.quit_requested.connect(self._quit)

        if not self.db.get_config("first_run_completed", 0):
            self._open_window()

    def _open_window(self):
        if self._window is None:
            self._window = MainWindow(
                rclone=self.rclone,
                job_service=self.job_service,
                sync_folder_service=self.sync_folder_service,
                tray=self.tray,
            )
        self._window.setWindowState(
            self._window.windowState() & ~self._window.windowState().Minimized
        )
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _sync_folder(self, folder_id: int):
        self.sync_folder_service.sync_now(folder_id)

    def _heartbeat_tick(self):
        self.scheduler.scan_and_execute()
        if not self.rcd.is_healthy():
            self.rcd.stop()
            self.rcd.start()
        folders = self.sync_folder_service.get_enabled()
        statuses = [
            (f.id, f.name, "active" if f.enabled else "inactive")
            for f in folders
        ]
        self.tray.set_sync_folders(statuses)

    def _quit(self):
        if self._window:
            self._window.close()
        self._heartbeat.stop()
        self.sync_manager.stop_all()
        self.tray.cleanup()
        self.rcd.stop()
        self.db.close()
        self.app.quit()

    def run(self):
        signal.signal(signal.SIGINT, lambda s, f: self._quit())
        signal.signal(signal.SIGTERM, lambda s, f: self._quit())
        self.start()
        return self.app.exec()


def run_gui():
    app = RcloneGUI()
    app.run()


def main():
    args = set(sys.argv[1:])
    if "--daemon" in args:
        from .daemon.daemon_app import main as daemon_main
        daemon_main()
    else:
        run_gui()


if __name__ == "__main__":
    main()
