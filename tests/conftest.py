from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QStandardPaths  # noqa: E402

QStandardPaths.setTestModeEnabled(True)  # lit artwork goes to ~/.qttest, not the real cache

FIXTURES = Path(__file__).parent / "fixtures"
SE = "SE0000000000TEST"
LEGACY = "RGBELITE00TEST"
RECEIVER = "SLIPSTREAM0TEST"
HEADSET = "VIRTUOSO00TEST"
COMMANDER = "COMMANDER0TEST"
LINK_HUB = "LINKHUB000TEST"
KEYBOARD = "K70CORE000TEST"
#: OpenLinkHub's icon per device kind, as GET /api/ reports it
IMAGES = {"mouse": "icon-mouse.svg", "keyboard": "icon-keyboard.svg", "headset": "icon-headphone.svg",
          "hub": "icon-device.svg"}


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def se_device() -> dict[str, Any]:
    return load_fixture("device_scimitar_elite_se.json")["device"]


@pytest.fixture
def legacy_device() -> dict[str, Any]:
    return load_fixture("device_scimitar_rgb_elite.json")["device"]


@pytest.fixture
def other_devices() -> list[dict[str, Any]]:
    """A headset, two hubs and a keyboard."""
    names = ("device_virtuoso_max.json", "device_commander_core.json", "device_icue_link.json", "device_k70_core.json")
    return [load_fixture(name)["device"] for name in names]


@pytest.fixture
def receiver_device() -> dict[str, Any]:
    from olhclient.api.receiver_page import parse_receiver_page

    return parse_receiver_page((FIXTURES / "slipstream_page.html").read_text())


