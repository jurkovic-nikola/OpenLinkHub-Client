import pytest

from olhclient.api.models import ActionType, DeviceState, valid_profile_name, validate_assignment


def test_parse_wireless_se(se_device):
    state = DeviceState.from_json(se_device)
    assert state.product == "SCIMITAR ELITE SE"
    assert state.product_id == 11042
    assert state.wireless and state.battery == 100 and state.usb is False
    assert (state.min_dpi, state.max_dpi) == (100, 33000)
    assert len(state.keys) == 17
    assert state.key_by_name("Side Button 1").index == 32
    assert state.active_profile == "Guildwars2"
    assert state.assignment_types[ActionType.SNIPER] == "Sniper"


def test_parse_dpi_stages(se_device):
    state = DeviceState.from_json(se_device)
    assert [s.index for s in state.stages] == [0, 1, 2, 3, 4, 5]
    assert state.stages[0].value == 800 and state.stages[0].color == "#ff0000"
    assert state.stages[-1].sniper and not any(s.sniper for s in state.stages[:-1])
    assert state.active_stage == 2


def test_parse_legacy_generation(legacy_device):
    state = DeviceState.from_json(legacy_device)
    assert state.key_by_name("Side Button 1").index == 256
    assert state.key_by_name("DPI Button").index == 64
    assert state.battery is None and not state.wireless
    assert state.active_profile == "default"


def test_keys_sorted_by_index(se_device):
    state = DeviceState.from_json(se_device)
    assert [k.index for k in state.keys] == sorted(k.index for k in state.keys)


@pytest.mark.parametrize(
    "action_type, hold, release, ok",
    [
        (ActionType.KEYBOARD, False, False, True),
        (ActionType.KEYBOARD, True, False, True),
        (ActionType.KEYBOARD, True, True, False),
        (ActionType.MACRO, True, False, False),
        (ActionType.MACRO, False, True, True),
        (ActionType.SNIPER, True, False, True),
        (ActionType.SNIPER, False, False, False),
        (ActionType.SNIPER, True, True, False),
    ],
)
def test_validate_assignment_matches_server_rules(action_type, hold, release, ok):
    assert (validate_assignment(action_type, press_and_hold=hold, on_release=release) is None) == ok


def test_parse_lighting(se_device):
    lighting = DeviceState.from_json(se_device).lighting
    assert lighting.effect == "colorshift"
    assert "static" in lighting.effects and "mouse" in lighting.effects
    assert lighting.brightness == 30
    assert [(z.index, z.name) for z in lighting.zones] == [(0, "Side"), (1, "Logo")]
    assert all(z.color.startswith("#") and len(z.color) == 7 for z in lighting.zones)


def test_settings_from_device_json(se_device, legacy_device):
    from olhclient.core.features.settings import SPECS_BY_KEY, build_item

    se = DeviceState.from_json(se_device)
    assert build_item(SPECS_BY_KEY["pollingRate"], se) is None  # not offered over the Slipstream dongle
    assert [o["value"] for o in build_item(SPECS_BY_KEY["sleepMode"], se)["options"]] == [1, 5, 10, 15, 30, 60]
    assert {"value": 6, "text": "Calibrated"} in build_item(SPECS_BY_KEY["liftHeight"], se)["options"]
    legacy = build_item(SPECS_BY_KEY["pollingRate"], DeviceState.from_json(legacy_device))
    assert [o["value"] for o in legacy["options"]] == [1, 2, 4, 8]  # "Not Set" (0) is left out
    assert legacy["value"] == 1


@pytest.mark.parametrize("name, ok", [("game", True), ("Raid25", True), ("ab", False), ("my game", False),
                                      ("dash-name", False), ("héllo", False)])
def test_valid_profile_name(name, ok):
    assert (valid_profile_name(name) is None) is ok
