"""Devices without a dedicated module: features come from what the device JSON offers."""

import pytest

from olhclient.api.client import ApiError
from olhclient.api.models import DeviceKind, DeviceState
from olhclient.core.backend import Backend
from olhclient.core.worker import Worker

from tests.conftest import COMMANDER, HEADSET, KEYBOARD, LINK_HUB, RECEIVER, SE, LEGACY


def writes(api, name):
    return [c for c in api.calls if c[0] == name]


@pytest.fixture
def session(make_session, every_api):
    return lambda serial: make_session(serial, every_api)


# -- models --------------------------------------------------------------------


def test_kinds_from_json(other_devices):
    kinds = [DeviceState.from_json(d).kind for d in other_devices]
    assert kinds == [DeviceKind.HEADSET, DeviceKind.HUB, DeviceKind.HUB, DeviceKind.KEYBOARD]


def test_headset_state(other_devices):
    state = DeviceState.from_json(other_devices[0], DeviceKind.HEADSET)
    assert state.lighting.brightness == 100 and not state.lighting.brightness_modes
    assert len(state.lighting.zones) == 6 and state.lighting.rgb_cluster is None
    assert [b.name for b in state.equalizer][:3] == ["32", "64", "125"] and len(state.equalizer) == 10
    assert state.keys == [] and state.stages == []


def test_hub_channels(other_devices):
    commander = DeviceState.from_json(other_devices[1])
    assert [(c.channel_id, c.title, c.rgb_device) for c in commander.channels] == [
        (0, "AIO Pump", False), (1, "Fan 1", False), (2, "Fan 2", False), (7, "Temperature Probe 1", False),
        (0, "Pump LED ring", True), (1, "Fan 1 LEDs", True),
    ]
    pump, probe = commander.channels[0], commander.channels[3]
    assert (pump.rpm, pump.temperature, pump.speed_profile, pump.rgb_profile) == (2410, 31.4, "aioPump", None)
    assert (probe.rpm, probe.temperature, probe.has_speed) == (None, 29.8, False)
    link = DeviceState.from_json(other_devices[2])
    assert [(c.title, c.rgb_profile) for c in link.channels] == [("iCUE LINK QX120 RGB", "colorpulse"), ("iCUE LINK H150i Pump", "static")]
    assert commander.lighting is None


def test_keyboard_keys(other_devices):
    state = DeviceState.from_json(other_devices[3])
    assert [k.name for k in state.keys] == ["Esc", "F1", "F2", "A", "Fn", "Space"]  # row by row
    a = state.key_by_name("A")
    assert (a.index, a.use_default, a.action_type, a.action_value, a.modifier) == (20, False, 3, 46, 1)
    assert state.key_by_name("Fn").locked
    assert state.keyboard.names == ("default", "gaming") and state.keyboard.active == "default"
    assert state.keyboard.modifiers[2] == "Left Shift"


# -- features per device -------------------------------------------------------------


@pytest.mark.parametrize("serial, features", [
    (SE, ["key_remap", "dpi", "lighting", "settings"]),
    (LEGACY, ["key_remap", "dpi", "lighting", "settings"]),
    (HEADSET, ["lighting", "equalizer", "settings"]),
    (COMMANDER, ["fans"]),
    (LINK_HUB, ["fans"]),
    (KEYBOARD, ["keyboard_keys", "lighting", "settings"]),
])
def test_features_follow_the_device_json(session, serial, features):
    s = session(serial)
    assert [f["id"] for f in s.features] == features
    assert s.hasArtwork == (serial in (SE, LEGACY))
    assert s.thumbnail.endswith(".svg")


def test_headset_settings(session, every_api):
    s = session(HEADSET)
    settings = s.controller("settings")
    items = {i["key"]: i for i in settings.items}
    assert list(items) == ["sleepMode", "noiseCancellation", "sideTone", "sideToneValue", "muteIndicator",
                           "leftWheel", "rightWheel"]
    assert items["sleepMode"]["options"][0] == {"value": 0, "text": "Off"}  # "Off" is a real choice here
    assert items["sideToneValue"]["kind"] == "slider" and not items["sideToneValue"]["enabled"]  # sidetone is off

    settings.apply("rightWheel", 1)
    settings.apply("noiseCancellation", 2)
    settings.apply("sideToneValue", 20)  # disabled: nothing is sent
    assert writes(every_api, "set_setting") == [
        ("set_setting", HEADSET, "headset/wheelOption", {"wheelOption": 1, "wheelId": 2}),
        ("set_setting", HEADSET, "headset/anc", {"noiseCancellation": 2}),
    ]
    assert {i["key"]: i["value"] for i in settings.items}["rightWheel"] == 1


