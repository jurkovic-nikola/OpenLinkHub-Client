"""Lighting, device settings, DPI colours and user profiles."""

import pytest

from olhclient.api.client import ApiError
from tests.conftest import LEGACY, SE


def writes(fake_api, name):
    return [c for c in fake_api.calls if c[0] == name]


# -- DPI colours -------------------------------------------------------------


def test_dpi_save_values_and_colours(make_session, fake_api):
    dpi = make_session().controller("dpi")
    values = [s["value"] for s in dpi.stages.items()]
    colors = [s["color"] for s in dpi.stages.items()]
    values[0] = 900
    colors[2] = "#123ABC"
    dpi.save(values, colors)
    assert writes(fake_api, "save_dpi") == [("save_dpi", SE, {0: 900})]
    assert writes(fake_api, "save_dpi_colors") == [("save_dpi_colors", SE, {2: "#123abc"})]
    assert dpi.stages.get(2)["color"] == "#123abc"


def test_dpi_save_only_colours(make_session, fake_api):
    session = make_session()
    dpi = session.controller("dpi")
    colors = [s["color"] for s in dpi.stages.items()]
    colors[0] = "#00ff00"
    dpi.save([s["value"] for s in dpi.stages.items()], colors)
    assert not writes(fake_api, "save_dpi")
    assert session.messages[-1] == ("DPI colours saved", False)


# -- lighting ----------------------------------------------------------------


def test_lighting_state(make_session):
    lighting = make_session().controller("lighting")
    assert lighting.available
    assert (lighting.effect, lighting.effectTitle, lighting.brightness) == ("colorshift", "Colorshift", 30)
    assert {"value": "cpu-temperature", "text": "Cpu temperature"} in lighting.effects
    assert [z["name"] for z in lighting.zones.items()] == ["Side", "Logo"]


def test_lighting_immediate_changes(make_session, fake_api):
    lighting = make_session().controller("lighting")
    lighting.setEffect("static")
    lighting.setBrightness(80)
    lighting.setRgbCluster(True)
    lighting.setOpenRgb(True)
    assert (lighting.effect, lighting.brightness, lighting.rgbCluster, lighting.openRgb) == ("static", 80, True, True)
    calls = len(fake_api.calls)
    lighting.setEffect("static")  # unchanged: no request
    lighting.setBrightness(80)
    assert len(fake_api.calls) == calls


def test_lighting_rejects_invalid_values(make_session, fake_api):
    session = make_session()
    lighting = session.controller("lighting")
    lighting.setEffect("disco")
    lighting.setBrightness(150)
    assert not writes(fake_api, "set_rgb_effect") and not writes(fake_api, "set_brightness")
    assert session.messages[-1][1] is True


def test_lighting_failure_tells_ui_to_reset(make_session, fake_api, qtbot):
    session = make_session()
    lighting = session.controller("lighting")
    fake_api.fail_with = ApiError("Unable to change")
    with qtbot.waitSignal(lighting.changed):
        lighting.setRgbCluster(True)
    assert not lighting.rgbCluster
    assert ("Unable to change", True) in session.messages


def test_zone_colours_send_only_changes(make_session, fake_api):
    lighting = make_session().controller("lighting")
    colors = [z["color"] for z in lighting.zones.items()]
    lighting.saveZoneColors(colors)
    assert not writes(fake_api, "save_zone_colors")
    colors[1] = "#00FF00"
    lighting.saveZoneColors(colors)
    assert writes(fake_api, "save_zone_colors") == [("save_zone_colors", SE, {1: "#00ff00"}, "mouse")]
    assert lighting.zones.get(1)["color"] == "#00ff00"


