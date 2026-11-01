import pytest

from olhclient.api.client import ApiError
from olhclient.core.backend import Backend
from olhclient.core.worker import Worker

from tests.conftest import LEGACY, SE


# -- session ---------------------------------------------------------------


def test_session_selects_first_unlocked_button(make_session):
    session = make_session()
    assert session.selectedButton == "Right Button"
    assert session.isLocked("Left Button") and session.isLocked("Profile Switch")


def test_session_views_and_callouts(make_session):
    session = make_session()
    assert [v["id"] for v in session.views] == ["side", "top"]
    side = session.views[0]
    assert len(side["hotspots"]) == 12 and side["image"].startswith("file://")
    assert [cell["label"] for cell in session.keypad[0]] == ["G3", "G6", "G9", "G12"]
    assert [b["button"] for b in session.buttonList][0] == "Left Button"
    assert session.connectionMode == "Wireless" and session.battery == 100


def test_describe_action(make_session):
    session = make_session()
    key = session.state.key_by_name("Side Button 1")
    assert session.describe_action(key) == "Keyboard: Letter T" or session.describe_action(key).startswith("Keyboard: ")
    default_key = session.state.key_by_name("Right Button")
    assert session.describe_action(default_key) == "Default"


# -- key remapping -----------------------------------------------------------


def test_key_list_order_and_labels(make_session):
    keys = make_session().controller("key_remap").keys.items()
    assert [k["name"] for k in keys[:5]] == ["Left Button", "Right Button", "Middle Button", "Profile Switch", "DPI Button"]
    assert [k["label"] for k in keys[5:8]] == ["G1", "G2", "G3"]
    assert keys[0]["locked"]


def test_save_key_assignment(make_session, fake_api):
    session = make_session()
    remap = session.controller("key_remap")
    session.selectedButton = "Side Button 2"
    index = remap.selected["keyIndex"]
    remap.save(index, False, 3, 10, False, False)
    assert fake_api.calls[-1] == (
        "update_key_assignment", SE, index,
        {"use_default": False, "action_type": 3, "action_value": 10, "press_and_hold": False, "on_release": False},
    )
    # reloaded from the "server"
    assert remap.selected["actionValue"] == 10
    assert session.messages[-1] == ("Key assignment saved", False)


def test_save_rejects_invalid_combination_without_calling_api(make_session, fake_api):
    session = make_session()
    remap = session.controller("key_remap")
    remap.save(remap.selected["keyIndex"], False, 8, 0, False, False)  # sniper without hold
    assert not [c for c in fake_api.calls if c[0] == "update_key_assignment"]
    assert session.messages[-1][1] is True


def test_save_rejects_locked_button(make_session, fake_api):
    session = make_session()
    remap = session.controller("key_remap")
    left = session.state.key_by_name("Left Button").index
    remap.save(left, False, 3, 10, False, False)
    assert not [c for c in fake_api.calls if c[0] == "update_key_assignment"]


def test_save_failure_is_reported(make_session, fake_api):
    session = make_session()
    remap = session.controller("key_remap")
    fake_api.fail_with = ApiError("Unable to apply key assignment")
    remap.save(remap.selected["keyIndex"], False, 3, 10, False, False)
    assert session.messages[-1] == ("Unable to apply key assignment", True)
    assert not remap.saving


def test_value_options(make_session, qtbot):
    remap = make_session().controller("key_remap")
    assert remap.valueOptions(0) == [{"value": 0, "text": "None"}]
    loaded = []
    remap.optionsLoaded.connect(loaded.append)
    options = remap.valueOptions(3)  # synchronous worker: loads immediately
    assert loaded == [3]
    assert remap.valueOptions(3)[0]["text"] == "Letter T"
    assert options == [] or options == remap.valueOptions(3)


def test_legacy_generation_uses_its_own_bitmasks(make_session, fake_api):
    session = make_session(LEGACY)
    remap = session.controller("key_remap")
    session.selectedButton = "Side Button 1"
    remap.save(remap.selected["keyIndex"], False, 3, 10, False, False)
    assert fake_api.calls[-1][2] == 256


# -- DPI -------------------------------------------------------------------


def test_dpi_save_sends_only_changes(make_session, fake_api):
    session = make_session()
    dpi = session.controller("dpi")
    values = [s["value"] for s in dpi.stages.items()]
    values[1] = 2000
    dpi.save(values)
    assert fake_api.calls[-1] == ("save_dpi", SE, {1: 2000})
    assert dpi.stages.get(1)["value"] == 2000


def test_dpi_no_changes_skips_request(make_session, fake_api):
    session = make_session()
    dpi = session.controller("dpi")
    dpi.save([s["value"] for s in dpi.stages.items()])
    assert not [c for c in fake_api.calls if c[0] == "save_dpi"]


def test_dpi_out_of_range(make_session, fake_api):
    session = make_session()
    dpi = session.controller("dpi")
    values = [s["value"] for s in dpi.stages.items()]
    values[0] = 50
    dpi.save(values)
    assert not [c for c in fake_api.calls if c[0] == "save_dpi"]
    assert session.messages[-1][1] is True


def test_dpi_range_and_active_stage(make_session):
    dpi = make_session().controller("dpi")
    assert (dpi.minDpi, dpi.maxDpi, dpi.step) == (100, 33000, 50)
    assert [s["active"] for s in dpi.stages.items()].index(True) == 2


# -- backend -----------------------------------------------------------------


@pytest.fixture
def backend(qtbot, fake_api, registry):
    return Backend(fake_api, registry, worker=Worker(synchronous=True))


def test_backend_poll_opens_first_device(backend):
    backend.refresh()
    assert backend.connected
    assert backend.devices.count == 3  # two mice, then the receiver
    assert backend.session is not None and backend.session.serial == LEGACY  # sorted by serial


def test_backend_select_device(backend):
    backend.refresh()
    backend.selectDevice(SE)
    assert backend.session.serial == SE


def test_backend_device_removed(backend, fake_api):
    backend.refresh()
    del fake_api.devices[LEGACY]
    backend.refresh()
    assert backend.devices.count == 2
    assert backend.session.serial == SE


def test_backend_connection_error_and_auth(backend, fake_api):
    fake_api.fail_with = ApiError("Cannot reach OpenLinkHub")
    backend.refresh()
    assert not backend.connected and backend.status == "Cannot reach OpenLinkHub"

    fake_api.fail_with = ApiError("Authentication required", http_status=401, auth_required=True)
    backend.refresh()
    assert backend.authRequired
    backend.login("admin", "pw")
    assert not backend.authRequired and backend.connected


def test_worker_drops_callbacks_of_deleted_owner(qtbot):
    import shiboken6
    from PySide6.QtCore import QObject

    worker = Worker()
    owner = QObject()
    results = []
    worker.submit(lambda: 42, on_done=results.append, owner=owner)
    shiboken6.delete(owner)
    worker.wait()
    qtbot.wait(20)
    assert results == [] and not worker.busy

    worker.submit(lambda: 7, on_done=results.append)
    qtbot.waitUntil(lambda: results == [7])
