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


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def se_device() -> dict[str, Any]:
    return load_fixture("device_scimitar_elite_se.json")["device"]


@pytest.fixture
def legacy_device() -> dict[str, Any]:
    return load_fixture("device_scimitar_rgb_elite.json")["device"]


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
        self.calls: list[tuple] = []
        self.fail_with: Exception | None = None

    def _check(self) -> None:
        if self.fail_with is not None:
            raise self.fail_with

    def list_mice(self) -> dict[str, str]:
        self._check()
        return {serial: d["product"] for serial, d in self.devices.items()}

    def get_device(self, serial: str) -> dict[str, Any]:
        self._check()
        return copy.deepcopy(self.devices[serial])

    def list_receivers(self) -> dict[str, str]:
        self._check()
        return {serial: "SLIPSTREAM" for serial in self.receivers}

    def get_receiver(self, serial: str) -> dict[str, Any]:
        self._check()
        return copy.deepcopy(self.receivers[serial])

    def battery_levels(self) -> dict[str, int]:
        return {s: d["BatteryLevel"] for s, d in self.devices.items() if "BatteryLevel" in d}

    def macros(self) -> dict[int, str]:
        return {1: "DPI"}

    def input_actions(self, kind: str) -> dict[int, str]:
        self.calls.append(("input_actions", kind))
        return {0: "None", 10: "Number 3", 46: "Letter T"} if kind == "keyboard" else {91: "(Mouse) Left Click"}

    def update_key_assignment(self, serial: str, key_index: int, **kwargs: Any) -> None:
        self._check()
        self.calls.append(("update_key_assignment", serial, key_index, kwargs))
        key = self.devices[serial]["KeyAssignment"][str(key_index)]
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

    def set_rgb_effect(self, serial: str, effect: str) -> None:
        self._check()
        self.calls.append(("set_rgb_effect", serial, effect))
        self._profile(serial)["RGBProfile"] = effect

    def set_brightness(self, serial: str, percent: int) -> None:
        self._check()
        self.calls.append(("set_brightness", serial, percent))
        self._profile(serial)["BrightnessSlider"] = percent

    def save_zone_colors(self, serial: str, colors: dict[int, str]) -> None:
        self._check()
        self.calls.append(("save_zone_colors", serial, dict(colors)))
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

    FIELDS = {
        "pollingRate": "PollingRate",
        "liftHeight": "LiftHeight",
        "sleepMode": "SleepMode",
        "angleSnapping": "AngleSnapping",
        "buttonOptimization": "ButtonOptimization",
    }

    def set_mouse_setting(self, serial: str, setting: str, value: int) -> None:
        self._check()
        self.calls.append(("set_mouse_setting", serial, setting, value))
        if serial in self.receivers:  # same endpoint, and the receiver restarts
            self.receivers[serial]["DeviceProfile"]["PollingRate"] = value
            return
        self._profile(serial)[self.FIELDS[setting]] = value

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


@pytest.fixture(scope="session")
def registry():
    from olhclient.devices.registry import Registry

    return Registry.discover()


@pytest.fixture
def make_session(qtbot, fake_api, registry):
    """Build a DeviceSession on the fake API; ``session.messages`` collects its messages."""
    from olhclient.api.models import MouseState
    from olhclient.core.session import DeviceSession
    from olhclient.core.worker import Worker

    def make(serial=SE):
        device = fake_api.get_device(serial)
        worker = Worker(synchronous=True)
        session = DeviceSession(fake_api, worker, registry.match(device), MouseState.from_json(device), {1: "DPI"})
        messages = []
        session.message.connect(lambda text, error: messages.append((text, error)))
        session.messages = messages
        return session

    return make
