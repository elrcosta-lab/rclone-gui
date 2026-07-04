"""Testes unitários — modelos, validação de dados, funções puras."""

from __future__ import annotations

from datetime import datetime

import subprocess
from unittest.mock import MagicMock

import pytest

from rclone_gui.models.remote import BackendMeta, BackendField, RemoteEntry, RemoteStatus
from rclone_gui.models.job import SyncJob, JobExecution, FilterRule
from rclone_gui.models.mount import MountConfig


class TestModels:
    """1.1 — Modelos de dados: criação e validação"""

    def test_remote_entry_creation(self):
        r = RemoteEntry(name="gdrive", type="drive", parameters={"client_id": "x"})
        assert r.name == "gdrive"
        assert r.type == "drive"
        assert r.parameters["client_id"] == "x"
        assert r.is_encrypted is False

    def test_remote_entry_encrypted_flag(self):
        r = RemoteEntry(name="crypt", type="crypt", is_encrypted=True)
        assert r.is_encrypted is True

    def test_backend_meta_defaults(self):
        b = BackendMeta(type="s3", display_name="Amazon S3", description="S3",
                         category="object_storage", requires_oauth=False)
        assert b.requires_oauth is False
        assert b.oauth_provider is None
        assert b.fields == []

    def test_backend_meta_with_oauth(self):
        b = BackendMeta(type="drive", display_name="Google Drive",
                         description="Drive", category="cloud",
                         requires_oauth=True, oauth_provider="drive")
        assert b.oauth_provider == "drive"

    def test_backend_field_choice(self):
        f = BackendField(name="region", label="Região", description="AWS Region",
                          required=True, field_type="choice",
                          choices=["us-east-1", "eu-west-1", "sa-east-1"])
        assert len(f.choices) == 3
        assert "sa-east-1" in f.choices

    def test_remote_status_defaults(self):
        s = RemoteStatus(name="gdrive")
        assert s.online is False
        assert s.quota_used is None
        assert s.error_message is None

    def test_sync_job_defaults(self):
        j = SyncJob(name="test", job_type="sync", source="/a", destination="/b")
        assert j.enabled is True
        assert j.dry_run_first is True
        assert j.schedule_type == "manual"
        assert j.filters == []
        assert j.id is None

    def test_sync_job_with_filters(self):
        f = FilterRule(rule_type="include", pattern="*.pdf")
        j = SyncJob(name="pdfs", job_type="copy", source="/docs", destination="gdrive:",
                     filters=[f], flags={"checksum": True})
        assert len(j.filters) == 1
        assert j.flags["checksum"] is True

    def test_job_execution_defaults(self):
        e = JobExecution(job_id=1, status="running", trigger="manual",
                          started_at=datetime.now().isoformat())
        assert e.is_dry_run is False
        assert e.files_transferred == 0
        assert e.fatal_error is None
        assert e.duration_seconds is None

    def test_job_execution_success(self):
        e = JobExecution(job_id=1, status="success", trigger="scheduled",
                          started_at="2026-01-01T00:00:00",
                          finished_at="2026-01-01T00:10:00",
                          duration_seconds=600.0, files_transferred=100)
        assert e.files_transferred == 100
        assert e.trigger == "scheduled"

    def test_mount_config_defaults(self):
        m = MountConfig(remote_name="gdrive", mountpoint="/mnt/gdrive")
        assert m.cache_mode == "writes"
        assert m.auto_mount is False
        assert m.network_timeout == "10m"

    def test_mount_config_auto_mount(self):
        m = MountConfig(remote_name="gdrive", mountpoint="/mnt/gdrive",
                         cache_mode="full", auto_mount=True)
        assert m.auto_mount is True
        assert m.cache_mode == "full"

    def test_filter_rule_creation(self):
        f = FilterRule(rule_type="exclude", pattern="*.tmp", description="Arquivos temporários")
        assert f.rule_type == "exclude"
        assert f.description == "Arquivos temporários"

    def test_filter_rule_missing_description(self):
        f = FilterRule(rule_type="min_size", pattern="10M")
        assert f.description is None


