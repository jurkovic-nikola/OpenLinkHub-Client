from PySide6.QtGui import QWindow

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
