from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFormLayout, QGroupBox,
    QCheckBox, QDialogButtonBox, QStackedWidget, QWidget,
    QListWidget, QMessageBox, QProgressBar,
)
from PySide6.QtCore import QProcess

from ..common.rclone_process import RcloneProcess
from ...services.rclone_service import RcloneService


class ConfigWizard(QDialog):
    def __init__(self, rclone: RcloneService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rclone = rclone
        self._backends = RcloneService.load_backends_catalog()
        self._selected_backend = None
        self._auth_process = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Adicionar Remoto")
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_search_page())
        self._stack.addWidget(self._build_form_page())
        self._stack.addWidget(self._build_auth_page())
        layout.addWidget(self._stack)

        buttons = QDialogButtonBox()
        self._prev_btn = buttons.addButton("Voltar", QDialogButtonBox.ActionRole)
        self._next_btn = buttons.addButton("Próximo", QDialogButtonBox.ActionRole)
        self._save_btn = buttons.addButton("Salvar", QDialogButtonBox.AcceptRole)
        self._cancel_btn = buttons.addButton(QDialogButtonBox.Cancel)

        self._prev_btn.clicked.connect(self._go_prev)
        self._next_btn.clicked.connect(self._go_next)
        self._save_btn.clicked.connect(self._save)
        self._cancel_btn.clicked.connect(self.reject)
        self._update_buttons()

        layout.addWidget(buttons)
        self._stack.setCurrentIndex(0)

    def _build_search_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        search_label = QLabel("Buscar tipo de armazenamento:")
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Ex: Google Drive, S3, SFTP...")
        self._search_input.textChanged.connect(self._filter_backends)

        self._backend_list = QListWidget()
        self._backend_list.itemDoubleClicked.connect(lambda: self._go_next())
        self._populate_backends()

        layout.addWidget(search_label)
        layout.addWidget(self._search_input)
        layout.addWidget(self._backend_list)
        return page

    def _build_form_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll = QWidget()
        self._form_layout = QFormLayout(scroll)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Ex: meu-google-drive")
        self._form_layout.addRow("Nome do remoto:", self._name_input)

        self._auth_btn = QPushButton("Autorizar via Navegador")
        self._form_layout.addRow(self._auth_btn)

        layout.addWidget(scroll)
        return page

    def _build_auth_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._auth_label = QLabel("Aguardando autorização...")
        self._auth_label.setAlignment(Qt.AlignCenter)
        self._auth_progress = QProgressBar()
        self._auth_progress.setRange(0, 0)
        layout.addWidget(self._auth_label)
        layout.addWidget(self._auth_progress)
        layout.addStretch()
        return page

    def _populate_backends(self, filter_text: str = ""):
        self._backend_list.clear()
        for b in self._backends:
            if filter_text.lower() in b.display_name.lower() or filter_text.lower() in b.type.lower():
                self._backend_list.addItem(f"{b.display_name} — {b.description}")

    def _filter_backends(self, text: str):
        self._populate_backends(text)

    def _go_next(self):
        idx = self._stack.currentIndex()
        if idx == 0:
            item = self._backend_list.currentItem()
            if not item:
                return
            name = item.text().split(" — ")[0]
            for b in self._backends:
                if b.display_name == name:
                    self._selected_backend = b
                    break
            if self._selected_backend and self._selected_backend.requires_oauth:
                self._stack.setCurrentIndex(2)
                self._start_auth()
            else:
                self._stack.setCurrentIndex(1)
        elif idx == 2:
            self._stack.setCurrentIndex(1)
        self._update_buttons()

    def _go_prev(self):
        idx = self._stack.currentIndex()
        if idx == 1 or (idx == 2 and self._selected_backend and self._selected_backend.requires_oauth):
            self._stack.setCurrentIndex(0)
            self._update_buttons()
        elif idx == 2:
            self._stack.setCurrentIndex(1)
            self._update_buttons()

    def _start_auth(self):
        if not self._selected_backend:
            return
        provider = self._selected_backend.oauth_provider or self._selected_backend.type
        self._auth_process = self.rclone.authorize(provider)
        self._auth_label.setText(f"Autorizando {self._selected_backend.display_name}...\n"
                                 f"Se o navegador não abrir, copie o URL manualmente.")

    def _update_buttons(self):
        idx = self._stack.currentIndex()
        self._prev_btn.setVisible(idx > 0)
        self._next_btn.setVisible(idx < 2)
        self._save_btn.setVisible(idx >= 1)

    def _save(self):
        if not self._selected_backend:
            return
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erro", "Informe um nome para o remoto.")
            return
        ok, msg = self.rclone.config_create(name, self._selected_backend.type)
        if ok:
            self.accept()
        else:
            QMessageBox.critical(self, "Erro ao salvar", msg)

    def selected_name(self) -> str:
        return self._name_input.text().strip()
