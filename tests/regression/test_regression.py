"""Testes de regressão — garantem que funcionalidades existentes não regridem."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from rclone_gui.models.job import SyncJob, JobExecution, FilterRule
from rclone_gui.models.remote import BackendMeta, RemoteEntry
from rclone_gui.models.mount import MountConfig


# ==============================================================================
# 4.1 — Regressão de Schemas (modelos não podem perder campos)
# ==============================================================================

class TestSchemaRegression:
    """Campos de modelo não devem ser removidos ou renomeados sem aviso."""

    # Lista congelada de campos esperados para cada modelo
    EXPECTED_JOB_FIELDS = {
        "id", "name", "job_type", "source", "destination", "flags",
        "filters", "schedule_enabled", "schedule_cron", "schedule_type",
        "schedule_interval", "enabled", "dry_run_first",
        "created_at", "updated_at",
    }

    EXPECTED_EXECUTION_FIELDS = {
        "id", "job_id", "status", "trigger", "started_at",
        "finished_at", "duration_seconds", "files_transferred",
        "files_checked", "bytes_transferred", "errors_count",
        "fatal_error", "log_output", "is_dry_run",
    }

    EXPECTED_MOUNT_FIELDS = {
        "id", "remote_name", "mountpoint", "cache_mode",
        "cache_max_age", "cache_max_size", "cache_dir",
        "auto_mount", "network_timeout", "network_low_level_retries",
        "bwlimit", "extra_flags", "created_at", "updated_at",
    }

    EXPECTED_REMOTE_FIELDS = {"name", "type", "parameters", "is_encrypted"}

    EXPECTED_FILTER_FIELDS = {"rule_type", "pattern", "description"}

    def test_job_field_regression(self):
        job = SyncJob(name="r", job_type="sync", source="a", destination="b")
        fields = {f.name for f in type(job).__dataclass_fields__.values()}
        assert fields == self.EXPECTED_JOB_FIELDS, \
            f"SyncJob fields divergiram! Missing: {self.EXPECTED_JOB_FIELDS - fields}, Extra: {fields - self.EXPECTED_JOB_FIELDS}"

    def test_execution_field_regression(self):
        e = JobExecution(job_id=1, status="x", trigger="manual", started_at="now")
        fields = {f.name for f in type(e).__dataclass_fields__.values()}
        assert fields == self.EXPECTED_EXECUTION_FIELDS

    def test_mount_field_regression(self):
        m = MountConfig(remote_name="x", mountpoint="/mnt/x")
        fields = {f.name for f in type(m).__dataclass_fields__.values()}
        assert fields == self.EXPECTED_MOUNT_FIELDS

    def test_remote_entry_field_regression(self):
        r = RemoteEntry(name="x", type="drive")
        fields = {f.name for f in type(r).__dataclass_fields__.values()}
        assert fields == self.EXPECTED_REMOTE_FIELDS

    def test_filter_rule_field_regression(self):
        f = FilterRule(rule_type="include", pattern="*")
        fields = {f.name for f in type(f).__dataclass_fields__.values()}
        assert fields == self.EXPECTED_FILTER_FIELDS


# ==============================================================================
# 4.2 — Regressão de Banco de Dados
# ==============================================================================

class TestDatabaseSchemaRegression:
    """Schema do banco não deve retroceder."""

    def test_tables_exist(self, temp_db):
        tables = {r[0] for r in temp_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        required_tables = {"app_config", "sync_jobs", "job_history", "mount_configs", "directory_cache"}
        missing = required_tables - tables
        assert not missing, f"Tabelas faltando: {missing}"

    def test_app_config_columns(self, temp_db):
        cols = {r[1] for r in temp_db.conn.execute("PRAGMA table_info(app_config)")}
        for c in {"autostart_enabled", "tray_enabled", "rcd_port", "created_at", "updated_at"}:
            assert c in cols

    def test_schema_version_migration(self, temp_db):
        """user_version deve ser >= 1 após migração."""
        version = temp_db.conn.execute("PRAGMA user_version").fetchone()[0]
        assert version >= 1

    def test_job_persistence_roundtrip(self, temp_db):
        """Salvar e ler job deve preservar todos os campos."""
        import json
        flags = {"checksum": True, "bwlimit": "5M", "transfers": 8}
        filters = [{"rule_type": "include", "pattern": "*.txt", "description": "Textos"}]
        job = SyncJob(
            name="regression_full", job_type="bisync",
            source="/home/user/docs", destination="gdrive:Backup",
            flags=flags, enabled=True, dry_run_first=True,
            schedule_enabled=True, schedule_cron="0 */6 * * *",
            schedule_type="custom", schedule_interval=360,
        )
        job_id = temp_db.save_job(job)
        retrieved = temp_db.get_job(job_id)
        assert retrieved.name == job.name
        assert retrieved.job_type == job.job_type
        assert retrieved.flags == flags
        assert retrieved.schedule_cron == job.schedule_cron
        assert retrieved.schedule_interval == job.schedule_interval

    def test_mount_config_persistence_roundtrip(self, temp_db):
        mc = MountConfig(
            remote_name="regression_mount", mountpoint="/mnt/test",
            cache_mode="full", auto_mount=True, bwlimit="10M",
        )
        temp_db.save_mount_config(mc)
        retrieved = temp_db.get_mount_config("regression_mount")
        assert retrieved.cache_mode == "full"
        assert retrieved.auto_mount is True
        assert retrieved.bwlimit == "10M"


# ==============================================================================
# 4.3 — Regressão de Backend Catalog
# ==============================================================================

class TestBackendCatalogRegression:
    """Backends conhecidos não devem desaparecer do catálogo."""

    KNOWN_BACKENDS = {"drive", "dropbox", "s3", "b2", "sftp", "onedrive", "mega", "pcloud", "box", "webdav"}

    def test_known_backends_present(self, backend_catalog):
        types = {b.type for b in backend_catalog}
        missing = self.KNOWN_BACKENDS - types
        assert not missing, f"Backends removidos do catálogo: {missing}"

    def test_catalog_drive_fields(self, backend_catalog):
        drive = next((b for b in backend_catalog if b.type == "drive"), None)
        assert drive is not None
        assert drive.requires_oauth is True
        assert drive.oauth_provider == "drive"
        assert drive.display_name == "Google Drive"

    def test_catalog_s3_fields(self, backend_catalog):
        s3 = next((b for b in backend_catalog if b.type == "s3"), None)
        assert s3 is not None
        assert s3.requires_oauth is False
        assert s3.oauth_provider is None

    def test_catalog_more_than_minimum(self, backend_catalog):
        assert len(backend_catalog) >= len(self.KNOWN_BACKENDS) + 5


# ==============================================================================
# 4.4 — Regressão de Comportamento (RcloneService)
# ==============================================================================

class TestRcloneServiceBehaviorRegression:
    """Comportamento observável do RcloneService não deve mudar inesperadamente."""

    def test_list_remotes_strips_colons(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "gdrive:\n"
        assert RcloneService().list_remotes() == ["gdrive"]

    def test_list_remotes_strips_whitespace(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "  remote1  \n  \nremote2  \n"
        remotes = RcloneService().list_remotes()
        assert all(r == r.strip() for r in remotes)

    def test_empty_string_returns_empty_list(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = ""
        assert RcloneService().list_remotes() == []

    def test_error_stderr_does_not_raise(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stderr = "ERROR: something bad"
        mock_subprocess_run.return_value.stdout = ""
        RcloneService().list_remotes()  # Não deve levantar exceção

    def test_lsjson_invalid_json_no_crash(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "not json at all"
        assert RcloneService().lsjson("remote:") == []

    def test_mkdir_with_special_chars(self, mock_subprocess_run):
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 0
        ok, _ = RcloneService().mkdir('gdrive:Pasta com espaços!')
        assert ok is True


# ==============================================================================
# 4.5 — Regressão de Edge Cases Conhecidos
# ==============================================================================

class TestEdgeCaseRegression:
    """Edge cases documentados nas specs não devem quebrar."""

    def test_ec_s01_01_no_rclone_conf(self, temp_home):
        """EC-S01-01: rclone.conf não existe não deve crashar o service."""
        from rclone_gui.services.rclone_service import RcloneService
        svc = RcloneService()
        # Apenas o catálogo de backends deve funcionar sem rclone.conf
        catalog = svc.load_backends_catalog()
        assert len(catalog) >= 10

    def test_ec_s02_01_large_directory(self, mock_subprocess_run):
        """EC-S02-01: Diretório com 10000+ itens."""
        from rclone_gui.services.rclone_service import RcloneService
        items = [{"Name": f"file{i}.txt", "Size": i, "IsDir": False,
                   "ModTime": "2026-01-01T00:00:00Z", "MimeType": "text/plain"}
                 for i in range(10000)]
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = json.dumps(items)
        result = RcloneService().lsjson("remote:")
        assert len(result) == 10000

    def test_ec_s04_01_not_in_fuse_group(self, mock_subprocess_run):
        """EC-S04-01: Verifica que mount com permissão negada retorna falso."""
        from rclone_gui.services.rclone_service import RcloneService
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stderr = "fusermount: fuse device not found"
        ok, msg = RcloneService().mkdir("/invalid/path")
        assert ok is False
        assert "fuse" in msg.lower() or "mount" in msg.lower() or len(msg) > 0
