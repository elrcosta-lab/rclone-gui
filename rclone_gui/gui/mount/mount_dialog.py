from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QDialogButtonBox, QLabel, QGroupBox, QSpinBox,
)

from ...models.mount import MountConfig
from ...db.database import Database


class MountDialog(QDialog):
    def __init__(self, remote_name: str, db: Database,
                 existing: Optional[MountConfig] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.remote_name = remote_name
        self.db = db
        self._config = existing or MountConfig(remote_name=remote_name)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"Montar — {self.remote_name}")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        mount_group = QGroupBox("Ponto de Montagem")
        mount_layout = QFormLayout(mount_group)
        default_mount = self._config.mountpoint or f"~/Rclone/Montagens/{self.remote_name}"
        self._mountpoint_input = QLineEdit(default_mount)
        mount_layout.addRow("Path:", self._mountpoint_input)
        layout.addWidget(mount_group)

        cache_group = QGroupBox("Cache VFS")
        cache_layout = QFormLayout(cache_group)

        self._cache_mode_combo = QComboBox()
        for k, v in [("Off (streaming)", "off"), ("Mínimo (minimal)", "minimal"),
                     ("Escritório (writes)", "writes"), ("Completo (full)", "full")]:
            self._cache_mode_combo.addItem(k, v)
        idx = self._cache_mode_combo.findData(self._config.cache_mode)
        if idx >= 0:
            self._cache_mode_combo.setCurrentIndex(idx)
        cache_layout.addRow("Modo de cache:", self._cache_mode_combo)

        self._max_age_input = QLineEdit(self._config.cache_max_age)
        self._max_age_input.setPlaceholderText("Ex: 1h, 24h")
        cache_layout.addRow("Max age:", self._max_age_input)

        self._max_size_input = QLineEdit(self._config.cache_max_size)
        self._max_size_input.setPlaceholderText("Ex: 1G, 10G")
        cache_layout.addRow("Max size:", self._max_size_input)

        layout.addWidget(cache_group)

        sched_group = QGroupBox("Comportamento")
        sched_layout = QVBoxLayout(sched_group)
        self._auto_mount_cb = QCheckBox("Montar automaticamente ao iniciar")
        self._auto_mount_cb.setChecked(self._config.auto_mount)
        sched_layout.addWidget(self._auto_mount_cb)
        layout.addWidget(sched_group)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        self._config.mountpoint = self._mountpoint_input.text().strip()
        self._config.cache_mode = self._cache_mode_combo.currentData()
        self._config.cache_max_age = self._max_age_input.text().strip()
        self._config.cache_max_size = self._max_size_input.text().strip()
        self._config.auto_mount = self._auto_mount_cb.isChecked()
        self.db.save_mount_config(self._config)
        self.accept()

    def config(self) -> MountConfig:
        return self._config
