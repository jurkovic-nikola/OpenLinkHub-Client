"""System tray icon with battery levels and a Show / Check for Updates / Quit menu."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QWindow
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from olhclient.core.listmodel import DictListModel

#: percent at and below which a battery counts as low (the status bar turns red there too)
LOW_BATTERY = 15


def show_window(window: QWindow) -> None:
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
    window.show()
    window.raise_()
    window.requestActivate()


def toggle_window(window: QWindow) -> None:
    # Not isActive(): clicking the tray icon may already have taken focus from the window.
    if window.isVisible() and not window.windowState() & Qt.WindowState.WindowMinimized:
        window.hide()
    else:
        show_window(window)


class TrayIcon(QSystemTrayIcon):
    """Tray icon for the main window. Closing the window hides it to the tray; Quit exits.

    The menu and the tooltip list the battery level of every device that reports one, and
    a notification tells when a battery runs low.
    """

    def __init__(self, app: QApplication, window: QWindow, check_updates: Callable[[], None] | None = None):
        super().__init__(app.windowIcon(), app)
        self.window = window
        self._title = app.applicationName()
        self._battery_actions: list[QAction] = []
        self._levels: list[tuple[str, int]] = []
        self._low: set[str] = set()  # serials already reported as low
        self.setToolTip(self._title)
        # QMenu cannot take a non-widget parent, so the tray keeps the reference.
        self.menu = QMenu()
        self.menu.addAction("Show", lambda: show_window(window))
        if check_updates is not None:
            self.menu.addAction("Check for Updates", lambda: (show_window(window), check_updates()))
        self.menu.addSeparator()
        self.menu.addAction("Quit", app.quit)
        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            toggle_window(self.window)

    def watch(self, devices: DictListModel) -> None:
        """Follow the battery levels of the device list (``battery`` -1: no battery)."""
        def changed(*_: object) -> None:
            self.set_batteries([(d["serial"], d["product"], d["battery"]) for d in devices.items()])

        devices.modelReset.connect(changed)
        devices.dataChanged.connect(changed)
        changed()

    def set_batteries(self, devices: list[tuple[str, str, int]]) -> None:
        """``(serial, name, level)`` per device; devices with a negative level are left out."""
        devices = [(serial, name, level) for serial, name, level in devices if level >= 0]
        levels = [(name, level) for _, name, level in devices]
        if levels != self._levels:
            self._levels = levels
            for action in self._battery_actions:
                self.menu.removeAction(action)
            first = self.menu.actions()[0]
            self._battery_actions = [QAction(f"{name}: {level}%", self.menu, enabled=False) for name, level in levels]
            if levels:
                self._battery_actions.append(QAction(self.menu, separator=True))
            self.menu.insertActions(first, self._battery_actions)
            self.setToolTip("\n".join([self._title, *(f"{name}: {level}%" for name, level in levels)]))

        for serial, name, level in devices:
            if level > LOW_BATTERY:
                self._low.discard(serial)
            elif serial not in self._low:
                self._low.add(serial)
                self.showMessage("Battery low", f"{name} is at {level}%",
                                 QSystemTrayIcon.MessageIcon.Warning, 10000)


def create_tray(app: QApplication, window: QWindow, check_updates: Callable[[], None] | None = None,
                devices: DictListModel | None = None) -> TrayIcon | None:
    """Show a tray icon and keep running when the window is closed; None without a system tray."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    tray = TrayIcon(app, window, check_updates)
    if devices is not None:
        tray.watch(devices)
    tray.show()
    app.setQuitOnLastWindowClosed(False)
    return tray
