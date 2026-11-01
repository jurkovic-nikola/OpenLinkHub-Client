from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.api.models import ActionType, DeviceKind, DeviceState, KeyAssignment, valid_profile_name, validate_assignment
from olhclient.core.features.base import FeatureController
from olhclient.core.listmodel import DictListModel

KEY_ROLES = (
    "keyIndex",
    "name",
    "label",
    "action",
    "useDefault",
    "actionType",
    "actionValue",
    "pressAndHold",
    "onRelease",
    "modifier",
    "locked",
)
#: device kinds whose buttons are remapped through /api/<kind>/updateKeyAssignment
REMAP_KINDS = ("mouse", "headset", "controller")


class KeyRemapController(FeatureController):
    selectedChanged = Signal()
    typeOptionsChanged = Signal()
    #: Value options for an action type finished loading.
    optionsLoaded = Signal(int)
    savingChanged = Signal()
    modifiersChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._keys = DictListModel(KEY_ROLES, self)
        self._type_options: list[dict[str, Any]] = []
        self._options: dict[int, list[dict[str, Any]]] = {}
        self._loading: set[int] = set()
        self._saving = False
        self._modifiers: list[dict[str, Any]] = []
        session.selectedButtonChanged.connect(self.selectedChanged)
        self._keys.dataChanged.connect(lambda *_: self.selectedChanged.emit())
        self._keys.modelReset.connect(self.selectedChanged)

    # -- data --------------------------------------------------------------

    @classmethod
    def supports(cls, state: DeviceState) -> bool:
        return bool(state.keys) and state.kind.api in REMAP_KINDS

    def update(self, state: DeviceState) -> None:
        missing = self.session.module.missing_buttons
        self._keys.set_items(self._row(key) for key in self._ordered(state.keys) if key.name not in missing)
        options = [{"value": value, "text": text} for value, text in state.assignment_types.items()]
        if options != self._type_options:
            self._type_options = options
            self.typeOptionsChanged.emit()
        modifiers = self._modifier_options(state)
        if modifiers != self._modifiers:
            self._modifiers = modifiers
            self.modifiersChanged.emit()

    def _modifier_options(self, state: DeviceState) -> list[dict[str, Any]]:
        return []

    def _ordered(self, keys: list[KeyAssignment]) -> list[KeyAssignment]:
        """Order keys like the device layout: callout list first, then the keypad."""
        layout = self.session.module.layout
        order = list(layout.button_list) + sorted(
            (name for row in layout.keypad for name in row), key=lambda n: _natural(self.session.module.button_label(n))
        )
        rank = {name: i for i, name in enumerate(order)}
        return sorted(keys, key=lambda k: (rank.get(k.name, len(rank)), _natural(k.name)))

    def _row(self, key: KeyAssignment) -> dict[str, Any]:
        return {
            "keyIndex": key.index,
            "name": key.name,
            "label": self.session.module.button_label(key.name),
            "action": self.session.describe_action(key),
            "useDefault": key.use_default,
            "actionType": key.action_type,
            "actionValue": key.action_value,
            "pressAndHold": key.press_and_hold,
            "onRelease": key.on_release,
            "modifier": key.modifier,
            "locked": key.locked or key.name in self.session.module.locked_buttons,
        }

    # -- QML API -----------------------------------------------------------

    @Property(QObject, constant=True)
    def keys(self) -> DictListModel:
        return self._keys

    @Property("QVariant", notify=selectedChanged)
    def selected(self) -> dict[str, Any] | None:
        row = self._keys.indexOf("name", self.session.selectedButton)
        return self._keys.get(row) if row >= 0 else None

    @Property("QVariantList", notify=typeOptionsChanged)
    def typeOptions(self) -> list[dict[str, Any]]:
        return self._type_options

    @Property("QVariantList", notify=modifiersChanged)
    def modifierOptions(self) -> list[dict[str, Any]]:
        """Modifier keys that can be combined with the action (keyboards); empty elsewhere."""
        return self._modifiers

    @Property(bool, notify=savingChanged)
    def saving(self) -> bool:
        return self._saving

    @Slot(int, result="QVariantList")
    def valueOptions(self, action_type: int) -> list[dict[str, Any]]:
        """Selectable values for ``action_type``; loads lazily and emits optionsLoaded."""
        try:
            source = ActionType(action_type).value_source
        except ValueError:
            source = None
        if source is None:
            return [{"value": 0, "text": "None"}]
        if action_type in self._options:
            return self._options[action_type]
        if action_type not in self._loading:
            self._loading.add(action_type)
            api = self.session.api
            fetch = api.macros if source == "macro" else (lambda: api.input_actions(source))
            self.session.worker.submit(
                fetch,
                on_done=lambda result: self._options_loaded(action_type, result),
                on_error=lambda exc: self._options_failed(action_type, exc),
                owner=self,
            )
        # A synchronous worker may already have filled the cache.
        return self._options.get(action_type, [])

    def _options_loaded(self, action_type: int, result: dict[int, str]) -> None:
        self._loading.discard(action_type)
        options = sorted(({"value": v, "text": t} for v, t in result.items()), key=lambda o: _natural(o["text"]))
        self._options[action_type] = options
        self.optionsLoaded.emit(action_type)

    def _options_failed(self, action_type: int, exc: Exception) -> None:
        self._loading.discard(action_type)
        self.session.report_error(exc)

    @Slot(int, bool, bool, result=str)
    def validate(self, action_type: int, press_and_hold: bool, on_release: bool) -> str:
        return validate_assignment(action_type, press_and_hold=press_and_hold, on_release=on_release) or ""

    @Slot(int, bool, int, int, bool, bool, int)
    def save(self, key_index: int, use_default: bool, action_type: int, action_value: int,
             press_and_hold: bool, on_release: bool, modifier: int = 0) -> None:
        row = self._keys.indexOf("keyIndex", key_index)
        if row < 0:
            return
        if self._keys.get(row)["locked"]:
            self.session.report_message("This button cannot be remapped", error=True)
            return
        problem = validate_assignment(action_type, press_and_hold=press_and_hold, on_release=on_release)
        if problem:
            self.session.report_message(problem, error=True)
            return
        self._set_saving(True)
        self.session.worker.submit(
            lambda: self.session.api.update_key_assignment(
                self.session.serial,
                key_index,
                use_default=use_default,
                action_type=action_type,
                action_value=action_value,
                press_and_hold=press_and_hold,
                on_release=on_release,
                modifier=modifier,
                kind=self.session.state.kind.api,
            ),
            on_done=lambda _: self._saved(),
            on_error=self._save_failed,
            owner=self,
        )

    def _saved(self) -> None:
        self._set_saving(False)
        self.session.report_message("Key assignment saved")
        self.session.reload()

    def _save_failed(self, exc: Exception) -> None:
        self._set_saving(False)
        self.session.report_error(exc)

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()


