"""The CONFIG tab: every :class:`Config` field, from the config file or its default."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, Signal, Slot

from olhclient.config import DEFAULTS, FIELDS, TYPES, Config, read_values, write_values

log = logging.getLogger(__name__)

MIN_POLL_INTERVAL = 0.5


def _kind(key: str) -> str:
    kind = TYPES[key]
    return "bool" if kind is bool else "number" if kind in (int, float) else "text"


def _display(key: str, value: Any) -> Any:
    """The value as the editor shows it: bools stay bools, everything else is text."""
    if _kind(key) == "bool":
        return bool(value)
    if _kind(key) == "number":
        return f"{float(value):g}"
    return str(value)


class ConfigEditor(QObject):
    """QML ``config``. Edits are kept here until ``save()`` writes them to the file.

    A key is *explicit* when the file sets it; ``useDefault`` removes it from the file on save.
    ``apply`` receives the saved :class:`Config` for the settings the running app can change
    (refresh interval); connection settings need a restart (``restart``).
    """

    changed = Signal()
    savedChanged = Signal()
    message = Signal(str, bool)

    def __init__(self, path: Path, *, openlinkhub: bool = True, overrides: dict[str, str] | None = None,
                 apply: Callable[[Config], None] | None = None, restart: Callable[[], None] | None = None,
                 parent: QObject | None = None):
        super().__init__(parent)
        self._path = path
        self._fields = [f for f in FIELDS if openlinkhub or f.group != "openlinkhub"]
        self._overrides = overrides or {}
        self._apply = apply
        self._restart = restart
        self._load_error = ""
        self._file: dict[str, Any] = self._read()
        self._startup = Config.from_values(self._file)
        self._restart_needed = False
        self._reset()

    def _read(self) -> dict[str, Any]:
        try:
            values = read_values(self._path)
        except (OSError, ValueError) as exc:  # tomllib.TOMLDecodeError is a ValueError
            self._load_error = f"Cannot read the config file: {exc}"
            return {}
        self._load_error = ""
        return values

    def _reset(self) -> None:
        self._values = {f.key: _display(f.key, self._file.get(f.key, DEFAULTS[f.key])) for f in self._fields}
        self._explicit = {f.key: f.key in self._file for f in self._fields}
        self._errors: dict[str, str] = {}
        self._dirty = False

    # -- QML API ---------------------------------------------------------------
    @Property(str, constant=True)
    def path(self) -> str:
        return str(self._path)

    @Property("QVariantList", constant=True)
    def fields(self) -> list[dict[str, Any]]:
        return [{"key": f.key, "label": f.label, "help": f.help, "group": f.group, "restart": f.restart,
                 "kind": _kind(f.key), "placeholder": f.placeholder,
                 "defaultValue": _display(f.key, DEFAULTS[f.key]), "override": self._overrides.get(f.key, "")}
                for f in self._fields]

    @Property("QVariantMap", notify=changed)
    def values(self) -> dict[str, Any]:
        return dict(self._values)

    @Property("QVariantMap", notify=changed)
    def explicit(self) -> dict[str, bool]:
        return dict(self._explicit)

    @Property("QVariantMap", notify=changed)
    def errors(self) -> dict[str, str]:
        return dict(self._errors)

    @Property(bool, notify=changed)
    def dirty(self) -> bool:
        return self._dirty

    @Property(str, notify=changed)
    def loadError(self) -> str:
        return self._load_error

    @Property(bool, notify=savedChanged)
    def restartNeeded(self) -> bool:
        return self._restart_needed

    @Property(bool, constant=True)
    def canRestart(self) -> bool:
        return self._restart is not None

    @Property("QVariantMap", notify=savedChanged)
    def saved(self) -> dict[str, Any]:
        """The settings as saved in the file (defaults filled in)."""
        return asdict(Config.from_values(self._file))

    @Slot(str, "QVariant")
    def setValue(self, key: str, value: Any) -> None:
        if key not in self._values:
            return
        self._values[key] = value
        self._explicit[key] = True
        self._errors.pop(key, None)
        if _kind(key) == "number":
            try:
                number = float(str(value).strip())
            except ValueError:
                number = None
            if number is None or number < MIN_POLL_INTERVAL:
                self._errors[key] = f"Enter a number of at least {MIN_POLL_INTERVAL:g}"
        self._dirty = True
        self.changed.emit()

    @Slot(str)
    def useDefault(self, key: str) -> None:
        if key not in self._values:
            return
        self._values[key] = _display(key, DEFAULTS[key])
        self._explicit[key] = False
        self._errors.pop(key, None)
        self._dirty = True
        self.changed.emit()

    @Slot()
    def revert(self) -> None:
        self._file = self._read()
        self._reset()
        self.changed.emit()

    @Slot(result=bool)
    def save(self) -> bool:
        if self._errors:
            return False
        values = {key: self._typed(key) for key, explicit in self._explicit.items() if explicit}
        remove = {key for key, explicit in self._explicit.items() if not explicit}
        try:
            write_values(self._path, values, remove)
        except (OSError, ValueError) as exc:
            log.warning("saving %s failed: %s", self._path, exc)
            self.message.emit(f"Cannot save the config: {exc}", True)
            return False
        self._file = self._read()
        self._reset()
        config = Config.from_values(self._file)
        self._restart_needed = any(getattr(config, f.key) != getattr(self._startup, f.key)
                                   for f in self._fields if f.restart)
        if self._apply is not None:
            self._apply(config)
        self.changed.emit()
        self.savedChanged.emit()
        self.message.emit("Restart to apply the connection settings" if self._restart_needed
                          else "Settings saved", False)
        return True

    @Slot()
    def restart(self) -> None:
        if self._restart is not None:
            self._restart()

    def _typed(self, key: str) -> Any:
        value = self._values[key]
        kind = TYPES[key]
        if kind is bool:
            return bool(value)
        if kind in (int, float):
            return float(str(value).strip())
        return str(value).strip()
