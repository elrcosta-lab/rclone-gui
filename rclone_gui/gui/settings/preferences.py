from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QCheckBox, QComboBox, QGroupBox, QDialogButtonBox,
)

from ...db.database import Database


class PreferencesDialog(QDialog):
    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.db = db
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Preferências")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        rclone_group = QGroupBox("rclone")
        rclone_layout = QFormLayout(rclone_group)
        self._binary_input = QLineEdit("rclone")
        rclone_layout.addRow("Binário:", self._binary_input)

        self._config_input = QLineEdit("~/.config/rclone/rclone.conf")
        rclone_layout.addRow("Config:", self._config_input)
        layout.addWidget(rclone_group)

        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)
        self._transfers_spin = QSpinBox()
        self._transfers_spin.setRange(1, 64)
        self._transfers_spin.setValue(4)
        perf_layout.addRow("Transfers padrão:", self._transfers_spin)

        self._checkers_spin = QSpinBox()
        self._checkers_spin.setRange(1, 256)
        self._checkers_spin.setValue(8)
        perf_layout.addRow("Checkers padrão:", self._checkers_spin)
        layout.addWidget(perf_group)

        tray_group = QGroupBox("Tray")
        tray_layout = QFormLayout(tray_group)
        self._tray_cb = QCheckBox()
        self._tray_cb.setChecked(True)
        tray_layout.addRow("Habilitar tray icon:", self._tray_cb)

        self._minimize_cb = QCheckBox()
        self._minimize_cb.setChecked(True)
        tray_layout.addRow("Minimizar para tray:", self._minimize_cb)

        self._close_cb = QCheckBox()
        self._close_cb.setChecked(True)
        tray_layout.addRow("Fechar para tray:", self._close_cb)
        layout.addWidget(tray_group)

        notif_group = QGroupBox("Notificações")
        notif_layout = QFormLayout(notif_group)
        self._notif_cb = QCheckBox()
        self._notif_cb.setChecked(True)
        notif_layout.addRow("Habilitar notificações:", self._notif_cb)

        self._succ_cb = QCheckBox("Notificar sucesso")
        self._succ_cb.setChecked(True)
        notif_layout.addRow(self._succ_cb)

        self._fail_cb = QCheckBox("Notificar falha")
        self._fail_cb.setChecked(True)
        notif_layout.addRow(self._fail_cb)
        layout.addWidget(notif_group)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._load()

    def _load(self):
        if self.db.conn is None:
            return
        self._tray_cb.setChecked(self.db.get_config("tray_enabled", 1))
        self._minimize_cb.setChecked(self.db.get_config("minimize_to_tray", 1))
        self._close_cb.setChecked(self.db.get_config("close_to_tray", 1))
        self._notif_cb.setChecked(self.db.get_config("notifications_enabled", 1))
        self._succ_cb.setChecked(self.db.get_config("notifications_job_success", 1))
        self._fail_cb.setChecked(self.db.get_config("notifications_job_failure", 1))

    def _save(self):
        self.db.set_config("tray_enabled", int(self._tray_cb.isChecked()))
        self.db.set_config("minimize_to_tray", int(self._minimize_cb.isChecked()))
        self.db.set_config("close_to_tray", int(self._close_cb.isChecked()))
        self.db.set_config("notifications_enabled", int(self._notif_cb.isChecked()))
        self.db.set_config("notifications_job_success", int(self._succ_cb.isChecked()))
        self.db.set_config("notifications_job_failure", int(self._fail_cb.isChecked()))
        self.accept()
