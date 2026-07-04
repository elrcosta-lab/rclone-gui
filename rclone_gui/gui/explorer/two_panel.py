from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter, QPushButton

from ...services.rclone_service import RcloneService
from .file_panel import FilePanel


class TwoPanelBrowser(QWidget):
    def __init__(self, rclone: RcloneService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rclone = rclone
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._left_panel = FilePanel(self.rclone, "Origem")
        self._right_panel = FilePanel(self.rclone, "Destino")

        middle = QWidget()
        mid_layout = QHBoxLayout(middle)
        mid_layout.setContentsMargins(4, 0, 4, 0)
        self._copy_btn = QPushButton("→ Copiar")
        self._copy_btn.clicked.connect(self._copy_to_right)
        self._move_btn = QPushButton("→ Mover")
        self._move_btn.clicked.connect(self._move_to_right)
        mid_layout.addWidget(self._copy_btn)
        mid_layout.addWidget(self._move_btn)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._left_panel)
        splitter.addWidget(middle)
        splitter.addWidget(self._right_panel)
        splitter.setSizes([400, 60, 400])
        layout.addWidget(splitter)

    def set_remotes(self, remotes: list[str]):
        self._left_panel.set_remotes(remotes)
        self._right_panel.set_remotes(remotes)

    def _copy_to_right(self):
        files = self._left_panel.selected_files()
        dst = self._right_panel.current_path()
        if not files:
            return
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Copiar",
                                f"Copiar {len(files)} arquivo(s) para {dst}\n"
                                "Funcionalidade completa em breve.")

    def _move_to_right(self):
        files = self._left_panel.selected_files()
        dst = self._right_panel.current_path()
        if not files:
            return
        from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QCheckBox
        from PySide6.QtWidgets import QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle("Mover Arquivos")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Mover {len(files)} arquivo(s) para {dst}?"))
        dry = QCheckBox("Executar dry-run primeiro (recomendado)")
        dry.setChecked(True)
        layout.addWidget(dry)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        if dialog.exec():
            QMessageBox.information(self, "Transferência",
                                    "Em andamento — implementação completa em breve.")
