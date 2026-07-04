from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..db.database import Database
from ..models.job import FilterRule, JobExecution, SyncJob


class JobService:
    def __init__(self, db: Database, rclone_binary: str = "rclone"):
        self.db = db
        self.rclone_binary = rclone_binary
        self._active_processes: dict[int, subprocess.Popen] = {}

    def get_all_jobs(self) -> list[SyncJob]:
        return self.db.get_all_jobs()

    def get_job(self, job_id: int) -> Optional[SyncJob]:
        return self.db.get_job(job_id)

    def save_job(self, job: SyncJob) -> int:
        return self.db.save_job(job)

    def delete_job(self, job_id: int):
        self.db.delete_job(job_id)

    def get_history(self, job_id: int, limit: int = 50) -> list[JobExecution]:
        return self.db.get_job_history(job_id, limit)

    def execute_job(
        self, job: SyncJob, trigger: str = "manual"
    ) -> tuple[subprocess.Popen, int]:
        exec_ = JobExecution(
            job_id=job.id or 0,
            status="running",
            trigger=trigger,
            started_at=datetime.now().isoformat(),
        )
        exec_id = self.db.add_execution(exec_)

        flags = job.flags.copy()
        for f in job.filters:
            key = f"--{f.rule_type}"
            flags[key] = f.pattern

        args = [self.rclone_binary, job.job_type, job.source, job.destination]
        for k, v in flags.items():
            flag_key = k if k.startswith("-") else f"--{k.replace('_', '-')}"
            if isinstance(v, bool):
                if v:
                    args.append(flag_key)
            else:
                args.append(f"{flag_key}={v}")

        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        self._active_processes[exec_id] = proc
        return proc, exec_id

    def cancel_job(self, exec_id: int):
        proc = self._active_processes.pop(exec_id, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def complete_execution(
        self, exec_id: int, status: str,
        files: int = 0, bytes_: int = 0, errors: int = 0,
        log: str = "", error_msg: str = "",
    ):
        now = datetime.now().isoformat()
        exec_row = self.db.conn.execute(
            "SELECT started_at FROM job_history WHERE id=?", (exec_id,)
        ).fetchone()
        started = exec_row["started_at"] if exec_row else now
        duration = None
        try:
            s = datetime.fromisoformat(started)
            f = datetime.fromisoformat(now)
            duration = (f - s).total_seconds()
        except (ValueError, TypeError):
            pass

        self.db.conn.execute(
            """UPDATE job_history SET status=?, finished_at=?,
            duration_seconds=?, files_transferred=?, bytes_transferred=?,
            errors_count=?, fatal_error=?, log_output=?
            WHERE id=?""",
            (status, now, duration, files, bytes_, errors, error_msg, log, exec_id),
        )
        self.db.conn.commit()
        self._active_processes.pop(exec_id, None)
