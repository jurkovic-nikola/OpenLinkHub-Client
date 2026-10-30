"""The device currently shown in the UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot

from olhclient.api.client import ApiClient, ApiError
from olhclient.api.models import ActionType, KeyAssignment, MouseState
from olhclient.core.features import CONTROLLERS, FeatureController
from olhclient.core.worker import Worker
from olhclient.devices.base import DeviceModule

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


def file_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path)).toString()


class DeviceSession(QObject):
    stateChanged = Signal()
    selectedButtonChanged = Signal()
    #: text, is_error
    message = Signal(str, bool)

    def __init__(self, api: ApiClient, worker: Worker, module: DeviceModule, state: MouseState,
                 macros: dict[int, str] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.worker = worker
        self.module = module
        self.state = state
        self._macros: dict[int, str] = dict(macros or {})
        self._selected = ""
        self._reloading = False
        self._controllers: dict[str, FeatureController] = {
            feature.id: CONTROLLERS[feature](self) for feature in CONTROLLERS if feature in module.features
        }
        self._apply(state)
        selectable = [k for k in self._key_order() if k not in module.locked_buttons]
        if selectable:
            self._selected = selectable[0]

    # -- state -------------------------------------------------------------

    @property
    def serial(self) -> str:
        return self.state.serial

    def reload(self) -> None:
        """Fetch the device again (after a save, or on the poll timer)."""
        if self._reloading:
            return
        self._reloading = True
        serial = self.serial

        def fetch() -> tuple[MouseState, dict[int, str]]:
            state = MouseState.from_json(self.api.get_device(serial))
            try:
                macros = self.api.macros()
            except ApiError:
                macros = self._macros
            return state, macros

        self.worker.submit(fetch, on_done=self._reloaded, on_error=self._reload_failed, owner=self)

    def _reloaded(self, result: tuple[MouseState, dict[int, str]]) -> None:
        self._reloading = False
        state, self._macros = result
        self._apply(state)

    def _reload_failed(self, exc: Exception) -> None:
        self._reloading = False
        self.report_error(exc)

    def _apply(self, state: MouseState) -> None:
        self.state = state
        for controller in self._controllers.values():
            controller.update(state)
        self.stateChanged.emit()

    def describe_action(self, key: KeyAssignment) -> str:
        if key.use_default:
            return "Default"
        kind = self.state.assignment_types.get(key.action_type, f"Type {key.action_type}")
        if key.action_type in (ActionType.MEDIA, ActionType.KEYBOARD, ActionType.MOUSE):
            action = (self.state.raw.get("InputActions") or {}).get(str(key.action_value)) or {}
            name = action.get("Name", f"#{key.action_value}")
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
        if not self.state.wireless:
            return "Wired"
        return "USB cable" if self.state.usb else "Wireless"

    @Property(str, constant=True)
    def thumbnail(self) -> str:
        return file_url(self.module.layout.thumbnail)

    @Property("QVariantList", notify=stateChanged)
    def views(self) -> list[dict[str, Any]]:
        present = {k.name for k in self.state.keys}
        return [
            {
                "id": view.id,
                "title": view.title,
                "image": file_url(view.image),
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
    def keypad(self) -> list[list[dict[str, Any]]]:
        return [[self._button(name) for name in row] for row in self.module.layout.keypad]

    @Property("QVariantList", notify=stateChanged)
    def buttonList(self) -> list[dict[str, Any]]:
        layout = self.module.layout
        names = list(layout.button_list)
        if not names:  # generic module: every key the device reports, minus the keypad
            keypad = {name for row in layout.keypad for name in row}
            names = [k.name for k in self.state.keys if k.name not in keypad]
        return [self._button(name) for name in names if self.state.key_by_name(name)]

    @Property("QVariantList", constant=True)
    def features(self) -> list[dict[str, Any]]:
        result = []
        for feature in sorted(self.module.features, key=lambda f: list(CONTROLLERS).index(f)):
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

    @Slot(str, result=QObject)
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
