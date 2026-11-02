"""System tray icon with a Show / Quit menu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


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
    """Tray icon for the main window. Closing the window hides it to the tray; Quit exits."""

    def __init__(self, app: QApplication, window: QWindow):
        super().__init__(app.windowIcon(), app)
        self.window = window
        self.setToolTip(app.applicationName())
        # QMenu cannot take a non-widget parent, so the tray keeps the reference.
        self.menu = QMenu()
        self.menu.addAction("Show", lambda: show_window(window))
        self.menu.addSeparator()
        self.menu.addAction("Quit", app.quit)
        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            toggle_window(self.window)


def create_tray(app: QApplication, window: QWindow) -> TrayIcon | None:
    """Show a tray icon and keep running when the window is closed; None without a system tray."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    tray = TrayIcon(app, window)
    tray.show()
    app.setQuitOnLastWindowClosed(False)
    return tray
