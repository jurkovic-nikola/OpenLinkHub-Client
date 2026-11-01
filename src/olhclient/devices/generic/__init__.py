"""Fallback for every device without a dedicated module: no artwork, all features
the device JSON offers."""

from __future__ import annotations

from typing import Any

from olhclient.devices.base import DeviceModule, Layout


class GenericDevice(DeviceModule):
    id = "generic"
    name = "Device"

    def match_score(self, device: dict[str, Any]) -> int:
        # Lowest possible score: only used when nothing better matches.
        return 1


MODULES = [GenericDevice(Layout())]
