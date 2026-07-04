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
        ok, msg = self._run_transfer(files, dst, move=False)
        from PySide6.QtWidgets import QMessageBox
        if ok:
            QMessageBox.information(
                self, "Copiar",
                f"{len(files)} arquivo(s) copiados com sucesso para {dst}."
            )
            self._left_panel._refresh()
            self._right_panel._refresh()
        else:
            QMessageBox.critical(self, "Erro na Cópia", msg)

    def _move_to_right(self):
        files = self._left_panel.selected_files()
        dst = self._right_panel.current_path()
        if not files:
            return
        from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QCheckBox
        from PySide6.QtWidgets import QDialogButtonBox, QLabel
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
            flags = {"dry_run": True} if dry.isChecked() else {}
            ok, msg = self._run_transfer(files, dst, move=True, flags=flags)
            if dry.isChecked() and ok:
                reply = QMessageBox.question(
                    self, "Confirmar Mover",
                    "Dry-run concluído. Deseja executar a movimentação real?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    ok, msg = self._run_transfer(files, dst, move=True)
            if ok:
                QMessageBox.information(
                    self, "Mover",
                    f"{len(files)} arquivo(s) movidos com sucesso para {dst}."
                )
                self._left_panel._refresh()
                self._right_panel._refresh()
            else:
                QMessageBox.critical(self, "Erro na Movimentação", msg)

    def _run_transfer(self, files: list[str], dst: str, move: bool = False,
                      flags: dict | None = None) -> tuple[bool, str]:
        for src in files:
            if move:
                ok, msg = self.rclone.move(src, dst, flags)
            else:
                ok, msg = self.rclone.copy(src, dst, flags)
            if not ok:
                return False, f"Falha em {src}:\n{msg}"
        return True, ""
