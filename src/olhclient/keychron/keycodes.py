"""QMK keycodes, as Keychron's ZMK firmware stores them in its VIA keymap.

Values follow QMK's ``keycodes.h`` (the copy in Keychron/zmk ``app/src/launcher``).
Only what the firmware turns back into a ZMK binding (``set_zmk_keymap`` in
``map_keycode.c``) is offered in the picker; anything else is still named.
"""

from __future__ import annotations

from dataclasses import dataclass

NO = 0x0000
TRANSPARENT = 0x0001

QK_MODS = 0x0100
QK_MOD_TAP = 0x2000
QK_LAYER_TAP = 0x4000
QK_LAYER_MOD = 0x5000
QK_TO = 0x5200
QK_MOMENTARY = 0x5220
QK_TOGGLE_LAYER = 0x5260
QK_ONE_SHOT_LAYER = 0x5280
QK_ONE_SHOT_MOD = 0x52A0
QK_LAYER_TAP_TOGGLE = 0x52C0
QK_MACRO = 0x7700
QK_KB = 0x7E00

#: modifier bits of QK_MODS, QK_MOD_TAP, QK_LAYER_MOD and QK_ONE_SHOT_MOD; 0x10 makes them right-hand
MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI, MOD_RIGHT = 0x01, 0x02, 0x04, 0x08, 0x10
MOD_NAMES = ((MOD_CTRL, "Ctrl"), (MOD_SHIFT, "Shift"), (MOD_ALT, "Alt"), (MOD_GUI, "Win/Cmd"))


@dataclass(frozen=True)
class Key:
    code: int
    name: str  # in lists and the picker
    short: str = ""  # on the drawn keyboard, when shorter than ``name``

    @property
    def cap(self) -> str:
        return self.short or self.name


def _keys(category: str, *keys: tuple) -> list[tuple[str, Key]]:
    return [(category, Key(*key)) for key in keys]


LETTERS = [("Basic", Key(0x04 + i, chr(ord("A") + i))) for i in range(26)]
DIGITS = [("Basic", Key(0x1E + i, str((i + 1) % 10))) for i in range(10)]
FKEYS = [("Basic", Key(0x3A + i, f"F{i + 1}")) for i in range(12)] + \
        [("Basic", Key(0x68 + i, f"F{i + 13}")) for i in range(12)]

