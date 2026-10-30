from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def se_device() -> dict[str, Any]:
    return load_fixture("device_scimitar_elite_se.json")["device"]


@pytest.fixture
def legacy_device() -> dict[str, Any]:
    return load_fixture("device_scimitar_rgb_elite.json")["device"]


class FakeApi:
    """In-memory stand-in for ApiClient, backed by the fixtures."""

    base_url = "http://fake:27003"

    def __init__(self, devices: list[dict[str, Any]]):
        self.devices = {d["serial"]: copy.deepcopy(d) for d in devices}
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

    def login(self, username: str, password: str) -> None:
        self.calls.append(("login", username))
        self.fail_with = None


@pytest.fixture
def fake_api(se_device, legacy_device) -> FakeApi:
    return FakeApi([se_device, legacy_device])
