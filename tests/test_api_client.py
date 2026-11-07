import json

import httpx
import pytest
import respx

from olhclient.api.client import ApiClient, ApiError
from tests.conftest import load_fixture

BASE = "http://127.0.0.1:27003"


@pytest.fixture
def api():
    client = ApiClient(BASE)
    yield client
    client.close()


@respx.mock
def test_list_devices(api):
    respx.get(f"{BASE}/api/").respond(json=load_fixture("api_root.json"))
    devices = api.list_devices()
    assert {s: (d.product, d.kind.value, d.hidden) for s, d in devices.items()} == {
        "SE0000000000TEST": ("SCIMITAR ELITE SE", "mouse", False),
        "VIRTUOSO00TEST": ("VIRTUOSO MAX", "headset", False),
        "VIRTUOSO0DNGL": ("HEADSET DONGLE", "dongle", True),
        "SLIPSTREAM0TEST": ("SLIPSTREAM", "dongle", True),
        "cluster": ("Cluster", "device", True),
    }


@respx.mock
def test_get_device_accepts_status_zero(api):
    # OpenLinkHub never sets status=1 on this endpoint.
    respx.get(f"{BASE}/api/devices/SE0000000000TEST").respond(json=load_fixture("device_scimitar_elite_se.json"))
    device = api.get_device("SE0000000000TEST")
    assert device["ProductId"] == 11042


@respx.mock
def test_get_device_unknown_serial(api):
    respx.get(f"{BASE}/api/devices/NOPE").respond(json={"code": 200, "status": 0})
    with pytest.raises(ApiError):
        api.get_device("NOPE")


@respx.mock
def test_update_key_assignment_payload_and_origin(api):
    route = respx.post(f"{BASE}/api/mouse/updateKeyAssignment").respond(json={"code": 200, "status": 1})
    api.update_key_assignment("SER", 32, use_default=False, action_type=3, action_value=46,
                              press_and_hold=False, on_release=True)
    request = route.calls.last.request
    assert request.headers["Origin"] == BASE
    assert json.loads(request.content) == {
        "deviceId": "SER",
        "keyIndex": 32,
        "enabled": False,
        "pressAndHold": False,
        "keyAssignmentType": 3,
        "keyAssignmentValue": 46,
        "onRelease": True,
    }


@respx.mock
def test_status_zero_raises_with_server_message(api):
    respx.post(f"{BASE}/api/mouse/dpi").respond(json={"code": 200, "status": 0, "message": "Unable to change DPI"})
    with pytest.raises(ApiError, match="Unable to change DPI"):
        api.save_dpi("SER", {0: 800})


@respx.mock
def test_save_dpi_stringifies_stage_keys(api):
    route = respx.post(f"{BASE}/api/mouse/dpi").respond(json={"code": 200, "status": 1})
    api.save_dpi("SER", {0: 800, 5: 200})
    assert json.loads(route.calls.last.request.content) == {"deviceId": "SER", "stages": {"0": 800, "5": 200}}


@respx.mock
def test_get_requests_have_no_origin(api):
    route = respx.get(f"{BASE}/api/").respond(json={"code": 200, "device": {}})
    api.list_devices()
    assert "Origin" not in route.calls.last.request.headers


@respx.mock
def test_auth_required(api):
    respx.get(f"{BASE}/api/").respond(401, text="Authentication required")
    with pytest.raises(ApiError) as info:
        api.list_devices()
    assert info.value.auth_required


@respx.mock
def test_connection_error(api):
    respx.get(f"{BASE}/api/").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ApiError, match="Cannot reach"):
        api.list_devices()


@respx.mock
def test_input_actions_and_macros(api):
    respx.get(f"{BASE}/api/input/mouse").respond(json=load_fixture("input_mouse.json"))
    respx.get(f"{BASE}/api/macro/").respond(json=load_fixture("macro.json"))
    actions = api.input_actions("mouse")
    assert actions[91] == "(Mouse) Left Click"
    assert api.macros() == {1: "DPI"}
    with pytest.raises(ValueError):
        api.input_actions("joystick")


@respx.mock
def test_macro_profiles(api):
    from olhclient.api.models import MacroStep

    respx.get(f"{BASE}/api/macro/").respond(json=load_fixture("macro.json"))
    [macro] = api.macro_profiles()
    assert (macro.id, macro.name, macro.repeat) == (1, "DPI", 0)
    assert macro.ordered[0].action_type == MacroStep.KEYBOARD
    assert macro.ordered[0].command == 77


