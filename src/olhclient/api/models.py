"""Typed views on the device JSON returned by ``GET /api/devices/{serial}``.

Most fields of the Go driver structs have no JSON tags, so keys are PascalCase
(``DeviceProfile``, ``KeyAssignment``...). Map keys arrive as strings.

Every part of :class:`DeviceState` is optional: OpenLinkHub drivers differ a lot,
so a part is only filled when the device JSON offers it. Features are shown
from what is there, the way OpenLinkHub's own pages are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class ActionType(IntEnum):
    NONE = 0
    MEDIA = 1
    DPI = 2
    KEYBOARD = 3
    SNIPER = 8
    MOUSE = 9
    MACRO = 10
    PROFILE_SWITCH = 11

    @property
    def value_source(self) -> str | None:
        """Where the selectable values for this type come from, if anywhere."""
        return {
            ActionType.MEDIA: "media",
            ActionType.KEYBOARD: "keyboard",
            ActionType.MOUSE: "mouse",
            ActionType.MACRO: "macro",
        }.get(self)


class DeviceKind(Enum):
    """What a device is, from the icon OpenLinkHub gives it (``Image`` in ``GET /api/``)."""

    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    HEADSET = "headset"
    HEADSET_STAND = "headset-stand"
    CONTROLLER = "controller"
    HUB = "hub"  # fan/LED hubs, Hydro AIOs, CPU blocks
    COOLER = "cooler"  # AIO coolers
    MOUSEPAD = "mousepad"
    MEMORY = "memory"
    PSU = "psu"
    LCD = "lcd"
    MOTHERBOARD = "motherboard"
    LIGHT_TOWERS = "towers"
    DONGLE = "dongle"
    DEVICE = "device"

    @classmethod
    def from_image(cls, image: str) -> DeviceKind:
        return _KIND_BY_IMAGE.get(image, cls.DEVICE)

    @property
    def title(self) -> str:
        return _KIND_TITLES[self]

    @property
    def api(self) -> str | None:
        """Path segment of the kind's own endpoints (``/api/<api>/sleep``...), if it has any."""
        return {
            DeviceKind.MOUSE: "mouse",
            DeviceKind.KEYBOARD: "keyboard",
            DeviceKind.HEADSET: "headset",
            DeviceKind.HEADSET_STAND: "headset",
            DeviceKind.CONTROLLER: "controller",
        }.get(self)


_KIND_BY_IMAGE = {
    "icon-mouse.svg": DeviceKind.MOUSE,
    "icon-keyboard.svg": DeviceKind.KEYBOARD,
    "icon-headphone.svg": DeviceKind.HEADSET,
    "icon-headphone-stand.svg": DeviceKind.HEADSET_STAND,
    "icon-controller.svg": DeviceKind.CONTROLLER,
    "icon-device.svg": DeviceKind.HUB,
    "icon-radiator.svg": DeviceKind.COOLER,
    "icon-mousepad.svg": DeviceKind.MOUSEPAD,
    "icon-ram.svg": DeviceKind.MEMORY,
    "icon-psu.svg": DeviceKind.PSU,
    "icon-lcd.svg": DeviceKind.LCD,
    "icon-motherboard.svg": DeviceKind.MOTHERBOARD,
    "icon-towers.svg": DeviceKind.LIGHT_TOWERS,
    "icon-dongle.svg": DeviceKind.DONGLE,
}
_KIND_TITLES = {
    DeviceKind.MOUSE: "Mouse",
    DeviceKind.KEYBOARD: "Keyboard",
    DeviceKind.HEADSET: "Headset",
    DeviceKind.HEADSET_STAND: "Headset stand",
    DeviceKind.CONTROLLER: "Controller",
    DeviceKind.HUB: "Hub",
    DeviceKind.COOLER: "AIO cooler",
    DeviceKind.MOUSEPAD: "Mousepad",
    DeviceKind.MEMORY: "Memory",
    DeviceKind.PSU: "Power supply",
    DeviceKind.LCD: "Display",
    DeviceKind.MOTHERBOARD: "Motherboard",
    DeviceKind.LIGHT_TOWERS: "Light towers",
    DeviceKind.DONGLE: "Receiver",
    DeviceKind.DEVICE: "Device",
}


@dataclass(frozen=True)
class DeviceInfo:
    """One entry of ``GET /api/``: enough to list a device before reading its JSON."""

    serial: str
    product: str
    kind: DeviceKind
    hidden: bool
    product_type: int

    @classmethod
    def from_json(cls, serial: str, data: dict[str, Any]) -> DeviceInfo:
        return cls(
            serial=serial,
            product=(data.get("Product") or serial).strip(),
            kind=DeviceKind.from_image(data.get("Image") or ""),
            hidden=bool(data.get("Hidden")),
            product_type=int(data.get("ProductType") or 0),
        )


