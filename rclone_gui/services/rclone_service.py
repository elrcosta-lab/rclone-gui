from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from ..models.remote import BackendMeta, RemoteEntry

BACKENDS_JSON = Path(__file__).parent.parent / "resources" / "backends.json"


class RcloneService:
    def __init__(self, binary: str = "rclone"):
        self.binary = binary

    def _run(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.binary, *args],
            capture_output=True, text=True, timeout=timeout,
        )

    def _run_async(self, *args: str):
        return subprocess.Popen(
            [self.binary, *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    def check_version(self) -> Optional[str]:
        try:
            r = self._run("version", timeout=10)
            if r.returncode == 0:
                return r.stdout.strip()
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def list_remotes(self) -> list[str]:
        r = self._run("listremotes")
        if r.returncode != 0:
            return []
        return [line.strip().rstrip(":") for line in r.stdout.strip().split("\n") if line.strip()]

    def config_show(self, remote: str) -> dict:
        r = self._run("config", "show", remote)
        if r.returncode != 0:
            return {}
        return self._parse_ini_section(r.stdout)

    def config_create(self, name: str, backend_type: str, **params) -> tuple[bool, str]:
        args = ["config", "create", name, backend_type]
        for k, v in params.items():
            args.append(f"{k}={v}")
        r = self._run(*args, timeout=60)
        ok = r.returncode == 0
        return ok, r.stdout + r.stderr

    def config_update(self, name: str, **params) -> tuple[bool, str]:
        args = ["config", "update", name]
        for k, v in params.items():
            args.append(f"{k}={v}")
        r = self._run(*args, timeout=60)
        ok = r.returncode == 0
        return ok, r.stdout + r.stderr

    def config_delete(self, name: str) -> tuple[bool, str]:
        r = self._run("config", "delete", name, timeout=30)
        ok = r.returncode == 0
        return ok, r.stdout + r.stderr

    def authorize(self, backend_type: str) -> subprocess.Popen:
        return self._run_async("authorize", backend_type)

    def about(self, remote: str, timeout: int = 90) -> dict:
        r = self._run("about", "--json", f"{remote}:", timeout=timeout)
        if r.returncode != 0:
            return {}
        try:
            return json.loads(r.stdout)
        except (json.JSONDecodeError, ValueError):
            return {}

    def lsjson(self, path: str) -> list[dict]:
        r = self._run("lsjson", path, timeout=60)
        if r.returncode != 0:
            return []
        try:
            return json.loads(r.stdout)
        except (json.JSONDecodeError, ValueError):
            return []

    def mkdir(self, path: str) -> tuple[bool, str]:
        r = self._run("mkdir", path, timeout=30)
        return r.returncode == 0, r.stderr

    def delete_file(self, path: str) -> tuple[bool, str]:
        r = self._run("deletefile", path, timeout=30)
        return r.returncode == 0, r.stderr

    def purge(self, path: str) -> tuple[bool, str]:
        r = self._run("purge", path, timeout=60)
        return r.returncode == 0, r.stderr

    def moveto(self, src: str, dst: str) -> tuple[bool, str]:
        r = self._run("moveto", src, dst, timeout=60)
        return r.returncode == 0, r.stderr

    def mount(self, remote_path: str, mountpoint: str, **flags) -> subprocess.Popen:
        args = ["mount", remote_path, mountpoint, "--daemon"]
        for k, v in flags.items():
            if isinstance(v, bool):
                if v:
                    args.append(f"--{k.replace('_', '-')}")
            else:
                args.append(f"--{k.replace('_', '-')}={v}")
        return self._run_async(*args)

    def _parse_ini_section(self, text: str) -> dict:
        result = {}
        for line in text.split("\n"):
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    def copy(self, source: str, destination: str, flags: dict | None = None) -> tuple[bool, str]:
        args = ["copy", source, destination]
        if flags:
            for k, v in flags.items():
                if isinstance(v, bool):
                    if v:
                        args.append(f"--{k.replace('_', '-')}")
                else:
                    args.append(f"--{k.replace('_', '-')}={v}")
        r = self._run(*args, timeout=300)
        if r.returncode == 0:
            return True, ""
        return False, r.stderr.strip() or r.stdout.strip()

    def move(self, source: str, destination: str, flags: dict | None = None) -> tuple[bool, str]:
        args = ["move", source, destination]
        if flags:
            for k, v in flags.items():
                if isinstance(v, bool):
                    if v:
                        args.append(f"--{k.replace('_', '-')}")
                else:
                    args.append(f"--{k.replace('_', '-')}={v}")
        r = self._run(*args, timeout=300)
        if r.returncode == 0:
            return True, ""
        return False, r.stderr.strip() or r.stdout.strip()

    def bisync(self, source: str, destination: str,
               conflict_resolution: str = "newer",
               resync: bool = False,
               **flags) -> tuple[bool, str]:
        args = ["bisync", source, destination,
                "--conflict-resolve", conflict_resolution]
        if resync:
            args.append("--resync")
        for k, v in flags.items():
            if isinstance(v, bool):
                if v:
                    args.append(f"--{k.replace('_', '-')}")
            else:
                args.append(f"--{k.replace('_', '-')}={v}")
        r = self._run(*args, timeout=600)
        if r.returncode == 0:
            return True, ""
        return False, r.stderr.strip() or r.stdout.strip()

    @classmethod
    def load_backends_catalog(cls) -> list[BackendMeta]:
        if BACKENDS_JSON.exists():
            with open(BACKENDS_JSON) as f:
                data = json.load(f)
            return [BackendMeta(**item) for item in data]
        return _DEFAULT_BACKENDS


_DEFAULT_BACKENDS = [
    BackendMeta(type="drive", display_name="Google Drive",
                description="Google Drive (nuvem Google Workspace)",
                category="cloud", requires_oauth=True, oauth_provider="drive"),
    BackendMeta(type="dropbox", display_name="Dropbox",
                description="Dropbox (armazenamento pessoal e empresarial)",
                category="cloud", requires_oauth=True, oauth_provider="dropbox"),
    BackendMeta(type="onedrive", display_name="Microsoft OneDrive",
                description="OneDrive (Microsoft 365)",
                category="cloud", requires_oauth=True, oauth_provider="onedrive"),
    BackendMeta(type="s3", display_name="Amazon S3",
                description="Amazon Simple Storage Service (S3)",
                category="object_storage", requires_oauth=False),
    BackendMeta(type="b2", display_name="Backblaze B2",
                description="Backblaze B2 Cloud Storage",
                category="object_storage", requires_oauth=False),
    BackendMeta(type="sftp", display_name="SFTP",
                description="Conexão SSH/SCP/SFTP",
                category="file_transfer", requires_oauth=False),
    BackendMeta(type="webdav", display_name="WebDAV",
                description="Servidor WebDAV (Nextcloud, OwnCloud, etc.)",
                category="file_transfer", requires_oauth=False),
    BackendMeta(type="local", display_name="Sistema Local",
                description="Arquivos do computador local",
                category="cloud", requires_oauth=False),
    BackendMeta(type="pcloud", display_name="pCloud",
                description="pCloud armazenamento na nuvem",
                category="cloud", requires_oauth=True, oauth_provider="pcloud"),
    BackendMeta(type="mega", display_name="MEGA",
                description="MEGA.nz armazenamento criptografado",
                category="cloud", requires_oauth=True, oauth_provider="mega"),
    BackendMeta(type="box", display_name="Box",
                description="Box.com armazenamento empresarial",
                category="cloud", requires_oauth=True, oauth_provider="box"),
]
