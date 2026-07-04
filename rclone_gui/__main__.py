from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .db.database import Database
from .gui.main_window import MainWindow


def run_gui():
    app = QApplication(sys.argv)
    app.setApplicationName("Rclone GUI")
    app.setOrganizationName("rclone-gui")
    app.setQuitOnLastWindowClosed(False)

    db = Database.get_instance()
    db.connect()

    window = MainWindow()
    window.show()

    result = app.exec()
    db.close()
    sys.exit(result)


def main():
    args = set(sys.argv[1:])
    if "--daemon" in args:
        from .daemon.daemon_app import main as daemon_main
        daemon_main()
    else:
        run_gui()


if __name__ == "__main__":
    main()
