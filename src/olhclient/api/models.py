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
                    color=color.get("Hex") or "#{:02x}{:02x}{:02x}".format(
                        int(color.get("red", 0)), int(color.get("green", 0)), int(color.get("blue", 0))
                    ),
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
            raw=data,
        )


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
