from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QStatusBar, QMessageBox, QApplication,
)

from ..db.database import Database
from ..services.rclone_service import RcloneService
from ..services.job_service import JobService
from ..daemon.tray_manager import TrayManager

from .remote.remote_list import RemoteListWidget
from .explorer.two_panel import TwoPanelBrowser
from .jobs.job_editor import JobListWidget
from .jobs.job_history import JobHistoryWidget
from .mount.mount_dialog import MountDialog
from .transfer.transfer_dialog import TransferDialog
from .verification.check_tool import CheckToolWidget
from .settings.preferences import PreferencesDialog
from .common.styles import apply_theme


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database.get_instance()
        self.rclone = RcloneService()
        self.job_service = JobService(self.db)
        self.tray = TrayManager(self)

        self._setup_ui()
        self._connect_signals()
        self._check_rclone()

    def _setup_ui(self):
        self.setWindowTitle("Rclone GUI")
        self.setMinimumSize(1000, 650)
        apply_theme(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        self._sidebar = QWidget()
        self._sidebar.setMaximumWidth(180)
        sb_layout = QVBoxLayout(self._sidebar)
        sb_layout.setContentsMargins(4, 8, 4, 8)
        sb_layout.setSpacing(2)

        sb_layout.addWidget(self._make_sidebar_btn("Remotos", 0))
        sb_layout.addWidget(self._make_sidebar_btn("Explorador", 1))
        sb_layout.addWidget(self._make_sidebar_btn("Jobs", 2))
        sb_layout.addWidget(self._make_sidebar_btn("Histórico", 3))
        sb_layout.addWidget(self._make_sidebar_btn("Montagens", 4))
        sb_layout.addWidget(self._make_sidebar_btn("Verificação", 5))
        sb_layout.addWidget(self._make_sidebar_btn("Transferir", 6))
        sb_layout.addStretch()
        sb_layout.addWidget(self._make_sidebar_btn("Preferências", 7))

        layout.addWidget(self._sidebar)

        # Content area
        self._stack = QStackedWidget()

        from PySide6.QtWidgets import QWidget as W
        self._pages: list[W] = []

        page0 = RemoteListWidget(self.rclone)
        self._pages.append(page0)

        page1 = TwoPanelBrowser(self.rclone)
        self._pages.append(page1)

        page2 = JobListWidget(self.job_service)
        self._pages.append(page2)

        page3 = JobHistoryWidget(self.job_service)
        self._pages.append(page3)

        from .mount.mount_dialog import MountDialog
        page4 = self._make_mount_page()
        self._pages.append(page4)

        page5 = CheckToolWidget(self.rclone)
        self._pages.append(page5)

        page6 = self._make_transfer_page()
        self._pages.append(page6)

        page7 = self._make_prefs_page()
        self._pages.append(page7)

        for p in self._pages:
            self._stack.addWidget(p)
        layout.addWidget(self._stack)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._version_label = QLabel("")
        self._status.addPermanentWidget(self._version_label)

        # Start at page 0
        self._stack.setCurrentIndex(0)

    def _make_sidebar_btn(self, text: str, page: int) -> QPushButton:
        btn = QPushButton(text)
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton { text-align: left; padding: 8px 12px;
                          border: none; border-radius: 4px;
                          font-size: 13px; }
            QPushButton:hover { background-color: #313244; }
            QPushButton:pressed { background-color: #45475a; }
        """)
        btn.clicked.connect(lambda: self._stack.setCurrentIndex(page))
        return btn

    def _connect_signals(self):
        self.tray.show_window_requested.connect(self.show)
        self.tray.quit_requested.connect(self._quit)

    def _check_rclone(self):
        version = self.rclone.check_version()
        if version:
            self._version_label.setText(f"rclone {version.split()[1] if len(version.split()) > 1 else ''}")
            self._status.showMessage("rclone encontrado", 3000)
            self._pages[0].refresh()  # remote list
            remotes = self.rclone.list_remotes()
            self._pages[1].set_remotes(remotes)
        else:
            self._version_label.setText("rclone não encontrado")
            self._status.showMessage("ERRO: rclone não encontrado no PATH", 10000)
            QMessageBox.critical(
                self, "rclone não encontrado",
                "O binário 'rclone' não foi encontrado no PATH.\n\n"
                "Instale o rclone para usar esta aplicação:\n"
                "https://rclone.org/install/\n\n"
                "Ou configure o caminho manualmente em Preferências."
            )

    def _make_mount_page(self) -> QWidget:
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
        p = QWidget()
        l = QVBoxLayout(p)
        l.addWidget(QLabel("Gerenciamento de montagens"))
        l.addWidget(QLabel("Selecione um remoto no explorador para montar."))
        l.addStretch()
        return p

    def _make_transfer_page(self) -> QWidget:
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
        p = QWidget()
        l = QVBoxLayout(p)
        l.addWidget(QLabel("Transferências Rápidas"))
        l.addWidget(QLabel("Selecione arquivos no explorador e pressione F5 (Copiar) ou F6 (Mover)."))
        l.addStretch()
        return p

    def _make_prefs_page(self) -> QWidget:
        from PySide6.QtWidgets import QPushButton, QWidget, QVBoxLayout
        p = QWidget()
        l = QVBoxLayout(p)
        btn = QPushButton("Abrir Preferências")
        btn.clicked.connect(lambda: PreferencesDialog(self.db, self).exec())
        l.addWidget(btn)
        l.addStretch()
        return p

    def showEvent(self, event):
        super().showEvent(event)
        self._pages[0].refresh()
        remotes = self.rclone.list_remotes()
        self._pages[1].set_remotes(remotes)
        if hasattr(self._pages[2], "refresh"):
            self._pages[2].refresh()

    def closeEvent(self, event):
        self.tray.cleanup()
        self.db.close()
        event.accept()

    def _quit(self):
        self.close()
