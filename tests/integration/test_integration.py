"""Testes de integração — interação entre componentes (service + db + subprocess real)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from rclone_gui.models.job import SyncJob, JobExecution


class TestJobServiceIntegration:
    """2.1 — JobService + Database"""

    def test_job_service_create(self, job_service):
        job = SyncJob(name="integ_test", job_type="sync", source="/a", destination="/b")
        job_id = job_service.save_job(job)
        assert job_id > 0

    def test_job_service_get(self, job_service):
        job = SyncJob(name="integ_test2", job_type="copy", source="/a", destination="/b")
        job_service.save_job(job)
        retrieved = job_service.get_job(job.id)
        assert retrieved is not None
        assert retrieved.name == "integ_test2"

    def test_job_service_list(self, job_service):
        for i in range(3):
            job = SyncJob(name=f"job_{i}", job_type="sync", source="/a", destination=f"/b{i}")
            job_service.save_job(job)
        assert len(job_service.get_all_jobs()) == 3

    def test_job_service_update(self, job_service):
        job = SyncJob(name="update_test", job_type="sync", source="/a", destination="/b")
        job_service.save_job(job)
        job.name = "updated"
        job_service.save_job(job)
        assert job_service.get_job(job.id).name == "updated"

    def test_job_service_delete(self, job_service):
        job = SyncJob(name="del_test", job_type="sync", source="/a", destination="/b")
        job_service.save_job(job)
        job_service.delete_job(job.id)
        assert len(job_service.get_all_jobs()) == 0

    def test_job_execution_history(self, job_service):
        job = SyncJob(name="hist_test", job_type="sync", source="/a", destination="/b")
        job_service.save_job(job)

        from datetime import datetime
        exec_ = JobExecution(
            job_id=job.id, status="running", trigger="manual",
            started_at=datetime.now().isoformat(),
        )
        exec_id = job_service.db.add_execution(exec_)
        assert exec_id > 0

        history = job_service.get_history(job.id)
        assert len(history) == 1
        assert history[0].status == "running"

    def test_job_execution_complete(self, job_service):
        job = SyncJob(name="complete_test", job_type="sync", source="/a", destination="/b")
        job_service.save_job(job)

        from datetime import datetime
        exec_ = JobExecution(
            job_id=job.id, status="running", trigger="manual",
            started_at=datetime.now().isoformat(),
        )
        exec_id = job_service.db.add_execution(exec_)
        job_service.complete_execution(
            exec_id, "success", files=10, bytes_=500,
            log="All files transferred", error_msg="",
        )
        history = job_service.get_history(job.id)
        assert history[0].status == "success"
        assert history[0].files_transferred == 10

    def test_job_execution_cancel(self, job_service):
        job = SyncJob(name="cancel_test", job_type="sync", source="/a", destination="/b")
        job_service.save_job(job)

        from datetime import datetime
        exec_ = JobExecution(
            job_id=job.id, status="running", trigger="manual",
            started_at=datetime.now().isoformat(),
        )
        exec_id = job_service.db.add_execution(exec_)

        # Simula cancelamento (sem processo real, apenas marcação)
        job_service.complete_execution(
            exec_id, "cancelled", log="Cancelled by user",
            error_msg="User cancelled",
        )
        history = job_service.get_history(job.id)
        assert history[0].status == "cancelled"

    def test_job_execution_failed(self, job_service):
        job = SyncJob(name="fail_test", job_type="sync", source="/a", destination="/b")
        job_service.save_job(job)

        from datetime import datetime
        exec_ = JobExecution(
            job_id=job.id, status="running", trigger="scheduled",
            started_at=datetime.now().isoformat(),
        )
        exec_id = job_service.db.add_execution(exec_)
        job_service.complete_execution(
            exec_id, "failed", errors=3, log="Connection timeout",
            error_msg="Backend offline",
        )
        history = job_service.get_history(job.id)
        assert history[0].status == "failed"
        assert "Backend offline" in (history[0].fatal_error or "")

    def test_database_persistence_across_service(self, job_service):
        """Verifica que dados escritos pelo JobService são lidos pelo Database."""
        job = SyncJob(name="persist_test", job_type="move", source="/a", destination="/b")
        job_service.save_job(job)

        from rclone_gui.db.database import Database
        db = Database.get_instance()
        retrieved = db.get_job(job.id)
        assert retrieved.job_type == "move"

    def test_mount_config_integration(self, temp_db):
        """Mount config via DB com operações completas."""
        from rclone_gui.models.mount import MountConfig

        mc = MountConfig(remote_name="test_mount", mountpoint="/mnt/test",
                          cache_mode="full", auto_mount=True,
                          bwlimit="5M", network_timeout="30s")
        temp_db.save_mount_config(mc)
        assert mc.id is not None

        retrieved = temp_db.get_mount_config("test_mount")
        assert retrieved.bwlimit == "5M"
        assert retrieved.cache_mode == "full"
        assert retrieved.network_timeout == "30s"

        retrieved.bwlimit = "10M"
        temp_db.save_mount_config(retrieved)
        assert temp_db.get_mount_config("test_mount").bwlimit == "10M"

        temp_db.delete_mount_config("test_mount")
        assert temp_db.get_mount_config("test_mount") is None


class TestSchedulerIntegration:
    """2.2 — Integração Scheduler + JobService (sem rclone real)"""

    def test_scheduler_scan_no_crash(self, job_service):
        from rclone_gui.daemon.daemon_app import Scheduler
        sched = Scheduler(job_service)
        # Deve executar sem erros mesmo sem jobs
        sched.scan_and_execute()

    def test_scheduler_scan_with_jobs(self, job_service):
        from rclone_gui.daemon.daemon_app import Scheduler
        job = SyncJob(name="scheduled_job", job_type="sync",
                       source="/a", destination="/b",
                       schedule_enabled=True,
                       schedule_cron="0 2 * * *",
                       schedule_type="daily")
        job_service.save_job(job)

        sched = Scheduler(job_service)
        # Deve executar sem crash (não executa jobs que não são devidos)
        sched.scan_and_execute()
