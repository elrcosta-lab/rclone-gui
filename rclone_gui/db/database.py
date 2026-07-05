from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from ..models.job import FilterRule, JobExecution, SyncJob
from ..models.mount import MountConfig
from ..models.sync_folder import SyncFolderConfig


def get_db_path() -> str:
    base = Path.home() / ".local" / "share" / "rclone-gui"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "rclone-gui.db")


class Database:
    _instance: Optional["Database"] = None

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()
        self.conn: Optional[sqlite3.Connection] = None

    @classmethod
    def get_instance(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _migrate(self):
        c = self.conn.execute("PRAGMA user_version")
        version = c.fetchone()[0]

        if version < 1:
            self._migrate_v1()
            version = 1
        if version < 2:
            self._migrate_v2()
            version = 2

    def _migrate_v1(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS app_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                autostart_enabled INTEGER DEFAULT 0,
                tray_enabled INTEGER DEFAULT 1,
                minimize_to_tray INTEGER DEFAULT 1,
                close_to_tray INTEGER DEFAULT 1,
                rcd_port INTEGER DEFAULT 5572,
                rcd_user TEXT DEFAULT 'rgui',
                rcd_pass_hash TEXT,
                daemon_log_level TEXT DEFAULT 'INFO',
                notifications_enabled INTEGER DEFAULT 1,
                notifications_job_success INTEGER DEFAULT 1,
                notifications_job_failure INTEGER DEFAULT 1,
                notifications_mount_error INTEGER DEFAULT 1,
                first_run_completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sync_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                job_type TEXT NOT NULL DEFAULT 'sync',
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                flags TEXT NOT NULL DEFAULT '{}',
                filters TEXT NOT NULL DEFAULT '[]',
                schedule_enabled INTEGER DEFAULT 0,
                schedule_cron TEXT,
                schedule_type TEXT DEFAULT 'manual',
                schedule_interval INTEGER,
                enabled INTEGER DEFAULT 1,
                dry_run_first INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS job_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES sync_jobs(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                trigger TEXT NOT NULL DEFAULT 'manual',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                files_transferred INTEGER DEFAULT 0,
                files_checked INTEGER DEFAULT 0,
                bytes_transferred INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                fatal_error TEXT,
                log_output TEXT,
                is_dry_run INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS mount_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                remote_name TEXT NOT NULL UNIQUE,
                mountpoint TEXT NOT NULL,
                cache_mode TEXT DEFAULT 'writes',
                cache_max_age TEXT DEFAULT '1h',
                cache_max_size TEXT DEFAULT '1G',
                cache_dir TEXT,
                auto_mount INTEGER DEFAULT 0,
                network_timeout TEXT DEFAULT '10m',
                network_low_level_retries INTEGER DEFAULT 10,
                bwlimit TEXT,
                extra_flags TEXT DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS directory_cache (
                path TEXT PRIMARY KEY,
                json_data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            INSERT OR IGNORE INTO app_config (id) VALUES (1);
            PRAGMA user_version = 1;
        """)
        self.conn.commit()

    def _migrate_v2(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                local_path TEXT NOT NULL UNIQUE,
                remote_path TEXT NOT NULL,
                sync_mode TEXT DEFAULT 'bisync',
                conflict_resolution TEXT DEFAULT 'newer',
                polling_interval INTEGER DEFAULT 300,
                debounce_seconds INTEGER DEFAULT 5,
                enabled INTEGER DEFAULT 1,
                last_sync_at TEXT,
                last_sync_status TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        try:
            self.conn.execute(
                "ALTER TABLE app_config ADD COLUMN sync_folder_root_path "
                "TEXT DEFAULT '~/RcloneSync'"
            )
        except sqlite3.OperationalError:
            pass
        self.conn.execute("PRAGMA user_version = 2")
        self.conn.commit()

    # ---- App Config ----

    def get_config(self, key: str, default=None):
        row = self.conn.execute(
            f"SELECT {key} FROM app_config WHERE id=1"
        ).fetchone()
        if row is None:
            return default
        return row[0]

    def set_config(self, key: str, value):
        self.conn.execute(
            f"UPDATE app_config SET {key}=?, updated_at=datetime('now') WHERE id=1",
            (value,),
        )
        self.conn.commit()

    # ---- Sync Jobs ----

    def get_all_jobs(self) -> list[SyncJob]:
        rows = self.conn.execute(
            "SELECT * FROM sync_jobs ORDER BY name"
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_job(self, job_id: int) -> Optional[SyncJob]:
        row = self.conn.execute(
            "SELECT * FROM sync_jobs WHERE id=?", (job_id,)
        ).fetchone()
        return self._row_to_job(row) if row else None

    def save_job(self, job: SyncJob) -> int:
        if job.id:
            self.conn.execute(
                """UPDATE sync_jobs SET
                name=?, job_type=?, source=?, destination=?, flags=?,
                filters=?, schedule_enabled=?, schedule_cron=?,
                schedule_type=?, schedule_interval=?, enabled=?,
                dry_run_first=?, updated_at=datetime('now')
                WHERE id=?""",
                (
                    job.name, job.job_type, job.source, job.destination,
                    json.dumps(job.flags), json.dumps([f.__dict__ for f in job.filters]),
                    int(job.schedule_enabled), job.schedule_cron,
                    job.schedule_type, job.schedule_interval,
                    int(job.enabled), int(job.dry_run_first),
                    job.id,
                ),
            )
        else:
            cur = self.conn.execute(
                """INSERT INTO sync_jobs
                (name, job_type, source, destination, flags, filters,
                 schedule_enabled, schedule_cron, schedule_type,
                 schedule_interval, enabled, dry_run_first)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job.name, job.job_type, job.source, job.destination,
                    json.dumps(job.flags), json.dumps([f.__dict__ for f in job.filters]),
                    int(job.schedule_enabled), job.schedule_cron,
                    job.schedule_type, job.schedule_interval,
                    int(job.enabled), int(job.dry_run_first),
                ),
            )
            job.id = cur.lastrowid
        self.conn.commit()
        return job.id

    def delete_job(self, job_id: int):
        self.conn.execute("DELETE FROM sync_jobs WHERE id=?", (job_id,))
        self.conn.commit()

    def _row_to_job(self, row) -> SyncJob:
        flags = json.loads(row["flags"]) if row["flags"] else {}
        filters_data = json.loads(row["filters"]) if row["filters"] else []
        filters = [FilterRule(**f) for f in filters_data]
        return SyncJob(
            id=row["id"],
            name=row["name"],
            job_type=row["job_type"],
            source=row["source"],
            destination=row["destination"],
            flags=flags,
            filters=filters,
            schedule_enabled=bool(row["schedule_enabled"]),
            schedule_cron=row["schedule_cron"],
            schedule_type=row["schedule_type"],
            schedule_interval=row["schedule_interval"],
            enabled=bool(row["enabled"]),
            dry_run_first=bool(row["dry_run_first"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ---- Job History ----

    def add_execution(self, exec_: JobExecution) -> int:
        cur = self.conn.execute(
            """INSERT INTO job_history
            (job_id, status, trigger, started_at, finished_at, duration_seconds,
             files_transferred, files_checked, bytes_transferred, errors_count,
             fatal_error, log_output, is_dry_run)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                exec_.job_id, exec_.status, exec_.trigger,
                exec_.started_at, exec_.finished_at, exec_.duration_seconds,
                exec_.files_transferred, exec_.files_checked,
                exec_.bytes_transferred, exec_.errors_count,
                exec_.fatal_error, exec_.log_output, int(exec_.is_dry_run),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_job_history(self, job_id: int, limit: int = 50) -> list[JobExecution]:
        rows = self.conn.execute(
            "SELECT * FROM job_history WHERE job_id=? ORDER BY started_at DESC LIMIT ?",
            (job_id, limit),
        ).fetchall()
        return [self._row_to_execution(r) for r in rows]

    def _row_to_execution(self, row) -> JobExecution:
        return JobExecution(
            id=row["id"],
            job_id=row["job_id"],
            status=row["status"],
            trigger=row["trigger"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            duration_seconds=row["duration_seconds"],
            files_transferred=row["files_transferred"],
            files_checked=row["files_checked"],
            bytes_transferred=row["bytes_transferred"],
            errors_count=row["errors_count"],
            fatal_error=row["fatal_error"],
            log_output=row["log_output"],
            is_dry_run=bool(row["is_dry_run"]),
        )

    # ---- Mount Configs ----

    def get_all_mount_configs(self) -> list[MountConfig]:
        rows = self.conn.execute(
            "SELECT * FROM mount_configs ORDER BY remote_name"
        ).fetchall()
        return [self._row_to_mount(r) for r in rows]

    def get_mount_config(self, remote_name: str) -> Optional[MountConfig]:
        row = self.conn.execute(
            "SELECT * FROM mount_configs WHERE remote_name=?", (remote_name,)
        ).fetchone()
        return self._row_to_mount(row) if row else None

    def save_mount_config(self, mc: MountConfig):
        if mc.id:
            self.conn.execute(
                """UPDATE mount_configs SET mountpoint=?, cache_mode=?,
                cache_max_age=?, cache_max_size=?, cache_dir=?,
                auto_mount=?, network_timeout=?, network_low_level_retries=?,
                bwlimit=?, extra_flags=?, updated_at=datetime('now')
                WHERE id=?""",
                (
                    mc.mountpoint, mc.cache_mode, mc.cache_max_age,
                    mc.cache_max_size, mc.cache_dir, int(mc.auto_mount),
                    mc.network_timeout, mc.network_low_level_retries,
                    mc.bwlimit, json.dumps(mc.extra_flags), mc.id,
                ),
            )
        else:
            cur = self.conn.execute(
                """INSERT INTO mount_configs
                (remote_name, mountpoint, cache_mode, cache_max_age,
                 cache_max_size, cache_dir, auto_mount, network_timeout,
                 network_low_level_retries, bwlimit, extra_flags)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    mc.remote_name, mc.mountpoint, mc.cache_mode,
                    mc.cache_max_age, mc.cache_max_size, mc.cache_dir,
                    int(mc.auto_mount), mc.network_timeout,
                    mc.network_low_level_retries, mc.bwlimit,
                    json.dumps(mc.extra_flags),
                ),
            )
            mc.id = cur.lastrowid
        self.conn.commit()

    def delete_mount_config(self, remote_name: str):
        self.conn.execute(
            "DELETE FROM mount_configs WHERE remote_name=?", (remote_name,)
        )
        self.conn.commit()

    def _row_to_mount(self, row) -> MountConfig:
        extra = json.loads(row["extra_flags"]) if row["extra_flags"] else {}
        return MountConfig(
            id=row["id"],
            remote_name=row["remote_name"],
            mountpoint=row["mountpoint"],
            cache_mode=row["cache_mode"],
            cache_max_age=row["cache_max_age"],
            cache_max_size=row["cache_max_size"],
            cache_dir=row["cache_dir"],
            auto_mount=bool(row["auto_mount"]),
            network_timeout=row["network_timeout"],
            network_low_level_retries=row["network_low_level_retries"],
            bwlimit=row["bwlimit"],
            extra_flags=extra,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ---- Sync Folders ----

    def save_sync_folder(self, cfg: SyncFolderConfig) -> int:
        if cfg.id:
            self.conn.execute(
                """UPDATE sync_folders SET name=?, local_path=?, remote_path=?,
                sync_mode=?, conflict_resolution=?, polling_interval=?,
                debounce_seconds=?, enabled=?, last_sync_at=?,
                last_sync_status=?, updated_at=datetime('now')
                WHERE id=?""",
                (
                    cfg.name, cfg.local_path, cfg.remote_path,
                    cfg.sync_mode, cfg.conflict_resolution,
                    cfg.polling_interval, cfg.debounce_seconds,
                    int(cfg.enabled), cfg.last_sync_at,
                    cfg.last_sync_status, cfg.id,
                ),
            )
        else:
            cur = self.conn.execute(
                """INSERT INTO sync_folders
                (name, local_path, remote_path, sync_mode, conflict_resolution,
                 polling_interval, debounce_seconds, enabled, last_sync_at,
                 last_sync_status)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    cfg.name, cfg.local_path, cfg.remote_path,
                    cfg.sync_mode, cfg.conflict_resolution,
                    cfg.polling_interval, cfg.debounce_seconds,
                    int(cfg.enabled), cfg.last_sync_at,
                    cfg.last_sync_status,
                ),
            )
            cfg.id = cur.lastrowid
        self.conn.commit()
        return cfg.id

    def get_all_sync_folders(self) -> list[SyncFolderConfig]:
        rows = self.conn.execute(
            "SELECT * FROM sync_folders ORDER BY name"
        ).fetchall()
        return [SyncFolderConfig.from_row(r) for r in rows]

    def delete_sync_folder(self, folder_id: int):
        self.conn.execute(
            "DELETE FROM sync_folders WHERE id=?", (folder_id,)
        )
        self.conn.commit()
