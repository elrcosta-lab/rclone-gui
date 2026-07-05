"""Testes unitarios — SyncFolderManager."""

import os
import tempfile

from rclone_gui.models.sync_folder import SyncFolderConfig
from rclone_gui.services.sync_folder_service import SyncFolderService


class TestSyncFolderManager:
    def test_manager_starts_and_stops(self, temp_db, qtbot):
        from rclone_gui.daemon.sync_folder_manager import SyncFolderManager

        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            path = os.path.join(tmp, "drive")
            service.register(SyncFolderConfig(
                name="Test", local_path=path, remote_path="test:",
            ))
            manager = SyncFolderManager(service)
            manager.start_all()
            folders = manager.active_folders()
            assert len(folders) == 1
            assert folders[0].name == "Test"
            manager.stop_all()
            assert len(manager.active_folders()) == 0

    def test_manager_skips_disabled_folders(self, temp_db, qtbot):
        from rclone_gui.daemon.sync_folder_manager import SyncFolderManager

        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            path = os.path.join(tmp, "drive")
            fid = service.register(SyncFolderConfig(
                name="Disabled", local_path=path, remote_path="test:",
            ))
            service.set_enabled(fid, False)
            manager = SyncFolderManager(service)
            manager.start_all()
            assert len(manager.active_folders()) == 0
            manager.stop_all()

    def test_watcher_triggers_sync(self, temp_db, qtbot, mocker):
        from rclone_gui.daemon.sync_folder_manager import SyncFolderManager
        from rclone_gui.services.rclone_service import RcloneService
        from PySide6.QtTest import QSignalSpy

        mocker.patch.object(RcloneService, "bisync", return_value=(True, ""))
        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            path = os.path.join(tmp, "drive")
            service.register(SyncFolderConfig(
                name="Test", local_path=path, remote_path="test:",
                debounce_seconds=0.1,
            ))
            manager = SyncFolderManager(service)
            spy = QSignalSpy(manager.sync_completed)
            manager.start_all()

            qtbot.wait(200)
            test_file = os.path.join(path, "new.txt")
            with open(test_file, "w") as f:
                f.write("hello")

            qtbot.wait(600)
            c = spy.count()
            assert c >= 1, f"sync_completed nao emitido: count={c}"
            manager.stop_all()

    def test_active_folders_returns_configs(self, temp_db, qtbot):
        from rclone_gui.daemon.sync_folder_manager import SyncFolderManager

        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            a = os.path.join(tmp, "a")
            b = os.path.join(tmp, "b")
            service.register(SyncFolderConfig(name="A", local_path=a, remote_path="ra:"))
            service.register(SyncFolderConfig(name="B", local_path=b, remote_path="rb:"))
            manager = SyncFolderManager(service)
            manager.start_all()
            assert len(manager.active_folders()) == 2
            names = [f.name for f in manager.active_folders()]
            assert "A" in names
            assert "B" in names
            manager.stop_all()
