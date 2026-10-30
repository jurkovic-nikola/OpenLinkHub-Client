"""Fallback for mice without a dedicated module: list-based UI, no hotspots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from olhclient.devices.base import DeviceModule, load_layout
from olhclient.devices.features import Feature

HERE = Path(__file__).parent


class GenericMouse(DeviceModule):
    id = "generic-mouse"
    name = "Mouse"
    features = frozenset({Feature.KEY_REMAP, Feature.DPI})
    locked_buttons = frozenset({"Left Button"})
    dpi_step = 50

    def match_score(self, device: dict[str, Any]) -> int:
        # Lowest possible score: only used when nothing better matches.
        return 1 if "KeyAssignment" in device or "DPIAmount" in device else 0


MODULES = [GenericMouse(load_layout(HERE / "layout.json", [HERE / "assets"]))]