@dataclass(frozen=True)
class KeyAssignment:
    index: int
    name: str
    use_default: bool
    action_type: int
    action_value: int
    press_and_hold: bool
    on_release: bool
    modifier: int = 0
    locked: bool = False  # keyboards: colour-only keys cannot be remapped

    @classmethod
    def from_json(cls, index: int, data: dict[str, Any]) -> KeyAssignment:
        return cls(
            index=index,
            name=data.get("name", f"Key {index}"),
            use_default=bool(data.get("default", True)),
            action_type=int(data.get("actionType", 0)),
            action_value=int(data.get("actionCommand", 0)),
            press_and_hold=bool(data.get("actionHold", False)),
            on_release=bool(data.get("onRelease", False)),
        )

    @classmethod
    def from_keyboard_json(cls, index: int, data: dict[str, Any]) -> KeyAssignment:
        """A key of ``DeviceProfile.Keyboards[profile].row[*].keys``."""
        name = data.get("keyName") or data.get("keyNameInternal") or f"Key {index}"
        return cls(
            index=index,
            name=" ".join(str(name).split()),
            use_default=bool(data.get("default", True)),
            action_type=int(data.get("actionType", 0)),
            action_value=int(data.get("actionCommand", 0)),
            press_and_hold=bool(data.get("actionHold", False)),
            on_release=bool(data.get("onRelease", False)),
            modifier=int(data.get("modifierKey", 0)),
            locked=bool(data.get("onlyColor", False)),
        )


@dataclass(frozen=True)
class DpiStage:
    index: int
    name: str
    value: int
    color: str
    sniper: bool


@dataclass(frozen=True)
class Zone:
    index: int
    name: str
    color: str


@dataclass(frozen=True)
class Lighting:
    effect: str
    effects: tuple[str, ...]
    brightness: int | None  # 0-100 slider, when the driver has one
    brightness_modes: dict[int, str]  # stepped brightness ("33 %"...), when there is no slider
    brightness_mode: int
    zones: tuple[Zone, ...]
    rgb_cluster: bool | None  # None: the driver has no such option
    openrgb: bool | None


@dataclass(frozen=True)
class Channel:
    """A fan, pump, probe or LED port of a hub or AIO."""

    channel_id: int
    name: str
    label: str
    rpm: int | None
    temperature: float | None
    has_speed: bool
    speed_profile: str
    rgb_profile: str | None  # None: no lighting on this channel
    rgb_device: bool  # listed in ``rgbDevices`` (Commander Core) rather than ``devices``

    @property
    def title(self) -> str:
        return self.label or self.name or f"Channel {self.channel_id}"


@dataclass(frozen=True)
class EqualizerBand:
    index: int
    name: str
    value: float


@dataclass(frozen=True)
class KeyboardProfiles:
    """Per-key layouts of a keyboard (not the OpenLinkHub user profiles)."""

    active: str
    names: tuple[str, ...]
    modifiers: dict[int, str]


def _hex(color: dict[str, Any]) -> str:
    return color.get("Hex") or "#{:02x}{:02x}{:02x}".format(
        int(color.get("red", 0)), int(color.get("green", 0)), int(color.get("blue", 0))
    )


def _choices(data: dict[str, Any] | None, *, skip: tuple[int, ...] = ()) -> dict[int, str]:
    """Map with string keys from the device JSON -> sorted ``{int: label}``."""
    items = sorted((int(k), v) for k, v in (data or {}).items())
    return {k: v for k, v in items if k not in skip}


def _by_index(data: dict[str, Any] | None) -> list[tuple[int, Any]]:
    return sorted(((int(k), v) for k, v in (data or {}).items()), key=lambda kv: kv[0])


def _kind_from_json(data: dict[str, Any]) -> DeviceKind:
    """Guess the kind when ``GET /api/`` did not tell (older servers, tests)."""
    if "KeyAssignment" in data or "DPIAmount" in data:
        return DeviceKind.MOUSE
    profile = data.get("DeviceProfile") or {}
    if "Keyboards" in profile:
        return DeviceKind.KEYBOARD
    if "Equalizers" in profile or "SideToneModes" in data:
        return DeviceKind.HEADSET
    if isinstance(data.get("devices"), dict) and data["devices"] and all(
        isinstance(v, dict) for v in data["devices"].values()
    ):
        return DeviceKind.HUB
    return DeviceKind.DEVICE


