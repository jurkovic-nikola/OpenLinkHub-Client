from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.api.models import DeviceState, Lighting
from olhclient.core.features.base import FeatureController
from olhclient.core.features.effect_profile import EffectProfile, effect_title
from olhclient.core.listmodel import DictListModel

ZONE_ROLES = ("zoneIndex", "name", "color")
#: device kinds with a zoneColors endpoint (/api/<kind>/zoneColors)
ZONE_KINDS = ("mouse", "headset", "controller")


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
        self._effect_profile = EffectProfile(self)

    @classmethod
    def supports(cls, state: DeviceState) -> bool:
        return state.lighting is not None

    def update(self, state: DeviceState) -> None:
        lighting = state.lighting
        zones = lighting.zones if lighting and state.kind.api in ZONE_KINDS else ()
        self._zones.set_items({"zoneIndex": z.index, "name": z.name, "color": z.color} for z in zones)
        if lighting != self._lighting:
            self._lighting = lighting
            self.changed.emit()
        self._effect_profile.load(lighting.effect if lighting else "")

    # -- QML API -----------------------------------------------------------

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._lighting is not None

    @Property(QObject, constant=True)
    def zones(self) -> DictListModel:
        return self._zones

    @Property(QObject, constant=True)
    def effectProfile(self) -> EffectProfile:
        return self._effect_profile

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

    @Property(bool, notify=changed)
    def hasBrightness(self) -> bool:
        """A 0-100 slider; otherwise see brightnessModes."""
        return bool(self._lighting and self._lighting.brightness is not None)

    @Property(int, notify=changed)
    def brightness(self) -> int:
        return (self._lighting.brightness or 0) if self._lighting else 0

    @Property("QVariantList", notify=changed)
    def brightnessModes(self) -> list[dict[str, Any]]:
        modes = self._lighting.brightness_modes if self._lighting else {}
        return [{"value": value, "text": text} for value, text in modes.items()]

    @Property(int, notify=changed)
    def brightnessMode(self) -> int:
        return self._lighting.brightness_mode if self._lighting else 0

    @Property(bool, notify=changed)
    def hasRgbCluster(self) -> bool:
        return bool(self._lighting and self._lighting.rgb_cluster is not None)

    @Property(bool, notify=changed)
    def rgbCluster(self) -> bool:
        return bool(self._lighting and self._lighting.rgb_cluster)

    @Property(bool, notify=changed)
    def hasOpenRgb(self) -> bool:
        return bool(self._lighting and self._lighting.openrgb is not None)

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
        if not self._lighting or self._lighting.brightness is None or percent == self._lighting.brightness:
            return
        if not 0 <= percent <= 100:
            self.session.report_message("Brightness must be between 0 and 100", error=True)
            return
        serial = self.session.serial
        self._apply(lambda: self.session.api.set_brightness(serial, percent), f"Brightness set to {percent} %")

    @Slot(int)
    def setBrightnessMode(self, mode: int) -> None:
        if not self._lighting or mode == self._lighting.brightness_mode:
            return
        text = self._lighting.brightness_modes.get(mode)
        if text is None:
            self.session.report_message("Unknown brightness", error=True)
            return
        serial = self.session.serial
        self._apply(lambda: self.session.api.set_brightness_mode(serial, mode), f"Brightness set to {text}")

    @Slot(bool)
    def setRgbCluster(self, enabled: bool) -> None:
        if not self._lighting or self._lighting.rgb_cluster is None or enabled == self._lighting.rgb_cluster:
            return
        serial = self.session.serial
        self._apply(
            lambda: self.session.api.set_rgb_cluster(serial, enabled),
            "RGB cluster enabled" if enabled else "RGB cluster disabled",
        )

    @Slot(bool)
    def setOpenRgb(self, enabled: bool) -> None:
        if not self._lighting or self._lighting.openrgb is None or enabled == self._lighting.openrgb:
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
        serial, kind = self.session.serial, self.session.state.kind.api
        self._set_saving(True)
        self.write(
            lambda: self.session.api.save_zone_colors(serial, changes, kind),
            "Zone colours saved",
            done=lambda ok: self._set_saving(False),
        )

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()
