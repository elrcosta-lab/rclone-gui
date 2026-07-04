from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Optional


@dataclasses.dataclass
class BackendMeta:
    type: str
    display_name: str
    description: str
    category: str
    requires_oauth: bool
    oauth_provider: Optional[str] = None
    fields: list[BackendField] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class BackendField:
    name: str
    label: str
    description: str
    required: bool = False
    advanced: bool = False
    field_type: str = "string"  # string, int, bool, choice, password, filepath
    choices: Optional[list[str]] = None
    default: Optional[str] = None
    placeholder: Optional[str] = None


@dataclasses.dataclass
class RemoteEntry:
    name: str
    type: str
    parameters: dict = dataclasses.field(default_factory=dict)
    is_encrypted: bool = False


@dataclasses.dataclass
class RemoteStatus:
    name: str
    online: bool = False
    quota_used: Optional[int] = None
    quota_free: Optional[int] = None
    quota_total: Optional[int] = None
    error_message: Optional[str] = None