class TestDatabaseUnit:
    """1.2 — Operações de banco de dados (CRUD isolado)"""

    def test_db_initialization(self, temp_db):
        from rclone_gui.db.database import Database
        # DB já inicializado pela fixture
        assert temp_db.conn is not None
        row = temp_db.conn.execute("SELECT id FROM app_config WHERE id=1").fetchone()
        assert row is not None
        assert row[0] == 1

    def test_app_config_get_set(self, temp_db):
        assert temp_db.get_config("rcd_port", 5572) == 5572
        temp_db.set_config("rcd_port", 5572)
        assert temp_db.get_config("rcd_port") == 5572

    def test_app_config_defaults(self, temp_db):
        assert temp_db.get_config("tray_enabled", 1) == 1
        assert temp_db.get_config("notifications_enabled", 1) == 1

    def test_save_and_retrieve_job(self, temp_db, sample_job):
        job_id = temp_db.save_job(sample_job)
        assert job_id > 0
        retrieved = temp_db.get_job(job_id)
        assert retrieved is not None
        assert retrieved.name == "backup_diario"
        assert retrieved.job_type == "sync"

    def test_update_job(self, temp_db, sample_job):
        job_id = temp_db.save_job(sample_job)
        sample_job.name = "backup_renamed"
        temp_db.save_job(sample_job)
        retrieved = temp_db.get_job(job_id)
        assert retrieved.name == "backup_renamed"

    def test_job_flags_preserved(self, temp_db, sample_job):
        temp_db.save_job(sample_job)
        retrieved = temp_db.get_job(sample_job.id)
        assert retrieved.flags["checksum"] is True
        assert retrieved.flags["bwlimit"] == "10M"

    def test_job_filters_preserved(self, temp_db, sample_job):
        temp_db.save_job(sample_job)
        retrieved = temp_db.get_job(sample_job.id)
        assert len(retrieved.filters) == 1
        assert retrieved.filters[0].pattern == "*.tmp"

    def test_get_all_jobs(self, temp_db, sample_job):
        temp_db.save_job(sample_job)
        jobs = temp_db.get_all_jobs()
        assert len(jobs) == 1

    def test_delete_job(self, temp_db, sample_job):
        temp_db.save_job(sample_job)
        temp_db.delete_job(sample_job.id)
        assert len(temp_db.get_all_jobs()) == 0

    def test_execution_history(self, temp_db, sample_job, sample_execution):
        temp_db.save_job(sample_job)
        sample_execution.job_id = sample_job.id
        exec_id = temp_db.add_execution(sample_execution)
        assert exec_id > 0
        history = temp_db.get_job_history(sample_job.id)
        assert len(history) == 1
        assert history[0].files_transferred == 45

    def test_mount_config_crud(self, temp_db, sample_mount):
        temp_db.save_mount_config(sample_mount)
        retrieved = temp_db.get_mount_config("gdrive")
        assert retrieved is not None
        assert retrieved.cache_mode == "writes"
        assert retrieved.auto_mount is True

        configs = temp_db.get_all_mount_configs()
        assert len(configs) == 1

        temp_db.delete_mount_config("gdrive")
        assert temp_db.get_mount_config("gdrive") is None

    def test_multiple_mount_configs(self, temp_db):
        for name in ["gdrive", "dropbox", "s3"]:
            from rclone_gui.models.mount import MountConfig
            mc = MountConfig(remote_name=name, mountpoint=f"/mnt/{name}")
            temp_db.save_mount_config(mc)
        assert len(temp_db.get_all_mount_configs()) == 3

    def test_schedule_fields(self, temp_db):
        from rclone_gui.models.job import SyncJob
        j = SyncJob(name="scheduled", job_type="bisync", source="/a", destination="/b",
                     schedule_enabled=True, schedule_cron="0 */6 * * *",
                     schedule_type="custom")
        temp_db.save_job(j)
        retrieved = temp_db.get_job(j.id)
        assert retrieved.schedule_cron == "0 */6 * * *"
        assert retrieved.schedule_type == "custom"


