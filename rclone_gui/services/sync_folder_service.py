from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..db.database import Database
from ..models.sync_folder import SyncFolderConfig
from .rclone_service import RcloneService


class SyncFolderService:
    def __init__(self, db: Optional[Database] = None,
                 db_path: Optional[str] = None,
                 rclone: Optional[RcloneService] = None):
        if db:
            self.db = db
        else:
            self.db = Database(db_path) if db_path else Database()
            self.db.connect()
        self.rclone = rclone or RcloneService()

    def register(self, config: SyncFolderConfig) -> int:
        existing = self.db.get_all_sync_folders()
        for f in existing:
            if str(Path(f.local_path).resolve()) == str(Path(config.local_path).resolve()):
                raise ValueError(
                    f"O caminho '{config.local_path}' j\u00e1 est\u00e1 registrado"
                )
        expanded = str(Path(config.local_path).expanduser().resolve())
        os.makedirs(expanded, exist_ok=True)
        config.local_path = expanded
        return self.db.save_sync_folder(config)

    def get_all(self) -> list[SyncFolderConfig]:
        return self.db.get_all_sync_folders()

    def get_enabled(self) -> list[SyncFolderConfig]:
        return [f for f in self.get_all() if f.enabled]

    def set_enabled(self, folder_id: int, enabled: bool):
        folders = self.get_all()
        for f in folders:
            if f.id == folder_id:
                f.enabled = enabled
                self.db.save_sync_folder(f)
                return

    def unregister(self, folder_id: int):
        self.db.delete_sync_folder(folder_id)

    def sync_now(self, folder_id: int) -> tuple[bool, str]:
        folders = self.get_all()
        cfg = next((f for f in folders if f.id == folder_id), None)
        if not cfg:
            return False, "Pasta de sincroniza\u00e7\u00e3o n\u00e3o encontrada"
        now = datetime.now(timezone.utc).isoformat()
        ok, msg = self.rclone.bisync(
            cfg.local_path, cfg.remote_path,
            conflict_resolution=cfg.conflict_resolution,
        )
        cfg.last_sync_at = now
        cfg.last_sync_status = "success" if ok else "failed"
        self.db.save_sync_folder(cfg)
        return ok, msg
