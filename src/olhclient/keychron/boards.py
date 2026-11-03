"""Keyboards the client knows, by USB product id.

Matrix size and layers come from the keyboard's shield in Keychron/zmk
(``app/boards/shields/keychron_<board>``): the launcher keymap has the matrix
rows minus the last one (the mode switches), and one layer per keymap layer.
Key positions follow the order of the shield's ``default_transform``, in key
units, with the usual key sizes.
"""

from __future__ import annotations

from dataclasses import dataclass

VENDOR_ID = 0x3434
#: 2.4 GHz receivers that pass the raw HID reports on to the keyboard, by USB product id
RECEIVERS = {0xD028: "Ultra-Link 8K"}

#: layers of the stock keymap; the OS switch picks layer 0 or 2
MAC_WIN_LAYERS = ("macOS", "macOS Fn", "Windows", "Windows Fn")


@dataclass(frozen=True)
class KeyPosition:
    row: int
    col: int
    x: float
    y: float
    w: float = 1.0
    h: float = 1.0


@dataclass(frozen=True)
class Board:
    product_id: int
    model: str
    layout: str  # ANSI, ISO, JIS
    rows: int
    cols: int
    layer_names: tuple[str, ...]
    encoders: int
    keys: tuple[KeyPosition, ...]
    #: the layer whose keys match the printed legends (Keychron prints the Windows ones)
    legend_layer: int = 0
    #: the matrix position of the knob's push button
    knob: tuple[int, int] | None = None

    @property
    def title(self) -> str:
        return f"Keychron {self.model} ({self.layout})"


def _rows(*rows: tuple[float, list]) -> tuple[KeyPosition, ...]:
    """Lay out ``(y, items)`` rows left to right. An item is a gap (a number) or
    ``(row, col[, width[, height]])``."""
    keys = []
    for y, items in rows:
        x = 0.0
        for item in items:
            if isinstance(item, (int, float)):
                x += item
                continue
            row, col, *size = item
            w, h = (*size, 1.0, 1.0)[:2]
            keys.append(KeyPosition(row, col, x, y, w, h))
            x += w
    return tuple(keys)


def _run(row: int, first: int, last: int) -> list[tuple[int, int]]:
    return [(row, col) for col in range(first, last + 1)]


# -- V3 Ultra 8K: TKL with a knob (0,13) in the function row ------------------

_V3_FUNCTION_ROW = (0.0, [(0, 0), 0.25, *_run(0, 1, 4), 0.25, *_run(0, 5, 8), 0.25, *_run(0, 9, 12), 0.25,
                          (0, 13), 0.25, *_run(0, 14, 16)])
_V3_NAV = {row: [0.25, *_run(row, 14, 16)] for row in (1, 2)}
_V3_BOTTOM = (5.25, [(5, 0, 1.25), (5, 1, 1.25), (5, 2, 1.25), (5, 6, 6.25), (5, 10, 1.25), (5, 11, 1.25),
                     (5, 12, 1.25), (5, 13, 1.25), 0.25, *_run(5, 14, 16)])

V3_ULTRA_ANSI = _rows(
    _V3_FUNCTION_ROW,
    (1.25, [*_run(1, 0, 12), (1, 13, 2), *_V3_NAV[1]]),
    (2.25, [(2, 0, 1.5), *_run(2, 1, 12), (2, 13, 1.5), *_V3_NAV[2]]),
    (3.25, [(3, 0, 1.75), *_run(3, 1, 11), (3, 12, 2.25)]),
    (4.25, [(4, 0, 2.25), *_run(4, 2, 11), (4, 12, 2.75), 1.25, (4, 15)]),
    _V3_BOTTOM,
)
# ISO: Enter (2,13) spans two rows (drawn as its lower part), # is (3,12), \ is (4,1)
V3_ULTRA_ISO = _rows(
    _V3_FUNCTION_ROW,
    (1.25, [*_run(1, 0, 12), (1, 13, 2), *_V3_NAV[1]]),
    (2.25, [(2, 0, 1.5), *_run(2, 1, 12), 0.25, (2, 13, 1.25, 2), *_V3_NAV[2]]),
    (3.25, [(3, 0, 1.75), *_run(3, 1, 12)]),
    (4.25, [(4, 0, 1.25), *_run(4, 1, 11), (4, 12, 2.75), 1.25, (4, 15)]),
    _V3_BOTTOM,
)
# JIS: Yen (1,13) and Backspace (3,13) share the number row, Ro is (4,12); the bottom row has
# Muhenkan (5,3), Henkan (5,9) and Kana (5,10). Widths are the common JIS ones, not measured.
V3_ULTRA_JIS = _rows(
    _V3_FUNCTION_ROW,
    (1.25, [*_run(1, 0, 13), (3, 13), *_V3_NAV[1]]),
    (2.25, [(2, 0, 1.5), *_run(2, 1, 12), 0.25, (2, 13, 1.25, 2), *_V3_NAV[2]]),
    (3.25, [(3, 0, 1.75), *_run(3, 1, 12)]),
    (4.25, [(4, 0, 2.25), *_run(4, 2, 12), (4, 13, 1.75), 1.25, (4, 15)]),
    (5.25, [(5, 0, 1.25), (5, 1, 1.25), (5, 2, 1.25), (5, 3, 1.25), (5, 6, 3.75), (5, 9, 1.25), (5, 10, 1.25),
            (5, 11, 1.25), (5, 12, 1.25), (5, 13, 1.25), 0.25, *_run(5, 14, 16)]),
)

BOARDS: dict[int, Board] = {
    board.product_id: board
    for board in (
        Board(0x0C30, "V3 Ultra 8K", "ANSI", 6, 17, MAC_WIN_LAYERS, 1, V3_ULTRA_ANSI,
              legend_layer=2, knob=(0, 13)),
        Board(0x0C31, "V3 Ultra 8K", "ISO", 6, 17, MAC_WIN_LAYERS, 1, V3_ULTRA_ISO,
              legend_layer=2, knob=(0, 13)),
        Board(0x0C32, "V3 Ultra 8K", "JIS", 6, 17, MAC_WIN_LAYERS, 1, V3_ULTRA_JIS,
              legend_layer=2, knob=(0, 13)),
    )
}