def test_refused_setting_is_reported_and_reset(session, every_api, qtbot):
    s = session(HEADSET)
    settings = s.controller("settings")
    every_api.fail_with = ApiError("Unable to change sleep mode")
    with qtbot.waitSignal(settings.itemsChanged):
        settings.apply("sleepMode", 30)
    every_api.fail_with = None
    assert s.messages[-1] == ("Unable to change sleep mode", True)


def test_headset_lighting_and_zones(session, every_api):
    s = session(HEADSET)
    lighting = s.controller("lighting")
    assert lighting.hasBrightness and not lighting.hasRgbCluster and not lighting.hasOpenRgb
    assert lighting.zones.count == 6
    colors = [z["color"] for z in lighting.zones.items()]
    colors[3] = "#123456"
    lighting.saveZoneColors(colors)
    assert writes(every_api, "save_zone_colors") == [("save_zone_colors", HEADSET, {3: "#123456"}, "headset")]


def test_stepped_brightness(make_session, every_api):
    profile = every_api.devices[HEADSET]["DeviceProfile"]
    profile["BrightnessSlider"] = None  # a driver without the 0-100 slider
    lighting = make_session(HEADSET, every_api).controller("lighting")
    assert not lighting.hasBrightness
    assert [m["text"] for m in lighting.brightnessModes] == ["RGB Profile", "33 %", "66 %", "100 %"]
    lighting.setBrightnessMode(2)
    lighting.setBrightness(50)  # no slider: ignored
    assert writes(every_api, "set_brightness_mode") == [("set_brightness_mode", HEADSET, 2)]
    assert not writes(every_api, "set_brightness") and lighting.brightnessMode == 2


def test_equalizer(session, every_api):
    eq = session(HEADSET).controller("equalizer")
    values = [b["value"] for b in eq.bands]
    eq.save(values)  # unchanged: nothing sent
    values[0], values[9] = 4.5, -3
    eq.save(values)
    (_, serial, bands), = writes(every_api, "set_equalizer")
    assert serial == HEADSET and len(bands) == 10 and bands[1] == 4.5 and bands[10] == -3
    assert eq.bands[0]["value"] == 4.5
    values[1] = 20
    eq.save(values)  # out of range
    assert len(writes(every_api, "set_equalizer")) == 1


def test_fans(session, every_api):
    s = session(COMMANDER)
    fans = s.controller("fans")
    assert [p["value"] for p in fans.speedProfiles] == ["aioPump", "Normal", "Quiet"]
    assert fans.selected["title"] == "AIO Pump" and fans.selected["rpm"] == 2410
    fans.setSpeedProfile(1, "Quiet")
    fans.setSpeedProfile(-1, "Normal")
    fans.setSpeedProfile(1, "Turbo")  # unknown: not sent
    fans.selectedKey = "rgb:0"
    assert fans.selected["title"] == "Pump LED ring" and fans.selected["hasRgb"]
    fans.setRgbProfile(0, "rainbow")
    fans.setLabel(0, True, "Ring")
    assert writes(every_api, "set_speed_profile") == [
        ("set_speed_profile", COMMANDER, 1, "Quiet"), ("set_speed_profile", COMMANDER, -1, "Normal")]
    assert writes(every_api, "set_rgb_effect") == [("set_rgb_effect", COMMANDER, "rainbow", 0)]
    assert writes(every_api, "set_label") == [("set_label", COMMANDER, 0, "Ring", True)]
    assert fans.selected["title"] == "Pump LED ring"
    assert fans.selected["label"] == "Ring"
    assert fans.selected["rgbProfile"] == "rainbow"
    assert fans.effectProfile.colorNames == [] and fans.effectProfile.hasSpeed  # rainbow: only a speed
    fans.setRgbProfile(0, "colorshift")
    profile = fans.effectProfile
    assert profile.effectTitle == "Colorshift" and profile.colorNames == ["Start", "End"]
    profile.save({**profile.values, "colors": ["#0000ff", "#ff6400"]})
    (_, serial, effect, saved), = writes(every_api, "save_rgb_profile")
    assert (serial, effect, saved["start"]["blue"], saved["start"]["red"]) == (COMMANDER, "colorshift", 255, 0)


