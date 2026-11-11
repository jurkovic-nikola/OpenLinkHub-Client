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
    check_updates = true   # look for a new release at startup
    start_minimized = false  # start in the tray (or minimized when there is no tray)

The CONFIG tab (``core/config_editor.py``) edits this file with :func:`write_values`, which keeps
comments and keys it does not know.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


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
    check_updates: bool = True
    start_minimized: bool = False

    @property
    def verify(self) -> bool | str:
        return self.ca_file or self.verify_tls

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        return cls.from_values(read_values(path or default_path()))

    @classmethod
    def from_values(cls, data: dict[str, Any]) -> Config:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass(frozen=True)
class Field:
    """How the CONFIG tab shows one :class:`Config` field."""
    key: str
    label: str
    help: str
    group: str  # "openlinkhub": only in editions that talk to OpenLinkHub
    restart: bool = True  # False: the running app applies it on save
    placeholder: str = ""


FIELDS: tuple[Field, ...] = (
    Field("base_url", "Server URL", "Address of OpenLinkHub.", "openlinkhub"),
    Field("origin", "Login origin",
          "Only with dashboard authentication: must equal authOrigin in OpenLinkHub's dashboard.json.",
          "openlinkhub", placeholder="not sent"),
    Field("ca_file", "CA certificate",
          "Certificate to verify OpenLinkHub's self-signed HTTPS certificate with, "
          "e.g. /opt/OpenLinkHub/certificates/server.crt. Takes precedence over Verify TLS.",
          "openlinkhub", placeholder="system certificates"),
    Field("verify_tls", "Verify TLS", "Check OpenLinkHub's HTTPS certificate.", "openlinkhub"),
    Field("username", "Username", "Filled in on the login dialog.", "openlinkhub", restart=False,
          placeholder="none"),
    Field("poll_interval", "Refresh interval", "Seconds between device list refreshes.", "client",
          restart=False),
    Field("check_updates", "Check for updates", "Look for a new release at startup.", "client",
          restart=False),
    Field("start_minimized", "Start minimized",
          "Start hidden in the system tray (minimized when there is no tray). Applies at the next start.",
          "client", restart=False),
)

DEFAULTS: dict[str, Any] = {f.name: f.default for f in fields(Config)}
TYPES: dict[str, type] = {f.name: type(f.default) for f in fields(Config)}


def read_values(path: Path) -> dict[str, Any]:
    """The top-level keys of the config file; empty when there is none."""
    if not path.is_file():
        return {}
    return tomllib.loads(path.read_text())


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float)):
        return repr(value)
    # A JSON string is a valid TOML basic string (same escapes, \uXXXX included).
    return json.dumps(str(value), ensure_ascii=False)


_TABLE = re.compile(r"^\s*\[")
_VALUE = r'(?:"(?:[^"\\]|\\.)*"|\'[^\']*\'|[^\s#]+)'


def _key_line(key: str) -> re.Pattern[str]:
    return re.compile(rf"^(\s*){re.escape(key)}(\s*=\s*){_VALUE}(\s*#.*)?\s*$")


def _key_start(key: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(key)}\s*=")


def write_values(path: Path, values: dict[str, Any], remove: set[str] = frozenset()) -> None:
    """Set ``values`` and drop the keys in ``remove`` (so they fall back to their default).

    Edits the file line by line so comments, blank lines and unknown keys survive; only
    single-line top-level ``key = value`` entries are touched.
    """
    text = path.read_text() if path.is_file() else ""
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines) if _TABLE.match(line)), len(lines))
    top, rest = lines[:end], lines[end:]
    for key in remove:
        top = [line for line in top if not _key_start(key).match(line)]
    for key, value in values.items():
        new = f"{key} = {toml_value(value)}"
        for i, line in enumerate(top):
            if _key_start(key).match(line):
                match = _key_line(key).match(line)
                top[i] = f"{match[1]}{key}{match[2]}{toml_value(value)}{match[3] or ''}" if match else new
                break
        else:
            while top and not top[-1].strip():
                top.pop()
            top.append(new)
    if rest:
        top.append("")
    out = "\n".join(top + rest).strip("\n")
    out = out + "\n" if out else ""
    tomllib.loads(out)  # never write a file the app cannot read back
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(out)
