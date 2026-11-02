"""Load the real QML against a fake API and fail on any QML warning."""

import pytest

from olhclient.api.client import ApiError
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from olhclient.core.backend import Backend
from olhclient.core.session import QML_DIR
from olhclient.core.worker import Worker
from olhclient.devices.registry import Registry

QQuickStyle.setStyle("Basic")  # must happen before any Controls QML loads


@pytest.fixture
def ui(qtbot, fake_api):
    backend = Backend(fake_api, Registry.discover(), worker=Worker(synchronous=True))
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    yield backend, window, warnings
    window.close()
    engine.deleteLater()


def settle(qtbot):
    qtbot.wait(50)


def test_main_window_loads_without_warnings(ui, qtbot):
    backend, window, warnings = ui
    backend.refresh()
    settle(qtbot)
    assert backend.session is not None
    assert warnings == []


def test_switch_features_and_devices(ui, qtbot):
    backend, window, warnings = ui
    backend.refresh()
    settle(qtbot)
    window.setProperty("featureId", "dpi")
    settle(qtbot)
    backend.selectDevice("SE0000000000TEST")
    settle(qtbot)
    backend.session.selectedButton = "Middle Button"  # lives on the top view
    window.setProperty("featureId", "key_remap")
    settle(qtbot)
    assert warnings == []


def test_disconnected_state(ui, qtbot, fake_api):
    from olhclient.api.client import ApiError

    backend, window, warnings = ui
    fake_api.fail_with = ApiError("Cannot reach OpenLinkHub")
    backend.refresh()
    settle(qtbot)
    assert not backend.connected
    assert warnings == []


def test_every_feature_panel_on_every_device(ui, qtbot, fake_api):
    backend, window, warnings = ui
    backend.refresh()
    settle(qtbot)
    for serial in ("RGBELITE00TEST", "SE0000000000TEST"):
        backend.selectDevice(serial)
        settle(qtbot)
        for feature in backend.session.features:
            window.setProperty("featureId", feature["id"])
            settle(qtbot)
    # writes (and a failing one) while the lighting and settings editors are shown
    session = backend.session
    window.setProperty("featureId", "lighting")
    settle(qtbot)
    session.controller("lighting").setEffect("static")
    fake_api.fail_with = ApiError("Unable to change")
    session.controller("lighting").setOpenRgb(True)
    fake_api.fail_with = None
    window.setProperty("featureId", "settings")
    settle(qtbot)
    session.controller("settings").apply("angleSnapping", 1)
    session.switchProfile("dbts")
    settle(qtbot)
    assert warnings == []


def test_receiver_page(ui, qtbot, fake_api):
    backend, window, warnings = ui
    backend.refresh()
    settle(qtbot)
    backend.selectDevice("SLIPSTREAM0TEST")
    settle(qtbot)
    assert backend.receiver is not None
    assert window.property("title").startswith("CORSAIR SLIPSTREAM WIRELESS USB Receiver")
    backend.receiver.setPollingRate(3)
    settle(qtbot)
    fake_api.fail_with = ApiError("Unable to change polling rate")
    backend.receiver.setPollingRate(1)
    fake_api.fail_with = None
    settle(qtbot)
    backend.selectDevice("SE0000000000TEST")  # back to a mouse
    settle(qtbot)
    assert backend.session is not None
    assert warnings == []


@pytest.fixture
def every_ui(qtbot, every_api):
    backend = Backend(every_api, Registry.discover(), worker=Worker(synchronous=True))
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.setInitialProperties({"backend": backend})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    yield backend, window, warnings
    window.close()
    engine.deleteLater()


def test_every_feature_on_every_device_kind(every_ui, qtbot, every_api):
    from tests.conftest import COMMANDER, HEADSET, KEYBOARD

    backend, window, warnings = every_ui
    every_api.unreadable["BROKEN0TEST"] = "HS80 RGB WIRELESS"
    backend.refresh()
    settle(qtbot)
    for row in range(backend.devices.count):
        backend.selectDevice(backend.devices.get(row)["serial"])
        settle(qtbot)
        for feature in backend.session.features if backend.session else []:
            window.setProperty("featureId", feature["id"])
            settle(qtbot)
    # writes while the new editors are shown
    backend.selectDevice(HEADSET)
    window.setProperty("featureId", "settings")
    settle(qtbot)
    backend.session.controller("settings").apply("sideTone", 1)
    window.setProperty("featureId", "equalizer")
    settle(qtbot)
    backend.selectDevice(COMMANDER)
    window.setProperty("featureId", "fans")
    settle(qtbot)
    backend.session.controller("fans").setSpeedProfile(-1, "Quiet")
    backend.selectDevice(KEYBOARD)
    window.setProperty("featureId", "keyboard_keys")
    settle(qtbot)
    backend.session.controller("keyboard_keys").switchKeyboardProfile("gaming")
    settle(qtbot)
    assert warnings == []


def test_update_dialog(qtbot, fake_api, monkeypatch):
    from olhclient.core.updater import Updater

    backend = Backend(fake_api, Registry.discover(), worker=Worker(synchronous=True))
    updater = Updater(Worker(synchronous=True))
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.setInitialProperties({"backend": backend, "updater": updater})
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    monkeypatch.setenv("FLATPAK_ID", "test")
    updater._release = {"tag_name": "v99.0.0", "html_url": "https://example.invalid", "assets": []}
    updater.open()
    for state in ("checking", "upToDate", "available", "downloading", "installing", "installed", "error"):
        updater._set_state(state, "message")
        updater._set_progress(5, 10)
        settle(qtbot)
    updater.close()
    settle(qtbot)
    window.close()
    engine.deleteLater()
    assert warnings == []