def test_keyboard_remap_and_profiles(session, every_api):
    s = session(KEYBOARD)
    keys = s.controller("keyboard_keys")
    assert [m["text"] for m in keys.modifierOptions][:2] == ["None", "Left Ctrl"]
    assert s.selectedButton == "Esc"
    s.selectedButton = "F1"
    keys.save(keys.selected["keyIndex"], False, 3, 46, False, False, 2)
    (_, serial, index, kwargs), = writes(every_api, "update_key_assignment")
    assert (serial, index, kwargs["kind"], kwargs["modifier"]) == (KEYBOARD, 2, "keyboard", 2)
    assert keys.selected["modifier"] == 2 and keys.selected["actionValue"] == 46

    s.selectedButton = "Fn"
    assert keys.selected["locked"]
    keys.save(keys.selected["keyIndex"], False, 3, 46, False, False, 0)
    assert len(writes(every_api, "update_key_assignment")) == 1  # colour-only key

    assert keys.keyboardProfiles == ["default", "gaming"]
    keys.switchKeyboardProfile("gaming")
    keys.newKeyboardProfile("gaming")  # exists
    keys.newKeyboardProfile("mmo")
    keys.deleteKeyboardProfile("default")  # never
    keys.deleteKeyboardProfile("mmo")
    assert [c[0] for c in every_api.calls if "keyboard_profile" in c[0]] == [
        "switch_keyboard_profile", "new_keyboard_profile", "delete_keyboard_profile"]
    assert keys.keyboardProfile == "gaming"


def test_keyboard_settings(session, every_api):
    settings = session(KEYBOARD).controller("settings")
    items = {i["key"]: i for i in settings.items}
    assert list(items) == ["pollingRate", "layout"]
    assert items["layout"]["kind"] == "textChoice" and items["layout"]["value"] == "US"
    settings.apply("layout", "BE")
    settings.apply("layout", "XX")  # not offered
    assert writes(every_api, "set_setting") == [("set_setting", KEYBOARD, "keyboard/layout", {"keyboardLayout": "BE"})]


# -- backend -----------------------------------------------------------------------


@pytest.fixture
def backend(qtbot, every_api, registry):
    return Backend(every_api, registry, worker=Worker(synchronous=True))


def test_backend_lists_every_kind(backend):
    backend.refresh()
    tiles = backend.devices.items()
    assert [t["serial"] for t in tiles] == [SE, LEGACY, KEYBOARD, HEADSET, COMMANDER, LINK_HUB, RECEIVER]
    assert [t["name"] for t in tiles][2:6] == ["Keyboard", "Headset", "Hub", "Hub"]
    assert tiles[3]["thumbnail"].endswith("kind-headset.svg")


def test_backend_device_without_json(backend, every_api):
    every_api.unreadable["BROKEN0TEST"] = "HS80 RGB WIRELESS"
    backend.refresh()
    backend.selectDevice("BROKEN0TEST")
    session = backend.session
    assert session.serial == "BROKEN0TEST" and session.product == "HS80 RGB WIRELESS"
    assert session.features == [] and session.kindTitle == "Headset"


def test_backend_never_asks_for_auth_on_a_broken_device(backend, every_api):
    every_api.unreadable["BROKEN0TEST"] = "HS80"
    original = every_api.get_device

    def needs_login(serial):
        if serial == "BROKEN0TEST":
            raise ApiError("Authentication required", http_status=401, auth_required=True)
        return original(serial)

    every_api.get_device = needs_login
    backend.refresh()
    assert backend.authRequired



def test_keyboard_actions_are_named_without_input_actions(session):
    s = session(KEYBOARD)  # keyboard JSON has no InputActions; names come from /api/input/keyboard
    s.reload()
    a = next(k for k in s.controller("keyboard_keys").keys.items() if k["name"] == "A")
    assert a["action"] == "Keyboard: Letter T"


def test_equalizer_band_titles(session):
    from olhclient.core.features.equalizer import band_title

    assert [band_title(n) for n in ("32", "1K", "16K", "Bass")] == ["32 Hz", "1 kHz", "16 kHz", "Bass"]
    assert session(HEADSET).controller("equalizer").bands[0]["name"] == "32 Hz"


def test_unreadable_device_claims_no_connection(backend, every_api):
    every_api.unreadable["BROKEN0TEST"] = "HS80"
    backend.refresh()
    backend.selectDevice("BROKEN0TEST")
    assert backend.session.connectionMode == ""


def test_keyboard_board(session, every_api):
    s = session(KEYBOARD)
    assert s.hasKeyboardLayout
    board = {k["name"]: k for k in s.controller("keyboard_keys").boardKeys}
    assert set(board) == {"Esc", "F1", "F2", "A", "Fn", "Space"}
    assert board["Esc"]["x"] == 0 and board["Esc"]["y"] == 0  # top-left corner
    assert all(0 <= k["x"] and k["x"] + k["w"] <= 1.0001 and k["y"] + k["h"] <= 1.0001 for k in board.values())
    assert board["A"]["remapped"] and not board["F1"]["remapped"] and board["Fn"]["locked"]
    assert board["Esc"]["color"] == "#ffffff"
    assert s.controller("keyboard_keys").boardAspect > 1
    assert not session(HEADSET).hasKeyboardLayout and session(HEADSET).controller("keyboard_keys") is None
