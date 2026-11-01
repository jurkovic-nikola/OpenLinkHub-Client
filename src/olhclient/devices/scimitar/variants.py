"""Scimitar family as supported by OpenLinkHub (src/devices/devices.go, slipstream.go).

Min/max DPI and stage count are read from the device at runtime; this table
only holds what the API does not tell us.

The legacy and new generations use different KeyAssignment bitmasks, but the
button names are identical, which is why the layout is keyed by name.
"""

from __future__ import annotations

from dataclasses import dataclass

# Wireless models also have a sleep timer and button response optimization.
WIRELESS_SETTINGS = ("pollingRate", "liftHeight", "angleSnapping", "sleepMode", "buttonOptimization")


@dataclass(frozen=True)
class Variant:
    id: str
    name: str
    product_ids: tuple[int, ...]
    templates: tuple[str, ...]
    dpi_step: int
    locked_buttons: tuple[str, ...] = ("Left Button",)
    missing_buttons: tuple[str, ...] = ()
    settings: tuple[str, ...] = ("pollingRate", "liftHeight", "angleSnapping")


VARIANTS = (
    Variant("scimitar-elite", "Scimitar Elite", (7139,), ("scimitar.html",), dpi_step=50),
    Variant("scimitar-rgb-elite", "Scimitar RGB Elite", (7051,), ("scimitarrgbelite.html",), dpi_step=50),
    Variant("scimitar-pro-rgb", "Scimitar Pro RGB", (6974,), ("scimitarprorgb.html",), dpi_step=50),
    Variant("scimitar-rgb", "Scimitar RGB", (6942,), ("scimitarrgb.html",), dpi_step=100),
    # Wireless models: the same PID is used over the USB cable (WU driver) and
    # through the Slipstream dongle (W driver).
    Variant(
        "scimitar-elite-wireless",
        "Scimitar Elite Wireless",
        (7131,),
        ("scimitarEliteW.html",),
        dpi_step=100,
        missing_buttons=("Profile Switch",),  # only the DPI button on top
        settings=WIRELESS_SETTINGS,
    ),
    Variant(
        "scimitar-elite-se",
        "Scimitar Elite Wireless SE",
        (11042,),
        ("scimitarEliteWSE.html",),
        dpi_step=50,
        missing_buttons=("Profile Switch",),
        settings=WIRELESS_SETTINGS,
    ),
)
