"""Testes unitários — SyncFolderService."""

from __future__ import annotations

import os
import tempfile

import pytest

from rclone_gui.models.sync_folder import SyncFolderConfig
from rclone_gui.services.sync_folder_service import SyncFolderService


class TestSyncFolderService:
    def test_register_creates_dir_and_saves(self, temp_db):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "gdrive")
            service = SyncFolderService(db=temp_db)
            cfg = SyncFolderConfig(name="My Drive", local_path=path, remote_path="gdrive:/")
            fid = service.register(cfg)
            assert fid > 0
            assert os.path.isdir(path)

    def test_register_fails_if_path_already_registered(self, temp_db):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mydrive")
            service = SyncFolderService(db=temp_db)
            cfg1 = SyncFolderConfig(name="A", local_path=path, remote_path="ra:")
            cfg2 = SyncFolderConfig(name="B", local_path=path, remote_path="rb:")
            service.register(cfg1)
            with pytest.raises(ValueError, match="já está registrado"):
                service.register(cfg2)

    def test_get_all_folders(self, temp_db):
        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            a = os.path.join(tmp, "a")
            b = os.path.join(tmp, "b")
            service.register(SyncFolderConfig(name="A", local_path=a, remote_path="ra:"))
            service.register(SyncFolderConfig(name="B", local_path=b, remote_path="rb:"))
            folders = service.get_all()
            assert len(folders) == 2

    def test_disable_folder(self, temp_db):
        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            path = os.path.join(tmp, "x")
            fid = service.register(SyncFolderConfig(name="X", local_path=path, remote_path="rx:"))
            service.set_enabled(fid, False)
            folders = service.get_all()
            assert folders[0].enabled is False

    def test_get_enabled_only(self, temp_db):
        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            a = os.path.join(tmp, "a")
            b = os.path.join(tmp, "b")
            fa = service.register(SyncFolderConfig(name="A", local_path=a, remote_path="ra:"))
            service.register(SyncFolderConfig(name="B", local_path=b, remote_path="rb:"))
            service.set_enabled(fa, False)
            enabled = service.get_enabled()
            assert len(enabled) == 1
            assert enabled[0].name == "B"

    def test_unregister_deletes_from_db(self, temp_db):
        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            path = os.path.join(tmp, "z")
            fid = service.register(SyncFolderConfig(name="Z", local_path=path, remote_path="rz:"))
            service.unregister(fid)
            assert len(service.get_all()) == 0

    def test_sync_now_runs_bisync(self, temp_db, mocker):
        from rclone_gui.services.rclone_service import RcloneService

        mock_bisync = mocker.patch.object(RcloneService, "bisync", return_value=(True, ""))
        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db, rclone=RcloneService())
            path = os.path.join(tmp, "drive")
            fid = service.register(SyncFolderConfig(
                name="Drive", local_path=path, remote_path="gdrive:/",
                conflict_resolution="newer",
            ))
            ok, msg = service.sync_now(fid)
            assert ok
            mock_bisync.assert_called_once()
            args, kwargs = mock_bisync.call_args
            assert args[0] == path
            assert args[1] == "gdrive:/"
            assert kwargs.get("resync") is True, "primeira sync deve usar --resync"

    def test_sync_now_first_uses_resync_second_does_not(self, temp_db, mocker):
        from rclone_gui.services.rclone_service import RcloneService

        mock_bisync = mocker.patch.object(RcloneService, "bisync",
                                          return_value=(True, ""))
        with tempfile.TemporaryDirectory() as tmp:
            service = SyncFolderService(db=temp_db)
            path = os.path.join(tmp, "d")
            fid = service.register(SyncFolderConfig(name="D", local_path=path, remote_path="rd:"))
            service.sync_now(fid)
            folders = service.get_all()
            assert folders[0].last_sync_at is not None
            assert folders[0].last_sync_status == "success"
            _, kwargs1 = mock_bisync.call_args_list[0]
            assert kwargs1.get("resync") is True

            service.sync_now(fid)
            _, kwargs2 = mock_bisync.call_args_list[1]
            assert kwargs2.get("resync") is False
