"""Load the real QML against a fake API and fail on any QML warning."""

import pytest
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
