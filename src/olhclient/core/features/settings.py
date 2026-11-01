from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from olhclient.api.client import MOUSE_SETTINGS
from olhclient.api.models import DeviceSettings, MouseState
from olhclient.core.features.base import FeatureController

#: key -> title, in display order. Keys are the request fields of the API.
TITLES = {
    "pollingRate": "Polling rate",
    "liftHeight": "Lift-off distance",
    "sleepMode": "Sleep timer",
    "angleSnapping": "Angle snapping",
    "buttonOptimization": "Button response optimization",
}
TOGGLES = ("angleSnapping", "buttonOptimization")


class SettingsController(FeatureController):
    """Sensor and power settings. Every change applies immediately."""

    itemsChanged = Signal()
    busyChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._items: list[dict[str, Any]] = []
        self._busy = False

    def update(self, state: MouseState) -> None:
        items = self._build(state)
        if items != self._items:
            self._items = items
            self.itemsChanged.emit()

    def _build(self, state: MouseState) -> list[dict[str, Any]]:
        settings = state.settings
        if settings is None:
            return []
        supported = self.session.module.settings
        choices = {
            "pollingRate": (settings.polling_rate, settings.polling_rates),
            "liftHeight": (settings.lift_height, settings.lift_heights),
            "sleepMode": (settings.sleep_mode, settings.sleep_modes),
        }
        toggles = {"angleSnapping": settings.angle_snapping, "buttonOptimization": settings.button_optimization}

        items = []
        for key, title in TITLES.items():
            if key not in supported or not self._shown(key, state, settings):
                continue
            if key in TOGGLES:
                items.append({"key": key, "title": title, "kind": "toggle", "value": int(toggles[key]), "options": []})
                continue
            value, options = choices[key]
            if not options:  # the driver (or connection mode) does not offer this setting
                continue
            items.append(
                {
                    "key": key,
                    "title": title,
                    "kind": "choice",
                    "value": value,
                    "options": [{"value": v, "text": text} for v, text in options.items()],
                }
            )
        return items

    @staticmethod
    def _shown(key: str, state: MouseState, settings: DeviceSettings) -> bool:
        # Like the web UI: the sleep timer only applies on the wireless (dongle) link.
        if key == "sleepMode":
            return state.wireless and state.usb is False
        return True

    @Property("QVariantList", notify=itemsChanged)
    def items(self) -> list[dict[str, Any]]:
        return self._items

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot(str, int)
    def apply(self, key: str, value: int) -> None:
        item = next((i for i in self._items if i["key"] == key), None)
        if item is None or key not in MOUSE_SETTINGS:
            self.session.report_message(f"{key} is not supported by this device", error=True)
            return
        if item["value"] == value:
            return
        if item["kind"] == "choice" and value not in {o["value"] for o in item["options"]}:
            self.session.report_message(f"Invalid value for {item['title']}", error=True)
            return
        serial = self.session.serial
        self._set_busy(True)
        self.write(
            lambda: self.session.api.set_mouse_setting(serial, key, value),
            f"{item['title']} updated",
            done=self._applied,
        )

    def _applied(self, ok: bool) -> None:
        self._set_busy(False)
        if not ok:  # the controls show the rejected value; rebuild them from the device data
            self.itemsChanged.emit()

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()
