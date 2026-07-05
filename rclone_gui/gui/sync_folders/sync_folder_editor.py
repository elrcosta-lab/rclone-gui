from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QCheckBox, QGroupBox, QDialogButtonBox, QComboBox, QPushButton,
    QFileDialog, QHBoxLayout, QMessageBox, QWidget,
)

from ...models.sync_folder import SyncFolderConfig


class SyncFolderEditor(QDialog):
    def __init__(self, remote_names: list[str],
                 existing: Optional[SyncFolderConfig] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.remote_names = remote_names
        self._config = existing or SyncFolderConfig(
            name="", local_path="", remote_path="",
        )
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Pasta de Sincronização")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        general_group = QGroupBox("Geral")
        general_layout = QFormLayout(general_group)
        self._name_input = QLineEdit(self._config.name)
        general_layout.addRow("Nome:", self._name_input)
        layout.addWidget(general_group)

        path_group = QGroupBox("Caminhos")
        path_layout = QFormLayout(path_group)

        local_row = QHBoxLayout()
        self._local_input = QLineEdit(self._config.local_path)
        local_row.addWidget(self._local_input)
        browse_btn = QPushButton("...")
        browse_btn.setMaximumWidth(30)
        browse_btn.clicked.connect(self._browse_local)
        local_row.addWidget(browse_btn)
        path_layout.addRow("Pasta local:", local_row)

        remote_row = QHBoxLayout()
        self._remote_combo = QComboBox()
        self._remote_combo.setEditable(True)
        self._remote_combo.addItems(self.remote_names)
        if self._config.remote_path:
            self._remote_combo.setCurrentText(self._config.remote_path)
        remote_row.addWidget(self._remote_combo)
        path_layout.addRow("Remoto:", remote_row)
        layout.addWidget(path_group)

        sync_group = QGroupBox("Sincronização")
        sync_layout = QFormLayout(sync_group)
        self._polling_spin = QSpinBox()
        self._polling_spin.setRange(1, 1440)
        self._polling_spin.setValue(self._config.polling_interval)
        self._polling_spin.setSuffix(" min")
        sync_layout.addRow("Intervalo de polling:", self._polling_spin)

        self._debounce_spin = QSpinBox()
        self._debounce_spin.setRange(1, 300)
        self._debounce_spin.setValue(self._config.debounce_seconds)
        self._debounce_spin.setSuffix(" s")
        sync_layout.addRow("Debounce local:", self._debounce_spin)

        self._enabled_cb = QCheckBox()
        self._enabled_cb.setChecked(self._config.enabled)
        sync_layout.addRow("Habilitado:", self._enabled_cb)
        layout.addWidget(sync_group)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse_local(self):
        path = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta local",
            self._local_input.text() or "",
        )
        if path:
            self._local_input.setText(path)

    def _save(self):
        name = self._name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validação", "Nome obrigatório.")
            return
        local_path = self._local_input.text().strip()
        if not local_path:
            QMessageBox.warning(self, "Validação", "Pasta local obrigatória.")
            return
        remote_path = self._remote_combo.currentText().strip()
        if not remote_path:
            QMessageBox.warning(self, "Validação", "Remoto obrigatório.")
            return
        self._config.name = name
        self._config.local_path = local_path
        if ":" not in remote_path:
            remote_path += ":"
        self._config.remote_path = remote_path
        self._config.polling_interval = self._polling_spin.value()
        self._config.debounce_seconds = self._debounce_spin.value()
        self._config.enabled = self._enabled_cb.isChecked()
        self.accept()

    def config(self) -> SyncFolderConfig:
        return self._config