def test_effect_profile(make_session, fake_api):
    session = make_session()
    profile = session.controller("lighting").effectProfile
    assert (profile.effectTitle, profile.colorNames, profile.hasSpeed, profile.hasAlternate) == (
        "Colorshift", ["Start", "End"], True, True)
    values = profile.values
    assert (values["colors"], values["speed"], values["alternate"]) == (["#ff0000", "#ff6400"], 4.0, False)
    profile.save(values)
    assert not writes(fake_api, "save_rgb_profile")
    assert session.messages[-1] == ("No changes to save", False)
    profile.save({**values, "colors": ["#FF0000", "#00FF00"], "speed": 2.5, "alternate": True})
    (_, serial, effect, saved), = writes(fake_api, "save_rgb_profile")
    assert (serial, effect, saved["speed"], saved["alternateColors"]) == (SE, "colorshift", 2.5, True)
    assert (saved["start"]["red"], saved["end"]["green"], saved["end"]["red"]) == (255, 255, 0)
    assert saved["smoothness"] == 50  # the rest comes back as fetched
    assert profile.values["colors"] == ["#ff0000", "#00ff00"]
    assert session.messages[-1] == ("Colorshift saved", False)


def test_effect_profile_rejects_invalid_values(make_session, fake_api):
    session = make_session()
    profile = session.controller("lighting").effectProfile
    for change in ({"speed": 0}, {"speed": 11}, {"colors": ["red", "#000000"]}, {"colors": ["#000000"]}):
        profile.save({**profile.values, **change})
        assert session.messages[-1][1] is True, change
    assert not writes(fake_api, "save_rgb_profile")


def test_effect_profile_temperatures(make_session, fake_api):
    session = make_session()
    lighting = session.controller("lighting")
    lighting.setEffect("cpu-temperature")
    profile = lighting.effectProfile
    assert (profile.colorNames, profile.hasTemperatures, profile.hasSpeed) == (["Start", "Middle", "End"], True, False)
    assert profile.values["temperatures"] == [20, 50, 95]
    profile.save({**profile.values, "temperatures": [30, 60, 90]})
    saved = writes(fake_api, "save_rgb_profile")[-1][3]
    assert [saved[slot]["temperature"] for slot in ("start", "middle", "end")] == [30, 60, 90]
    profile.save({**profile.values, "temperatures": [30, 60, 120]})
    assert session.messages[-1][1] is True


def test_effect_profile_gradient(make_session, fake_api):
    session = make_session()
    lighting = session.controller("lighting")
    lighting.setEffect("gradient")
    profile = lighting.effectProfile
    assert profile.hasGradient and profile.colorNames == []
    assert profile.values["gradient"] == [{"color": "#ff0000", "position": 0, "brightness": 1},
                                          {"color": "#0000ff", "position": 1, "brightness": 0.5}]
    stops = [{"color": "#00ff00", "position": 0.5, "brightness": 0.8}, *profile.values["gradient"]]
    profile.save({**profile.values, "gradient": stops})
    saved = writes(fake_api, "save_rgb_profile")[-1][3]["gradients"]
    assert [(s["Hex"], s["position"]) for s in saved.values()] == [("#FF0000", 0), ("#00FF00", 0.5), ("#0000FF", 1)]
    assert saved["1"]["brightness"] == 0.8
    profile.save({**profile.values, "gradient": stops[:1]})  # one colour is not a gradient
    assert session.messages[-1] == ("A gradient needs at least two colours", True)


@pytest.mark.parametrize(("effect", "names", "speed", "direction"), [
    ("static", ["Start"], False, False),
    ("rainbow", [], True, False),
    ("colorwave", ["Start", "End"], True, True),
    ("probe-temperature", ["Start", "End"], True, False),
])
def test_effect_profile_options_per_effect(make_session, effect, names, speed, direction):
    profile = make_session().controller("lighting").effectProfile
    profile.load(effect)
    assert (profile.colorNames, profile.hasSpeed, profile.hasDirection) == (names, speed, direction)
    assert profile.hasTempRange == (effect == "probe-temperature")
    assert profile.speedMax == (3 if effect == "colorwave" else 10)


def test_effect_profile_not_for_device_effects(make_session):
    profile = make_session().controller("lighting").effectProfile
    profile.load("mouse")
    assert not profile.available


