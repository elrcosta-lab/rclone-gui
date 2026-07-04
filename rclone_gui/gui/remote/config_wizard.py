from __future__ import annotations

import json
import re
from typing import Optional

from PySide6.QtCore import Qt, QProcess
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFormLayout, QGroupBox,
    QCheckBox, QDialogButtonBox, QStackedWidget, QWidget,
    QListWidget, QMessageBox, QProgressBar,
)

from ...services.rclone_service import RcloneService


class ConfigWizard(QDialog):
    def __init__(self, rclone: RcloneService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rclone = rclone
        self._backends = RcloneService.load_backends_catalog()
        self._selected_backend = None
        self._auth_process: Optional[QProcess] = None
        self._auth_output = ""
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
        self._cancel_btn.clicked.connect(self._on_cancel)

        layout.addWidget(buttons)
        self._stack.setCurrentIndex(0)
        self._update_buttons()

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

        layout.addWidget(scroll)
        return page

    def _build_auth_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._auth_label = QLabel("Clique em 'Autorizar' para conectar sua conta.")
        self._auth_label.setAlignment(Qt.AlignCenter)
        self._auth_label.setWordWrap(True)

        self._auth_url_label = QLabel("")
        self._auth_url_label.setWordWrap(True)
        self._auth_url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._auth_url_label.hide()

        self._auth_btn = QPushButton("Autorizar via Navegador")
        self._auth_btn.clicked.connect(self._start_auth)

        self._auth_progress = QProgressBar()
        self._auth_progress.setRange(0, 0)
        self._auth_progress.hide()

        self._auth_status = QLabel("")
        self._auth_status.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._auth_label)
        layout.addWidget(self._auth_url_label)
        layout.addWidget(self._auth_btn)
        layout.addWidget(self._auth_progress)
        layout.addWidget(self._auth_status)
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
                self._update_buttons()
                return
            else:
                self._stack.setCurrentIndex(1)
        elif idx == 2:
            self._stack.setCurrentIndex(1)
        self._update_buttons()

    def _go_prev(self):
        idx = self._stack.currentIndex()
        if idx == 1:
            self._stack.setCurrentIndex(0)
        elif idx == 2:
            if self._selected_backend and self._selected_backend.requires_oauth:
                self._stack.setCurrentIndex(0)
            else:
                self._stack.setCurrentIndex(1)
        self._update_buttons()

    def _start_auth(self):
        if not self._selected_backend:
            return
        provider = self._selected_backend.oauth_provider or self._selected_backend.type

        self._auth_btn.setEnabled(False)
        self._auth_btn.setText("Autorizando...")
        self._auth_progress.show()
        self._auth_status.setText("Iniciando rclone authorize...")
        self._auth_output = ""

        self._auth_process = QProcess(self)
        self._auth_process.setProgram("rclone")
        self._auth_process.setArguments(["authorize", provider])
        self._auth_process.setProcessChannelMode(QProcess.MergedChannels)
        self._auth_process.readyReadStandardOutput.connect(self._on_auth_stdout)
        self._auth_process.finished.connect(self._on_auth_finished)
        self._auth_process.start()

    def _on_auth_stdout(self):
        if not self._auth_process:
            return
        data = self._auth_process.readAllStandardOutput().data().decode()
        self._auth_output += data

        urls = re.findall(r'https?://[^\s<>"]+', data)
        if urls:
            self._auth_url_label.setText(f"URL: {urls[0]}")
            self._auth_url_label.show()
            self._auth_status.setText("Abrindo navegador... Se não abrir, copie o URL acima.")

        if "token" in self._auth_output.lower() or "response" in self._auth_output.lower():
            self._auth_status.setText("Autorização recebida! Salvando...")

    def _on_auth_finished(self, exit_code: int, _exit_status):
        self._auth_progress.hide()
        self._auth_btn.setEnabled(True)
        self._auth_btn.setText("Autorizar via Navegador")

        if exit_code == 0 and self._auth_output.strip():
            try:
                token_data = json.loads(self._auth_output.strip())
                self._auth_status.setText("Autorização concluída com sucesso!")
                self._auth_token = token_data
                self._stack.setCurrentIndex(1)
                self._update_buttons()
            except json.JSONDecodeError:
                self._auth_status.setText("Resposta inválida do rclone. Tente novamente.")
                self._auth_token = None
        else:
            self._auth_status.setText("Autorização falhou ou foi cancelada.")
            self._auth_token = None

    def _on_cancel(self):
        if self._auth_process and self._auth_process.state() == QProcess.Running:
            self._auth_process.terminate()
            if not self._auth_process.waitForFinished(2000):
                self._auth_process.kill()
        self.reject()

    def _update_buttons(self):
        idx = self._stack.currentIndex()
        is_auth_page = idx == 2
        is_search_page = idx == 0

        self._prev_btn.setVisible(idx > 0)
        self._next_btn.setVisible(is_search_page)
        self._save_btn.setVisible(idx == 1)

    def _save(self):
        if not self._selected_backend:
            return
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Erro", "Informe um nome para o remoto.")
            return

        if self._selected_backend.requires_oauth:
            if not hasattr(self, '_auth_token') or not self._auth_token:
                QMessageBox.warning(self, "Erro", "Autorize a conta primeiro.")
                return

        ok, msg = self.rclone.config_create(name, self._selected_backend.type)
        if ok:
            self.accept()
        else:
            QMessageBox.critical(self, "Erro ao salvar", msg)

    def selected_name(self) -> str:
        return self._name_input.text().strip()
