"""Simple device settings (polling rate, sleep timer, sidetone...) for every device kind.

OpenLinkHub pairs an options map in the device JSON (``SleepModes``) with the
current value in ``DeviceProfile`` (``SleepMode``); toggles and sliders only
have the ``DeviceProfile`` field. A setting is shown when its fields are there.
The driver may still lack the setter, so every write can come back refused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from olhclient.api.models import DeviceKind, DeviceState
from olhclient.core.features.base import FeatureController

CHOICE, TOGGLE, SLIDER, TEXT_CHOICE = "choice", "toggle", "slider", "textChoice"


@dataclass(frozen=True)
class SettingSpec:
    key: str  # unique id, also used in module allow-lists
    title: str
    kinds: tuple[str, ...]  # DeviceKind.api values
    endpoint: str  # under /api/<kind>/
    field: str  # request field carrying the value
    current: str  # DeviceProfile field with the current value
    type: str = CHOICE
    options: str | None = None  # device JSON field with the choices (CHOICE, TEXT_CHOICE)
    range: tuple[int, int] = (0, 100)  # SLIDER
    extra: dict[str, Any] = field(default_factory=dict)  # fixed request fields
    requires: tuple[str, Any] | None = None  # (DeviceProfile field, value) that enables it


MOUSE, HEADSET, KEYBOARD, CONTROLLER = "mouse", "headset", "keyboard", "controller"
EVERY = (MOUSE, HEADSET, KEYBOARD, CONTROLLER)

#: In display order. From OpenLinkHub's request handlers (src/server/requests/requests.go).
SPECS = (
    SettingSpec("pollingRate", "Polling rate", (MOUSE, KEYBOARD), "pollingRate", "pollingRate", "PollingRate",
                options="PollingRates"),
    SettingSpec("liftHeight", "Lift-off distance", (MOUSE,), "liftHeight", "liftHeight", "LiftHeight",
                options="LiftHeights"),
    SettingSpec("surfaceSelection", "Surface", (MOUSE,), "surfaceSelection", "surfaceSelection", "SurfaceSelection",
                options="SurfaceSelections"),
    SettingSpec("sleepMode", "Sleep timer", EVERY, "sleep", "sleepMode", "SleepMode", options="SleepModes"),
    SettingSpec("noiseCancellation", "Noise cancellation", (HEADSET,), "anc", "noiseCancellation",
                "NoiseCancellation", options="NoiseCancellations"),
    SettingSpec("sideTone", "Sidetone", (HEADSET,), "sidetone", "sideTone", "SideTone", options="SideToneModes"),
    SettingSpec("sideToneValue", "Sidetone level", (HEADSET,), "sidetoneValue", "sideToneValue", "SideToneValue",
                type=SLIDER, requires=("SideTone", 1)),
    SettingSpec("muteIndicator", "Mute indicator", (HEADSET,), "muteIndicator", "muteIndicator",
                "DisableMicIndicator", options="MuteIndicators"),
    SettingSpec("leftWheel", "Left wheel", (HEADSET,), "wheelOption", "wheelOption", "LeftWheel",
                options="WheelOptions", extra={"wheelId": 1}),
    SettingSpec("rightWheel", "Right wheel", (HEADSET,), "wheelOption", "wheelOption", "RightWheel",
                options="WheelOptions", extra={"wheelId": 2}),
    SettingSpec("debounceTime", "Debounce time", (KEYBOARD,), "debounceTime", "debounceTime", "DebounceTime",
                options="DebounceTimes"),
    SettingSpec("layout", "Keyboard layout", (KEYBOARD,), "layout", "keyboardLayout", "Layout",
                type=TEXT_CHOICE, options="Layouts"),
    SettingSpec("angleSnapping", "Angle snapping", (MOUSE,), "angleSnapping", "angleSnapping", "AngleSnapping",
                type=TOGGLE),
    SettingSpec("buttonOptimization", "Button response optimization", (MOUSE,), "buttonOptimization",
                "buttonOptimization", "ButtonOptimization", options="ButtonOptimizations"),
    SettingSpec("motionSync", "Motion sync", (MOUSE,), "motionSync", "motionSync", "MotionSync", type=TOGGLE),
    SettingSpec("rippleControl", "Ripple control", (MOUSE,), "rippleControl", "rippleControl", "RippleControl",
                type=TOGGLE),
    SettingSpec("leftHandMode", "Left-handed mode", (MOUSE,), "leftHandMode", "leftHandMode", "LeftHandMode",
                type=TOGGLE),
    SettingSpec("autoBrightness", "Automatic brightness", (KEYBOARD,), "autoBrightness", "autoBrightness",
                "AutoBrightness", type=TOGGLE),
    SettingSpec("leftVibration", "Left vibration", (CONTROLLER,), "vibration", "vibrationValue",
                "LeftVibrationValue", type=SLIDER, extra={"vibrationModule": 0}),
    SettingSpec("rightVibration", "Right vibration", (CONTROLLER,), "vibration", "vibrationValue",
                "RightVibrationValue", type=SLIDER, extra={"vibrationModule": 1}),
)
SPECS_BY_KEY = {spec.key: spec for spec in SPECS}


def _options(spec: SettingSpec, state: DeviceState) -> list[dict[str, Any]] | None:
    raw = state.raw.get(spec.options) if spec.options else None
    if spec.type == TEXT_CHOICE:
        return [{"value": str(v), "text": str(v)} for v in raw] if isinstance(raw, list) and raw else None
    if not isinstance(raw, dict) or not raw:
        return None
    options = []
    for key, text in sorted(((int(k), v) for k, v in raw.items())):
        if key == 0 and str(text).lower() == "not set":  # the server refuses it
            continue
        options.append({"value": key, "text": str(text)})
    return options or None


def build_item(spec: SettingSpec, state: DeviceState) -> dict[str, Any] | None:
    """The UI row for ``spec``, or None when the device does not offer it."""
    profile = state.profile
    if state.kind.api not in spec.kinds or spec.current not in profile or profile[spec.current] is None:
        return None
    value = profile[spec.current]
    item: dict[str, Any] = {"key": spec.key, "title": spec.title, "options": [], "min": 0, "max": 0,
                            "enabled": True}
    if spec.requires:
        item["enabled"] = profile.get(spec.requires[0]) == spec.requires[1]
    if spec.type in (CHOICE, TEXT_CHOICE):
        options = _options(spec, state)
        if options is None:
            # Mice without a ButtonOptimizations map have it as an on/off switch.
            if spec.key != "buttonOptimization":
                return None
            return {**item, "kind": TOGGLE, "value": int(bool(value))}
        return {**item, "kind": spec.type, "value": value if spec.type == TEXT_CHOICE else int(value),
                "options": options}
    if spec.type == TOGGLE:
        return {**item, "kind": TOGGLE, "value": int(bool(value))}
    return {**item, "kind": SLIDER, "value": int(value), "min": spec.range[0], "max": spec.range[1]}


class SettingsController(FeatureController):
    """Every simple setting the device offers. Every change applies immediately."""

    itemsChanged = Signal()
    busyChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._items: list[dict[str, Any]] = []
        self._busy = False

    @classmethod
    def supports(cls, state: DeviceState) -> bool:
        return any(build_item(spec, state) for spec in SPECS)

    def update(self, state: DeviceState) -> None:
        items = self._build(state)
        if items != self._items:
            self._items = items
            self.itemsChanged.emit()

    def _build(self, state: DeviceState) -> list[dict[str, Any]]:
        allowed = self.session.module.settings
        items = []
        for spec in SPECS:
            if allowed is not None and spec.key not in allowed:
                continue
            if not self._shown(spec, state):
                continue
            item = build_item(spec, state)
            if item:
                items.append(item)
        return items

    @staticmethod
    def _shown(spec: SettingSpec, state: DeviceState) -> bool:
        # Like the web UI: a wireless mouse's sleep timer only applies on the wireless (dongle) link.
        if spec.key == "sleepMode" and state.kind is DeviceKind.MOUSE:
            return state.wireless and state.usb is False
        return True

    @Property("QVariantList", notify=itemsChanged)
    def items(self) -> list[dict[str, Any]]:
        return self._items

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot(str, "QVariant")
    def apply(self, key: str, value: Any) -> None:
        item = next((i for i in self._items if i["key"] == key), None)
        spec = SPECS_BY_KEY.get(key)
        if item is None or spec is None:
            self.session.report_message(f"{key} is not supported by this device", error=True)
            return
        value = str(value) if item["kind"] == TEXT_CHOICE else int(value)
        if item["value"] == value or not item["enabled"]:
            return
        if item["kind"] in (CHOICE, TEXT_CHOICE) and value not in {o["value"] for o in item["options"]}:
            self.session.report_message(f"Invalid value for {item['title']}", error=True)
            return
        if item["kind"] == SLIDER and not item["min"] <= value <= item["max"]:
            self.session.report_message(f"{item['title']} must be between {item['min']} and {item['max']}", error=True)
            return
        serial, endpoint = self.session.serial, f"{self.session.state.kind.api}/{spec.endpoint}"
        self._set_busy(True)
        self.write(
            lambda: self.session.api.set_setting(serial, endpoint, {spec.field: value, **spec.extra}),
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
