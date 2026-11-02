"""The device currently shown in the UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from olhclient.api.client import ApiClient, ApiError
from olhclient.api.models import ActionType, DeviceKind, DeviceState, KeyAssignment, valid_profile_name
from olhclient.core.artwork import lit, zone_colors
from olhclient.core.features import CONTROLLERS, FeatureController
from olhclient.core.worker import Worker
from olhclient.devices.base import DeviceModule

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


def kind_icon(kind: DeviceKind) -> Path:
    """Stand-in picture for devices without artwork."""
    return QML_DIR / "icons" / f"kind-{kind.value}.svg"


def file_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path)).toString()


class DeviceSession(QObject):
    stateChanged = Signal()
    selectedButtonChanged = Signal()
    profileBusyChanged = Signal()
    #: text, is_error
    message = Signal(str, bool)

    def __init__(self, api: ApiClient, worker: Worker, module: DeviceModule, state: DeviceState,
                 macros: dict[int, str] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.worker = worker
        self.module = module
        self.state = state
        self._macros: dict[int, str] = dict(macros or {})
        # names of keyboard/media/mouse actions, for devices whose JSON lacks InputActions (keyboards)
        self._input_names: dict[str, dict[int, str]] = {}
        self._selected = ""
        self._reloading = False
        self._reload_again = False
        self._profile_busy = False
        self._colors: dict[str, str] | None = None
        self._images: dict[str, str] = {}  # view id (and "thumbnail") -> lit artwork URL
        # Features are fixed for the session: what the device offered when it was opened.
        self._controllers: dict[str, FeatureController] = {
            feature.id: controller(self)
            for feature, controller in CONTROLLERS.items()
            if (module.features is None or feature in module.features) and controller.supports(state)
        }
        self._apply(state)
        selectable = [k for k in self._key_order() if k not in module.locked_buttons | module.missing_buttons]
        if selectable:
            self._selected = selectable[0]

    # -- state -------------------------------------------------------------

    @property
    def serial(self) -> str:
        return self.state.serial

    @property
    def macro_names(self) -> dict[int, str]:
        """Macro id -> name, as of the last reload."""
        return dict(self._macros)

    def reload(self) -> None:
        """Fetch the device again (after a save, or on the poll timer)."""
        if self._reloading:
            # A fetch is in flight and may predate a write; fetch once more afterwards.
            self._reload_again = True
            return
        self._reloading = True
        serial = self.serial

        kind = self.state.kind

        def fetch() -> tuple[DeviceState, dict[int, str], dict[str, dict[int, str]]]:
            state = DeviceState.from_json(self.api.get_device(serial), kind)
            try:
                macros = self.api.macros()
            except ApiError:
                macros = self._macros
            names = dict(self._input_names)
            for source in self._missing_input_names(state) - set(names):
                try:
                    names[source] = self.api.input_actions(source)
                except ApiError:
                    pass
            return state, macros, names

        self.worker.submit(fetch, on_done=self._reloaded, on_error=self._reload_failed, owner=self)

    def _reloaded(self, result: tuple[DeviceState, dict[int, str], dict[str, dict[int, str]]]) -> None:
        self._reloading = False
        state, self._macros, self._input_names = result
        self._apply(state)
        self._maybe_reload_again()

    def _reload_failed(self, exc: Exception) -> None:
        self._reloading = False
        self.report_error(exc)
        self._maybe_reload_again()

    def _maybe_reload_again(self) -> None:
        if self._reload_again:
            self._reload_again = False
            self.reload()

    def _apply(self, state: DeviceState) -> None:
        self.state = state
        colors = zone_colors(state)
        if colors != self._colors:
            self._colors = colors
            layout = self.module.layout
            missing = self.module.missing_buttons
            self._images = {view.id: file_url(lit(view.image, colors, missing)) for view in layout.views}
            thumbnail = lit(layout.thumbnail, colors, missing) if layout.thumbnail else kind_icon(state.kind)
            self._images["thumbnail"] = file_url(thumbnail)
        for controller in self._controllers.values():
            controller.update(state)
        self.stateChanged.emit()

    @staticmethod
    def _missing_input_names(state: DeviceState) -> set[str]:
        """Action lists to fetch because the device JSON does not name its actions."""
        if "InputActions" in state.raw:
            return set()
        return {ActionType(k.action_type).value_source for k in state.keys
                if not k.use_default and k.action_type in (ActionType.MEDIA, ActionType.KEYBOARD, ActionType.MOUSE)}

    def describe_action(self, key: KeyAssignment) -> str:
        if key.use_default:
            return "Default"
        kind = self.state.assignment_types.get(key.action_type, f"Type {key.action_type}")
        if key.action_type in (ActionType.MEDIA, ActionType.KEYBOARD, ActionType.MOUSE):
            action = (self.state.raw.get("InputActions") or {}).get(str(key.action_value)) or {}
            source = ActionType(key.action_type).value_source
            name = action.get("Name") or self._input_names.get(source, {}).get(key.action_value) or f"#{key.action_value}"
            return f"{kind}: {name}"
        if key.action_type == ActionType.MACRO:
            return f"Macro: {self._macros.get(key.action_value, f'#{key.action_value}')}"
        return kind

    def _key_order(self) -> list[str]:
        layout = self.module.layout
        names = list(layout.button_list) + [name for row in layout.keypad for name in row]
        return names or [k.name for k in self.state.keys]

    # -- messages ----------------------------------------------------------

    def report_message(self, text: str, *, error: bool = False) -> None:
        self.message.emit(text, error)

    def report_error(self, exc: Exception) -> None:
        self.message.emit(exc.message if isinstance(exc, ApiError) else str(exc), True)

    # -- QML API -----------------------------------------------------------

    @Property(str, notify=stateChanged)
    def serialNumber(self) -> str:
        return self.state.serial

    @Property(str, notify=stateChanged)
    def product(self) -> str:
        return self.state.product or self.module.name

    @Property(str, constant=True)
    def moduleId(self) -> str:
        return self.module.id

    @Property(str, constant=True)
    def kind(self) -> str:
        return self.state.kind.value

    @Property(str, constant=True)
    def kindTitle(self) -> str:
        return self.state.kind.title

    @Property(str, notify=stateChanged)
    def firmware(self) -> str:
        return self.state.firmware

    @Property(bool, constant=True)
    def hasArtwork(self) -> bool:
        return bool(self.module.layout.views)

    @Property(bool, constant=True)
    def hasKeyboardLayout(self) -> bool:
        """A keyboard whose key layout OpenLinkHub sends, so it can be drawn."""
        return "keyboard_keys" in self._controllers and bool(self.state.keyboard and self.state.keyboard.layout)

    @Slot()
    def openInBrowser(self) -> None:
        """OpenLinkHub's own page for this device, for what the client does not cover."""
        QDesktopServices.openUrl(QUrl(f"{self.api.base_url}/device/{self.serial}"))

    @Property(str, notify=stateChanged)
    def profileName(self) -> str:
        return self.state.active_profile

    @Property("QStringList", notify=stateChanged)
    def profiles(self) -> list[str]:
        return self.state.profiles

    @Property(bool, notify=stateChanged)
    def connected(self) -> bool:
        return self.state.connected

    @Property(int, notify=stateChanged)
    def battery(self) -> int:
        return -1 if self.state.battery is None else self.state.battery

    @Property(str, notify=stateChanged)
    def connectionMode(self) -> str:
        if not self.state.raw.get("DeviceProfile"):
            return ""  # OpenLinkHub could not send the device data; nothing is known
        if not self.state.wireless:
            return "Wired"
        return "USB cable" if self.state.usb else "Wireless"

    @Property(str, notify=stateChanged)
    def thumbnail(self) -> str:
        return self._images["thumbnail"]

    @Property("QVariantList", notify=stateChanged)
    def views(self) -> list[dict[str, Any]]:
        present = {k.name for k in self.state.keys} - self.module.missing_buttons
        return [
            {
                "id": view.id,
                "title": view.title,
                "image": self._images[view.id],
                "hotspots": [
                    {
                        "button": spot.button,
                        "label": self.module.button_label(spot.button),
                        "x": spot.x,
                        "y": spot.y,
                        "w": spot.w,
                        "h": spot.h,
                        "radius": spot.radius,
                        "locked": spot.button in self.module.locked_buttons,
                    }
                    for spot in view.hotspots
                    if spot.button in present
                ],
            }
            for view in self.module.layout.views
        ]

    def _button(self, name: str) -> dict[str, Any]:
        key = self.state.key_by_name(name)
        return {
            "button": name,
            "label": self.module.button_label(name),
            "action": self.describe_action(key) if key else "",
            "locked": name in self.module.locked_buttons,
        }

    @Property("QVariantList", notify=stateChanged)
    def buttonList(self) -> list[dict[str, Any]]:
        layout = self.module.layout
        names = list(layout.button_list)
        if not names:  # generic module: every key the device reports, minus the keypad
            keypad = {name for row in layout.keypad for name in row}
            names = [k.name for k in self.state.keys if k.name not in keypad]
        return [
            self._button(name) for name in names
            if self.state.key_by_name(name) and name not in self.module.missing_buttons
        ]

    @Property("QVariantList", constant=True)
    def features(self) -> list[dict[str, Any]]:
        result = []
        for feature in (f for f in CONTROLLERS if f.id in self._controllers):
            override = self.module.qml_override(feature)
            result.append(
                {
                    "id": feature.id,
                    "title": feature.title,
                    "listQml": file_url(QML_DIR / feature.value.list_qml),
                    "editorQml": file_url(Path(override)) if override else file_url(QML_DIR / feature.value.editor_qml),
                }
            )
        return result

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
        return name in self.module.locked_buttons

    @Slot()
    def refresh(self) -> None:
        self.reload()

    # -- user profiles -----------------------------------------------------

    @Property(bool, notify=profileBusyChanged)
    def profileBusy(self) -> bool:
        return self._profile_busy

    def _set_profile_busy(self, value: bool) -> None:
        if value != self._profile_busy:
            self._profile_busy = value
            self.profileBusyChanged.emit()

    def _profile_call(self, call: Any, success: str) -> None:
        self._set_profile_busy(True)

        def finished(_: Any) -> None:
            self._set_profile_busy(False)
            self.report_message(success)
            self.reload()

        def failed(exc: Exception) -> None:
            self._set_profile_busy(False)
            self.report_error(exc)
            self.reload()

        self.worker.submit(call, on_done=finished, on_error=failed, owner=self)

    @Slot(str, result=str)
    def profileNameProblem(self, name: str) -> str:
        """Why ``name`` cannot be used for a new profile, or an empty string."""
        if name in self.state.profiles:
            return "A profile with this name already exists"
        return valid_profile_name(name) or ""

    @Slot(str, result=bool)
    def canDeleteProfile(self, name: str) -> bool:
        return name in self.state.profiles and name != "default" and name != self.state.active_profile

    @Slot(str)
    def switchProfile(self, name: str) -> None:
        if name == self.state.active_profile or name not in self.state.profiles:
            return
        self._profile_call(lambda: self.api.switch_user_profile(self.serial, name), f"Switched to profile {name}")

    @Slot(str)
    def createProfile(self, name: str) -> None:
        """Save the current settings as a new profile (it does not become active)."""
        problem = self.profileNameProblem(name)
        if problem:
            self.report_message(problem, error=True)
            return
        self._profile_call(lambda: self.api.save_user_profile(self.serial, name), f"Profile {name} created")

    @Slot(str)
    def deleteProfile(self, name: str) -> None:
        if not self.canDeleteProfile(name):
            self.report_message("The active and the default profile cannot be deleted", error=True)
            return
        self._profile_call(lambda: self.api.delete_user_profile(self.serial, name), f"Profile {name} deleted")
