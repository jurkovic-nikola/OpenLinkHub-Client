"""Slipstream USB receiver: page parsing, API, model, session and backend."""

import httpx
import pytest
import respx

from olhclient.api.client import ApiClient, ApiError
from olhclient.api.models import DeviceInfo, ReceiverState
from olhclient.api.receiver_page import parse_receiver_page
from olhclient.core.backend import Backend
from olhclient.core.receiver import ReceiverSession
from olhclient.core.worker import Worker

from tests.conftest import FIXTURES, LEGACY, RECEIVER, SE

BASE = "http://127.0.0.1:27003"
PAGE = (FIXTURES / "slipstream_page.html").read_text()


# -- page parsing ------------------------------------------------------------


def test_parse_receiver_page():
    data = parse_receiver_page(PAGE)
    assert data["serial"] == RECEIVER
    assert data["product"] == "CORSAIR SLIPSTREAM WIRELESS USB Receiver"
    assert data["firmware"] == "5.12.54"  # not the sidebar's build info
    assert data["PollingRates"]["4"] == "1000 Hz / 1 msec" and len(data["PollingRates"]) == 5
    assert data["DeviceProfile"] == {"PollingRate": 4}
    assert data["PairedDevices"] == {"11042": {"product": "SCIMITAR ELITE SE", "serial": SE}}


def test_parse_receiver_page_without_polling_rates():
    # Receivers without a PollingRates map break off the template at the select.
    html = PAGE.split("<select")[0]
    data = parse_receiver_page(html)
    assert data["PollingRates"] == {} and data["firmware"] == "5.12.54"


def test_parse_other_page_fails():
    with pytest.raises(ValueError):
        parse_receiver_page("<html><body><main><h1>404</h1></main></body></html>")


# -- API -----------------------------------------------------------------------


@pytest.fixture
def api():
    client = ApiClient(BASE)
    yield client
    client.close()


def test_backend_only_lists_hidden_slipstreams_as_receivers(qtbot, registry, receiver_device, se_device):
    from tests.conftest import FakeApi

    api = FakeApi([se_device], [receiver_device])
    listed = api.list_devices
    # a headset dongle is hidden too, but it is not a Slipstream receiver
    api.list_devices = lambda: {**listed(), "HS": DeviceInfo.from_json("HS", {"Product": "HEADSET DONGLE", "Hidden": True})}
    backend = Backend(api, registry, worker=Worker(synchronous=True))
    backend.refresh()
    assert [t["serial"] for t in backend.devices.items()] == [SE, RECEIVER]


@respx.mock
def test_get_receiver_falls_back_to_dashboard_page(api):
    # OpenLinkHub fails to encode the receiver and sends an empty body.
    respx.get(f"{BASE}/api/devices/{RECEIVER}").respond(200, content=b"")
    page = respx.get(f"{BASE}/device/{RECEIVER}").respond(200, html=PAGE)
    assert api.get_receiver(RECEIVER)["DeviceProfile"] == {"PollingRate": 4}
    assert page.calls.last.request.headers["Accept"] == "text/html"


@respx.mock
def test_get_receiver_prefers_json(api):
    device = {"serial": RECEIVER, "product": "SLIPSTREAM", "PollingRates": {"1": "125 Hz / 8 msec"}}
    respx.get(f"{BASE}/api/devices/{RECEIVER}").respond(json={"code": 200, "device": device})
    page = respx.get(f"{BASE}/device/{RECEIVER}")
    assert api.get_receiver(RECEIVER) == device
    assert not page.called


@respx.mock
def test_get_receiver_errors(api):
    respx.get(f"{BASE}/api/devices/GONE").respond(json={"code": 200})
    respx.get(f"{BASE}/device/GONE").respond(200, html="<html><main>404</main></html>")
    with pytest.raises(ApiError, match="not found"):
        api.get_receiver("GONE")

    respx.get(f"{BASE}/api/devices/{RECEIVER}").respond(401)
    with pytest.raises(ApiError) as exc:
        api.get_receiver(RECEIVER)
    assert exc.value.auth_required


@respx.mock
def test_receiver_polling_rate_uses_mouse_endpoint(api):
    route = respx.post(f"{BASE}/api/mouse/pollingRate").respond(json={"status": 1})
    api.set_setting(RECEIVER, "mouse/pollingRate", {"pollingRate": 3})
    assert route.calls.last.request.read() == httpx.Request(
        "POST", "/", json={"deviceId": RECEIVER, "pollingRate": 3}
    ).read()


# -- model -----------------------------------------------------------------------


def test_receiver_state(receiver_device):
    state = ReceiverState.from_json(receiver_device)
    assert state.serial == RECEIVER and state.firmware == "5.12.54"
    assert state.polling_rate == 4
    assert list(state.polling_rates) == [1, 2, 3, 4]  # "Not Set" (0) is left out
    assert [(d.product_id, d.serial) for d in state.paired] == [(11042, SE)]


