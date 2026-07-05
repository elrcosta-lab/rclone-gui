from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..models.sync_folder import SyncFolderConfig
from ..services.sync_folder_service import SyncFolderService
from .sync_folder_poller import SyncFolderPoller
from .sync_folder_watcher import SyncFolderWatcher


class _ManagedFolder(QObject):
    sync_completed = Signal(int, str)

    def __init__(self, config: SyncFolderConfig, service: SyncFolderService,
                 parent=None):
        super().__init__(parent)
        self.config = config
        self._service = service
        self._watcher = SyncFolderWatcher(
            config.local_path, config.debounce_seconds,
        )
        self._poller = SyncFolderPoller(config.polling_interval)
        self._syncing = False

        self._watcher.changes_detected.connect(self._on_changes)
        self._poller.time_to_sync.connect(self._on_poll)
        self._poller.start()

    def start_watching(self):
        self._watcher.start()

    def stop(self):
        self._watcher.stop()
        self._poller.stop()

    def _on_changes(self):
        self._poller.set_suppressed(True)
        self._do_sync()

    def _on_poll(self):
        self._do_sync()

    def _do_sync(self):
        if self._syncing:
            return
        self._syncing = True
        ok, _ = self._service.sync_now(self.config.id)
        status = "success" if ok else "failed"
        self._syncing = False
        self.sync_completed.emit(self.config.id, status)
        self._poller.set_suppressed(False)


class SyncFolderManager(QObject):
    sync_completed = Signal(int, str)

    def __init__(self, service: SyncFolderService, parent=None):
        super().__init__(parent)
        self._service = service
        self._folders: dict[int, _ManagedFolder] = {}

    def start_all(self):
        for cfg in self._service.get_enabled():
            self._start_one(cfg)

    def stop_all(self):
        for mf in list(self._folders.values()):
            mf.stop()
        self._folders.clear()

    def active_folders(self) -> list[SyncFolderConfig]:
        return [mf.config for mf in self._folders.values()]

    def _start_one(self, cfg: SyncFolderConfig):
        if cfg.id in self._folders:
            return
        mf = _ManagedFolder(cfg, self._service, self)
        mf.sync_completed.connect(lambda fid, st: self.sync_completed.emit(fid, st))
        mf.start_watching()
        self._folders[cfg.id] = mf