_TABLE: list[tuple[str, Key]] = [
    *_keys("Special", (NO, "None", " "), (TRANSPARENT, "Transparent (lower layer)", "▽")),
    *LETTERS,
    *DIGITS,
    *_keys(
        "Basic",
        (0x28, "Enter"), (0x29, "Escape", "Esc"), (0x2A, "Backspace", "Bksp"), (0x2B, "Tab"), (0x2C, "Space"),
        (0x2D, "- _", "-"), (0x2E, "= +", "="), (0x2F, "[ {", "["), (0x30, "] }", "]"), (0x31, "\\ |", "\\"),
        (0x32, "# ~ (ISO)", "#"), (0x33, "; :", ";"), (0x34, "' \"", "'"), (0x35, "` ~", "`"), (0x36, ", <", ","),
        (0x37, ". >", "."), (0x38, "/ ?", "/"), (0x39, "Caps Lock", "Caps"), (0x64, "\\ | (ISO)", "\\"),
    ),
    *FKEYS,
    *_keys(
        "Basic",
        (0x46, "Print Screen", "PrtSc"), (0x47, "Scroll Lock", "ScrLk"), (0x48, "Pause"), (0x49, "Insert", "Ins"),
        (0x4A, "Home"), (0x4B, "Page Up", "PgUp"), (0x4C, "Delete", "Del"), (0x4D, "End"),
        (0x4E, "Page Down", "PgDn"), (0x4F, "Right", "→"), (0x50, "Left", "←"), (0x51, "Down", "↓"),
        (0x52, "Up", "↑"), (0x65, "Menu"),
        (0xE0, "Left Ctrl", "Ctrl"), (0xE1, "Left Shift", "Shift"), (0xE2, "Left Alt", "Alt"),
        (0xE3, "Left Win/Cmd", "Win"), (0xE4, "Right Ctrl", "Ctrl"), (0xE5, "Right Shift", "Shift"),
        (0xE6, "Right Alt", "Alt"), (0xE7, "Right Win/Cmd", "Win"),
    ),
    *_keys(
        "Numpad",
        (0x53, "Num Lock", "Num"), (0x54, "Numpad /", "/"), (0x55, "Numpad *", "*"), (0x56, "Numpad -", "-"),
        (0x57, "Numpad +", "+"), (0x58, "Numpad Enter", "Enter"), *((0x59 + i, f"Numpad {(i + 1) % 10}",
                                                                     str((i + 1) % 10)) for i in range(10)),
        (0x63, "Numpad .", "."), (0x67, "Numpad =", "="), (0x85, "Numpad ,", ","),
    ),
    *_keys(
        "International",
        (0x87, "International 1 (Ro)", "Ro"), (0x88, "International 2 (Kana)", "Kana"),
        (0x89, "International 3 (Yen)", "¥"), (0x8A, "International 4 (Henkan)", "Henkan"),
        (0x8B, "International 5 (Muhenkan)", "Muhenk"), (0x90, "Language 1 (Han/Yeong, Kana)", "Lang1"),
        (0x91, "Language 2 (Hanja, Eisu)", "Lang2"),
    ),
    *_keys(
        "Media",
        (0xA5, "System Power", "Power"), (0xA6, "System Sleep", "Sleep"), (0xA7, "System Wake", "Wake"),
        (0xA8, "Mute"), (0xA9, "Volume Up", "Vol+"), (0xAA, "Volume Down", "Vol-"),
        (0xAB, "Next Track", "Next"), (0xAC, "Previous Track", "Prev"), (0xAD, "Stop"),
        (0xAE, "Play / Pause", "Play"), (0xAF, "Media Select", "Media"), (0xB0, "Eject"), (0xB1, "Mail"),
        (0xB2, "Calculator", "Calc"), (0xB3, "My Computer", "PC"), (0xB4, "Browser Search", "Search"),
        (0xB5, "Browser Home", "WHome"), (0xB6, "Browser Back", "Back"), (0xB7, "Browser Forward", "Fwd"),
        (0xB8, "Browser Stop", "WStop"), (0xB9, "Browser Refresh", "Refresh"), (0xBA, "Browser Favorites", "Fav"),
        (0xBB, "Fast Forward", "FF"), (0xBC, "Rewind", "Rew"), (0xBD, "Screen Brightness Up", "Bri+"),
        (0xBE, "Screen Brightness Down", "Bri-"), (0xBF, "Control Panel", "Ctrl Pnl"),
        (0xC0, "Assistant"), (0xC1, "Mission Control", "MCtl"), (0xC2, "Launchpad", "LPad"),
    ),
    *_keys(
        "Mouse",
        (0xCD, "Mouse Up", "M↑"), (0xCE, "Mouse Down", "M↓"), (0xCF, "Mouse Left", "M←"),
        (0xD0, "Mouse Right", "M→"), *((0xD1 + i, f"Mouse Button {i + 1}", f"MB{i + 1}") for i in range(8)),
        (0xD9, "Wheel Up", "Wh↑"), (0xDA, "Wheel Down", "Wh↓"), (0xDB, "Wheel Left", "Wh←"),
        (0xDC, "Wheel Right", "Wh→"),
    ),
    *_keys(
        "Lighting",
        (0x7820, "Lighting On/Off", "RGB"), (0x7821, "Next Effect", "Eff+"), (0x7822, "Previous Effect", "Eff-"),
        (0x7823, "Hue Up", "Hue+"), (0x7824, "Hue Down", "Hue-"), (0x7825, "Saturation Up", "Sat+"),
        (0x7826, "Saturation Down", "Sat-"), (0x7827, "Brightness Up", "Bri+"),
        (0x7828, "Brightness Down", "Bri-"), (0x7829, "Effect Speed Up", "Spd+"),
        (0x782A, "Effect Speed Down", "Spd-"),
    ),
    *_keys(
        "Keychron",
        (QK_KB + 0, "Bluetooth Host 1", "BT1"), (QK_KB + 1, "Bluetooth Host 2", "BT2"),
        (QK_KB + 2, "Bluetooth Host 3", "BT3"), (QK_KB + 3, "Bootloader", "Boot"),
        (QK_KB + 4, "Pair 2.4 GHz", "2.4G"), (QK_KB + 5, "Screen Lock (macOS)", "Lock"),
        (QK_KB + 6, "Cmd+, (Preferences)", "Prefs"), (QK_KB + 7, "Left Option", "Opt"),
        (QK_KB + 8, "Right Option", "Opt"), (QK_KB + 9, "Left Command", "Cmd"),
        (QK_KB + 10, "Right Command", "Cmd"), (QK_KB + 11, "Ctrl+Left (previous desktop)", "Ctrl←"),
        (QK_KB + 12, "Ctrl+Right (next desktop)", "Ctrl→"), (QK_KB + 13, "Emoji (macOS)", "Emoji"),
        (QK_KB + 14, "Task View (Windows)", "Tasks"), (QK_KB + 15, "Previous Desktop (Windows)", "Desk←"),
        (QK_KB + 16, "Next Desktop (Windows)", "Desk→"), (QK_KB + 17, "File Explorer (Windows)", "Files"),
        (QK_KB + 18, "Lock (Windows)", "Lock"), (QK_KB + 19, "Settings (Windows)", "Settings"),
        (QK_KB + 20, "Emoji (Windows)", "Emoji"), (QK_KB + 21, "Screenshot (Windows)", "Snip"),
        (QK_KB + 22, "Screenshot (macOS)", "Snap"), (QK_KB + 23, "Battery Level", "Batt"),
        (QK_KB + 24, "Siri"), (QK_KB + 25, "Cortana"),
        (0x7013, "Toggle NKRO", "NKRO"), (0x700B, "Toggle Win/Cmd Lock", "GUI Lk"),
        (0x7C16, "Grave Escape", "Esc `"),
    ),
]