class KeyboardKeysController(KeyRemapController):
    """Key remapping on a keyboard, plus its keyboard profiles (per-key layouts).

    Keyboards share the key assignment endpoint with mice; keys come from the
    active keyboard profile and are listed in keyboard order.
    """

    keyboardProfilesChanged = Signal()
    boardChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._profile_names: list[str] = []
        self._active = ""
        self._board: list[dict[str, Any]] = []
        self._board_size = (0.0, 0.0)

    @classmethod
    def supports(cls, state: DeviceState) -> bool:
        return state.kind is DeviceKind.KEYBOARD and bool(state.keys)

    def update(self, state: DeviceState) -> None:
        super().update(state)
        keyboard = state.keyboard
        names, active = (list(keyboard.names), keyboard.active) if keyboard else ([], "")
        if (names, active) != (self._profile_names, self._active):
            self._profile_names, self._active = names, active
            self.keyboardProfilesChanged.emit()
        board, size = self._build_board(state)
        if (board, size) != (self._board, self._board_size):
            self._board, self._board_size = board, size
            self.boardChanged.emit()

    def _build_board(self, state: DeviceState) -> tuple[list[dict[str, Any]], tuple[float, float]]:
        """The keys as OpenLinkHub draws them, scaled to 0..1 of the board."""
        rects = state.keyboard.layout if state.keyboard else {}
        if not rects:
            return [], (0.0, 0.0)
        width = max(r.x + r.w for r in rects.values())
        height = max(r.y + r.h for r in rects.values())
        keys = {k.index: k for k in state.keys}
        board = []
        for index, rect in rects.items():
            key = keys.get(index)
            if key is None:
                continue
            board.append({
                "keyIndex": index,
                "name": key.name,
                "label": "" if rect.bar else key.caption or key.name,
                "x": rect.x / width, "y": rect.y / height, "w": rect.w / width, "h": rect.h / height,
                "color": key.color or "#bf8d19",
                "locked": key.locked,
                "remapped": not key.use_default,
                "bar": rect.bar,
            })
        return board, (width, height)

    def _ordered(self, keys: list[KeyAssignment]) -> list[KeyAssignment]:
        return keys  # row by row, as on the keyboard

    def _modifier_options(self, state: DeviceState) -> list[dict[str, Any]]:
        modifiers = state.keyboard.modifiers if state.keyboard else {}
        return [{"value": value, "text": text} for value, text in modifiers.items()]

    @Property("QVariantList", notify=boardChanged)
    def boardKeys(self) -> list[dict[str, Any]]:
        """Keys with their place on the board (0..1); empty when the device does not tell its layout."""
        return self._board

    @Property(float, notify=boardChanged)
    def boardAspect(self) -> float:
        width, height = self._board_size
        return width / height if height else 0.0

    @Property("QStringList", notify=keyboardProfilesChanged)
    def keyboardProfiles(self) -> list[str]:
        return self._profile_names

    @Property(str, notify=keyboardProfilesChanged)
    def keyboardProfile(self) -> str:
        return self._active

    @Slot(str, result=str)
    def keyboardProfileProblem(self, name: str) -> str:
        if name in self._profile_names:
            return "A keyboard profile with this name already exists"
        return valid_profile_name(name) or ""

    @Slot(str)
    def switchKeyboardProfile(self, name: str) -> None:
        if name == self._active or name not in self._profile_names:
            return
        serial = self.session.serial
        self.write(lambda: self.session.api.switch_keyboard_profile(serial, name), f"Switched to keyboard profile {name}")

    @Slot(str)
    def newKeyboardProfile(self, name: str) -> None:
        problem = self.keyboardProfileProblem(name)
        if problem:
            self.session.report_message(problem, error=True)
            return
        serial = self.session.serial
        self.write(lambda: self.session.api.new_keyboard_profile(serial, name), f"Keyboard profile {name} created")

    @Slot(str)
    def deleteKeyboardProfile(self, name: str) -> None:
        if name == "default" or name not in self._profile_names:
            self.session.report_message("The default keyboard profile cannot be deleted", error=True)
            return
        serial = self.session.serial
        self.write(lambda: self.session.api.delete_keyboard_profile(serial, name), f"Keyboard profile {name} deleted")


def _natural(text: str) -> tuple:
    """Sort key that orders "G2" before "G10"."""
    return tuple(int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text))
