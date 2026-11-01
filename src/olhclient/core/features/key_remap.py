from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.api.models import ActionType, KeyAssignment, MouseState, validate_assignment
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
    "locked",
)


class KeyRemapController(FeatureController):
    selectedChanged = Signal()
    typeOptionsChanged = Signal()
    #: Value options for an action type finished loading.
    optionsLoaded = Signal(int)
    savingChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._keys = DictListModel(KEY_ROLES, self)
        self._type_options: list[dict[str, Any]] = []
        self._options: dict[int, list[dict[str, Any]]] = {}
        self._loading: set[int] = set()
        self._saving = False
        session.selectedButtonChanged.connect(self.selectedChanged)
        self._keys.dataChanged.connect(lambda *_: self.selectedChanged.emit())
        self._keys.modelReset.connect(self.selectedChanged)

    # -- data --------------------------------------------------------------

    def update(self, state: MouseState) -> None:
        missing = self.session.module.missing_buttons
        self._keys.set_items(self._row(key) for key in self._ordered(state.keys) if key.name not in missing)
        options = [{"value": value, "text": text} for value, text in state.assignment_types.items()]
        if options != self._type_options:
            self._type_options = options
            self.typeOptionsChanged.emit()

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
            "locked": key.name in self.session.module.locked_buttons,
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

    @Slot(int, bool, int, int, bool, bool)
    def save(self, key_index: int, use_default: bool, action_type: int, action_value: int,
             press_and_hold: bool, on_release: bool) -> None:
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


def _natural(text: str) -> tuple:
    """Sort key that orders "G2" before "G10"."""
    return tuple(int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text))
