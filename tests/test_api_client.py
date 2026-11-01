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
def test_list_mice(api):
    respx.get(f"{BASE}/api/devices/mouse").respond(json=load_fixture("devices_mouse.json"))
    assert api.list_mice() == {"SE0000000000TEST": "SCIMITAR ELITE SE"}


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
    route = respx.get(f"{BASE}/api/devices/mouse").respond(json={"code": 200, "status": 1, "data": {}})
    api.list_mice()
    assert "Origin" not in route.calls.last.request.headers


@respx.mock
def test_auth_required(api):
    respx.get(f"{BASE}/api/devices/mouse").respond(401, text="Authentication required")
    with pytest.raises(ApiError) as info:
        api.list_mice()
    assert info.value.auth_required


@respx.mock
def test_connection_error(api):
    respx.get(f"{BASE}/api/devices/mouse").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ApiError, match="Cannot reach"):
        api.list_mice()


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
@pytest.mark.parametrize(
    "setting, path",
    [("pollingRate", "pollingRate"), ("liftHeight", "liftHeight"), ("sleepMode", "sleep"),
     ("angleSnapping", "angleSnapping"), ("buttonOptimization", "buttonOptimization")],
)
def test_mouse_settings_endpoints(api, setting, path):
    route = respx.post(f"{BASE}/api/mouse/{path}").respond(json=OK)
    api.set_mouse_setting("SER", setting, 3)
    assert json.loads(route.calls.last.request.content) == {"deviceId": "SER", setting: 3}


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
