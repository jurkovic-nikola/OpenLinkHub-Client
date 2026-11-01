from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.api.models import Lighting, MouseState
from olhclient.core.features.base import FeatureController
from olhclient.core.listmodel import DictListModel

ZONE_ROLES = ("zoneIndex", "name", "color")


def effect_title(effect: str) -> str:
    return effect.replace("-", " ").capitalize()


class LightingController(FeatureController):
    """RGB effect, brightness and zone colours of the active profile.

    Effect, brightness and the toggles apply immediately, like in iCUE. Zone
    colours are edited as a draft and saved together.
    """

    changed = Signal()
    savingChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._zones = DictListModel(ZONE_ROLES, self)
        self._lighting: Lighting | None = None
        self._saving = False

    def update(self, state: MouseState) -> None:
        lighting = state.lighting
        zones = lighting.zones if lighting else ()
        self._zones.set_items({"zoneIndex": z.index, "name": z.name, "color": z.color} for z in zones)
        if lighting != self._lighting:
            self._lighting = lighting
            self.changed.emit()

    # -- QML API -----------------------------------------------------------

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._lighting is not None

    @Property(QObject, constant=True)
    def zones(self) -> DictListModel:
        return self._zones

    @Property(str, notify=changed)
    def effect(self) -> str:
        return self._lighting.effect if self._lighting else ""

    @Property(str, notify=changed)
    def effectTitle(self) -> str:
        return effect_title(self.effect)

    @Property("QVariantList", notify=changed)
    def effects(self) -> list[dict[str, Any]]:
        effects = self._lighting.effects if self._lighting else ()
        return [{"value": e, "text": effect_title(e)} for e in effects]

    @Property(int, notify=changed)
    def brightness(self) -> int:
        return self._lighting.brightness if self._lighting else 0

    @Property(bool, notify=changed)
    def rgbCluster(self) -> bool:
        return bool(self._lighting and self._lighting.rgb_cluster)

    @Property(bool, notify=changed)
    def openRgb(self) -> bool:
        return bool(self._lighting and self._lighting.openrgb)

    @Property(bool, notify=savingChanged)
    def saving(self) -> bool:
        return self._saving

    @Slot(str)
    def setEffect(self, effect: str) -> None:
        if not self._lighting or effect == self._lighting.effect:
            return
        if effect not in self._lighting.effects:
            self.session.report_message(f"Unknown effect {effect}", error=True)
            return
        serial = self.session.serial
        self._apply(lambda: self.session.api.set_rgb_effect(serial, effect), f"Effect set to {effect_title(effect)}")

    @Slot(int)
    def setBrightness(self, percent: int) -> None:
        if not self._lighting or percent == self._lighting.brightness:
            return
        if not 0 <= percent <= 100:
            self.session.report_message("Brightness must be between 0 and 100", error=True)
            return
        serial = self.session.serial
        self._apply(lambda: self.session.api.set_brightness(serial, percent), f"Brightness set to {percent} %")

    @Slot(bool)
    def setRgbCluster(self, enabled: bool) -> None:
        if not self._lighting or enabled == self._lighting.rgb_cluster:
            return
        serial = self.session.serial
        self._apply(
            lambda: self.session.api.set_rgb_cluster(serial, enabled),
            "RGB cluster enabled" if enabled else "RGB cluster disabled",
        )

    @Slot(bool)
    def setOpenRgb(self, enabled: bool) -> None:
        if not self._lighting or enabled == self._lighting.openrgb:
            return
        serial = self.session.serial
        self._apply(
            lambda: self.session.api.set_openrgb(serial, enabled),
            "OpenRGB integration enabled" if enabled else "OpenRGB integration disabled",
        )

    def _apply(self, call, success: str) -> None:
        # On failure the device data does not change, so tell the UI to drop
        # the value the user picked and show the real one again.
        self.write(call, success, done=lambda ok: ok or self.changed.emit())

    def changed_colors(self, colors: list[Any]) -> dict[int, str]:
        return {
            zone["zoneIndex"]: str(color).lower()
            for zone, color in zip(self._zones.items(), colors)
            if str(color).lower() != zone["color"].lower()
        }

    @Slot("QVariantList")
    def saveZoneColors(self, colors: list[Any]) -> None:
        """Save zone colours (``#rrggbb``), given in model order. Unchanged zones are not sent."""
        changes = self.changed_colors(colors)
        if not changes:
            self.session.report_message("No colour changes to save")
            return
        serial = self.session.serial
        self._set_saving(True)
        self.write(
            lambda: self.session.api.save_zone_colors(serial, changes),
            "Zone colours saved",
            done=lambda ok: self._set_saving(False),
        )

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()
