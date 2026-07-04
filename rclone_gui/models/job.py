from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Optional


@dataclasses.dataclass
class FilterRule:
    rule_type: str  # include, exclude, filter, min_size, max_size, min_age, max_age
    pattern: str
    description: Optional[str] = None


@dataclasses.dataclass
class SyncJob:
    id: Optional[int] = None
    name: str = ""
    job_type: str = "sync"  # sync, copy, move, bisync
    source: str = ""
    destination: str = ""
    flags: dict = dataclasses.field(default_factory=dict)
    filters: list[FilterRule] = dataclasses.field(default_factory=list)
    schedule_enabled: bool = False
    schedule_cron: Optional[str] = None
    schedule_type: str = "manual"  # manual, minutes, hourly, daily, weekly, custom
    schedule_interval: Optional[int] = None
    enabled: bool = True
    dry_run_first: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclasses.dataclass
class JobExecution:
    id: Optional[int] = None
    job_id: int = 0
    status: str = ""  # running, success, failed, cancelled
    trigger: str = ""  # manual, scheduled
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    files_transferred: int = 0
    files_checked: int = 0
    bytes_transferred: int = 0
    errors_count: int = 0
    fatal_error: Optional[str] = None
    log_output: Optional[str] = None
    is_dry_run: bool = False