@respx.mock
def test_macro_writes(api):
    from olhclient.api.models import MacroAction, MacroStep

    ok = {"code": 200, "status": 1, "message": "OK"}
    routes = {
        ("PUT", "/api/macro/new"): respx.put(f"{BASE}/api/macro/new").respond(json=ok),
        ("DELETE", "/api/macro/profile"): respx.delete(f"{BASE}/api/macro/profile").respond(json=ok),
        ("POST", "/api/macro/updateSettings"): respx.post(f"{BASE}/api/macro/updateSettings").respond(json=ok),
        ("POST", "/api/macro/newValue"): respx.post(f"{BASE}/api/macro/newValue").respond(json=ok),
        ("POST", "/api/macro/updateValue"): respx.post(f"{BASE}/api/macro/updateValue").respond(json=ok),
        ("DELETE", "/api/macro/value"): respx.delete(f"{BASE}/api/macro/value").respond(json=ok),
    }

    def sent(method: str, path: str) -> dict:
        return json.loads(routes[(method, path)].calls.last.request.content)

    move = MacroAction(MacroStep.MOUSE_MOVE, x=10, y=20, absolute=True, repeat=2, repeat_delay=5)
    api.new_macro("Combo")
    assert sent("PUT", "/api/macro/new") == {"macroName": "Combo"}
    api.delete_macro(3)
    assert sent("DELETE", "/api/macro/profile") == {"macroId": 3}
    api.update_macro_settings(3, -1, 250)
    assert sent("POST", "/api/macro/updateSettings") == {"macroId": 3, "macroRepeat": -1, "macroRepeatDelay": 250}
    api.add_macro_action(3, move)
    assert sent("POST", "/api/macro/newValue") == {
        "macroId": 3, "macroType": 20, "macroValue": 0, "macroDelay": 0, "macroText": "",
        "mousePositionX": 10, "mousePositionY": 20, "mousePositionAbsolute": True,
    }
    api.update_macro_action(3, 1, move)
    assert sent("POST", "/api/macro/updateValue") == {
        "macroId": 3, "macroIndex": 1, "pressAndHold": False, "actionRepeatValue": 2, "actionRepeatDelay": 5,
        "mousePositionX": 10, "mousePositionY": 20, "mousePositionAbsolute": True,
    }
    api.delete_macro_action(3, 1)
    assert sent("DELETE", "/api/macro/value") == {"macroId": 3, "macroIndex": 1}


@respx.mock
def test_battery_levels(api):
    respx.get(f"{BASE}/api/batteryStats").respond(json=load_fixture("batteryStats.json"))
    assert api.battery_levels() == {"SE0000000000TEST": 100}


@respx.mock
def test_login_uses_configured_origin():
    client = ApiClient("https://localhost:27003", origin="https://127.0.0.1:27003")
    route = respx.post("https://localhost:27003/auth/login").respond(204)
    client.login("admin", "secret")
    request = route.calls.last.request
    assert request.headers["Origin"] == "https://127.0.0.1:27003"
    assert json.loads(request.content) == {"username": "admin", "password": "secret"}

    respx.post("https://localhost:27003/auth/login").respond(401, text="Invalid credentials")
    with pytest.raises(ApiError, match="Invalid credentials"):
        client.login("admin", "wrong")


OK = {"code": 200, "status": 1, "message": "ok"}


@respx.mock
def test_color_maps_are_sent_as_rgb(api):
    route = respx.post(f"{BASE}/api/mouse/dpiColors").respond(json=OK)
    api.save_dpi_colors("SER", {0: "#ff8000", 5: "#00FF7f"})
    assert json.loads(route.calls.last.request.content) == {
        "deviceId": "SER",
        "colorZones": {"0": {"red": 255, "green": 128, "blue": 0}, "5": {"red": 0, "green": 255, "blue": 127}},
    }
    with pytest.raises(ValueError):
        api.save_zone_colors("SER", {0: "#fff"})


@respx.mock
def test_set_setting_posts_to_the_kind_endpoint(api):
    route = respx.post(f"{BASE}/api/headset/wheelOption").respond(json=OK)
    api.set_setting("SER", "headset/wheelOption", {"wheelOption": 2, "wheelId": 1})
    assert json.loads(route.calls.last.request.content) == {"deviceId": "SER", "wheelOption": 2, "wheelId": 1}


