"""Client settings, read from ``$XDG_CONFIG_HOME/olh-client/config.toml``.

Example::

    base_url = "https://127.0.0.1:27003"
    # Must equal "authOrigin" in OpenLinkHub's dashboard.json when auth is on.
    origin = "https://127.0.0.1:27003"
    # OpenLinkHub generates a self-signed certificate; point at it to verify TLS.
    ca_file = "/opt/OpenLinkHub/certificates/server.crt"
    verify_tls = true
    username = "admin"
    poll_interval = 5
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


def default_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "olh-client" / "config.toml"


@dataclass
class Config:
    base_url: str = "http://127.0.0.1:27003"
    origin: str = ""
    ca_file: str = ""
    verify_tls: bool = True
    username: str = ""
    poll_interval: float = 5.0

    @property
    def verify(self) -> bool | str:
        return self.ca_file or self.verify_tls

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or default_path()
        if not path.is_file():
            return cls()
        data = tomllib.loads(path.read_text())
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