def _lighting(data: dict[str, Any], profile: dict[str, Any]) -> Lighting | None:
    if "RGBProfile" not in profile:
        return None
    zones = tuple(
        Zone(index=index, name=zone.get("Name", f"Zone {index + 1}"), color=_hex(zone.get("Color") or {}))
        for index, zone in _by_index(profile.get("ZoneColors"))
    )
    slider = profile.get("BrightnessSlider")
    modes = data.get("Brightness") if isinstance(data.get("Brightness"), dict) else None
    mode = profile.get("Brightness")
    return Lighting(
        effect=profile.get("RGBProfile") or "",
        effects=tuple(data.get("RGBModes") or ()),
        brightness=int(slider) if slider is not None else None,
        # 0 is "RGB Profile" (the effect's own brightness); the server takes 0-4.
        brightness_modes=_choices(modes) if slider is None else {},
        brightness_mode=int(mode) if isinstance(mode, (int, float)) else 0,
        zones=zones,
        rgb_cluster=bool(profile["RGBCluster"]) if "RGBCluster" in profile else None,
        openrgb=bool(profile["OpenRGBIntegration"]) if "OpenRGBIntegration" in profile else None,
    )


def _channels(data: dict[str, Any], profile: dict[str, Any]) -> tuple[Channel, ...]:
    def entries(key: str) -> list[dict[str, Any]]:
        value = data.get(key)
        if not isinstance(value, dict):
            return []
        return [v for _, v in _by_index(value) if isinstance(v, dict) and "channelId" in v]

    labels = profile.get("Labels") or {}
    rgb_devices = entries("rgbDevices")
    channels = []
    for entry in entries("devices"):
        channel_id = int(entry["channelId"])
        has_temp = bool(entry.get("HasTemps") or entry.get("IsTemperatureProbe"))
        channels.append(
            Channel(
                channel_id=channel_id,
                name=entry.get("name") or "",
                label=entry.get("label") or labels.get(str(channel_id), "") or "",
                rpm=int(entry["rpm"]) if entry.get("HasSpeed") and "rpm" in entry else None,
                temperature=float(entry["temperature"]) if has_temp and "temperature" in entry else None,
                has_speed=bool(entry.get("HasSpeed")),
                speed_profile=entry.get("profile") or "",
                # Commander Core lists its LED ports separately; elsewhere LEDs are not reported
                # per channel, so every channel gets the effect choice.
                rgb_profile=None if rgb_devices else entry.get("rgb"),
                rgb_device=False,
            )
        )
    for entry in rgb_devices:
        channel_id = int(entry["channelId"])
        channels.append(
            Channel(
                channel_id=channel_id,
                name=entry.get("name") or "",
                label=entry.get("label") or "",
                rpm=None,
                temperature=None,
                has_speed=False,
                speed_profile="",
                rgb_profile=entry.get("rgb") or "",
                rgb_device=True,
            )
        )
    return tuple(channels)


def _keyboard(profile: dict[str, Any], data: dict[str, Any]) -> tuple[list[KeyAssignment], KeyboardProfiles | None]:
    keyboards = profile.get("Keyboards")
    if not isinstance(keyboards, dict) or not keyboards:
        return [], None
    active = profile.get("Profile") or next(iter(keyboards))
    keyboard = keyboards.get(active) or {}
    keys = [
        KeyAssignment.from_keyboard_json(index, key)
        for _, row in _by_index(keyboard.get("row"))
        for index, key in _by_index((row or {}).get("keys"))
    ]
    names = profile.get("Profiles") or list(keyboards)
    return keys, KeyboardProfiles(
        active=active, names=tuple(names), modifiers=_choices(data.get("KeyAssignmentModifiers"))
    )


