from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QDialogButtonBox, QPushButton, QListWidget,
    QMessageBox,
)


class TransferDialog(QDialog):
    def __init__(self, files: list[str], destination: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.files = files
        self.destination = destination
        self._confirm = False
        self._is_move = False
        self._dry_run = True
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Transferência Rápida")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Transferir {len(self.files)} arquivo(s):"))

        self._file_list = QListWidget()
        for f in self.files[:20]:
            self._file_list.addItem(f)
        if len(self.files) > 20:
            self._file_list.addItem(f"... e mais {len(self.files) - 20}")
        layout.addWidget(self._file_list)

        form = QHBoxLayout()
        form.addWidget(QLabel("Destino:"))
        self._dest_input = QLineEdit(self.destination)
        self._dest_input.setReadOnly(True)
        form.addWidget(self._dest_input)
        layout.addLayout(form)

        self._dry_run_cb = QCheckBox("Dry-run (simular, não executar)")
        self._dry_run_cb.setChecked(True)
        layout.addWidget(self._dry_run_cb)

        self._move_cb = QCheckBox("Mover (deletar origem após cópia)")
        layout.addWidget(self._move_cb)

        btns = QDialogButtonBox()
        self._transfer_btn = btns.addButton("Transferir", QDialogButtonBox.AcceptRole)
        self._cancel_btn = btns.addButton(QDialogButtonBox.Cancel)
        self._transfer_btn.clicked.connect(self._do_transfer)
        self._cancel_btn.clicked.connect(self.reject)
        layout.addWidget(btns)

    def _do_transfer(self):
        self._dry_run = self._dry_run_cb.isChecked()
        self._is_move = self._move_cb.isChecked()
        self._confirm = True
        if self._is_move:
            reply = QMessageBox.question(
                self, "Confirmar Movimentação",
                "Mover irá deletar a origem após a cópia.\nContinuar?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        self.accept()

    def is_confirmed(self) -> bool:
        return self._confirm

    def should_move(self) -> bool:
        return self._is_move

    def is_dry_run(self) -> bool:
        return self._dry_run
