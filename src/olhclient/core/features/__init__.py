"""Controllers backing the generic feature panels (see devices/features.py)."""

from __future__ import annotations

from olhclient.core.features.base import FeatureController
from olhclient.core.features.dpi import DpiController
from olhclient.core.features.key_remap import KeyRemapController
from olhclient.core.features.lighting import LightingController
from olhclient.core.features.settings import SettingsController
from olhclient.devices.features import Feature

CONTROLLERS: dict[Feature, type[FeatureController]] = {
    Feature.KEY_REMAP: KeyRemapController,
    Feature.DPI: DpiController,
    Feature.LIGHTING: LightingController,
    Feature.SETTINGS: SettingsController,
}

__all__ = ["CONTROLLERS", "FeatureController"]
