"""Typed views on the device JSON returned by ``GET /api/devices/{serial}``.

Most fields of the Go driver structs have no JSON tags, so keys are PascalCase
(``DeviceProfile``, ``KeyAssignment``...). Map keys arrive as strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
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


@dataclass(frozen=True)
class KeyAssignment:
    index: int
    name: str
    use_default: bool
    action_type: int
    action_value: int
    press_and_hold: bool
    on_release: bool

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
    brightness: int  # 0-100
    zones: tuple[Zone, ...]
    rgb_cluster: bool
    openrgb: bool


@dataclass(frozen=True)
class DeviceSettings:
    """Sensor and power settings of the active profile, with their choices."""

    polling_rate: int
    polling_rates: dict[int, str]
    lift_height: int
    lift_heights: dict[int, str]
    sleep_mode: int
    sleep_modes: dict[int, str]
    angle_snapping: bool
    button_optimization: bool


def _hex(color: dict[str, Any]) -> str:
    return color.get("Hex") or "#{:02x}{:02x}{:02x}".format(
        int(color.get("red", 0)), int(color.get("green", 0)), int(color.get("blue", 0))
    )


def _choices(data: dict[str, Any] | None, *, skip: tuple[int, ...] = ()) -> dict[int, str]:
    """Map with string keys from the device JSON -> sorted ``{int: label}``."""
    items = sorted((int(k), v) for k, v in (data or {}).items())
    return {k: v for k, v in items if k not in skip}


@dataclass
class MouseState:
    serial: str
    product: str
    product_id: int
    template: str
    connected: bool
    usb: bool | None
    battery: int | None
    min_dpi: int
    max_dpi: int
    active_stage: int
    active_profile: str
    profiles: list[str]
    stages: list[DpiStage]
    keys: list[KeyAssignment]
    assignment_types: dict[int, str]
    lighting: Lighting | None = None
    settings: DeviceSettings | None = None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def wireless(self) -> bool:
        return self.battery is not None

    def key(self, index: int) -> KeyAssignment | None:
        return next((k for k in self.keys if k.index == index), None)

    def key_by_name(self, name: str) -> KeyAssignment | None:
        return next((k for k in self.keys if k.name == name), None)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> MouseState:
        profile = data.get("DeviceProfile") or {}

        stages = []
        for index, stage in sorted((profile.get("Profiles") or {}).items(), key=lambda kv: int(kv[0])):
            color = stage.get("Color") or {}
            stages.append(
                DpiStage(
                    index=int(index),
                    name=stage.get("name", f"Stage {int(index) + 1}"),
                    value=int(stage.get("Value", 0)),
                    color=_hex(color),
                    sniper=bool(stage.get("Sniper", False)),
                )
            )

        keys = [
            KeyAssignment.from_json(int(index), key)
            for index, key in sorted((data.get("KeyAssignment") or {}).items(), key=lambda kv: int(kv[0]))
        ]

        user_profiles = data.get("userProfiles") or {}
        active_profile = next(
            (name for name, p in user_profiles.items() if (p or {}).get("Active")), "default"
        )

        zones = tuple(
            Zone(index=int(index), name=zone.get("Name", f"Zone {int(index) + 1}"), color=_hex(zone.get("Color") or {}))
            for index, zone in sorted((profile.get("ZoneColors") or {}).items(), key=lambda kv: int(kv[0]))
        )
        lighting = None
        if "RGBProfile" in profile:
            lighting = Lighting(
                effect=profile.get("RGBProfile", ""),
                effects=tuple(data.get("RGBModes") or ()),
                brightness=int(profile.get("BrightnessSlider") or 0),
                zones=zones,
                rgb_cluster=bool(profile.get("RGBCluster", False)),
                openrgb=bool(profile.get("OpenRGBIntegration", False)),
            )

        settings = DeviceSettings(
            polling_rate=int(profile.get("PollingRate", 0)),
            # 0 is "Not Set", which the server refuses (1..10).
            polling_rates=_choices(data.get("PollingRates"), skip=(0,)),
            lift_height=int(profile.get("LiftHeight", 0)),
            lift_heights=_choices(data.get("LiftHeights")),
            sleep_mode=int(profile.get("SleepMode", 0)),
            sleep_modes=_choices(data.get("SleepModes")),
            angle_snapping=bool(profile.get("AngleSnapping", 0)),
            button_optimization=bool(profile.get("ButtonOptimization", 0)),
        )

        battery = data.get("BatteryLevel")
        return cls(
            serial=data.get("serial", ""),
            product=data.get("product", ""),
            product_id=int(data.get("ProductId", 0)),
            template=data.get("Template", ""),
            connected=bool(data.get("Connected", True)),
            usb=data.get("Usb"),
            battery=int(battery) if battery is not None else None,
            min_dpi=int(data.get("MinDPI", 100)),
            max_dpi=int(data.get("MaxDPI", 0)) or max((s.value for s in stages), default=0),
            active_stage=int(profile.get("Profile", 0)),
            active_profile=active_profile,
            profiles=list(data.get("profileOrder") or user_profiles.keys()),
            stages=stages,
            keys=keys,
            assignment_types={
                int(k): v for k, v in sorted((data.get("KeyAssignmentTypes") or {}).items(), key=lambda kv: int(kv[0]))
            },
            lighting=lighting,
            settings=settings,
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