class FakeApi:
    """In-memory stand-in for ApiClient, backed by the fixtures."""

    base_url = "http://fake:27003"

    def __init__(self, devices: list[dict[str, Any]], receivers: list[dict[str, Any]] = ()):
        self.devices = {d["serial"]: copy.deepcopy(d) for d in devices}
        self.receivers = {r["serial"]: copy.deepcopy(r) for r in receivers}
        #: serials whose JSON OpenLinkHub cannot encode (GET /api/devices/{serial} has an empty body)
        self.unreadable: dict[str, str] = {}
        self.calls: list[tuple] = []
        self.fail_with: Exception | None = None
        #: macro id -> macro JSON, as GET /api/macro/ returns it
        self.macro_data: dict[int, dict[str, Any]] = {
            int(k): v for k, v in copy.deepcopy(load_fixture("macro.json")["data"]).items()}

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def list_devices(self) -> dict[str, Any]:
        from olhclient.api.models import DeviceInfo, DeviceState

        self._check()
        listed = {
            serial: DeviceInfo.from_json(serial, {"Product": d["product"],
                                                  "Image": IMAGES.get(DeviceState.from_json(d).kind.value, "")})
            for serial, d in self.devices.items()
        }
        listed.update({serial: DeviceInfo.from_json(serial, {"Product": product, "Image": "icon-headphone.svg"})
                       for serial, product in self.unreadable.items()})
        listed.update({serial: DeviceInfo.from_json(serial, {"Product": "SLIPSTREAM", "Hidden": True})
                       for serial in self.receivers})
        return listed

    def get_device(self, serial: str) -> dict[str, Any]:
        from olhclient.api.client import ApiError

        self._check()
        if serial in self.unreadable:
            raise ApiError(f"Invalid response from /api/devices/{serial}")
        return copy.deepcopy(self.devices[serial])

    def get_receiver(self, serial: str) -> dict[str, Any]:
        self._check()
        return copy.deepcopy(self.receivers[serial])

    def battery_levels(self) -> dict[str, int]:
        return {s: d["BatteryLevel"] for s, d in self.devices.items() if "BatteryLevel" in d}

    def macros(self) -> dict[int, str]:
        return {macro_id: macro["name"] for macro_id, macro in self.macro_data.items()}

    # -- macros, with OpenLinkHub's indexing: a new action gets index len(actions)

    def macro_profiles(self) -> list[Any]:
        from olhclient.api.models import Macro

        self._check()
        return [Macro.from_json(copy.deepcopy(m)) for _, m in sorted(self.macro_data.items())]

    def new_macro(self, name: str) -> None:
        self._check()
        self.calls.append(("new_macro", name))
        macro_id = max(self.macro_data, default=0) + 1
        self.macro_data[macro_id] = {"id": macro_id, "name": name, "repeat": 0, "repeatDelay": 0, "actions": {}}

    def delete_macro(self, macro_id: int) -> None:
        self._check()
        self.calls.append(("delete_macro", macro_id))
        del self.macro_data[macro_id]

    def update_macro_settings(self, macro_id: int, repeat: int, repeat_delay: int) -> None:
        self._check()
        self.calls.append(("update_macro_settings", macro_id, repeat, repeat_delay))
        self.macro_data[macro_id].update(repeat=repeat, repeatDelay=repeat_delay)

    def add_macro_action(self, macro_id: int, action: Any) -> None:
        self._check()
        self.calls.append(("add_macro_action", macro_id, action))
        actions = self.macro_data[macro_id]["actions"]
        actions[str(len(actions))] = {
            "actionType": action.action_type, "actionCommand": action.command, "actionDelay": action.delay,
            "actionHold": False, "actionRepeat": 0, "actionRepeatDelay": 0, "actionText": action.text,
            "mousePositionX": action.x, "mousePositionY": action.y, "mousePositionAbsolute": action.absolute,
        }

    def update_macro_action(self, macro_id: int, index: int, action: Any) -> None:
        from olhclient.api.client import ApiError

        self._check()
        self.calls.append(("update_macro_action", macro_id, index, action))
        actions = self.macro_data[macro_id]["actions"]
        if action.hold:  # the server refuses holding every non-delay action
            pressed = [i for i, a in actions.items() if a["actionType"] != 5]
            if all(i == str(index) or actions[i]["actionHold"] for i in pressed):
                raise ApiError("Unable to update macro value: press and hold")
        actions[str(index)].update(
            actionHold=action.hold, actionRepeat=action.repeat, actionRepeatDelay=action.repeat_delay,
            mousePositionX=action.x, mousePositionY=action.y, mousePositionAbsolute=action.absolute)

    def delete_macro_action(self, macro_id: int, index: int) -> None:
        self._check()
        self.calls.append(("delete_macro_action", macro_id, index))
        del self.macro_data[macro_id]["actions"][str(index)]

    def input_actions(self, kind: str) -> dict[int, str]:
        self.calls.append(("input_actions", kind))
        return {0: "None", 10: "Number 3", 46: "Letter T"} if kind == "keyboard" else {91: "(Mouse) Left Click"}

    def update_key_assignment(self, serial: str, key_index: int, **kwargs: Any) -> None:
        self._check()
        self.calls.append(("update_key_assignment", serial, key_index, kwargs))
        device = self.devices[serial]
        if "KeyAssignment" in device:
            key = device["KeyAssignment"][str(key_index)]
        else:  # keyboard: the key in the active keyboard profile
            profile = device["DeviceProfile"]
            rows = profile["Keyboards"][profile["Profile"]]["row"].values()
            key = next(row["keys"][str(key_index)] for row in rows if str(key_index) in row["keys"])
            key["modifierKey"] = kwargs.get("modifier", 0)
        key.update(
            default=kwargs["use_default"],
            actionType=kwargs["action_type"],
            actionCommand=kwargs["action_value"],
            actionHold=kwargs["press_and_hold"],
            onRelease=kwargs["on_release"],
        )

    def save_dpi(self, serial: str, stages: dict[int, int]) -> None:
        self._check()
        self.calls.append(("save_dpi", serial, dict(stages)))
        for index, value in stages.items():
            self.devices[serial]["DeviceProfile"]["Profiles"][str(index)]["Value"] = value

    def save_dpi_colors(self, serial: str, colors: dict[int, str]) -> None:
        self._check()
        self.calls.append(("save_dpi_colors", serial, dict(colors)))
        for index, color in colors.items():
            self.devices[serial]["DeviceProfile"]["Profiles"][str(index)]["Color"]["Hex"] = color

    # -- lighting

    def _profile(self, serial: str) -> dict[str, Any]:
        return self.devices[serial]["DeviceProfile"]

    def set_rgb_effect(self, serial: str, effect: str, channel: int = 0) -> None:
        self._check()
        self.calls.append(("set_rgb_effect", serial, effect, channel))
        device = self.devices[serial]
        if "RGBProfile" in device["DeviceProfile"]:
            device["DeviceProfile"]["RGBProfile"] = effect
            return
        for entry in self._channels(serial, rgb=True):
            if channel in (-1, entry["channelId"]):
                entry["rgb"] = effect

    def set_brightness_mode(self, serial: str, mode: int) -> None:
        self._check()
        self.calls.append(("set_brightness_mode", serial, mode))
        self._profile(serial)["Brightness"] = mode

    def set_brightness(self, serial: str, percent: int) -> None:
        self._check()
        self.calls.append(("set_brightness", serial, percent))
        self._profile(serial)["BrightnessSlider"] = percent

    def save_zone_colors(self, serial: str, colors: dict[int, str], kind: str = "mouse") -> None:
        self._check()
        self.calls.append(("save_zone_colors", serial, dict(colors), kind))
        for index, color in colors.items():
            self._profile(serial)["ZoneColors"][str(index)]["Color"]["Hex"] = color

    def set_rgb_cluster(self, serial: str, enabled: bool) -> None:
        self._check()
        self.calls.append(("set_rgb_cluster", serial, enabled))
        self._profile(serial)["RGBCluster"] = enabled

    def set_openrgb(self, serial: str, enabled: bool) -> None:
        self._check()
        self.calls.append(("set_openrgb", serial, enabled))
        self._profile(serial)["OpenRGBIntegration"] = enabled

    # -- settings

    def set_setting(self, serial: str, endpoint: str, values: dict[str, Any]) -> None:
        from olhclient.core.features.settings import SPECS

        self._check()
        self.calls.append(("set_setting", serial, endpoint, dict(values)))
        if serial in self.receivers:  # same endpoint as a mouse, and the receiver restarts
            self.receivers[serial]["DeviceProfile"]["PollingRate"] = values["pollingRate"]
            return
        name = endpoint.split("/", 1)[1]
        spec = next(s for s in SPECS if s.endpoint == name and s.field in values
                    and all(values.get(k) == v for k, v in s.extra.items()))
        self._profile(serial)[spec.current] = values[spec.field]

    def set_equalizer(self, serial: str, bands: dict[int, float]) -> None:
        self._check()
        self.calls.append(("set_equalizer", serial, dict(bands)))
        for index, value in bands.items():
            self._profile(serial)["Equalizers"][str(index)]["Value"] = value

    # -- hubs

    def _channels(self, serial: str, *, rgb: bool = False) -> list[dict[str, Any]]:
        device = self.devices[serial]
        source = device.get("rgbDevices") if rgb and device.get("rgbDevices") else device.get("devices")
        return list((source or {}).values())

    def temperature_profiles(self) -> list[str]:
        self._check()
        return ["aioPump", "Normal", "Quiet"]

    def set_speed_profile(self, serial: str, channel: int, profile: str) -> None:
        self._check()
        self.calls.append(("set_speed_profile", serial, channel, profile))
        for entry in self._channels(serial):
            if entry["HasSpeed"] and channel in (-1, entry["channelId"]):
                entry["profile"] = profile

    def set_label(self, serial: str, channel: int, label: str, *, rgb_device: bool = False) -> None:
        self._check()
        self.calls.append(("set_label", serial, channel, label, rgb_device))
        entries = self._channels(serial, rgb=rgb_device)
        next(e for e in entries if e["channelId"] == channel)["label"] = label

    # -- keyboard profiles

    def new_keyboard_profile(self, serial: str, name: str) -> None:
        self._check()
        self.calls.append(("new_keyboard_profile", serial, name))
        profile = self._profile(serial)
        profile["Keyboards"][name] = copy.deepcopy(profile["Keyboards"][profile["Profile"]])
        profile["Profiles"].append(name)

    def switch_keyboard_profile(self, serial: str, name: str) -> None:
        self._check()
        self.calls.append(("switch_keyboard_profile", serial, name))
        self._profile(serial)["Profile"] = name

    def delete_keyboard_profile(self, serial: str, name: str) -> None:
        self._check()
        self.calls.append(("delete_keyboard_profile", serial, name))
        profile = self._profile(serial)
        del profile["Keyboards"][name]
        profile["Profiles"].remove(name)

    # -- user profiles

    def switch_user_profile(self, serial: str, name: str) -> None:
        self._check()
        self.calls.append(("switch_user_profile", serial, name))
        for profile_name, profile in self.devices[serial]["userProfiles"].items():
            profile["Active"] = profile_name == name

    def save_user_profile(self, serial: str, name: str) -> None:
        self._check()
        self.calls.append(("save_user_profile", serial, name))
        device = self.devices[serial]
        device["userProfiles"][name] = {"Active": False}
        device["profileOrder"].append(name)

    def delete_user_profile(self, serial: str, name: str) -> None:
        self._check()
        self.calls.append(("delete_user_profile", serial, name))
        device = self.devices[serial]
        del device["userProfiles"][name]
        device["profileOrder"].remove(name)

    def login(self, username: str, password: str) -> None:
        self.calls.append(("login", username))
        self.fail_with = None


@pytest.fixture
def fake_api(se_device, legacy_device, receiver_device) -> FakeApi:
    return FakeApi([se_device, legacy_device], [receiver_device])


@pytest.fixture
def every_api(se_device, legacy_device, other_devices, receiver_device) -> FakeApi:
    """Every kind of device the fixtures have."""
    return FakeApi([se_device, legacy_device, *other_devices], [receiver_device])


@pytest.fixture(scope="session")
def registry():
    from olhclient.devices.registry import Registry

    return Registry.discover()


@pytest.fixture
def make_session(qtbot, fake_api, registry):
    """Build a DeviceSession on the fake API; ``session.messages`` collects its messages."""
    from olhclient.api.models import DeviceState
    from olhclient.core.session import DeviceSession
    from olhclient.core.worker import Worker

    def make(serial=SE, api=None):
        api = api or fake_api
        device = api.get_device(serial)
        worker = Worker(synchronous=True)
        session = DeviceSession(api, worker, registry.match(device), DeviceState.from_json(device), {1: "DPI"})
        messages = []
        session.message.connect(lambda text, error: messages.append((text, error)))
        session.messages = messages
        return session

    return make
