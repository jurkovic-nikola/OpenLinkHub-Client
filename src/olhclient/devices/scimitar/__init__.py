"""Corsair Scimitar MMO mice (all variants supported by OpenLinkHub)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from olhclient.devices.base import DeviceModule, Layout, load_layout
from olhclient.devices.features import Feature
from olhclient.devices.scimitar.variants import VARIANTS, Variant

HERE = Path(__file__).parent


class ScimitarMouse(DeviceModule):
    features = frozenset({Feature.KEY_REMAP, Feature.DPI, Feature.LIGHTING, Feature.SETTINGS})

    def __init__(self, variant: Variant, layout: Layout):
        super().__init__(layout)
        self.variant = variant
        self.id = variant.id
        self.name = variant.name
        self.dpi_step = variant.dpi_step
        self.locked_buttons = frozenset(variant.locked_buttons)
        self.settings = frozenset(variant.settings)

    def match_score(self, device: dict[str, Any]) -> int:
        if device.get("ProductId") not in self.variant.product_ids:
            return 0
        return 20 if device.get("Template") in self.variant.templates else 10


def _build(variant: Variant) -> ScimitarMouse:
    # assets/<variant id>/ overrides the shared artwork, e.g. a real render.
    asset_dirs = [HERE / "assets" / variant.id, HERE / "assets"]
    return ScimitarMouse(variant, load_layout(HERE / "layout.json", asset_dirs))


MODULES = [_build(variant) for variant in VARIANTS]
