from __future__ import annotations

import json
from typing import Optional

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeView, QFileSystemModel, QLabel, QComboBox,
    QPushButton, QHeaderView, QAbstractItemView,
    QMenu, QInputDialog, QMessageBox,
)
from PySide6.QtGui import QAction

from ...services.rclone_service import RcloneService


class RemoteFileModel(QObject):
    listing_ready = Signal(list)

    def __init__(self, rclone: RcloneService, parent=None):
        super().__init__(parent)
        self.rclone = rclone
        self.current_path = ""
        self._thread = None
        self._worker = None

    def _cleanup_thread(self):
        try:
            if self._thread is not None:
                if self._thread.isRunning():
                    self._thread.quit()
                    if not self._thread.wait(2000):
                        self._thread.terminate()
                        self._thread.wait(1000)
                self._thread.deleteLater()
                self._thread = None
            if self._worker is not None:
                self._worker.deleteLater()
                self._worker = None
        except RuntimeError:
            pass

    def navigate(self, path: str):
        self.current_path = path
        self._cleanup_thread()
        self._worker = _LsWorker(self.rclone, path)
        self._worker.listing_done.connect(self._on_worker_done)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.do_work)
        self._worker.listing_done.connect(self._thread.quit, Qt.QueuedConnection)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def _on_worker_done(self, items: list[dict]):
        self.listing_ready.emit(items)

    def shutdown(self):
        self._cleanup_thread()


class _LsWorker(QObject):
    listing_done = Signal(list)

    def __init__(self, rclone: RcloneService, path: str):
        super().__init__()
        self._rclone = rclone
        self._path = path

    def do_work(self):
        items = self._rclone.lsjson(self._path)
        self.listing_done.emit(items)


