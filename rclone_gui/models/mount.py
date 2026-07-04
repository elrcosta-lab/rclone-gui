from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Optional


@dataclasses.dataclass
class MountConfig:
    id: Optional[int] = None
    remote_name: str = ""
    mountpoint: str = ""
    cache_mode: str = "writes"  # off, minimal, writes, full
    cache_max_age: str = "1h"
    cache_max_size: str = "1G"
    cache_dir: Optional[str] = None
    auto_mount: bool = False
    network_timeout: str = "10m"
    network_low_level_retries: int = 10
    bwlimit: Optional[str] = None
    extra_flags: dict = dataclasses.field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