# -- session -----------------------------------------------------------------------


@pytest.fixture
def receiver(qtbot, fake_api):
    session = ReceiverSession(fake_api, Worker(synchronous=True),
                              ReceiverState.from_json(fake_api.get_receiver(RECEIVER)))
    session.messages = []
    session.message.connect(lambda text, error: session.messages.append((text, error)))
    return session


def test_receiver_session_properties(receiver):
    assert receiver.product == "CORSAIR SLIPSTREAM WIRELESS USB Receiver"
    assert receiver.pollingRate == 4
    assert receiver.pollingRates[0] == {"value": 1, "text": "125 Hz / 8 msec"}
    assert receiver.pairedDevices == [{"productId": 11042, "product": "SCIMITAR ELITE SE", "serial": SE}]


def test_set_polling_rate_applies_without_waiting(receiver, fake_api):
    receiver.setPollingRate(3)
    assert fake_api.calls[-1] == ("set_setting", RECEIVER, "mouse/pollingRate", {"pollingRate": 3})
    assert receiver.messages[-1] == ("Polling rate 500 Hz / 2 msec sent to the receiver", False)
    assert receiver.pollingRate == 3 and not receiver.busy and receiver.may_be_restarting
    # nothing is locked: the next change goes straight out
    receiver.setPollingRate(2)
    assert fake_api.calls[-1] == ("set_setting", RECEIVER, "mouse/pollingRate", {"pollingRate": 2})


def test_restart_grace_ends(receiver, monkeypatch):
    import olhclient.core.receiver as module

    receiver.setPollingRate(3)
    now = module.time.monotonic()
    monkeypatch.setattr(module.time, "monotonic", lambda: now + module.RESTART_GRACE_S + 1)
    assert not receiver.may_be_restarting


@pytest.mark.parametrize("value", [4, 0, 9])
def test_set_polling_rate_skips_current_and_invalid(receiver, fake_api, value):
    receiver.setPollingRate(value)
    assert not fake_api.calls
    assert not receiver.may_be_restarting


def test_set_polling_rate_failure(receiver, fake_api):
    fake_api.receivers[RECEIVER]["DeviceProfile"]["PollingRate"] = 4
    original = fake_api.set_setting

    def reject(*args):
        raise ApiError("Unable to change polling rate")

    fake_api.set_setting = reject
    receiver.setPollingRate(1)
    fake_api.set_setting = original
    assert receiver.messages[-1] == ("Unable to change polling rate", True)
    assert not receiver.may_be_restarting and not receiver.busy and receiver.pollingRate == 4


# -- backend -------------------------------------------------------------------------


@pytest.fixture
def backend(qtbot, fake_api, registry):
    return Backend(fake_api, registry, worker=Worker(synchronous=True))


def test_backend_lists_receiver_after_mice(backend):
    backend.refresh()
    tiles = backend.devices.items()
    assert [t["serial"] for t in tiles] == [SE, LEGACY, RECEIVER]
    assert tiles[2]["product"] == "SLIPSTREAM RECEIVER" and tiles[2]["thumbnail"].endswith("slipstream.svg")


def test_backend_select_receiver_and_back(backend):
    backend.refresh()
    backend.selectDevice(RECEIVER)
    assert backend.session is None and backend.receiver.serial == RECEIVER
    assert backend.selectedSerial == RECEIVER
    backend.refresh()  # a new mouse must not take over the selection
    assert backend.receiver is not None
    backend.selectDevice(SE)
    assert backend.receiver is None and backend.selectedSerial == SE


def test_backend_keeps_restarting_receiver(backend, fake_api):
    backend.refresh()
    backend.selectDevice(RECEIVER)
    backend.receiver.setPollingRate(2)
    data = fake_api.receivers.pop(RECEIVER)
    mouse = fake_api.devices.pop(SE)
    backend.refresh()  # receiver and its mouse are gone while it restarts
    assert backend.receiver is not None and backend.receiver.may_be_restarting

    fake_api.receivers[RECEIVER] = data
    fake_api.devices[SE] = mouse
    backend.refresh()
    assert backend.receiver is not None and backend.selectedSerial == RECEIVER


def test_backend_receiver_removed(backend, fake_api):
    backend.refresh()
    backend.selectDevice(RECEIVER)
    del fake_api.receivers[RECEIVER]
    backend.refresh()
    assert backend.receiver is None and backend.session.serial == SE


def test_backend_only_receiver(qtbot, registry, receiver_device):
    from tests.conftest import FakeApi

    backend = Backend(FakeApi([], [receiver_device]), registry, worker=Worker(synchronous=True))
    backend.refresh()
    assert backend.receiver is not None and backend.receiver.serial == RECEIVER


def test_backend_battery_failure_is_ignored(backend, fake_api, monkeypatch):
    def fail():
        raise ApiError("boom")

    monkeypatch.setattr(fake_api, "battery_levels", fail)
    backend.refresh()
    assert backend.connected and backend.devices.count == 3