def test_effect_profile_without_rgb_profiles(make_session, fake_api, monkeypatch):
    def refuse(serial, effect):
        raise ApiError("No such RGB profile")

    monkeypatch.setattr(fake_api, "rgb_profile", refuse)
    session = make_session()
    assert not session.controller("lighting").effectProfile.available
    assert not any(error for _, error in session.messages)


# -- device settings -----------------------------------------------------------


def keys(controller):
    return [item["key"] for item in controller.items]


def test_settings_wireless_dongle(make_session):
    settings = make_session().controller("settings")
    # no polling rate over the dongle; sleep timer only there
    assert keys(settings) == ["liftHeight", "sleepMode", "angleSnapping", "buttonOptimization"]
    sleep = settings.items[1]
    assert sleep["kind"] == "choice" and sleep["value"] == 5
    assert {"value": 60, "text": "1 hour"} in sleep["options"]


def test_settings_wireless_cable_hides_sleep(make_session, fake_api):
    fake_api.devices[SE]["Usb"] = True
    assert "sleepMode" not in keys(make_session().controller("settings"))


def test_settings_legacy(make_session):
    settings = make_session(LEGACY).controller("settings")
    assert keys(settings) == ["pollingRate", "liftHeight", "angleSnapping"]
    assert [o["value"] for o in settings.items[0]["options"]] == [1, 2, 4, 8]


def test_settings_apply(make_session, fake_api):
    session = make_session()
    settings = session.controller("settings")
    settings.apply("angleSnapping", 1)
    settings.apply("liftHeight", 4)
    assert writes(fake_api, "set_setting") == [
        ("set_setting", SE, "mouse/angleSnapping", {"angleSnapping": 1}),
        ("set_setting", SE, "mouse/liftHeight", {"liftHeight": 4}),
    ]
    assert settings.items[0]["value"] == 4 and settings.items[2]["value"] == 1
    assert session.messages[-1] == ("Lift-off distance updated", False)


@pytest.mark.parametrize("key, value", [("liftHeight", 5), ("pollingRate", 1), ("bogus", 1), ("liftHeight", 2)])
def test_settings_apply_rejects_or_skips(make_session, fake_api, key, value):
    # 5 is not an offered lift height, polling rate is not offered over the dongle,
    # and 2 is the current lift height (nothing to do)
    make_session().controller("settings").apply(key, value)
    assert not writes(fake_api, "set_setting")


# -- user profiles -------------------------------------------------------------


def test_switch_profile(make_session, fake_api):
    session = make_session()
    assert session.profileName == "Guildwars2"
    session.switchProfile("dbts")
    assert writes(fake_api, "switch_user_profile") == [("switch_user_profile", SE, "dbts")]
    assert session.profileName == "dbts"
    session.switchProfile("dbts")  # already active
    session.switchProfile("missing")
    assert len(writes(fake_api, "switch_user_profile")) == 1


def test_create_profile(make_session, fake_api):
    session = make_session()
    assert session.profileNameProblem("dbts") == "A profile with this name already exists"
    assert session.profileNameProblem("no spaces") != ""
    session.createProfile("x")
    assert not writes(fake_api, "save_user_profile")
    session.createProfile("Raid")
    assert writes(fake_api, "save_user_profile") == [("save_user_profile", SE, "Raid")]
    assert "Raid" in session.profiles
    assert session.profileName == "Guildwars2"  # creating does not switch


def test_delete_profile(make_session, fake_api):
    session = make_session()
    assert not session.canDeleteProfile("Guildwars2")  # active
    assert not session.canDeleteProfile("default")
    session.deleteProfile("default")
    assert not writes(fake_api, "delete_user_profile")
    session.deleteProfile("dbts")
    assert writes(fake_api, "delete_user_profile") == [("delete_user_profile", SE, "dbts")]
    assert session.profiles == ["Guildwars2", "default"]
    assert not session.profileBusy
