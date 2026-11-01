"""The keyboard grid port against where OpenLinkHub's own page draws each key."""

import json
import statistics

import pytest

from olhclient.api.keyboard_grid import layout
from olhclient.api.models import DeviceKind, DeviceState

from tests.conftest import FIXTURES, KEYBOARD

LAYOUTS = FIXTURES / "keyboards"
PAGE = json.loads((LAYOUTS / "openlinkhub_page.json").read_text())


@pytest.mark.parametrize("name", sorted(PAGE))
def test_keys_sit_where_openlinkhub_draws_them(name):
    page = PAGE[name]
    unit = page["key"]
    rects = layout(json.loads((LAYOUTS / f"{name}.json").read_text()), page["uiKeyboardRow"])
    measured = {int(kid): box for kid, box in page["keys"].items()}
    # only the absolutely positioned LED bars (thin, colour-only) are left out
    left_out = set(measured) - set(rects)
    assert all(min(measured[kid][2], measured[kid][3]) < unit * 0.2 for kid in left_out)
    common = [kid for kid in measured if kid in rects]
    # the page centres the keyboard; compare positions relative to it
    dx = statistics.median(measured[k][0] - rects[k].x * unit for k in common)
    dy = statistics.median(measured[k][1] - rects[k].y * unit for k in common)
    for kid in common:
        x, y, w, h = measured[kid]
        r = rects[kid]
        assert (r.x * unit + dx, r.y * unit + dy, r.w * unit, r.h * unit) == pytest.approx((x, y, w, h), abs=1.5), kid


def test_iso_enter_reaches_into_the_row_above():
    rects = layout(json.loads((LAYOUTS / "k65plus-iso.json").read_text()), "keyboard-row-17")
    enter = next(r for kid, r in rects.items() if r.h > 2)
    assert enter.h == pytest.approx(125 / 60, abs=0.01)


def test_led_bars_are_marked():
    rects = layout(json.loads((LAYOUTS / "k100.json").read_text()), "keyboard-row-26")
    bars = [r for r in rects.values() if r.bar]
    assert bars and all(min(r.w, r.h) < 0.2 for r in bars)


def test_unknown_grid_gives_no_layout():
    assert layout({"row": {"0": {"keys": {"1": {"keyName": "A"}}}}}, "") == {}


def test_keyboard_state_with_a_real_layout(other_devices):
    device = other_devices[3]
    device["DeviceProfile"]["Keyboards"]["default"] = json.loads((LAYOUTS / "k70core.json").read_text())
    device["UIKeyboardRow"] = "keyboard-row-25"
    state = DeviceState.from_json(device, DeviceKind.KEYBOARD)
    names = [k.name for k in state.keys]
    # repeated key names get a number, so each key can be selected on its own
    assert names.count("Shift") == 1 and "Shift 2" in names
    shift2 = state.key_by_name("Shift 2")
    assert shift2.caption == "Shift" and shift2.index in state.keyboard.layout
    assert len(state.keyboard.layout) >= 100