@respx.mock
def test_generic_device_calls(api):
    routes = {path: respx.route(method=method, url=f"{BASE}/api/{path}").respond(json=OK) for method, path in (
        ("POST", "brightness"), ("POST", "headset/equalizer"), ("POST", "speed"), ("POST", "label"),
        ("POST", "headset/zoneColors"), ("POST", "keyboard/updateKeyAssignment"), ("PUT", "keyboard/profile/new"),
        ("POST", "keyboard/profile/change"), ("DELETE", "keyboard/profile/delete"))}
    api.set_brightness_mode("SER", 2)
    api.set_equalizer("SER", {1: 3.5, 2: -1})
    api.set_speed_profile("SER", -1, "Quiet")
    api.set_label("SER", 3, "Pump", rgb_device=True)
    api.save_zone_colors("SER", {0: "#ff0000"}, "headset")
    api.update_key_assignment("SER", 20, use_default=False, action_type=3, action_value=46, modifier=2,
                              kind="keyboard")
    api.new_keyboard_profile("SER", "gaming")
    api.switch_keyboard_profile("SER", "gaming")
    api.delete_keyboard_profile("SER", "gaming")

    def sent(path):
        return json.loads(routes[path].calls.last.request.content)

    assert sent("brightness") == {"deviceId": "SER", "brightness": 2}
    assert sent("headset/equalizer") == {"deviceId": "SER", "equalizers": {"1": 3.5, "2": -1.0}}
    assert sent("speed") == {"deviceId": "SER", "channelId": -1, "profile": "Quiet"}
    assert sent("label") == {"deviceId": "SER", "channelId": 3, "label": "Pump", "deviceType": 1}
    assert sent("headset/zoneColors")["colorZones"] == {"0": {"red": 255, "green": 0, "blue": 0}}
    key = sent("keyboard/updateKeyAssignment")
    assert key["keyIndex"] == 20 and key["keyAssignmentModifier"] == 2 and key["keyAssignmentValue"] == 46
    assert sent("keyboard/profile/new") == {"deviceId": "SER", "keyboardProfileName": "gaming", "new": True}
    assert sent("keyboard/profile/delete") == {"deviceId": "SER", "keyboardProfileName": "gaming"}


@respx.mock
def test_temperature_profiles_accept_status_zero(api):
    respx.get(f"{BASE}/api/temperatures/").respond(json={"code": 200, "status": 0, "data": {"Quiet": {}, "aioPump": {}}})
    assert api.temperature_profiles() == ["aioPump", "Quiet"]


@respx.mock
def test_lighting_calls(api):
    color = respx.post(f"{BASE}/api/color").respond(json=OK)
    brightness = respx.post(f"{BASE}/api/brightness/gradual").respond(json=OK)
    cluster = respx.post(f"{BASE}/api/color/setCluster").respond(json=OK)
    openrgb = respx.post(f"{BASE}/api/color/setOpenRgbIntegration").respond(json=OK)
    api.set_rgb_effect("SER", "static")
    api.set_brightness("SER", 40)
    api.set_rgb_cluster("SER", True)
    api.set_openrgb("SER", False)
    assert json.loads(color.calls.last.request.content) == {"deviceId": "SER", "channelId": 0, "profile": "static"}
    assert json.loads(brightness.calls.last.request.content) == {"deviceId": "SER", "brightness": 40}
    assert json.loads(cluster.calls.last.request.content) == {"deviceId": "SER", "mode": 1}
    assert json.loads(openrgb.calls.last.request.content) == {"deviceId": "SER", "mode": 0}


@respx.mock
def test_rgb_profile_calls(api):
    profile = {"speed": 4, "start": {"red": 255, "green": 0, "blue": 0, "brightness": 1, "temperature": 0},
               "end": {"red": 255, "green": 100, "blue": 0, "brightness": 1, "temperature": 0},
               "gradients": None, "minTemp": 0, "maxTemp": 0, "alternateColors": False, "rgbDirection": 0}
    respx.get(f"{BASE}/api/color/profile/SER/colorshift").respond(json={"status": 1, "data": profile})
    change = respx.put(f"{BASE}/api/color/change").respond(json=OK)
    assert api.rgb_profile("SER", "colorshift") == profile
    api.save_rgb_profile("SER", "colorshift", {**profile, "end": {**profile["end"], "red": 0, "green": 255, "blue": 128}})
    assert json.loads(change.calls.last.request.content) == {
        "deviceId": "SER", "profile": "colorshift",
        "startColor": {"red": 255, "green": 0, "blue": 0, "temperature": 0},
        "middleColor": {"red": 0, "green": 0, "blue": 0, "temperature": 0},
        "endColor": {"red": 0, "green": 255, "blue": 128, "temperature": 0},
        "speed": 4, "alternateColors": False, "rgbDirection": 0, "rgbMinTemp": 0, "rgbMaxTemp": 0,
        "colorZones": None,
    }


