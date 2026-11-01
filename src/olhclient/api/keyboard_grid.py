"""Where OpenLinkHub draws each key of a keyboard.

OpenLinkHub's keyboard page lays the keys of ``DeviceProfile.Keyboards[profile]``
out in a CSS grid (``web/<keyboard>.html`` with ``static/css/themes/default.css``):
every row is a grid of ``UIKeyboardRow`` columns, keys take one cell or span
several (``wide``, ``wide3``...), ``keyEmpty`` entries are empty cells, and a
few classes make keys taller, shorter or shifted. This module ports those rules,
so the client draws the same keyboard for every layout OpenLinkHub ships. It was
checked key by key against OpenLinkHub's page for all its layouts.

The numeric ``width``/``left``/``top`` fields of a key are not used: OpenLinkHub
ignores them and they do not match the page for every layout.

Decorative LED bars that the page positions absolutely are left out; they are
colour-only and cannot be remapped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

#: gap between keys, in keys (5 px at the page's 60 px key)
GAP = 5 / 60
#: .keyboard-margin-top: 65 px above rows whose "top" is 65
ROW_MARGIN = 65 / 60
_WIDE = re.compile(r"^wide(\d*)$")
_ABSOLUTE = re.compile(r"^(height125top\d*(right)?|height125topright|height30top40|(left|right)-led-\d+)$")


@dataclass(frozen=True)
class KeyRect:
    """A key's box in key units (a plain key is 1 x 1), from the grid's top-left corner."""

    x: float
    y: float
    w: float
    h: float
    bar: bool  # a decorative LED bar rather than a key


def _classes(key: dict[str, Any]) -> list[str]:
    return ((key.get("keySpace") or "keyboard-key") + " " + (key.get("css") or "")).split()


def _span(classes: list[str]) -> int:
    span = 1
    for c in classes:
        m = _WIDE.match(c)
        if m and c != "wide100":
            span = int(m.group(1) or 2)
    return span


def _size(classes: list[str]) -> tuple[float | None, float, float, bool]:
    """(width, or None to fill the cells; height; margin-top; is a LED bar) of an in-flow item."""
    c = set(classes)
    wide = "keyboard-key" in c and any(_WIDE.match(x) and x != "wide100" for x in c)
    if c & {"enter-custom", "enter-custom2"}:  # ISO Enter: 125 px tall, reaching 65 px into the row above
        return None, 125 / 60, -65 / 60, False
    if "keyboard-key-half" in c:  # no flex parent on the page: as tall as its text
        return None if c & {"wide3", "wide4"} else 1.0, 1 / 3, 0.0, False
    if "keyboard-key-125-125" in c:
        return 2.0833, 2.0833, 0.0, False
    if c & {"keyboard-key-125", "keyboard-key-125-top32"}:
        # .keyboard-key.wide is more specific than .keyboard-key-125: the width then fills the cells
        return None if wide else 1.0, 2.0833, 0.0, False
    if "wide100" in c:
        return None, 0.1666, 0.0, True
    if "height100" in c:
        return 0.1666, 1.0, 0.0, True
    if c & {"height50", "height50-50"}:
        return 0.1666, 0.5, 0.0, True
    if "height40" in c:
        return 0.1666, 0.4, 0.0, True
    if "height40-50" in c:
        return 0.1666, 0.4, -0.5, True
    if "top-32auto" in c:
        return None, 1.0, 1.0666, False
    return None, 1.0, 0.54 if "top-32" in c else 0.0, False


def _advance(col: int, line: int, span: int, columns: int) -> tuple[int, int]:
    col += span
    return (0, line + 1) if col >= columns else (col, line)


def layout(keyboard: dict[str, Any], ui_row: str) -> dict[int, KeyRect]:
    """Key id -> box, for one keyboard of ``DeviceProfile.Keyboards`` and the device's ``UIKeyboardRow``.

    Hidden placeholder keys (class ``empty``) and absolutely positioned LED bars are left out.
    """
    try:
        columns = int(ui_row.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return {}
    rows = sorted((keyboard.get("row") or {}).items(), key=lambda kv: int(kv[0]))
    rects: dict[int, KeyRect] = {}
    for index, (_, row) in enumerate(rows):
        margin = ROW_MARGIN if row.get("top") == 65 else 0.0
        items, col, line = [], 0, 0
        for kid, key in sorted((row.get("keys") or {}).items(), key=lambda kv: int(kv[0])):
            for _ in (key.get("keyEmpty") or []) + (key.get("spacing") or []):
                col, line = _advance(col, line, 1, columns)
            classes = _classes(key)
            if any(_ABSOLUTE.match(c) for c in classes):
                continue  # out of the grid flow
            span = _span(classes)
            if col + span > columns:
                col, line = 0, line + 1
            w, h, mt, bar = _size(classes)
            cells = span + (span - 1) * GAP
            shift = 0.54 if "keyboard-key-125-top32" in classes else 0.0
            items.append((int(kid), col * (1 + GAP), line, cells if w is None else w, h, mt, shift, bar,
                          "empty" in classes))
            col, line = _advance(col, line, span, columns)
        if not items:
            continue
        # Each line of the row is as tall as its tallest margin box; the whole row is
        # centred in its track of the outer grid (align-items: center).
        heights: dict[int, float] = {}
        for item in items:
            heights[item[2]] = max(heights.get(item[2], 0.0), item[4] + item[5])
        offsets, y = {}, 0.0
        for ln in sorted(heights):
            offsets[ln] = y
            y += heights[ln] + GAP
        row_y = index * (1 + GAP) + margin + (1 - (y - GAP) - margin) / 2
        for kid, x, ln, w, h, mt, shift, bar, hidden in items:
            if not hidden:
                rects[kid] = KeyRect(x, row_y + offsets[ln] + mt + shift, w, h, bar)
    if not rects:
        return {}
    # from the top-left corner of what is drawn
    left = min(r.x for r in rects.values())
    top = min(r.y for r in rects.values())
    return {kid: KeyRect(r.x - left, r.y - top, r.w, r.h, r.bar) for kid, r in rects.items()}
