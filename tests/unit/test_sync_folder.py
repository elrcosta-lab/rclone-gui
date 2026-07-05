"""Testes unitários — SyncFolderConfig model + DB CRUD."""

from __future__ import annotations

import pytest

from rclone_gui.models.sync_folder import SyncFolderConfig


class TestSyncFolderModel:
    """SyncFolderConfig dataclass."""

    def test_sync_folder_defaults(self):
        cfg = SyncFolderConfig()
        assert cfg.sync_mode == "bisync"
        assert cfg.conflict_resolution == ""
        assert cfg.polling_interval == 300
        assert cfg.debounce_seconds == 5
        assert cfg.enabled is True

    def test_sync_folder_custom_values(self):
        cfg = SyncFolderConfig(
            name="Google Drive",
            local_path="/home/user/RcloneSync/gdrive",
            remote_path="gdrive:/",
            sync_mode="bisync",
            conflict_resolution="path1",
            polling_interval=120,
            debounce_seconds=10,
            enabled=False,
        )
        assert cfg.name == "Google Drive"
        assert cfg.remote_path == "gdrive:/"
        assert cfg.conflict_resolution == "path1"
        assert cfg.polling_interval == 120
        assert cfg.enabled is False

    def test_to_dict_excludes_dates(self):
        cfg = SyncFolderConfig(name="Test", local_path="/t", remote_path="t:")
        d = cfg.to_dict()
        assert "created_at" not in d
        assert "updated_at" not in d
        assert d["name"] == "Test"

    def test_from_row(self):
        class MockRow(dict):
            def __getitem__(self, key):
                if key == "enabled":
                    return 1
                return {"id": 1, "name": "Drive", "local_path": "/a",
                        "remote_path": "r:/"}.get(key, None)

        row = MockRow()
        cfg = SyncFolderConfig.from_row(row)
        assert cfg.name == "Drive"
        assert cfg.enabled is True
        assert cfg.last_sync_at is None


class TestSyncFolderDB:
    """SyncFolder DB CRUD via Database."""

    def test_table_created(self, temp_db):
        from rclone_gui.db.database import Database

        tables = temp_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "sync_folders" in table_names

    def test_save_and_get_sync_folder(self, temp_db):

        cfg = SyncFolderConfig(
            name="Test Drive",
            local_path="/tmp/sync/test",
            remote_path="test:",
        )
        fid = temp_db.save_sync_folder(cfg)
        assert fid > 0
        folders = temp_db.get_all_sync_folders()
        assert len(folders) == 1
        assert folders[0].name == "Test Drive"
        assert folders[0].enabled is True

    def test_update_sync_folder(self, temp_db):

        cfg = SyncFolderConfig(name="A", local_path="/a", remote_path="ra:")
        fid = temp_db.save_sync_folder(cfg)
        cfg.id = fid
        cfg.enabled = False
        temp_db.save_sync_folder(cfg)
        folders = temp_db.get_all_sync_folders()
        assert folders[0].enabled is False

    def test_delete_sync_folder(self, temp_db):

        cfg = SyncFolderConfig(name="Z", local_path="/z", remote_path="rz:")
        fid = temp_db.save_sync_folder(cfg)
        temp_db.delete_sync_folder(fid)
        assert len(temp_db.get_all_sync_folders()) == 0
