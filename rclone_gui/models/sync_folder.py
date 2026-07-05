from __future__ import annotations

import dataclasses
from typing import Optional


@dataclasses.dataclass
class SyncFolderConfig:
    id: Optional[int] = None
    name: str = ""
    local_path: str = ""
    remote_path: str = ""
    sync_mode: str = "bisync"
    conflict_resolution: str = "newer"
    polling_interval: int = 300
    debounce_seconds: int = 5
    enabled: bool = True
    last_sync_at: Optional[str] = None
    last_sync_status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d.pop("created_at", None)
        d.pop("updated_at", None)
        return d

    @classmethod
    def from_row(cls, row) -> "SyncFolderConfig":
        return cls(
            id=row["id"],
            name=row["name"],
            local_path=row["local_path"],
            remote_path=row["remote_path"],
            sync_mode=row["sync_mode"],
            conflict_resolution=row["conflict_resolution"],
            polling_interval=row["polling_interval"],
            debounce_seconds=row["debounce_seconds"],
            enabled=bool(row["enabled"]),
            last_sync_at=row["last_sync_at"],
            last_sync_status=row["last_sync_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
