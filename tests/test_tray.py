from PySide6.QtGui import QWindow

from olhclient.core.listmodel import DictListModel
from olhclient.tray import TrayIcon, show_window, toggle_window


def test_menu_has_show_and_quit(qapp):
    window = QWindow()
    tray = TrayIcon(qapp, window)
    assert [a.text() for a in tray.menu.actions() if not a.isSeparator()] == ["Show", "Quit"]


def test_menu_checks_for_updates(qapp):
    window = QWindow()
    checks = []
    tray = TrayIcon(qapp, window, lambda: checks.append(True))
    actions = [a for a in tray.menu.actions() if not a.isSeparator()]
    assert [a.text() for a in actions] == ["Show", "Check for Updates", "Quit"]
    actions[1].trigger()
    assert checks == [True]
    assert window.isVisible()
    window.close()


def test_show_restores_hidden_window(qapp):
    window = QWindow()
    window.hide()
    show_window(window)
    assert window.isVisible()
    window.close()


def test_toggle_hides_and_shows(qapp):
    window = QWindow()
    window.show()
    toggle_window(window)
    assert not window.isVisible()
    toggle_window(window)
    assert window.isVisible()
    window.close()


def test_battery_levels_in_menu_and_tooltip(qapp):
    tray = TrayIcon(qapp, QWindow())
    tray.set_batteries([("SE", "SCIMITAR ELITE SE", 80), ("RX", "SLIPSTREAM", -1), ("HS", "VIRTUOSO MAX", 40)])
    texts = [a.text() for a in tray.menu.actions() if not a.isSeparator()]
    assert texts == ["SCIMITAR ELITE SE: 80%", "VIRTUOSO MAX: 40%", "Show", "Quit"]
    assert not tray.menu.actions()[0].isEnabled()
    assert tray.toolTip().splitlines()[1:] == ["SCIMITAR ELITE SE: 80%", "VIRTUOSO MAX: 40%"]
    tray.set_batteries([("SE", "SCIMITAR ELITE SE", 79)])
    assert [a.text() for a in tray.menu.actions() if not a.isSeparator()] == ["SCIMITAR ELITE SE: 79%", "Show", "Quit"]
    tray.set_batteries([])
    assert [a.text() for a in tray.menu.actions() if not a.isSeparator()] == ["Show", "Quit"]
    assert len(tray.menu.actions()) == 3  # Show, separator, Quit


def test_low_battery_is_notified_once(qapp, monkeypatch):
    tray = TrayIcon(qapp, QWindow())
    shown = []
    monkeypatch.setattr(tray, "showMessage", lambda title, text, *args: shown.append(text))
    for level in (20, 15, 14, 10, 30, 12):
        tray.set_batteries([("SE", "SCIMITAR ELITE SE", level)])
    assert shown == ["SCIMITAR ELITE SE is at 15%", "SCIMITAR ELITE SE is at 12%"]


def test_watch_follows_the_device_list(qapp):
    tray = TrayIcon(qapp, QWindow())
    devices = DictListModel(("serial", "product", "battery"))
    tray.watch(devices)
    devices.set_items([{"serial": "SE", "product": "SCIMITAR ELITE SE", "battery": 90}])
    assert tray.menu.actions()[0].text() == "SCIMITAR ELITE SE: 90%"
    devices.set_items([{"serial": "SE", "product": "SCIMITAR ELITE SE", "battery": 85}])
    assert tray.menu.actions()[0].text() == "SCIMITAR ELITE SE: 85%"
