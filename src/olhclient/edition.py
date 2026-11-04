"""The three apps built from this code: which devices each drives, and its name and app id.

Each is its own Flatpak (``flatpak/<app id>.yaml``) and finds itself through ``FLATPAK_ID``. A
source or pip install picks one with ``--edition`` and drives everything by default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Edition:
    key: str  # --edition value
    app_id: str
    name: str  # application name: tray, desktop file
    brand: str  # top bar and window titles
    bundle: str  # release asset: <bundle>-<tag>.flatpak
    openlinkhub: bool  # Corsair devices through OpenLinkHub
    keychron: bool  # Keychron keyboards over raw HID
    gpu: bool  # graphics card lighting over I2C


OPENLINKHUB = Edition("openlinkhub", "io.github.mdmatthias.OpenLinkHub-Client", "OpenLinkHub Client",
                      "OpenLinkHub", "OpenLinkHub-Client", openlinkhub=True, keychron=False, gpu=False)
PLUS = Edition("plus", "io.github.mdmatthias.OpenLinkHub-Client-Plus", "OpenLinkHub Client Plus",
               "OpenLinkHub", "OpenLinkHub-Client-Plus", openlinkhub=True, keychron=True, gpu=True)
DEVICES = Edition("devices", "io.github.mdmatthias.OpenDeviceHub", "OpenDeviceHub",
                  "OpenDeviceHub", "OpenDeviceHub", openlinkhub=False, keychron=True, gpu=True)

EDITIONS = {edition.key: edition for edition in (OPENLINKHUB, PLUS, DEVICES)}
#: outside the Flatpaks: everything
DEFAULT = PLUS


def current(choice: str | None = None) -> Edition:
    """The installed Flatpak's edition, else ``choice`` (an --edition key), else :data:`DEFAULT`."""
    flatpak_id = os.environ.get("FLATPAK_ID")
    for edition in EDITIONS.values():
        if edition.app_id == flatpak_id:
            return edition
    return EDITIONS[choice] if choice else DEFAULT
