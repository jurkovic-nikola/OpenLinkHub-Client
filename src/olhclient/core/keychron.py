"""A Keychron keyboard shown in the UI, talked to over raw HID instead of OpenLinkHub.

:class:`KeychronSession` offers the QML API of :class:`DeviceSession`, so the
main window, the keyboard view and the library panel treat it like any other
device; its features have their own controllers (``core/features/keychron.py``).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from olhclient.api.models import DeviceKind
from olhclient.core.features.base import FeatureController
from olhclient.core.features.keychron import KeychronKeysController, KeychronLightingController, KeychronSettingsController
from olhclient.core.session import QML_DIR, file_url, kind_icon
from olhclient.core.worker import Worker
from olhclient.keychron.device import KeyboardState, read_settings
from olhclient.keychron.protocol import KeychronClient

#: feature id -> (title, controller, list QML, editor QML), in display order
FEATURES = {
    "keyboard_keys": ("Keyboard keys", KeychronKeysController, "features/KeychronKeysList.qml",
                      "features/KeychronKeyEditor.qml"),
    "lighting": ("Lighting", KeychronLightingController, "features/LightingList.qml",
                 "features/KeychronLightingEditor.qml"),
    "settings": ("Device settings", KeychronSettingsController, "features/SettingsList.qml",
                 "features/SettingsEditor.qml"),
}


def error_text(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc)


class KeychronSession(QObject):
    stateChanged = Signal()
    selectedButtonChanged = Signal()
    profileBusyChanged = Signal()
    #: text, is_error
    message = Signal(str, bool)

    def __init__(self, client: KeychronClient, worker: Worker, state: KeyboardState, parent: QObject | None = None):
        super().__init__(parent)
        self.client = client
        self.worker = worker
        self.state = state
        self._selected = ""
        self._connected = True  # a keyboard behind a receiver stops answering when it sleeps
        self._reloading = False
        self._reload_again = False
        self._controllers: dict[str, FeatureController] = {}
        for feature_id, (_, controller, _, _) in FEATURES.items():
            if controller.supports(state):
                self._controllers[feature_id] = controller(self)
        self._apply(state)

    @property
    def serial(self) -> str:
        return self.state.serial

    # -- state -------------------------------------------------------------

    def reload(self) -> None:
        """Read the settings again: Fn shortcuts and the OS switch change them on the keyboard.

        The keymap only changes through the client, which updates it after each write.
        """
        if self._reloading:
            self._reload_again = True
            return
        self._reloading = True
        self.worker.submit(read_settings, self.client, on_done=self._reloaded, on_error=self._reload_failed,
                           owner=self)

    def _reloaded(self, settings: Any) -> None:
        self._reloading = False
        if settings != self.state.settings or not self._connected:
            self._connected = True
            self._apply(replace(self.state, settings=settings))
        self._maybe_reload_again()

    def _reload_failed(self, exc: Exception) -> None:
        self._reloading = False
        if self._connected:  # once, not on every poll while the keyboard sleeps
            self._connected = False
            self.report_error(exc)
            self.stateChanged.emit()
        self._maybe_reload_again()

    def _maybe_reload_again(self) -> None:
        if self._reload_again:
            self._reload_again = False
            self.reload()

    def apply(self, state: KeyboardState) -> None:
        """Show ``state``, e.g. after a write changed one key."""
        self._apply(state)

    def _apply(self, state: KeyboardState) -> None:
        self.state = state
        for controller in self._controllers.values():
            controller.update(state)
        self.stateChanged.emit()

    # -- messages ----------------------------------------------------------

    def report_message(self, text: str, *, error: bool = False) -> None:
        self.message.emit(text, error)

    def report_error(self, exc: Exception) -> None:
        self.message.emit(error_text(exc), True)

    # -- QML API (that of DeviceSession) -------------------------------------

    @Property(str, notify=stateChanged)
    def serialNumber(self) -> str:
        return self.state.serial

    @Property(str, notify=stateChanged)
    def product(self) -> str:
        return self.state.board.title

    @Property(str, constant=True)
    def moduleId(self) -> str:
        return "keychron"

    @Property(str, constant=True)
    def kind(self) -> str:
        return DeviceKind.KEYBOARD.value

    @Property(str, constant=True)
    def kindTitle(self) -> str:
        return DeviceKind.KEYBOARD.title

    @Property(str, notify=stateChanged)
    def firmware(self) -> str:
        return self.state.firmware.split(" ", 1)[0]  # the rest is the build date

    @Property(bool, constant=True)
    def hasArtwork(self) -> bool:
        return False

    @Property(bool, constant=True)
    def hasKeyboardLayout(self) -> bool:
        return "keyboard_keys" in self._controllers

    @Property(bool, constant=True)
    def hasWebPage(self) -> bool:
        """OpenLinkHub does not know this keyboard."""
        return False

    @Slot()
    def openInBrowser(self) -> None:
        pass

    @Property(str, constant=True)
    def profileName(self) -> str:
        return ""

    @Property("QStringList", constant=True)
    def profiles(self) -> list[str]:
        return []

    @Property(bool, notify=stateChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(int, constant=True)
    def battery(self) -> int:
        return -1

    @Property(str, constant=True)
    def connectionMode(self) -> str:
        return "Wireless" if self.state.receiver else "Wired"

    @Property(str, constant=True)
    def thumbnail(self) -> str:
        return file_url(kind_icon(DeviceKind.KEYBOARD))

    @Property("QVariantList", constant=True)
    def views(self) -> list[dict[str, Any]]:
        return []

    @Property("QVariantList", constant=True)
    def buttonList(self) -> list[dict[str, Any]]:
        return []

    @Property("QVariantList", constant=True)
    def features(self) -> list[dict[str, Any]]:
        return [
            {"id": feature_id, "title": title, "listQml": file_url(QML_DIR / list_qml),
             "editorQml": file_url(QML_DIR / editor_qml)}
            for feature_id, (title, _, list_qml, editor_qml) in FEATURES.items()
            if feature_id in self._controllers
        ]

    # QVariant, not QObject: PySide hands QML an invalid object for None, which crashes QML.
    @Slot(str, result="QVariant")
    def controller(self, feature_id: str) -> FeatureController | None:
        return self._controllers.get(feature_id)

    def _get_selected(self) -> str:
        return self._selected

    def _set_selected(self, name: str) -> None:
        if name != self._selected:
            self._selected = name
            self.selectedButtonChanged.emit()

    selectedButton = Property(str, _get_selected, _set_selected, notify=selectedButtonChanged)

    @Slot(str, result=bool)
    def isLocked(self, name: str) -> bool:
        return False

    @Slot()
    def refresh(self) -> None:
        self.reload()

    # The keyboard has no OpenLinkHub user profiles; ProfilesPanel stays hidden.

    @Property(bool, constant=True)
    def profileBusy(self) -> bool:
        return False

    @Slot(str, result=str)
    def profileNameProblem(self, name: str) -> str:
        return "Not supported on this keyboard"

    @Slot(str, result=bool)
    def canDeleteProfile(self, name: str) -> bool:
        return False

    @Slot(str)
    def switchProfile(self, name: str) -> None:
        pass

    @Slot(str)
    def createProfile(self, name: str) -> None:
        pass

    @Slot(str)
    def deleteProfile(self, name: str) -> None:
        pass