KEYS: dict[int, Key] = {key.code: key for _, key in _TABLE}
_CATEGORY: dict[int, str] = {key.code: name for name, key in _TABLE}
CATEGORIES = ("Basic", "Media", "Mouse", "Layers", "Lighting", "Keychron", "Numpad", "International", "Special")
#: layer keys, by their QMK range and how they read
LAYER_KINDS = (
    (QK_MOMENTARY, "MO", "Hold for layer"),
    (QK_TOGGLE_LAYER, "TG", "Toggle layer"),
    (QK_TO, "TO", "Switch to layer"),
    (QK_ONE_SHOT_LAYER, "OSL", "Next key on layer"),
    (QK_LAYER_TAP_TOGGLE, "TT", "Tap to toggle layer"),
)


def _mods(mods: int) -> str:
    side = "Right " if mods & MOD_RIGHT else ""
    names = [name for bit, name in MOD_NAMES if mods & bit]
    return side + "+".join(names) if names else "None"


def describe(code: int, layer_names: tuple[str, ...] = ()) -> str:
    """Full name of ``code``, e.g. ``Ctrl+C`` or ``Hold for layer 1 (macOS Fn)``."""
    key = KEYS.get(code)
    if key is not None:
        return key.name
    if QK_MODS <= code < QK_MOD_TAP:
        base = KEYS.get(code & 0xFF)
        return f"{_mods(code >> 8 & 0x1F)}+{base.name if base else hex(code & 0xFF)}"
    if QK_MOD_TAP <= code < QK_LAYER_TAP:
        base = KEYS.get(code & 0xFF)
        return f"{base.name if base else hex(code & 0xFF)} when tapped, {_mods(code >> 8 & 0x1F)} when held"
    if QK_LAYER_TAP <= code < QK_LAYER_MOD:
        base = KEYS.get(code & 0xFF)
        layer = code >> 8 & 0x0F
        return f"{base.name if base else hex(code & 0xFF)} when tapped, layer {_layer(layer, layer_names)} when held"
    if QK_LAYER_MOD <= code < QK_TO:
        return f"Layer {_layer(code >> 5 & 0x0F, layer_names)} with {_mods(code & 0x1F)}"
    for base, _, text in LAYER_KINDS:
        if base <= code < base + 0x20:
            return f"{text} {_layer(code & 0x1F, layer_names)}"
    if QK_ONE_SHOT_MOD <= code < QK_ONE_SHOT_MOD + 0x20:
        return f"One-shot {_mods(code & 0x1F)}"
    if QK_MACRO <= code < QK_MACRO + 0x80:
        return f"Macro {code - QK_MACRO}"
    return f"Keycode 0x{code:04X}"


def _layer(layer: int, names: tuple[str, ...]) -> str:
    return f"{layer} ({names[layer]})" if layer < len(names) else str(layer)


def cap(code: int) -> str:
    """Short text for the key on the drawn keyboard."""
    key = KEYS.get(code)
    if key is not None:
        return key.cap
    if QK_MODS <= code < QK_MOD_TAP:
        base = KEYS.get(code & 0xFF)
        short = "".join(name[0] for bit, name in MOD_NAMES if code >> 8 & bit)
        return f"{short}+{base.cap if base else '?'}"
    if QK_MOD_TAP <= code < QK_LAYER_MOD:
        base = KEYS.get(code & 0xFF)
        return base.cap if base else "?"
    for base, short, _ in LAYER_KINDS:
        if base <= code < base + 0x20:
            return f"{short} {code & 0x1F}"
    if QK_MACRO <= code < QK_MACRO + 0x80:
        return f"M{code - QK_MACRO}"
    return f"{code:04X}"


def category(code: int) -> str:
    """The picker category ``code`` is listed under; ``Basic`` for a key with modifiers."""
    if code in _CATEGORY:
        return _CATEGORY[code]
    if QK_MODS <= code < QK_MOD_TAP:
        return "Basic"
    if any(base <= code < base + 0x20 for base, _, _ in LAYER_KINDS):
        return "Layers"
    return ""


def options(category_name: str, layer_names: tuple[str, ...] = ()) -> list[dict[str, object]]:
    """``[{value, text}]`` for the picker."""
    if category_name == "Layers":
        return [{"value": base + layer, "text": f"{text} {_layer(layer, layer_names)}"}
                for base, _, text in LAYER_KINDS for layer in range(len(layer_names))]
    return [{"value": key.code, "text": key.name} for name, key in _TABLE if name == category_name]


def with_mods(code: int, mods: int) -> int:
    """A basic key combined with modifiers (``LCTL(KC_C)``); ``mods`` 0 gives the plain key."""
    base = code & 0xFF
    return QK_MODS | (mods & 0x1F) << 8 | base if mods else base


def mods_of(code: int) -> int:
    return code >> 8 & 0x1F if QK_MODS <= code < QK_MOD_TAP else 0
