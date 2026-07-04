from __future__ import annotations

from typing import Optional, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QToolButton, QStatusBar,
    QSplitter, QMessageBox, QDialog, QFormLayout, QLineEdit,
    QTextEdit, QDialogButtonBox,
)

from ...services.rclone_service import RcloneService
from .config_wizard import ConfigWizard


class RemoteListWidget(QWidget):
    def __init__(self, rclone: RcloneService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rclone = rclone
        self._remotes: list[str] = []
        self._on_remote_selected: Optional[Callable[[str], None]] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Remotos Configurados")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("Adicionar Remoto")
        self._add_btn.clicked.connect(self._add_remote)
        btn_layout.addWidget(self._add_btn)
        self._edit_btn = QPushButton("Editar")
        self._edit_btn.clicked.connect(self._edit_remote)
        self._edit_btn.setEnabled(False)
        btn_layout.addWidget(self._edit_btn)
        self._del_btn = QPushButton("Excluir")
        self._del_btn.clicked.connect(self._delete_remote)
        self._del_btn.setEnabled(False)
        btn_layout.addWidget(self._del_btn)
        layout.addLayout(btn_layout)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list)

        self._status_bar = QStatusBar()
        layout.addWidget(self._status_bar)

    def set_on_remote_selected(self, callback: Callable[[str], None]):
        self._on_remote_selected = callback

    def refresh(self):
        self._remotes = self.rclone.list_remotes()
        self._list.clear()
        for name in self._remotes:
            item = QListWidgetItem(f"{name}:  ")
            item.setData(Qt.UserRole, name)
            self._list.addItem(item)
        self._status_bar.showMessage(f"{len(self._remotes)} remoto(s) configurado(s)")

    def _on_item_clicked(self, item: QListWidgetItem):
        self._edit_btn.setEnabled(True)
        self._del_btn.setEnabled(True)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        name = item.data(Qt.UserRole)
        if self._on_remote_selected:
            self._on_remote_selected(name)

    def _add_remote(self):
        wizard = ConfigWizard(self.rclone, self)
        if wizard.exec():
            self.refresh()

    def _edit_remote(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        cfg = self.rclone.config_show(name)
        if not cfg:
            QMessageBox.critical(self, "Erro",
                                 f"Não foi possível ler a configuração do remoto '{name}'.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Editar Remoto: {name}")
        layout = QFormLayout(dlg)
        type_edit = QLineEdit(cfg.get("type", ""))
        type_edit.setReadOnly(True)
        layout.addRow("Tipo:", type_edit)
        params_edit = QTextEdit()
        params = []
        for k, v in cfg.items():
            if k != "type":
                params.append(f"{k}={v}")
        params_edit.setPlainText("\n".join(params))
        params_edit.setMinimumHeight(120)
        layout.addRow("Parâmetros (um por linha):", params_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        if dlg.exec():
            ok_count = 0
            for line in params_edit.toPlainText().strip().split("\n"):
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    ok, _ = self.rclone.config_update(
                        name, **{k.strip(): v.strip()}
                    )
                    if ok:
                        ok_count += 1
            QMessageBox.information(
                self, "Salvar",
                f"{ok_count} parâmetro(s) atualizado(s) para '{name}'."
            )
            self.refresh()

    def _delete_remote(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Remover o remoto '{name}' permanentemente?\n"
            "Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            ok, msg = self.rclone.config_delete(name)
            if ok:
                self.refresh()
            else:
                QMessageBox.critical(self, "Erro", msg)
