"""Base types for device modules.

A device module describes how a family of devices looks (views with clickable
hotspots) and what the client can do with it (features). It never talks to
the API itself; the core controllers do that.

Layout files (``layout.json``) use pixel coordinates in the artwork's own
coordinate space (``size``); they are normalised to 0..1 when loaded so the
UI can scale the artwork freely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from olhclient.devices.features import Feature

IMAGE_EXTENSIONS = (".png", ".webp", ".svg")


@dataclass(frozen=True)
class Hotspot:
    button: str  # KeyAssignment name as reported by OpenLinkHub, e.g. "Side Button 1"
    x: float
    y: float
    w: float
    h: float
    radius: float = 0.0  # corner radius, relative to the hotspot height


@dataclass(frozen=True)
class DeviceView:
    id: str
    title: str
    image: Path
    hotspots: tuple[Hotspot, ...] = ()


@dataclass(frozen=True)
class Layout:
    views: tuple[DeviceView, ...]
    thumbnail: Path
    button_labels: dict[str, str] = field(default_factory=dict)
    # Grid callout (rows of button names), e.g. the 3x4 keypad of an MMO mouse.
    keypad: tuple[tuple[str, ...], ...] = ()
    # Vertical callout list of the remaining buttons.
    button_list: tuple[str, ...] = ()


def resolve_image(asset_dirs: list[Path], name: str) -> Path:
    """Find ``name`` in the first asset dir that has it, preferring raster renders.

    This lets users drop a ``side.png`` render next to (or in a variant folder
    above) the bundled ``side.svg`` without touching the layout file.
    """
    stem = Path(name).stem
    for directory in asset_dirs:
        for ext in IMAGE_EXTENSIONS:
            candidate = directory / f"{stem}{ext}"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"image {name!r} not found in {[str(d) for d in asset_dirs]}")


def load_layout(path: Path, asset_dirs: list[Path]) -> Layout:
    data: dict[str, Any] = json.loads(path.read_text())
    views = []
    for view in data.get("views", []):
        width, height = view["size"]
        hotspots = tuple(
            Hotspot(
                button=spot["button"],
                x=spot["rect"][0] / width,
                y=spot["rect"][1] / height,
                w=spot["rect"][2] / width,
                h=spot["rect"][3] / height,
                radius=spot.get("radius", 0) / spot["rect"][3] if spot["rect"][3] else 0.0,
            )
            for spot in view.get("hotspots", [])
        )
        views.append(
            DeviceView(
                id=view["id"],
                title=view.get("title", view["id"]),
                image=resolve_image(asset_dirs, view["image"]),
                hotspots=hotspots,
            )
        )
    return Layout(
        views=tuple(views),
        thumbnail=resolve_image(asset_dirs, data.get("thumbnail", views[0].image.name if views else "thumb")),
        button_labels=dict(data.get("button_labels", {})),
        keypad=tuple(tuple(row) for row in data.get("keypad", [])),
        button_list=tuple(data.get("button_list", [])),
    )


class DeviceModule:
    """Describes one device model (or a set of models that look the same)."""

    id: str = ""
    name: str = ""
    features: frozenset[Feature] = frozenset()
    # Buttons that are shown but cannot be remapped (e.g. left click).
    locked_buttons: frozenset[str] = frozenset()
    dpi_step: int = 50

    def __init__(self, layout: Layout):
        self.layout = layout

    def match_score(self, device: dict[str, Any]) -> int:
        """How well this module fits the device JSON; 0 means not at all."""
        return 0

    def button_label(self, name: str) -> str:
        return self.layout.button_labels.get(name, name)

    def qml_override(self, feature: Feature) -> str | None:
        """Absolute path of a QML file replacing the generic editor for ``feature``."""
        return None

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.id}>"