@dataclass
class DeviceState:
    serial: str
    product: str
    kind: DeviceKind
    product_id: int
    template: str
    firmware: str
    connected: bool
    usb: bool | None
    battery: int | None
    active_profile: str
    profiles: list[str]
    keys: list[KeyAssignment]
    assignment_types: dict[int, str]
    # mouse DPI
    min_dpi: int = 100
    max_dpi: int = 0
    active_stage: int = 0
    stages: list[DpiStage] = field(default_factory=list)
    lighting: Lighting | None = None
    channels: tuple[Channel, ...] = ()
    keyboard: KeyboardProfiles | None = None
    equalizer: tuple[EqualizerBand, ...] = ()
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def wireless(self) -> bool:
        return self.battery is not None

    @property
    def profile(self) -> dict[str, Any]:
        """The active ``DeviceProfile`` as OpenLinkHub sends it."""
        return self.raw.get("DeviceProfile") or {}

    def key(self, index: int) -> KeyAssignment | None:
        return next((k for k in self.keys if k.index == index), None)

    def key_by_name(self, name: str) -> KeyAssignment | None:
        return next((k for k in self.keys if k.name == name), None)

    @classmethod
    def from_json(cls, data: dict[str, Any], kind: DeviceKind | None = None) -> DeviceState:
        profile = data.get("DeviceProfile") or {}
        kind = kind or _kind_from_json(data)

        stages = []
        if "DPIAmount" in data or "MaxDPI" in data:
            for index, stage in _by_index(profile.get("Profiles") if isinstance(profile.get("Profiles"), dict) else None):
                color = stage.get("Color") or {}
                stages.append(
                    DpiStage(
                        index=index,
                        name=stage.get("name", f"Stage {index + 1}"),
                        value=int(stage.get("Value", 0)),
                        color=_hex(color),
                        sniper=bool(stage.get("Sniper", False)),
                    )
                )

        keyboard = None
        if kind is DeviceKind.KEYBOARD:
            keys, keyboard = _keyboard(profile, data)
        else:
            keys = [KeyAssignment.from_json(index, key) for index, key in _by_index(data.get("KeyAssignment"))]

        user_profiles = data.get("userProfiles") or {}
        active_profile = next(
            (name for name, p in user_profiles.items() if (p or {}).get("Active")), "default"
        )

        battery = data.get("BatteryLevel")
        return cls(
            serial=data.get("serial", ""),
            product=(data.get("product") or "").strip(),
            kind=kind,
            product_id=int(data.get("ProductId", 0)),
            template=data.get("Template", ""),
            firmware=data.get("firmware", ""),
            connected=bool(data.get("Connected", True)),
            usb=data.get("Usb"),
            battery=int(battery) if battery is not None else None,
            active_profile=active_profile,
            profiles=list(data.get("profileOrder") or user_profiles.keys()),
            keys=keys,
            assignment_types=_choices(data.get("KeyAssignmentTypes")),
            min_dpi=int(data.get("MinDPI", 100)),
            max_dpi=int(data.get("MaxDPI", 0)) or max((s.value for s in stages), default=0),
            active_stage=int(profile.get("Profile", 0)) if stages else 0,
            stages=stages,
            lighting=_lighting(data, profile),
            channels=_channels(data, profile),
            keyboard=keyboard,
            equalizer=tuple(
                EqualizerBand(index=index, name=(band or {}).get("Name", str(index)), value=float((band or {}).get("Value", 0)))
                for index, band in _by_index(profile.get("Equalizers") if isinstance(profile.get("Equalizers"), dict) else None)
            ),
            raw=data,
        )


@dataclass(frozen=True)
class PairedDevice:
    product_id: int
    product: str
    serial: str


@dataclass
class ReceiverState:
    """A Slipstream USB receiver and the wireless devices paired with it."""

    serial: str
    product: str
    firmware: str
    polling_rate: int
    polling_rates: dict[int, str]
    paired: tuple[PairedDevice, ...]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReceiverState:
        paired = tuple(
            PairedDevice(product_id=int(pid), product=(device or {}).get("product", ""),
                         serial=(device or {}).get("serial", ""))
            for pid, device in sorted((data.get("PairedDevices") or {}).items(), key=lambda kv: int(kv[0]))
        )
        return cls(
            serial=data.get("serial", ""),
            product=data.get("product", ""),
            firmware=data.get("firmware", ""),
            polling_rate=int((data.get("DeviceProfile") or {}).get("PollingRate", 0)),
            # 0 is "Not Set", which the server refuses (1..10).
            polling_rates=_choices(data.get("PollingRates"), skip=(0,)),
            paired=paired,
            raw=data,
        )


def valid_profile_name(name: str) -> str | None:
    """Mirror the server rules for user profile names; returns an error message or ``None``."""
    if len(name) < 3:
        return "Use at least 3 characters"
    if not name.isascii() or not name.isalnum():
        return "Only letters and numbers are allowed"
    return None


def validate_assignment(action_type: int, *, press_and_hold: bool, on_release: bool) -> str | None:
    """Mirror the server-side checks of ProcessChangeKeyAssignment.

    Returns an error message, or ``None`` when the combination is allowed.
    """
    if action_type == ActionType.MACRO and press_and_hold:
        return "Press and hold is not allowed for macros"
    if on_release and press_and_hold:
        return "Press and hold cannot be combined with on release"
    if action_type == ActionType.SNIPER and on_release:
        return "Sniper cannot be triggered on release"
    if action_type == ActionType.SNIPER and not press_and_hold:
        return "Sniper requires press and hold"
    return None
