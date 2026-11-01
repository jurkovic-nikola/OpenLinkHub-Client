from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.api.models import Channel, DeviceState
from olhclient.core.features.base import FeatureController
from olhclient.core.features.lighting import effect_title
from olhclient.core.listmodel import DictListModel

CHANNEL_ROLES = ("key", "channelId", "title", "label", "rpm", "temperature", "hasSpeed", "speedProfile",
                 "hasRgb", "rgbProfile", "rgbDevice")
#: channel id that addresses every channel of the device
ALL = -1


def channel_key(channel: Channel) -> str:
    # Commander Core numbers its LED ports separately from its fan ports.
    return f"{'rgb' if channel.rgb_device else 'dev'}:{channel.channel_id}"


class FansController(FeatureController):
    """Channels of a fan/LED hub or AIO cooler: speed profile, lighting effect and label.

    Speeds and temperatures refresh with the regular device poll.
    """

    selectedChanged = Signal()
    profilesChanged = Signal()
    effectsChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._channels = DictListModel(CHANNEL_ROLES, self)
        self._selected = ""
        self._profiles: list[str] = []
        self._effects: list[str] = []
        self._loading = False
        self._channels.dataChanged.connect(lambda *_: self.selectedChanged.emit())
        self._channels.modelReset.connect(self.selectedChanged)

    @classmethod
    def supports(cls, state: DeviceState) -> bool:
        return bool(state.channels)

    def update(self, state: DeviceState) -> None:
        self._channels.set_items(self._row(c) for c in state.channels)
        if not self._selected and state.channels:
            self._set_selected(channel_key(state.channels[0]))
        effects = list(state.raw.get("RGBModes") or [])
        if effects != self._effects:
            self._effects = effects
            self.effectsChanged.emit()
        if not self._profiles and not self._loading and any(c.has_speed for c in state.channels):
            self._load_profiles()

    @staticmethod
    def _row(channel: Channel) -> dict[str, Any]:
        return {
            "key": channel_key(channel),
            "channelId": channel.channel_id,
            "title": channel.title,
            "label": channel.label,
            "rpm": -1 if channel.rpm is None else channel.rpm,
            "temperature": "" if channel.temperature is None else f"{channel.temperature:.1f} °C",
            "hasSpeed": channel.has_speed,
            "speedProfile": channel.speed_profile,
            "hasRgb": channel.rgb_profile is not None,
            "rgbProfile": channel.rgb_profile or "",
            "rgbDevice": channel.rgb_device,
        }

    def _load_profiles(self) -> None:
        self._loading = True

        def done(profiles: list[str]) -> None:
            self._loading = False
            self._profiles = profiles
            self.profilesChanged.emit()

        def failed(exc: Exception) -> None:
            self._loading = False
            self.session.report_error(exc)

        self.session.worker.submit(self.session.api.temperature_profiles, on_done=done, on_error=failed, owner=self)

    # -- QML API -----------------------------------------------------------

    @Property(QObject, constant=True)
    def channels(self) -> DictListModel:
        return self._channels

    def _get_selected(self) -> str:
        return self._selected

    def _set_selected(self, key: str) -> None:
        if key != self._selected:
            self._selected = key
            self.selectedChanged.emit()

    selectedKey = Property(str, _get_selected, _set_selected, notify=selectedChanged)

    @Property("QVariant", notify=selectedChanged)
    def selected(self) -> dict[str, Any] | None:
        row = self._channels.indexOf("key", self._selected)
        return self._channels.get(row) if row >= 0 else None

    @Property("QVariantList", notify=profilesChanged)
    def speedProfiles(self) -> list[dict[str, Any]]:
        return [{"value": p, "text": p} for p in self._profiles]

    @Property("QVariantList", notify=effectsChanged)
    def effects(self) -> list[dict[str, Any]]:
        return [{"value": e, "text": effect_title(e)} for e in self._effects]

    @Slot(int, str)
    def setSpeedProfile(self, channel: int, profile: str) -> None:
        if profile not in self._profiles:
            self.session.report_message(f"Unknown speed profile {profile}", error=True)
            return
        serial = self.session.serial
        where = "all channels" if channel == ALL else self._title(channel, rgb_device=False)
        self.write(lambda: self.session.api.set_speed_profile(serial, channel, profile),
                   f"Speed profile of {where} set to {profile}", done=lambda ok: ok or self.selectedChanged.emit())

    @Slot(int, str)
    def setRgbProfile(self, channel: int, effect: str) -> None:
        if effect not in self._effects:
            self.session.report_message(f"Unknown effect {effect}", error=True)
            return
        serial = self.session.serial
        self.write(lambda: self.session.api.set_rgb_effect(serial, effect, channel),
                   f"Effect set to {effect_title(effect)}", done=lambda ok: ok or self.selectedChanged.emit())

    @Slot(int, bool, str)
    def setLabel(self, channel: int, rgb_device: bool, label: str) -> None:
        label = label.strip()
        if not label:
            self.session.report_message("A label cannot be empty", error=True)
            return
        serial = self.session.serial
        self.write(lambda: self.session.api.set_label(serial, channel, label, rgb_device=rgb_device),
                   f"Label set to {label}")

    def _title(self, channel: int, *, rgb_device: bool) -> str:
        key = f"{'rgb' if rgb_device else 'dev'}:{channel}"
        row = self._channels.indexOf("key", key)
        return self._channels.get(row)["title"] if row >= 0 else f"channel {channel}"
