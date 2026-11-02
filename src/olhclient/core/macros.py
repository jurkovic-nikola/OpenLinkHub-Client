"""OpenLinkHub's macros (``/api/macro/*``), shared by every device.

OpenLinkHub can append an action, change an action's hold, repeat and mouse
position, and delete an action. A new action gets the index ``len(actions)``,
and drivers play indexes 0, 1, 2... up to that length, so deleting an action
other than the last leaves a gap: the next new action overwrites the last one,
and the actions after the gap never play. Saving therefore rewrites the macro
from the first action that changed: the actions from there are deleted and
added again in their new order.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.api.client import INPUT_KINDS, ApiClient, ApiError
from olhclient.api.models import (NEW_MACRO_STEPS, Macro, MacroAction, MacroStep, valid_profile_name,
                                  validate_macro)
from olhclient.core.features.key_remap import _natural
from olhclient.core.worker import Worker

#: ("delete", index) | ("add", action) | ("update", index, action) | ("settings", repeat, repeat_delay)
Write = tuple


def plan_macro(macro: Macro, actions: list[MacroAction], repeat: int, repeat_delay: int) -> list[Write]:
    """The writes that turn ``macro`` into ``actions`` with the given settings."""
    keep = 0  # actions 0..keep-1 are in place and need at most an update
    while (keep < len(actions) and keep in macro.actions
           and macro.actions[keep].created_as() == actions[keep].created_as()):
        keep += 1
    writes: list[Write] = [("delete", index) for index in sorted(macro.actions, reverse=True) if index >= keep]
    writes += [("add", action.created_as()) for action in actions[keep:]]
    updates = [("update", index, action) for index, action in enumerate(actions)
               if action != (macro.actions[index] if index < keep else action.created_as())]
    # The server refuses holding every key, so release keys before holding others.
    writes += sorted(updates, key=lambda write: write[2].hold)
    if (repeat, repeat_delay) != (macro.repeat, macro.repeat_delay):
        writes.append(("settings", repeat, repeat_delay))
    return writes


def run_writes(api: ApiClient, macro_id: int, writes: list[Write]) -> None:
    for write in writes:
        if write[0] == "delete":
            api.delete_macro_action(macro_id, write[1])
        elif write[0] == "add":
            api.add_macro_action(macro_id, write[1])
        elif write[0] == "update":
            api.update_macro_action(macro_id, write[1], write[2])
        else:
            api.update_macro_settings(macro_id, write[1], write[2])


def action_to_qml(action: MacroAction) -> dict[str, Any]:
    return {
        "type": action.action_type, "command": action.command, "delay": action.delay, "text": action.text,
        "hold": action.hold, "repeat": action.repeat, "repeatDelay": action.repeat_delay,
        "posX": action.x, "posY": action.y, "absolute": action.absolute,
    }


def action_from_qml(data: dict[str, Any]) -> MacroAction:
    return MacroAction(
        action_type=int(data.get("type", 0)), command=int(data.get("command", 0)), delay=int(data.get("delay", 0)),
        text=str(data.get("text", "")), hold=bool(data.get("hold", False)), repeat=int(data.get("repeat", 0)),
        repeat_delay=int(data.get("repeatDelay", 0)), x=int(data.get("posX", 0)), y=int(data.get("posY", 0)),
        absolute=bool(data.get("absolute", False)),
    )


class MacroLibrary(QObject):
    """The macros page: list, create, delete and edit macros."""

    macrosChanged = Signal()
    currentChanged = Signal()
    namesChanged = Signal()
    busyChanged = Signal()
    #: text, is_error
    message = Signal(str, bool)

    def __init__(self, api: ApiClient, worker: Worker, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.worker = worker
        self._macros: list[Macro] = []
        self._current_id = -1
        self._select_name = ""  # select this macro once it is listed (after creating it)
        # input kind -> {code: name}, for the keys of keyboard, mouse and media actions
        self._names: dict[str, dict[int, str]] = {}
        self._loaded = False
        self._busy = False

    # -- loading -----------------------------------------------------------

    @Slot()
    def reload(self) -> None:
        names = dict(self._names)

        def fetch() -> tuple[list[Macro], dict[str, dict[int, str]]]:
            macros = self.api.macro_profiles()
            for kind in set(INPUT_KINDS) - set(names):
                try:
                    names[kind] = self.api.input_actions(kind)
                except ApiError:
                    pass
            return macros, names

        self.worker.submit(fetch, on_done=self._reloaded, on_error=self._report_error, owner=self)

    def _reloaded(self, result: tuple[list[Macro], dict[str, dict[int, str]]]) -> None:
        macros, names = result
        if names != self._names:
            self._names = names
            self.namesChanged.emit()
        old = self._find(self._current_id)
        if macros != self._macros or not self._loaded:
            self._macros = macros
            self._loaded = True
            self.macrosChanged.emit()
        if self._select_name:
            match = next((m for m in macros if m.name.lower() == self._select_name.lower()), None)
            self._select_name = ""
            if match is not None:
                self._current_id = match.id
        if self._find(self._current_id) is None:
            self._current_id = macros[0].id if macros else -1
        if self._find(self._current_id) != old:
            self.currentChanged.emit()

    def _find(self, macro_id: int) -> Macro | None:
        return next((m for m in self._macros if m.id == macro_id), None)

    # -- writes ------------------------------------------------------------

    def _write(self, call: Any, success: str) -> None:
        self._set_busy(True)

        def finished(_: Any) -> None:
            self._set_busy(False)
            self.message.emit(success, False)
            self.reload()

        def failed(exc: Exception) -> None:
            self._set_busy(False)
            self._report_error(exc)
            self.reload()

        self.worker.submit(call, on_done=finished, on_error=failed, owner=self)

    @Slot(str, result=str)
    def nameProblem(self, name: str) -> str:
        """Why ``name`` cannot be used for a new macro, or an empty string."""
        # The server stores a macro as <lowercase name>.json.
        if any(m.name.lower() == name.lower() for m in self._macros):
            return "A macro with this name already exists"
        return valid_profile_name(name) or ""

    @Slot(str)
    def create(self, name: str) -> None:
        problem = self.nameProblem(name)
        if problem:
            self.message.emit(problem, True)
            return
        self._select_name = name
        self._write(lambda: self.api.new_macro(name), f"Macro {name} created")

    @Slot(int)
    def deleteMacro(self, macro_id: int) -> None:
        macro = self._find(macro_id)
        if macro is None:
            return
        self._write(lambda: self.api.delete_macro(macro_id), f"Macro {macro.name} deleted")

    @Slot("QVariantList", result=str)
    def validate(self, actions: list[dict[str, Any]]) -> str:
        return validate_macro([action_from_qml(a) for a in actions]) or ""

    @Slot(int, int, int, "QVariantList")
    def save(self, macro_id: int, repeat: int, repeat_delay: int, actions: list[dict[str, Any]]) -> None:
        macro = self._find(macro_id)
        if macro is None:
            return
        wanted = [action_from_qml(a) for a in actions]
        problem = validate_macro(wanted)
        if problem:
            self.message.emit(problem, True)
            return
        writes = plan_macro(macro, wanted, repeat, repeat_delay)
        if writes:
            self._write(lambda: run_writes(self.api, macro_id, writes), f"Macro {macro.name} saved")

    # -- helpers -----------------------------------------------------------

    def _report_error(self, exc: Exception) -> None:
        self.message.emit(exc.message if isinstance(exc, ApiError) else str(exc), True)

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    # -- QML API -----------------------------------------------------------

    @Property("QVariantList", notify=macrosChanged)
    def macros(self) -> list[dict[str, Any]]:
        return [{"id": m.id, "name": m.name, "count": len(m.actions)} for m in self._macros]

    @Property(bool, notify=macrosChanged)
    def loaded(self) -> bool:
        return self._loaded

    def _get_current_id(self) -> int:
        return self._current_id

    def _set_current_id(self, macro_id: int) -> None:
        if macro_id != self._current_id and self._find(macro_id) is not None:
            self._current_id = macro_id
            self.currentChanged.emit()

    currentId = Property(int, _get_current_id, _set_current_id, notify=currentChanged)

    @Property("QVariant", notify=currentChanged)
    def current(self) -> dict[str, Any] | None:
        macro = self._find(self._current_id)
        if macro is None:
            return None
        return {
            "id": macro.id,
            "name": macro.name,
            "repeat": macro.repeat,
            "repeatDelay": macro.repeat_delay,
            "actions": [action_to_qml(a) for a in macro.ordered],
            # gaps make the actions after them unreachable; saving closes them
            "gaps": sorted(macro.actions) != list(range(len(macro.actions))),
        }

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property("QVariantList", constant=True)
    def stepTypes(self) -> list[dict[str, Any]]:
        """Action types a new action can have."""
        return [{"value": int(step), "text": step.title} for step in NEW_MACRO_STEPS]

    @Slot(int, result=str)
    def stepTitle(self, action_type: int) -> str:
        try:
            return MacroStep(action_type).title
        except ValueError:
            return f"Type {action_type}"

    @Slot(int, result="QVariantList")
    def keyOptions(self, action_type: int) -> list[dict[str, Any]]:
        """``{value, text}`` keys for a keyboard, mouse or media action, by name."""
        try:
            source = MacroStep(action_type).value_source
        except ValueError:
            source = None
        names = self._names.get(source or "", {})
        options = ({"value": code, "text": name} for code, name in names.items() if code)
        return sorted(options, key=lambda o: _natural(o["text"]))

    @Slot(int, int, result=str)
    def keyName(self, action_type: int, command: int) -> str:
        try:
            source = MacroStep(action_type).value_source
        except ValueError:
            source = None
        return self._names.get(source or "", {}).get(command, f"#{command}")
