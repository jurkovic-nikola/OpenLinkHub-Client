import pytest

from olhclient.api.client import ApiError
from olhclient.api.models import Macro, MacroAction, MacroStep, validate_macro
from olhclient.core.macros import MacroLibrary, action_to_qml, plan_macro, run_writes
from olhclient.core.worker import Worker

A = MacroAction(MacroStep.KEYBOARD, command=10)
B = MacroAction(MacroStep.KEYBOARD, command=46)
WAIT = MacroAction(MacroStep.DELAY, delay=50)
TEXT = MacroAction(MacroStep.TEXT, text="gg", repeat=3, repeat_delay=100)


def macro(*actions: MacroAction, indexes: list[int] | None = None, repeat: int = 0) -> Macro:
    indexes = indexes if indexes is not None else list(range(len(actions)))
    return Macro(id=1, name="Test", repeat=repeat, repeat_delay=0, actions=dict(zip(indexes, actions)))


def test_append_only_adds():
    assert plan_macro(macro(A), [A, WAIT], 0, 0) == [("add", WAIT)]


def test_unchanged_macro_needs_no_writes():
    assert plan_macro(macro(A, WAIT), [A, WAIT], 0, 0) == []


def test_hold_and_repeat_are_updated_in_place():
    held = MacroAction(MacroStep.KEYBOARD, command=10, hold=True)
    assert plan_macro(macro(A, B), [held, B], 0, 0) == [("update", 0, held)]


def test_deleting_an_action_rewrites_the_rest():
    """Deleting index 1 alone would leave a gap that stops C from playing."""
    assert plan_macro(macro(A, WAIT, B), [A, B], 0, 0) == [("delete", 2), ("delete", 1), ("add", B)]


def test_reordering_rewrites_from_the_first_change():
    writes = plan_macro(macro(A, WAIT, TEXT), [A, TEXT, WAIT], 0, 0)
    assert writes == [("delete", 2), ("delete", 1), ("add", TEXT.created_as()), ("add", WAIT), ("update", 1, TEXT)]


def test_gaps_are_closed():
    writes = plan_macro(macro(A, B, indexes=[0, 2]), [A, B], 0, 0)
    assert writes == [("delete", 2), ("add", B)]


def test_keys_are_released_before_others_are_held():
    held_a = MacroAction(MacroStep.KEYBOARD, command=10, hold=True)
    held_b = MacroAction(MacroStep.KEYBOARD, command=46, hold=True)
    writes = plan_macro(macro(A, held_b), [held_a, B], 0, 0)
    assert writes == [("update", 1, B), ("update", 0, held_a)]


def test_settings_change():
    assert plan_macro(macro(A), [A], -1, 200) == [("settings", -1, 200)]


@pytest.mark.parametrize(
    "actions, problem",
    [
        ([A], None),
        ([MacroAction(MacroStep.KEYBOARD)], "Action 1: Choose a key"),
        ([A, MacroAction(MacroStep.DELAY)], "Action 2: A delay is 1 to 65535 ms"),
        ([MacroAction(MacroStep.TEXT)], "Action 1: Enter the text to type"),
        ([MacroAction(MacroStep.TEXT, text="x", repeat=101)], "Action 1: Repeat is 0 to 100 times"),
        ([MacroAction(MacroStep.KEYBOARD, command=10, hold=True), WAIT], "At least one action must not be press and hold"),
    ],
)
def test_validate_macro(actions, problem):
    assert validate_macro(actions) == problem


def run_plan(fake_api, actions: list[MacroAction], repeat: int = 0, repeat_delay: int = 0) -> Macro:
    current = next(m for m in fake_api.macro_profiles() if m.id == 1)
    run_writes(fake_api, 1, plan_macro(current, actions, repeat, repeat_delay))
    return next(m for m in fake_api.macro_profiles() if m.id == 1)


@pytest.mark.parametrize(
    "steps",
    [
        [[A, WAIT, B, TEXT], [A, B, TEXT]],  # delete in the middle
        [[A, WAIT, B, TEXT], [TEXT, B, WAIT, A]],  # reverse
        [[A, B], [MacroAction(MacroStep.KEYBOARD, command=10, hold=True), B], [A, MacroAction(MacroStep.KEYBOARD, command=46, hold=True)]],
        [[A, WAIT], []],  # delete everything
    ],
)
def test_plans_reach_the_wanted_macro_on_the_server(fake_api, steps):
    for actions in steps:
        result = run_plan(fake_api, actions, repeat=2, repeat_delay=10)
        assert result.ordered == actions
        assert sorted(result.actions) == list(range(len(actions)))  # no gaps
        assert (result.repeat, result.repeat_delay) == (2, 10)


@pytest.fixture
def library(qtbot, fake_api):
    library = MacroLibrary(fake_api, Worker(synchronous=True))
    messages = []
    library.message.connect(lambda text, error: messages.append((text, error)))
    library.messages = messages
    library.reload()
    return library


def test_library_lists_macros_and_key_names(library):
    assert library.macros == [{"id": 1, "name": "DPI", "count": 1}]
    assert library.current["name"] == "DPI"
    assert library.current["gaps"] is False
    assert library.keyOptions(MacroStep.KEYBOARD) == [{"value": 46, "text": "Letter T"}, {"value": 10, "text": "Number 3"}]
    assert library.keyName(MacroStep.KEYBOARD, 46) == "Letter T"
    assert library.keyName(MacroStep.KEYBOARD, 999) == "#999"
    assert library.stepTitle(MacroStep.MOUSE_MOVE) == "Mouse position"


def test_create_selects_the_new_macro(library, fake_api):
    assert library.nameProblem("dpi") == "A macro with this name already exists"
    assert library.nameProblem("a b") == "Only letters and numbers are allowed"
    library.create("Combo")
    assert fake_api.calls[-1] == ("new_macro", "Combo")
    assert library.current["name"] == "Combo"
    assert library.messages[-1] == ("Macro Combo created", False)


def test_save_and_delete(library, fake_api):
    actions = [action_to_qml(a) for a in (A, WAIT, TEXT)]
    assert library.validate(actions) == ""
    library.save(1, -1, 0, actions)
    assert [a for a in library.current["actions"]] == actions
    assert library.current["repeat"] == -1
    library.deleteMacro(1)
    assert library.macros == []
    assert library.current is None


def test_failed_save_shows_the_server_state(library, fake_api):
    fake_api.fail_with = ApiError("Unable to create macro profile value")
    library.save(1, 0, 0, [action_to_qml(a) for a in (A, WAIT)])
    fake_api.fail_with = None
    library.reload()
    assert library.messages[-1] == ("Unable to create macro profile value", True)
    assert len(library.current["actions"]) == 1


def test_invalid_save_is_refused(library, fake_api):
    library.save(1, 0, 0, [action_to_qml(MacroAction(MacroStep.TEXT))])
    assert library.messages[-1] == ("Action 1: Enter the text to type", True)
    assert not [c for c in fake_api.calls if c[0].endswith("macro_action")]


def test_key_remap_lists_new_macros(make_session, fake_api):
    session = make_session()
    fake_api.new_macro("Combo")
    session.reload()
    options = session.controller("key_remap").valueOptions(10)
    assert [o["text"] for o in options] == ["Combo", "DPI"]
