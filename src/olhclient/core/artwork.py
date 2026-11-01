"""Device artwork lit in the colours of the device's lighting zones.

SVG elements with ``class="zone-<zone name>"`` (e.g. ``zone-side``, ``zone-logo``)
take the colour of the lighting zone with that name, including their children,
so a class on a gradient recolours its stops. Elements with
``class="button-<button name>"`` (e.g. ``button-profile-switch``) are dropped for
models without that button. The result is written to the cache directory,
named after its content: QML caches images by URL, so a new colour must get a
new file.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from olhclient.api.models import DeviceState

SVG_NS = "http://www.w3.org/2000/svg"
#: LEDs that are switched off
UNLIT = "#3a3a3d"
COLOR_ATTRIBUTES = ("fill", "stroke", "stop-color")

ET.register_namespace("", SVG_NS)


def zone_colors(state: DeviceState) -> dict[str, str]:
    """``{zone name (lower case): #rrggbb}`` the artwork should show."""
    lighting = state.lighting
    if lighting is None:
        return {}
    off = lighting.effect == "off" or lighting.brightness == 0
    return {zone.name.lower(): UNLIT if off else zone.color for zone in lighting.zones}


def css_name(button: str) -> str:
    return button.lower().replace(" ", "-")


def tint(svg: str, colors: dict[str, str], missing: frozenset[str] = frozenset()) -> str:
    root = ET.fromstring(svg)
    dropped = {f"button-{css_name(button)}" for button in missing}
    for parent in list(root.iter()):
        for child in list(parent):
            if dropped & set((child.get("class") or "").split()):
                parent.remove(child)
    for element in root.iter():
        zone = next((c[5:] for c in (element.get("class") or "").split() if c.startswith("zone-")), None)
        if zone not in colors:
            continue
        for child in element.iter():
            for attribute in COLOR_ATTRIBUTES:
                value = child.get(attribute)
                if value and value != "none" and not value.startswith("url("):
                    child.set(attribute, colors[zone])
    return ET.tostring(root, encoding="unicode")


def cache_dir() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)) / "artwork"


def lit(image: Path, colors: dict[str, str], missing: frozenset[str] = frozenset()) -> Path:
    """``image`` in the given zone colours and without ``missing`` buttons, or ``image``
    itself when there is nothing to change."""
    if image.suffix != ".svg" or not (colors or missing):
        return image
    svg = image.read_text()
    if "zone-" not in svg and "button-" not in svg:
        return image
    result = tint(svg, colors, missing)
    target = cache_dir() / f"{image.stem}-{hashlib.sha1(result.encode()).hexdigest()[:16]}.svg"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result)
    return target
