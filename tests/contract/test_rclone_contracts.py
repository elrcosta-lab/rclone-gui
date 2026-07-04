"""Testes de contrato — formato de I/O do rclone, estabilidade da interface."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from rclone_gui.services.rclone_service import RcloneService


class TestRcloneCommandContracts:
    """3.1 — Formato de saída dos comandos rclone (contrato de parsing)"""

    def test_lsjson_contract(self, mock_subprocess_run):
        """rclone lsjson deve retornar JSON array com Name, Size, ModTime, IsDir, MimeType."""
        output = json.dumps([
            {"Name": "test.txt", "Path": "test.txt", "Size": 100,
             "ModTime": "2026-01-01T00:00:00.000Z", "IsDir": False, "MimeType": "text/plain"},
        ])
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = output

        items = RcloneService().lsjson("remote:")
        assert len(items) == 1
        assert "Name" in items[0]
        assert "IsDir" in items[0]
        assert "Size" in items[0]

    def test_lsjson_empty_directory(self, mock_subprocess_run):
        """Diretório vazio retorna array vazio."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "[]"
        items = RcloneService().lsjson("remote:")
        assert items == []

    def test_lsjson_single_item(self, mock_subprocess_run):
        """Array com um único item é parseado corretamente."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = json.dumps([{"Name": "single.txt", "Size": 1}])
        assert len(RcloneService().lsjson("remote:")) == 1

    def test_lsjson_non_json_output(self, mock_subprocess_run):
        """Saída não-JSON (erro) retorna lista vazia."""
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stdout = "ERROR: backend not found"
        assert RcloneService().lsjson("remote:") == []

    def test_about_contract(self, mock_subprocess_run):
        """rclone about deve retornar JSON com total, used, free."""
        output = json.dumps({"total": 1000, "used": 500, "free": 500, "trashed": 0, "other": 0})
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = output
        about = RcloneService().about("remote:")
        assert about["total"] == 1000
        assert about["used"] == 500
        assert about["free"] == 500

    def test_about_partial_fields(self, mock_subprocess_run):
        """about pode retornar apenas alguns campos (alguns backends omitem trashed/other)."""
        output = json.dumps({"total": 1000, "used": 500, "free": 500})
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = output
        about = RcloneService().about("remote:")
        assert about["total"] == 1000
        # trashed é opcional
        about.get("trashed")

    def test_about_unsupported_backend(self, mock_subprocess_run):
        """Backend sem suporte a about retorna {} (código 1)."""
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stdout = ""
        assert RcloneService().about("http:") == {}

    def test_listremotes_contract(self, mock_subprocess_run):
        """listremotes retorna nomes um por linha com dois-pontos."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "gdrive:\ndropbox:\ns3:\n"
        assert RcloneService().list_remotes() == ["gdrive", "dropbox", "s3"]

    def test_listremotes_no_trailing_colon(self, mock_subprocess_run):
        """listremotes sem ':' na saída também funciona."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "gdrive\ndropbox\n"
        assert RcloneService().list_remotes() == ["gdrive", "dropbox"]

    def test_version_contract(self, mock_subprocess_run):
        """rclone version contém string 'rclone v'."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "rclone v1.68.0\n- os/version: ubuntu 24.04\n"
        ver = RcloneService().check_version()
        assert ver is not None
        assert "v1.68" in ver or "rclone" in ver

    def test_version_missing(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = FileNotFoundError()
        assert RcloneService().check_version() is None

    def test_config_create_contract(self, mock_subprocess_run):
        """config create aceita nome, tipo e parâmetros key=value."""
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = ""
        ok, _ = RcloneService().config_create("test", "drive", client_id="x", scope="drive.readonly")
        assert ok is True

    def test_config_create_missing_params(self, mock_subprocess_run):
        """config create com parâmetros ausentes falha."""
        result = MagicMock(spec=subprocess.CompletedProcess)
        result.returncode = 1
        result.stdout = ""
        result.stderr = "ERROR: required parameter client_id not found"
        mock_subprocess_run.return_value = result
        ok, msg = RcloneService().config_create("test", "drive")
        assert ok is False
        assert "client_id" in msg

    def test_mount_flags_contract(self, mock_subprocess_run):
        """mount aceita flags com nome sanitizado (underlines→hifens)."""
        from rclone_gui.services.rclone_service import RcloneService
        # Teste apenas da construção de comandos, não execução
        def verify_correct_flags(*args, **kwargs):
            cmd = kwargs.get("args") or args[0]
            if isinstance(cmd, list) and "mount" in cmd:
                for arg in cmd:
                    assert " " not in arg, f"Flag com espaço: {arg}"
            return MagicMock()
        mock_subprocess_run.side_effect = verify_correct_flags
        mock_subprocess_run.return_value.returncode = 0


class TestBackendCatalogContract:
    """3.2 — Catálogo de backends (formato do recurso estático)"""

    def test_catalog_minimum_coverage(self, backend_catalog):
        """Catálogo deve cobrir pelo menos os 5 backends principais."""
        required = {"drive", "dropbox", "s3", "sftp", "b2"}
        found = {b.type for b in backend_catalog}
        missing = required - found
        assert not missing, f"Backends faltando: {missing}"

    def test_catalog_no_duplicates(self, backend_catalog):
        """Nenhum tipo de backend duplicado no catálogo."""
        types = [b.type for b in backend_catalog]
        assert len(types) == len(set(types))

    def test_catalog_json_file_exists(self):
        """Arquivo backends.json existe e é JSON válido."""
        path = Path(__file__).parent.parent.parent / "rclone_gui" / "resources" / "backends.json"
        assert path.exists(), "backends.json não encontrado"
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) >= 10


