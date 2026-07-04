from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from ..db.database import Database
from ..services.job_service import JobService
from ..services.rclone_service import RcloneService


class RCDManager:
    def __init__(self, port: int = 5572, user: str = "rgui", password: str = ""):
        self.port = port
        self.user = user
        self.password = password
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        if self.process and self.process.poll() is None:
            return True
        try:
            self.process = subprocess.Popen(
                [
                    "rclone", "rcd",
                    f"--rc-addr=localhost:{self.port}",
                    f"--rc-user={self.user}",
                    f"--rc-pass={self.password}",
                    "--rc-no-auth=false",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
            return self.process.poll() is None
        except FileNotFoundError:
            return False

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def is_healthy(self) -> bool:
        if not self.process or self.process.poll() is not None:
            return False
        try:
            r = subprocess.run(
                ["rclone", "rc", "core/version",
                 f"--rc-addr=localhost:{self.port}",
                 f"--rc-user={self.user}",
                 f"--rc-pass={self.password}"],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


class Scheduler:
    def __init__(self, job_service: JobService):
        self.job_service = job_service
        self._running = False
        self._paused = False

    def scan_and_execute(self):
        if self._paused:
            return
        from datetime import datetime
        import dateutil.parser

        jobs = self.job_service.get_all_jobs()
        now = datetime.now()
        for job in jobs:
            if not job.enabled or not job.schedule_enabled:
                continue
            if job.schedule_cron:
                try:
                    from croniter import croniter
                    base = croniter(job.schedule_cron, now)
                    prev = base.get_prev(datetime)
                    if (now - prev).total_seconds() < 90:
                        self.job_service.execute_job(job, trigger="scheduled")
                except (ImportError, ValueError):
                    pass
            elif job.schedule_type in ("minutes", "hourly", "daily", "weekly") and job.schedule_interval:
                from datetime import timedelta
                last_exec = self.job_service.db.conn.execute(
                    "SELECT started_at FROM job_history WHERE job_id=? ORDER BY started_at DESC LIMIT 1",
                    (job.id,),
                ).fetchone()
                if last_exec:
                    last_time = dateutil.parser.parse(last_exec[0])
                    if (now - last_time).total_seconds() < job.schedule_interval * 60:
                        continue
                self.job_service.execute_job(job, trigger="scheduled")


class DaemonApp:
    def __init__(self):
        self.db = Database.get_instance()
        self.db.connect()
        self.rclone = RcloneService()
        self.job_service = JobService(self.db)
        self.scheduler = Scheduler(self.job_service)
        self.rcd = RCDManager(
            port=self.db.get_config("rcd_port", 5572),
            user=self.db.get_config("rcd_user", "rgui"),
            password=self.db.get_config("rcd_pass_hash", ""),
        )
        self._running = False

    def start(self):
        self._running = True
        self.rcd.start()
        self._run_loop()

    def stop(self):
        self._running = False
        self.rcd.stop()
        self.db.close()

    def _run_loop(self):
        import select
        while self._running:
            self.scheduler.scan_and_execute()
            if not self.rcd.is_healthy():
                self.rcd.stop()
                self.rcd.start()
            time.sleep(30)

    def run(self):
        signal.signal(signal.SIGINT, lambda s, f: self.stop())
        signal.signal(signal.SIGTERM, lambda s, f: self.stop())
        self.start()


def main():
    app = DaemonApp()
    app.run()