class TestRcloneServiceUnit:
    """1.3 — RcloneService com subprocess mockado"""

    def test_list_remotes_empty(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = ""
        svc = RcloneService()
        assert svc.list_remotes() == []

    def test_list_remotes_with_data(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "gdrive:\ndropbox:\ns3:\n"
        svc = RcloneService()
        remotes = svc.list_remotes()
        assert remotes == ["gdrive", "dropbox", "s3"]

    def test_list_remotes_multiline_cleanup(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "  remote1:\nremote2:  \n  \n"
        svc = RcloneService()
        remotes = svc.list_remotes()
        assert remotes == ["remote1", "remote2"]

    def test_list_remotes_failure(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stdout = ""
        svc = RcloneService()
        assert svc.list_remotes() == []

    def test_about_success(self, mock_subprocess_run, sample_about_output):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = sample_about_output
        svc = RcloneService()
        result = svc.about("gdrive")
        assert result["total"] == 16106127360
        assert result["used"] == 7730941132

    def test_about_failure(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stdout = ""
        svc = RcloneService()
        assert svc.about("gdrive") == {}

    def test_lsjson_success(self, mock_subprocess_run, sample_lsjson_output):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = sample_lsjson_output
        svc = RcloneService()
        items = svc.lsjson("gdrive:")
        assert len(items) == 2
        assert items[0]["Name"] == "foto.jpg"
        assert items[1]["IsDir"] is True

    def test_config_create_success(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = ""
        svc = RcloneService()
        ok, msg = svc.config_create("test", "drive", client_id="abc")
        assert ok is True

    def test_config_create_failure(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 1
        result.stdout = ""
        result.stderr = "error: invalid backend"
        mock_subprocess_run.return_value = result
        svc = RcloneService()
        ok, msg = svc.config_create("test", "invalid")
        assert ok is False
        assert "invalid" in msg

    def test_config_delete_success(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        svc = RcloneService()
        ok, _ = svc.config_delete("gdrive")
        assert ok is True

    def test_mkdir_success(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        svc = RcloneService()
        ok, _ = svc.mkdir("gdrive:nova-pasta")
        assert ok is True

    def test_mkdir_failure(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stderr = "permission denied"
        svc = RcloneService()
        ok, msg = svc.mkdir("gdrive:restrito")
        assert ok is False
        assert "permission" in msg.lower()

    def test_delete_file_success(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        svc = RcloneService()
        ok, _ = svc.delete_file("gdrive:foto.jpg")
        assert ok is True

    def test_moveto_success(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        svc = RcloneService()
        ok, _ = svc.moveto("gdrive:old", "gdrive:new")
        assert ok is True

    def test_check_version_found(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "rclone v1.68.0\n"
        svc = RcloneService()
        ver = svc.check_version()
        assert ver is not None
        assert "v1.68" in ver

    def test_check_version_not_found(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.side_effect = FileNotFoundError()
        svc = RcloneService()
        assert svc.check_version() is None

    def test_purge_success(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        svc = RcloneService()
        ok, _ = svc.purge("gdrive:lixeira")
        assert ok is True


class TestBackendCatalogUnit:
    """1.4 — Catálogo de backends (fonte de dados estática)"""

    def test_catalog_loaded(self, backend_catalog):
        assert len(backend_catalog) >= 10

    def test_catalog_all_have_types(self, backend_catalog):
        for b in backend_catalog:
            assert b.type, f"Backend {b.display_name} missing type"

    def test_catalog_all_have_display_names(self, backend_catalog):
        for b in backend_catalog:
            assert b.display_name, f"Backend {b.type} missing display_name"

    def test_catalog_all_have_categories(self, backend_catalog):
        for b in backend_catalog:
            assert b.category in ("cloud", "object_storage", "file_transfer")

    def test_catalog_oauth_backends_have_provider(self, backend_catalog):
        for b in backend_catalog:
            if b.requires_oauth:
                assert b.oauth_provider, f"{b.type} requires oauth but no provider"

    def test_catalog_non_oauth_backends_no_provider(self, backend_catalog):
        for b in backend_catalog:
            if not b.requires_oauth:
                assert b.oauth_provider is None, f"{b.type} should not have oauth_provider"

    def test_catalog_has_google_drive(self, backend_catalog):
        types = [b.type for b in backend_catalog]
        assert "drive" in types

    def test_catalog_has_amazon_s3(self, backend_catalog):
        types = [b.type for b in backend_catalog]
        assert "s3" in types

    def test_catalog_has_sftp(self, backend_catalog):
        types = [b.type for b in backend_catalog]
        assert "sftp" in types
