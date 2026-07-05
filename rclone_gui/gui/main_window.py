from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QProcess
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QStatusBar, QMessageBox, QApplication,
)

from ..db.database import Database
from ..services.rclone_service import RcloneService
from ..services.job_service import JobService
from ..services.sync_folder_service import SyncFolderService
from ..daemon.tray_manager import TrayManager

from .remote.remote_list import RemoteListWidget
from .explorer.two_panel import TwoPanelBrowser
from .jobs.job_editor import JobListWidget
from .jobs.job_history import JobHistoryWidget
from .mount.mount_dialog import MountDialog
from .transfer.transfer_dialog import TransferDialog
from .verification.check_tool import CheckToolWidget
from .settings.preferences import PreferencesDialog
from .sync_folders.sync_folder_list import SyncFolderList
from .common.styles import apply_theme


class MainWindow(QMainWindow):
    def __init__(self, rclone: Optional[RcloneService] = None,
                 job_service: Optional[JobService] = None,
                 sync_folder_service: Optional[SyncFolderService] = None,
                 tray: Optional[TrayManager] = None):
        super().__init__()
        self.db = Database.get_instance()
        self.rclone = rclone or RcloneService()
        self.job_service = job_service or JobService(self.db)
        self.sync_folder_service = sync_folder_service or SyncFolderService(self.db)
        self.tray = tray or TrayManager(self)

        self._setup_ui()
        self._connect_signals()
        self._check_rclone()
        self._first_run_check()

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
        sb_layout.addWidget(self._make_sidebar_btn("Sync Folders", 5))
        sb_layout.addWidget(self._make_sidebar_btn("Verificação", 6))
        sb_layout.addWidget(self._make_sidebar_btn("Transferir", 7))
        sb_layout.addStretch()
        sb_layout.addWidget(self._make_sidebar_btn("Preferências", 8))

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

        page5 = SyncFolderList(self.rclone, self.sync_folder_service)
        self._pages.append(page5)

        page6 = CheckToolWidget(self.rclone)
        self._pages.append(page6)

        page7 = self._make_transfer_page()
        self._pages.append(page7)

        page8 = self._make_prefs_page()
        self._pages.append(page8)

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
            self._pages[0].refresh()
            remotes = self.rclone.list_remotes()
            self._pages[1].set_remotes(remotes)
        else:
            self._version_label.setText("rclone não encontrado")
            self._status.showMessage("ERRO: rclone não encontrado no PATH", 10000)
            reply = QMessageBox.question(
                self, "rclone não encontrado",
                "O rclone não está instalado no sistema.\n\n"
                "Deseja instalar o rclone agora?\n\n"
                "Isso executará o script oficial de instalação:\n"
                "  curl https://rclone.org/install.sh | sudo bash",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._install_rclone()

    def _install_rclone(self):
        self._status.showMessage("Instalando rclone...")
        self._process = QProcess(self)
        self._process.setProgram("bash")
        self._process.setArguments(["-c", "curl https://rclone.org/install.sh | sudo bash"])
        self._process.finished.connect(self._on_rclone_install_finished)
        self._process.errorOccurred.connect(self._on_rclone_install_error)
        self._process.start()

    def _on_rclone_install_finished(self, exit_code: int):
        if exit_code == 0:
            QMessageBox.information(
                self, "Instalação concluída",
                "rclone foi instalado com sucesso!\n\n"
                "Reinicie a aplicação para usar o rclone.",
            )
            self._status.showMessage("rclone instalado. Reinicie a aplicação.", 10000)
        else:
            QMessageBox.critical(
                self, "Erro na instalação",
                "A instalação do rclone falhou.\n\n"
                "Tente instalar manualmente:\n"
                "  curl https://rclone.org/install.sh | sudo bash\n\n"
                "Ou veja: https://rclone.org/install/",
            )
            self._status.showMessage("Falha na instalação do rclone", 5000)

    def _on_rclone_install_error(self, error):
        QMessageBox.critical(
            self, "Erro na instalação",
            f"Não foi possível iniciar a instalação.\n{error}\n\n"
            "Tente instalar manualmente:\n"
            "  curl https://rclone.org/install.sh | sudo bash",
        )
        self._status.showMessage("Falha ao iniciar instalação do rclone", 5000)

    def _first_run_check(self):
        if self.db.get_config("first_run_completed", 0):
            return
        is_test = os.environ.get("QT_QPA_PLATFORM") == "offscreen"
        sync_dir = Path.home() / "RcloneSync"
        sync_dir.mkdir(parents=True, exist_ok=True)
        if not is_test:
            msg = QMessageBox(self)
            msg.setWindowTitle("Bem-vindo ao Rclone GUI")
            msg.setText(
                "Primeira execução detectada!\n\n"
                "A pasta ~/RcloneSync/ foi criada para sincronização bidirecional "
                "com seus remotos.\n\n"
                "Você pode configurar pastas de sincronização na página "
                "'Sync Folders' no menu lateral.\n\n"
                "Recomendado:\n"
                "1. Configure seus remotos em 'Remotos'\n"
                "2. Vá em 'Sync Folders' e adicione uma pasta\n\n"
                "Você pode alterar as configurações em Preferências a qualquer momento."
            )
            msg.exec()
        self.db.set_config("first_run_completed", 1)

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
        event.accept()

    def _quit(self):
        self.close()
