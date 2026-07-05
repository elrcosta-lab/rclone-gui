from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QStatusBar, QMessageBox,
)

from ...models.sync_folder import SyncFolderConfig
from ...services.rclone_service import RcloneService
from ...services.sync_folder_service import SyncFolderService
from .sync_folder_editor import SyncFolderEditor


class SyncFolderList(QWidget):
    def __init__(self, rclone: RcloneService,
                 sync_folder_service: SyncFolderService,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rclone = rclone
        self.sync_folder_service = sync_folder_service
        self._folders: list[SyncFolderConfig] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Pastas de Sincronização")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        desc = QLabel(
            "Pastas locais sincronizadas bidirecionalmente com remotos. "
            "Altera\u00e7\u00f5es locais s\u00e3o detectadas automaticamente "
            "e sincronizadas via bisync."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 0 4px 8px 4px;")
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("Adicionar")
        self._add_btn.clicked.connect(self._add)
        btn_layout.addWidget(self._add_btn)

        self._edit_btn = QPushButton("Editar")
        self._edit_btn.clicked.connect(self._edit)
        self._edit_btn.setEnabled(False)
        btn_layout.addWidget(self._edit_btn)

        self._remove_btn = QPushButton("Remover")
        self._remove_btn.clicked.connect(self._remove)
        self._remove_btn.setEnabled(False)
        btn_layout.addWidget(self._remove_btn)

        self._sync_btn = QPushButton("Sincronizar agora")
        self._sync_btn.clicked.connect(self._sync_now)
        self._sync_btn.setEnabled(False)
        btn_layout.addWidget(self._sync_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_selection)
        self._list.itemDoubleClicked.connect(self._edit)
        layout.addWidget(self._list)

        self._status_bar = QStatusBar()
        layout.addWidget(self._status_bar)

        self.refresh()

    def refresh(self):
        self._folders = self.sync_folder_service.get_all()
        self._list.clear()
        for f in self._folders:
            status = "Ativo" if f.enabled else "Inativo"
            text = f"{f.name}  —  {f.remote_path}  →  {f.local_path}  [{status}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, f.id)
            if f.last_sync_at:
                item.setToolTip(f"\u00daltima sincroniza\u00e7\u00e3o: {f.last_sync_at}")
            self._list.addItem(item)
        self._status_bar.showMessage(
            f"{len(self._folders)} pasta(s) configurada(s)"
        )
        self._edit_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)
        self._sync_btn.setEnabled(False)

    def _on_selection(self):
        has_selection = bool(self._list.currentItem())
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)
        self._sync_btn.setEnabled(has_selection)

    def _selected_id(self) -> Optional[int]:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _add(self):
        remotes = self.rclone.list_remotes()
        editor = SyncFolderEditor(remotes, parent=self)
        if editor.exec():
            cfg = editor.config()
            try:
                self.sync_folder_service.register(cfg)
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Erro", str(e))

    def _edit(self):
        fid = self._selected_id()
        if fid is None:
            return
        existing = next((f for f in self._folders if f.id == fid), None)
        if existing is None:
            return
        remotes = self.rclone.list_remotes()
        editor = SyncFolderEditor(remotes, existing=existing, parent=self)
        if editor.exec():
            cfg = editor.config()
            cfg.id = fid
            self.sync_folder_service.db.save_sync_folder(cfg)
            self.refresh()

    def _remove(self):
        fid = self._selected_id()
        if fid is None:
            return
        ok = QMessageBox.question(
            self, "Confirmar",
            "Remover esta pasta de sincroniza\u00e7\u00e3o?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ok == QMessageBox.Yes:
            self.sync_folder_service.unregister(fid)
            self.refresh()

    def _sync_now(self):
        fid = self._selected_id()
        if fid is None:
            return
        self._sync_btn.setEnabled(False)
        self._status_bar.showMessage("Sincronizando...")
        ok, msg = self.sync_folder_service.sync_now(fid)
        if ok:
            self._status_bar.showMessage("Sincroniza\u00e7\u00e3o conclu\u00edda", 5000)
        else:
            self._status_bar.showMessage(f"Erro: {msg}", 5000)
            QMessageBox.warning(self, "Erro na sincroniza\u00e7\u00e3o", msg)
        self.refresh()