class FilePanel(QWidget):
    path_changed = Signal(str)

    def __init__(self, rclone: RcloneService, label: str = "",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rclone = rclone
        self._current_path = ""
        self._remote_model = RemoteFileModel(rclone)
        self._remote_model.listing_ready.connect(self._on_listing_ready)
        self._local_model = QFileSystemModel()
        self._is_local = True
        self._items: list[dict] = []
        self._items_by_row: list[dict] = []
        self._setup_ui(label)

    def closeEvent(self, event):
        self._remote_model.shutdown()
        event.accept()

    def _setup_ui(self, label: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        top = QHBoxLayout()
        top_label = QLabel(label)
        top_label.setStyleSheet("font-weight: bold;")
        top.addWidget(top_label)

        self._source_combo = QComboBox()
        self._source_combo.setMinimumWidth(120)
        self._source_combo.addItem("Sistema Local")
        self._source_combo.currentIndexChanged.connect(self._on_source_changed)
        top.addWidget(self._source_combo)
        top.addStretch()

        self._refresh_btn = QPushButton("Atualizar")
        self._refresh_btn.clicked.connect(self._refresh)
        self._refresh_btn.setMaximumWidth(80)
        top.addWidget(self._refresh_btn)
        layout.addLayout(top)

        self._breadcrumb = QLabel("/")
        self._breadcrumb.setStyleSheet("padding: 2px; color: #a6adc8;")
        self._breadcrumb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._breadcrumb)

        self._tree = QTreeView()
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.doubleClicked.connect(self._on_double_click)
        self._tree.setModel(self._local_model)
        self._local_model.setRootPath("/")
        self._tree.setRootIndex(self._local_model.index("/"))
        self._tree.setSortingEnabled(True)
        layout.addWidget(self._tree)

        self._info = QLabel("")
        layout.addWidget(self._info)

    def set_remotes(self, remotes: list[str]):
        self._source_combo.blockSignals(True)
        self._source_combo.clear()
        self._source_combo.addItem("Sistema Local")
        for r in remotes:
            self._source_combo.addItem(f"{r}:")
        self._source_combo.blockSignals(False)
        self._source_combo.setCurrentIndex(0)

    def current_path(self) -> str:
        return self._current_path

    def selected_files(self) -> list[str]:
        indexes = self._tree.selectionModel().selectedIndexes()
        paths = []
        for idx in indexes:
            if idx.column() == 0:
                if self._is_local:
                    paths.append(self._local_model.filePath(idx))
                else:
                    entry_json = idx.data(Qt.UserRole + 1)
                    if entry_json:
                        entry = json.loads(entry_json)
                        paths.append(f"{self._current_path}/{entry.get('Name', '')}")
        return list(set(paths))

    def _on_source_changed(self, idx: int):
        if idx == 0:
            self._switch_to_local()
        else:
            remote = self._source_combo.currentText()
            self._switch_to_remote(remote)

    def _switch_to_local(self):
        self._is_local = True
        self._tree.setModel(self._local_model)
        self._tree.setRootIndex(self._local_model.index("/"))
        self._current_path = "/"
        self._breadcrumb.setText("/")
        self._info.setText("Sistema local")

    def _switch_to_remote(self, remote: str):
        self._is_local = False
        path = remote
        self._current_path = path
        self._breadcrumb.setText(path)
        self._remote_model.navigate(path)

    def _refresh(self):
        if self._is_local:
            import os
            current = self._current_path or "/"
            parent = os.path.dirname(current) or "/"
            self._local_model.setRootPath(parent)
            root_idx = self._local_model.setRootPath(current)
            self._tree.setRootIndex(root_idx)
        else:
            self._remote_model.navigate(self._current_path)

    def _on_listing_ready(self, items: list[dict]):
        if self._is_local:
            return
        self._items = items
        self._items_by_row = []
        self._tree.setModel(None)
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Nome", "Tamanho", "Modificado"])

        dirs = [i for i in items if i.get("IsDir")]
        files = [i for i in items if not i.get("IsDir")]
        for entry in dirs + files:
            self._items_by_row.append(entry)
            name = entry.get("Name", "?")
            size = entry.get("Size", 0)
            mod = entry.get("ModTime", "")
            fmt_size = self._format_size(size) if not entry.get("IsDir") else "<DIR>"
            row = [QStandardItem(name), QStandardItem(fmt_size), QStandardItem(mod[:16] if mod else "")]
            # Armazena entrada serializada em JSON — seguro para QVariant
            entry_json = json.dumps(entry)
            for item in row:
                item.setData(entry_json, Qt.UserRole + 1)
            model.appendRow(row)

        self._tree.setSortingEnabled(False)
        self._tree.setModel(model)
        self._tree.setSortingEnabled(True)
        self._info.setText(f"{len(items)} itens")

    def _on_double_click(self, index):
        if self._is_local:
            path = self._local_model.fileInfo(index).absoluteFilePath()
            if self._local_model.isDir(index):
                self._current_path = path
                self._breadcrumb.setText(path)
        else:
            if index.column() == 0:
                entry_json = index.data(Qt.UserRole + 1)
                if entry_json:
                    entry = json.loads(entry_json)
                    if entry.get("IsDir"):
                        name = entry.get("Name", "")
                        self._current_path = f"{self._current_path}/{name}".replace("//", "/")
                        self._breadcrumb.setText(self._current_path)
                        self._remote_model.navigate(self._current_path)

    def _context_menu(self, pos):
        menu = QMenu()
        if not self._is_local:
            mkdir_action = QAction("Criar Pasta", menu)
            mkdir_action.triggered.connect(self._mkdir)
            menu.addAction(mkdir_action)
            menu.addSeparator()
        delete_action = QAction("Excluir", menu)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _mkdir(self):
        name, ok = QInputDialog.getText(self, "Nova Pasta", "Nome da pasta:")
        if ok and name:
            path = f"{self._current_path}/{name}".replace("//", "/")
            ok, msg = self.rclone.mkdir(path)
            if ok:
                self._refresh()
            else:
                QMessageBox.critical(self, "Erro", msg)

    def _delete_selected(self):
        files = self.selected_files()
        if not files:
            return
        reply = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Excluir {len(files)} arquivo(s)?\nEsta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            for f in files:
                if self._is_local:
                    import os
                    try:
                        os.remove(f)
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", str(e))
                else:
                    ok, msg = self.rclone.delete_file(f)
                    if not ok:
                        QMessageBox.critical(self, "Erro", msg)
            self._refresh()

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