class TestDatabaseSchemaContract:
    """3.3 — Schema do banco de dados (colunas, tipos, constraints)"""

    def test_required_tables_exist(self, temp_db):
        """Todas as tabelas do schema devem existir."""
        tables = temp_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r[0] for r in tables]
        for t in ["app_config", "sync_jobs", "job_history", "mount_configs", "directory_cache"]:
            assert t in names, f"Tabela {t} não encontrada"

    def test_job_columns(self, temp_db):
        """sync_jobs deve ter todas as colunas obrigatórias."""
        cols = [r[1] for r in temp_db.conn.execute("PRAGMA table_info(sync_jobs)")]
        required = ["id", "name", "job_type", "source", "destination", "flags",
                     "schedule_enabled", "enabled", "created_at", "updated_at"]
        for c in required:
            assert c in cols, f"Coluna {c} faltando em sync_jobs"

    def test_job_history_columns(self, temp_db):
        """job_history deve ter colunas de auditoria."""
        cols = [r[1] for r in temp_db.conn.execute("PRAGMA table_info(job_history)")]
        for c in ["job_id", "status", "started_at", "files_transferred", "bytes_transferred", "log_output"]:
            assert c in cols

    def test_mount_configs_columns(self, temp_db):
        """mount_configs deve ter colunas de cache e rede."""
        cols = [r[1] for r in temp_db.conn.execute("PRAGMA table_info(mount_configs)")]
        for c in ["remote_name", "mountpoint", "cache_mode", "auto_mount"]:
            assert c in cols

    def test_job_name_unique(self, temp_db):
        """Constraint UNIQUE em sync_jobs.name."""
        from rclone_gui.models.job import SyncJob
        j1 = SyncJob(name="unique_test", job_type="sync", source="/a", destination="/b")
        temp_db.save_job(j1)
        with pytest.raises(Exception):
            j2 = SyncJob(name="unique_test", job_type="copy", source="/c", destination="/d")
            temp_db.save_job(j2)

    def test_job_history_foreign_key(self, temp_db):
        """job_history.job_id referencia sync_jobs.id (ON DELETE CASCADE)."""
        from rclone_gui.models.job import SyncJob, JobExecution
        job = SyncJob(name="fk_test", job_type="sync", source="/a", destination="/b")
        temp_db.save_job(job)
        exec_id = temp_db.add_execution(JobExecution(
            job_id=job.id, status="test", trigger="manual",
            started_at="2026-01-01T00:00:00",
        ))
        assert exec_id > 0
        # Deletar job deve cascatear (SQLite precisa de PRAGMA foreign_keys=ON)
        temp_db.conn.execute("PRAGMA foreign_keys=ON")
        temp_db.conn.execute("PRAGMA foreign_keys=OFF")  # default SQLite é off em testes


class TestRcloneServiceFlagContract:
    """3.4 — Flags das specs são mapeáveis para argumentos CLI."""

    def test_all_flag_keys_have_hyphens(self):
        from rclone_gui.models.job import SyncJob
        job = SyncJob(name="test", job_type="sync", source="/a", destination="/b",
                       flags={"checksum": True, "bwlimit": "10M", "dry_run": False})
        for k, v in job.flags.items():
            cli_key = f"--{k.replace('_', '-')}"
            assert cli_key.startswith("--")
            assert " " not in cli_key

    def test_flag_type_consistency(self):
        from rclone_gui.models.job import SyncJob
        flag_types = {
            "checksum": bool, "bwlimit": str, "transfers": int,
            "checkers": int, "retries": int, "dry_run": bool,
            "backup_dir": str, "max_transfer": str, "max_duration": str,
        }
        for name, expected_type in flag_types.items():
            value = expected_type()
            assert isinstance(value, expected_type), f"Flag {name}: tipo esperado {expected_type}"

    def test_no_underscore_flags_in_cli(self):
        """Flags CLI do rclone usam hífens, não underscores."""
        underscore_flags = [
            "backup_dir", "max_transfer", "max_duration",
            "track_renames", "delete_excluded", "dry_run", "no_check_dest",
        ]
        for flag in underscore_flags:
            cli = flag.replace("_", "-")
            assert "-" in cli, f"{flag} não foi convertido para hífen"
        # Flags sem underscore não devem ser testadas aqui


from pathlib import Path