@respx.mock
def test_user_profile_calls_use_put_and_delete(api):
    change = respx.post(f"{BASE}/api/userProfile/change").respond(json=OK)
    save = respx.put(f"{BASE}/api/userProfile").respond(json=OK)
    delete = respx.delete(f"{BASE}/api/userProfile/delete").respond(json=OK)
    api.switch_user_profile("SER", "game")
    api.save_user_profile("SER", "game")
    api.delete_user_profile("SER", "game")
    for route in (change, save, delete):
        request = route.calls.last.request
        assert json.loads(request.content) == {"deviceId": "SER", "userProfileName": "game"}
        assert request.headers["Origin"] == BASE


@respx.mock
def test_temperature_form_uses_sensor_api_and_dashboard_hardware(api):
    respx.get(f"{BASE}/api/temperatures/sensors/").respond(
        json={"status": 1, "data": {"10": "PSU", "4": "Temperature Probe", "0": "CPU"}})
    respx.get(f"{BASE}/temperature").respond(text="""
        <select id="sensor"><option value="0">Ignored</option></select>
        <select id="probeData"><option value="0;0">Select probe</option>
        <option value="ABC;0">Inlet &amp; reservoir</option></select>""")
    respx.get(f"{BASE}/api/temperatures/").respond(json={"data": {
        "Quiet": {}, "Normal": {}, "Performance": {}, "Liquid": {}, "aioCriticalTemperature": {},
    }})
    form = api.temperature_form()
    assert form["profiles"] == ["Liquid"]
    assert api.temperature_profiles() == ["Liquid", "Normal", "Performance", "Quiet"]
    assert form["options"]["sensor"] == [{"value": 0, "text": "CPU"}, {"value": 4, "text": "Temperature Probe"},
                                         {"value": 10, "text": "PSU"}]
    assert form["options"]["probeData"] == [{"value": "ABC;0", "text": "Inlet & reservoir"}]


@respx.mock
def test_temperature_profile_editor_requests(api):
    from urllib.parse import parse_qs

    profiles = {"Liquid": {}, "aioCriticalTemperature": {}, "internal": {"Hidden": True}}
    respx.get(f"{BASE}/api/temperatures/").respond(json={"data": profiles})
    assert api.temperature_profiles() == ["Liquid"]

    points = [{"x": 0, "y": 50}, {"x": 60, "y": 100}]
    detail = {"sensor": 2, "points": {"0": points, "1": points}}
    respx.get(f"{BASE}/api/temperatures/Liquid").respond(json={"status": 1, "data": detail})
    assert api.temperature_profile("Liquid") == detail

    graph = respx.put(f"{BASE}/api/temperatures/updateGraph").respond(json=OK)
    api.save_temperature_curve("Liquid", 0.0, points)
    assert type(json.loads(graph.calls.last.request.content)["updateType"]) is int

    table = respx.put(f"{BASE}/api/temperatures/update").respond(json=OK)
    values = {"1": {"pump": 55.0, "fans": 35.0}}
    api.save_temperature_ranges("Liquid", values)
    form = parse_qs(table.calls.last.request.content.decode())
    assert all(type(v) is int for v in json.loads(form["data"][0])["1"].values())
    assert form["profile"] == ["Liquid"] and json.loads(form["data"][0]) == values

    delete = respx.delete(f"{BASE}/api/temperatures/delete").respond(json=OK)
    api.delete_temperature_profile("Liquid")
    assert json.loads(delete.calls.last.request.content) == {"profile": "Liquid"}

@pytest.mark.parametrize("sensor,extra", [(8.0, {"gpuIndex": 0.0}), (4.0, {"channelId": 2.0}),
                                          (9.0, {"channelId": 2.0})])
@respx.mock
def test_temperature_creation_serializes_qml_numbers_as_integers(api, sensor, extra):
    route = respx.post(f"{BASE}/api/temperatures/new").respond(json=OK)
    payload = {"profile": "Test", "sensor": sensor, "static": False, "zeroRpm": True, **extra}
    api.create_temperature_profile(payload)
    sent = json.loads(route.calls.last.request.content)
    for field in ("sensor", *extra):
        assert type(sent[field]) is int

    assert sent["static"] is False and sent["zeroRpm"] is True
    assert type(payload["sensor"]) is float