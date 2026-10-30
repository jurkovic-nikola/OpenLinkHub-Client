"""Discovery of device modules.

Every sub-package of :mod:`olhclient.devices` that exposes a ``MODULES``
sequence is picked up automatically. External packages can add modules through
the ``olhclient.devices`` entry-point group; the entry point must resolve to a
sequence of :class:`DeviceModule` or a callable returning one.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from importlib.metadata import entry_points
from typing import Any, Iterable

import olhclient.devices as devices_pkg
from olhclient.devices.base import DeviceModule

log = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "olhclient.devices"


class Registry:
    def __init__(self, modules: Iterable[DeviceModule]):
        self.modules = list(modules)

    @classmethod
    def discover(cls) -> Registry:
        modules: list[DeviceModule] = []
        for info in pkgutil.iter_modules(devices_pkg.__path__, devices_pkg.__name__ + "."):
            if not info.ispkg:
                continue
            package = importlib.import_module(info.name)
            modules.extend(getattr(package, "MODULES", ()))
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            try:
                loaded = ep.load()
                modules.extend(loaded() if callable(loaded) else loaded)
            except Exception:  # a broken plugin must not take the client down
                log.exception("failed to load device plugin %s", ep.name)
        return cls(modules)

    def match(self, device: dict[str, Any]) -> DeviceModule:
        scored = [(module.match_score(device), module) for module in self.modules]
        score, module = max(scored, key=lambda item: item[0], default=(0, None))
        if module is None or score <= 0:
            raise LookupError(f"no device module for product id {device.get('ProductId')}")
        return module

    def get(self, module_id: str) -> DeviceModule:
        return next(m for m in self.modules if m.id == module_id)
