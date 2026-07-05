from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest


# ---- Fixtures: Database ----

@pytest.fixture
def temp_home() -> Generator[str, None, None]:
    """Temp home directory for DB isolation."""
    with tempfile.TemporaryDirectory() as d:
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = d
        yield d
        if old_home:
            os.environ["HOME"] = old_home
        else:
            del os.environ["HOME"]


@pytest.fixture
def temp_db(temp_home: str) -> Generator[Database, None, None]:
    """Isolated SQLite database for each test."""
    from rclone_gui.db.database import Database

    Database._instance = None
    db = Database.get_instance()
    db.db_path = os.path.join(temp_home, "test.db")
    db.connect()
    yield db
    db.close()


# ---- Fixtures: Services ----

@pytest.fixture
def rclone_service() -> RcloneService:
    from rclone_gui.services.rclone_service import RcloneService
    return RcloneService()


@pytest.fixture
def job_service(temp_db: Database) -> JobService:
    from rclone_gui.services.job_service import JobService
    return JobService(temp_db)


# ---- Fixtures: Models ----

@pytest.fixture
def sample_job() -> SyncJob:
    from rclone_gui.models.job import SyncJob, FilterRule
    return SyncJob(
        name="backup_diario",
        job_type="sync",
        source="/home/user/docs",
        destination="gdrive:Backup",
        flags={"checksum": True, "bwlimit": "10M", "transfers": 4, "checkers": 8},
        filters=[FilterRule(rule_type="exclude", pattern="*.tmp")],
        schedule_enabled=True,
        schedule_cron="0 2 * * *",
        schedule_type="daily",
        dry_run_first=True,
    )


@pytest.fixture
def sample_execution() -> JobExecution:
    from rclone_gui.models.job import JobExecution
    return JobExecution(
        job_id=1,
        status="success",
        trigger="scheduled",
        started_at="2026-07-04T02:00:00",
        finished_at="2026-07-04T02:15:30",
        duration_seconds=930.0,
        files_transferred=45,
        bytes_transferred=234_000_000,
        errors_count=0,
        is_dry_run=False,
    )


@pytest.fixture
def sample_mount() -> MountConfig:
    from rclone_gui.models.mount import MountConfig
    return MountConfig(
        remote_name="gdrive",
        mountpoint="/home/user/Rclone/Montagens/gdrive",
        cache_mode="writes",
        auto_mount=True,
    )

# ---- Fixtures: Mocked subprocess ----

@pytest.fixture
def mock_subprocess_run() -> Generator[MagicMock, None, None]:
    """Mock subprocess.run for unit tests."""
    with patch("subprocess.run") as mock:
        yield mock


@pytest.fixture
def mock_subprocess_popen() -> Generator[MagicMock, None, None]:
    """Mock subprocess.Popen for async tests."""
    with patch("subprocess.Popen") as mock:
        yield mock


# ---- Fixtures: Backend catalog ----

@pytest.fixture
def backend_catalog() -> list[BackendMeta]:
    from rclone_gui.services.rclone_service import RcloneService
    return RcloneService.load_backends_catalog()


# ---- Fixtures: Sample data for contract tests ----

@pytest.fixture
def sample_lsjson_output() -> str:
    return json.dumps([
        {"Name": "foto.jpg", "Path": "foto.jpg", "Size": 2048576, "ModTime": "2026-06-15T10:30:00.000Z", "IsDir": False, "MimeType": "image/jpeg"},
        {"Name": "Documentos", "Path": "Documentos", "Size": -1, "ModTime": "2026-07-01T08:00:00.000Z", "IsDir": True, "MimeType": "inode/directory"},
    ])


@pytest.fixture
def sample_about_output() -> str:
    return json.dumps({"total": 16106127360, "used": 7730941132, "free": 8375186228, "trashed": 0, "other": 0})


# Need to import the types at module level for fixtures
from rclone_gui.models.job import SyncJob, JobExecution, FilterRule
from rclone_gui.models.mount import MountConfig
from rclone_gui.models.remote import BackendMeta
from rclone_gui.models.sync_folder import SyncFolderConfig
from rclone_gui.services.rclone_service import RcloneService
from rclone_gui.services.job_service import JobService
from rclone_gui.db.database import Database
