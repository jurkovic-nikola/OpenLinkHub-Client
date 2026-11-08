"""Exercise cluster controls through the same status-zero reply as the daemon."""

import json

import httpx
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from olhclient.api.client import ApiClient
from tests.test_qml_smoke import settle, ui


def test_cluster_page(ui, qtbot, monkeypatch):
    backend, window, warnings = ui
    backend.refresh()
    cluster = backend.cluster
    members = [{"Product": "Memory", "Serial": serial} for serial in ("i2c15-3", "i2c15-1")]
    profile = {"RGBProfile": "nebula", "BrightnessSlider": 100}
    rain = {"speed": 4, "start": {"red": 255, "green": 0, "blue": 0}, "end": {"red": 0, "green": 0, "blue": 255}}
    writes = []

    def handle(request):
        if request.method == "GET" and request.url.path == "/api/color/profile/cluster/rain":
            return httpx.Response(200, json={"status": 1, "data": rain})
        if request.method == "GET" and request.url.path.startswith("/api/color/profile/cluster/"):
            return httpx.Response(200, json={"status": 1, "data": {"speed": 2}})
        if request.method == "GET":
            assert request.url.path == "/api/devices/cluster"
            return httpx.Response(200, json={"status": 0, "device": {"DeviceProfile": profile,
                                  "RGBModes": ["nebula", "rain"], "Controllers": members}})
        data = json.loads(request.content)
        writes.append((request.url.path, data))
        if request.url.path == "/api/color":
            profile["RGBProfile"] = data["profile"]
        elif request.url.path == "/api/color/change":
            rain.update(speed=data["speed"], start=data["startColor"], end=data["endColor"])
        else:
            profile["BrightnessSlider"] = data["brightness"]
        return httpx.Response(200, json={"status": 1})

    api = ApiClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr(cluster, "api", api)
    window.setProperty("page", "cluster")
    settle(qtbot)
    assert window.property("title") == "RGB Cluster — OpenLinkHub"
    assert cluster.data["members"] == members
    slider = window.findChild(type(window.contentItem()), "clusterBrightness")
    point = slider.mapToScene(QPointF(slider.width() / 2, slider.height() / 2))
    QTest.mouseClick(window, Qt.LeftButton, pos=point.toPoint())
    cluster.setEffect("rain")
    settle(qtbot)
    effect = cluster.effectProfile
    assert effect.available and effect.colorNames == ["Start", "End"]
    effect.save({**effect.values, "colors": ["#00ff00", "#0000ff"], "speed": 3})
    settle(qtbot)
    assert writes[:2] == [
        ("/api/brightness/gradual", {"deviceId": "cluster", "brightness": 50}),
        ("/api/color", {"deviceId": "cluster", "channelId": 0, "profile": "rain"}),
    ]
    (path, saved), = writes[2:]
    assert (path, saved["profile"], saved["speed"], saved["startColor"]["green"]) == ("/api/color/change", "rain", 3, 255)
    assert cluster.data["effect"] == "rain"
    assert effect.values["colors"] == ["#00ff00", "#0000ff"] and effect.values["speed"] == 3
    assert warnings == []
    api.close()
