"""Controllers of a Keychron keyboard (see core/keychron.py).

They take the role of the OpenLinkHub controllers: the keyboard view and the
lighting and settings lists bind to the same properties.
"""

from __future__ import annotations

import colorsys
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.core.features.base import FeatureController
from olhclient.core.listmodel import DictListModel
from olhclient.keychron import keycodes
from olhclient.keychron.device import KeyboardState
from olhclient.keychron.protocol import DEBOUNCE_PRESS, DEBOUNCE_RELEASE, MIN_IDLE_S, MIN_SLEEP_S, POLLING_RATES, RgbValue

if TYPE_CHECKING:
    from olhclient.core.keychron import KeychronSession

KEY_ROLES = ("keyIndex", "name", "label", "action", "locked", "keycode", "category", "mods")
#: key index of the knob turns: ENCODER_INDEX + 2 * encoder (+ 1 counter-clockwise)
ENCODER_INDEX = 1000


def _percent(value: int) -> int:
    return round(value * 100 / 255)


def _byte(percent: int) -> int:
    return round(max(0, min(100, percent)) * 255 / 100)


class KeychronKeysController(FeatureController):
    """The keymap, one layer at a time. Keys are written one by one, as in Keychron Launcher."""

    session: KeychronSession
    selectedChanged = Signal()
    layerChanged = Signal()
    boardChanged = Signal()
    savingChanged = Signal()

    def __init__(self, session: KeychronSession):
        super().__init__(session)
        self._keys = DictListModel(KEY_ROLES, self)
        self._layer: int | None = None
        self._names: dict[int, str] = {}  # key index -> name, fixed for the session
        self._board: list[dict[str, Any]] = []
        self._aspect = 0.0
        self._saving = False
        session.selectedButtonChanged.connect(self.selectedChanged)
        self._keys.dataChanged.connect(lambda *_: self.selectedChanged.emit())
        self._keys.modelReset.connect(self.selectedChanged)

    @classmethod
    def supports(cls, state: KeyboardState) -> bool:
        return bool(state.keymap)

    def update(self, state: KeyboardState) -> None:
        if self._layer is None or self._layer >= state.layers:
            self._layer = min(state.settings.active_layer, state.layers - 1)
            self.layerChanged.emit()
        if not self._names:
            self._names = self._make_names(state)
            first = next(iter(self._names.values()), "")
            if not self.session.selectedButton:
                self.session.selectedButton = first
        self._rebuild(state)

    # -- keys --------------------------------------------------------------

    def _slots(self, state: KeyboardState) -> list[tuple[int, int]]:
        """(key index, keycode on the shown layer) in keyboard order, then the knob turns."""
        board, layer = state.board, self._layer or 0
        slots = [(key.row * board.cols + key.col, state.keymap.get((layer, key.row, key.col), 0))
                 for key in sorted(board.keys, key=lambda k: (k.y, k.x))]
        for encoder in range(board.encoders):
            for ccw in (0, 1):
                slots.append((ENCODER_INDEX + 2 * encoder + ccw, state.encoders.get((layer, encoder, not ccw), 0)))
        return slots

    def _make_names(self, state: KeyboardState) -> dict[int, str]:
        """Name keys after their legend (the legend layer's keycode); the selection follows names."""
        board = state.board
        legend_layer = board.legend_layer if board.legend_layer < state.layers else 0
        names: dict[int, str] = {}
        seen: dict[str, int] = {}
        for index, _ in self._slots(state):
            if index >= ENCODER_INDEX:
                encoder, ccw = divmod(index - ENCODER_INDEX, 2)
                name = ("Knob counter-clockwise" if ccw else "Knob clockwise") + (f" {encoder + 1}" if encoder else "")
            else:
                row, col = divmod(index, board.cols)
                legend = state.keymap.get((legend_layer, row, col), 0)
                name = "Knob press" if (row, col) == board.knob else keycodes.describe(legend)
            seen[name] = seen.get(name, 0) + 1
            names[index] = name if seen[name] == 1 else f"{name} {seen[name]}"
        return names

    def _rebuild(self, state: KeyboardState) -> None:
        layer_names = state.board.layer_names
        rows = []
        for index, code in self._slots(state):
            name = self._names.get(index, f"Key {index}")
            rows.append({
                "keyIndex": index,
                "name": name,
                "label": name,
                "action": keycodes.describe(code, layer_names),
                "locked": False,
                "keycode": code,
                "category": keycodes.category(code),
                "mods": keycodes.mods_of(code),
            })
        self._keys.set_items(rows)

        board, layer = state.board, self._layer or 0
        width = max((k.x + k.w for k in board.keys), default=0.0)
        height = max((k.y + k.h for k in board.keys), default=0.0)
        drawn = [
            {
                "keyIndex": key.row * board.cols + key.col,
                "name": self._names.get(key.row * board.cols + key.col, ""),
                "label": keycodes.cap(state.keymap.get((layer, key.row, key.col), 0)),
                "x": key.x / width, "y": key.y / height, "w": key.w / width, "h": key.h / height,
                "color": "#bf8d19",
                "locked": False,
                "remapped": False,
                "bar": False,
            }
            for key in board.keys
        ] if width and height else []
        aspect = width / height if height else 0.0
        if (drawn, aspect) != (self._board, self._aspect):
            self._board, self._aspect = drawn, aspect
            self.boardChanged.emit()

    # -- QML API -----------------------------------------------------------

    @Property(QObject, constant=True)
    def keys(self) -> DictListModel:
        return self._keys

    @Property("QVariant", notify=selectedChanged)
    def selected(self) -> dict[str, Any] | None:
        row = self._keys.indexOf("name", self.session.selectedButton)
        return self._keys.get(row) if row >= 0 else None

    @Property("QVariantList", notify=boardChanged)
    def boardKeys(self) -> list[dict[str, Any]]:
        return self._board

    @Property(float, notify=boardChanged)
    def boardAspect(self) -> float:
        return self._aspect

    @Property("QStringList", constant=True)
    def layerNames(self) -> list[str]:
        state = self.session.state
        names = state.board.layer_names
        return [names[i] if i < len(names) else f"Layer {i}" for i in range(state.layers)]

    @Property(int, notify=layerChanged)
    def layer(self) -> int:
        return self._layer or 0

    @Slot(int)
    def setLayer(self, layer: int) -> None:
        if layer == self._layer or not 0 <= layer < self.session.state.layers:
            return
        self._layer = layer
        self.layerChanged.emit()
        self._rebuild(self.session.state)

    @Property("QVariantList", constant=True)
    def categories(self) -> list[dict[str, Any]]:
        return [{"value": name, "text": name} for name in keycodes.CATEGORIES]

    @Slot(str, result="QVariantList")
    def keyOptions(self, category: str) -> list[dict[str, Any]]:
        return keycodes.options(category, tuple(self.layerNames))

    @Slot(int, result=str)
    def categoryOf(self, code: int) -> str:
        return keycodes.category(code)

    @Slot(int, result=int)
    def modsOf(self, code: int) -> int:
        return keycodes.mods_of(code)

    @Slot(int, int, result=int)
    def withMods(self, code: int, mods: int) -> int:
        return keycodes.with_mods(code, mods)

    @Slot(int, result=str)
    def describe(self, code: int) -> str:
        return keycodes.describe(code, tuple(self.layerNames))

    @Property(bool, notify=savingChanged)
    def saving(self) -> bool:
        return self._saving

    @Slot(int, int)
    def save(self, key_index: int, keycode: int) -> None:
        if not 0 <= keycode <= 0xFFFF or self._keys.indexOf("keyIndex", key_index) < 0:
            return
        session, layer = self.session, self._layer or 0
        client, cols = session.client, session.state.board.cols

        if key_index >= ENCODER_INDEX:
            encoder, ccw = divmod(key_index - ENCODER_INDEX, 2)

            def write() -> int:
                client.set_encoder(layer, encoder, not ccw, keycode)
                return client.encoder(layer, encoder, not ccw)

            def store(code: int) -> KeyboardState:
                return session.state.with_encoder(layer, encoder, not ccw, code)
        else:
            row, col = divmod(key_index, cols)

            def write() -> int:
                client.set_keycode(layer, row, col, keycode)
                return client.keycode(layer, row, col)

            def store(code: int) -> KeyboardState:
                return session.state.with_key(layer, row, col, code)

        def done(code: int) -> None:
            self._set_saving(False)
            session.apply(store(code))
            if code == keycode:
                session.report_message("Key saved")
            else:
                session.report_message("The keyboard did not take this key", error=True)

        def failed(exc: Exception) -> None:
            self._set_saving(False)
            session.report_error(exc)

        self._set_saving(True)
        session.worker.submit(write, on_done=done, on_error=failed, owner=self)

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()


#: rgb matrix effects of Keychron's ZMK firmware, by number (rgb_effect_funcs in app/src/rgb/rgb_effects.c)
EFFECTS = (
    "Off", "Solid colour", "Breathing", "Spiral brightness", "Cycle all", "Cycle left/right", "Cycle up/down",
    "Rainbow moving", "Cycle out/in", "Cycle out/in dual", "Pinwheel", "Spiral", "Spin around centre",
    "Rainbow spin", "Random raindrops", "Random light key", "Typing heatmap", "Digital rain", "Reactive",
    "Reactive multi-wide", "Reactive multi-nexus", "Splash", "Solid splash", "Per-key colours", "Mixed colours",
)


class KeychronLightingController(FeatureController):
    """Effect, brightness, speed and colour. Every change applies and is stored at once."""

    session: KeychronSession
    changed = Signal()

    def __init__(self, session: KeychronSession):
        super().__init__(session)
        self._zones = DictListModel(("zoneIndex", "name", "color"), self)  # none; LightingList shows zones
        self._rgb = None

    @classmethod
    def supports(cls, state: KeyboardState) -> bool:
        return state.settings.rgb is not None

    def update(self, state: KeyboardState) -> None:
        if state.settings.rgb != self._rgb:
            self._rgb = state.settings.rgb
            self.changed.emit()

    def _set(self, value: RgbValue, data: tuple[int, ...], success: str) -> None:
        client = self.session.client
        # on failure nothing changes, so tell the UI to drop what the user picked
        self.write(lambda: client.set_rgb(value, *data), success, done=lambda ok: ok or self.changed.emit())

    # -- QML API (LightingList's part matches LightingController) -----------------

    @Property(bool, notify=changed)
    def available(self) -> bool:
        return self._rgb is not None

    @Property(QObject, constant=True)
    def zones(self) -> DictListModel:
        return self._zones

    @Property(int, notify=changed)
    def effect(self) -> int:
        return self._rgb.effect if self._rgb else 0

    @Property(str, notify=changed)
    def effectTitle(self) -> str:
        effect = self.effect
        return EFFECTS[effect] if effect < len(EFFECTS) else f"Effect {effect}"

    @Property("QVariantList", constant=True)
    def effects(self) -> list[dict[str, Any]]:
        return [{"value": number, "text": title} for number, title in enumerate(EFFECTS)]

    @Property(bool, constant=True)
    def hasBrightness(self) -> bool:
        return True

    @Property(int, notify=changed)
    def brightness(self) -> int:
        return _percent(self._rgb.brightness) if self._rgb else 0

    @Property("QVariantList", constant=True)
    def brightnessModes(self) -> list[dict[str, Any]]:
        return []

    @Property(int, constant=True)
    def brightnessMode(self) -> int:
        return 0

    @Property(int, notify=changed)
    def speed(self) -> int:
        return _percent(self._rgb.speed) if self._rgb else 0

    @Property(str, notify=changed)
    def color(self) -> str:
        if not self._rgb:
            return "#000000"
        red, green, blue = colorsys.hsv_to_rgb(self._rgb.hue / 255, self._rgb.saturation / 255, 1.0)
        return "#{:02x}{:02x}{:02x}".format(round(red * 255), round(green * 255), round(blue * 255))

    @Slot(int)
    def setEffect(self, effect: int) -> None:
        if not self._rgb or effect == self._rgb.effect:
            return
        if not 0 <= effect < len(EFFECTS):
            self.session.report_message(f"Unknown effect {effect}", error=True)
            return
        self._set(RgbValue.EFFECT, (effect,), f"Effect set to {EFFECTS[effect]}")

    @Slot(int)
    def setBrightness(self, percent: int) -> None:
        if not self._rgb or percent == self.brightness:
            return
        if not 0 <= percent <= 100:
            self.session.report_message("Brightness must be between 0 and 100", error=True)
            return
        self._set(RgbValue.BRIGHTNESS, (_byte(percent),), f"Brightness set to {percent} %")

    @Slot(int)
    def setSpeed(self, percent: int) -> None:
        if not self._rgb or percent == self.speed:
            return
        if not 0 <= percent <= 100:
            self.session.report_message("Speed must be between 0 and 100", error=True)
            return
        self._set(RgbValue.SPEED, (_byte(percent),), f"Effect speed set to {percent} %")

    @Slot(str)
    def setColor(self, color: str) -> None:
        """``#rrggbb``; the keyboard keeps hue and saturation, brightness is separate."""
        value = color.lstrip("#")
        if not self._rgb or len(value) != 6:
            return
        try:
            red, green, blue = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except ValueError:
            self.session.report_message(f"Invalid colour {color}", error=True)
            return
        hue, saturation, _ = colorsys.rgb_to_hsv(red, green, blue)
        data = (round(hue * 255) % 256, round(saturation * 255))
        if data == (self._rgb.hue, self._rgb.saturation):
            return
        self._set(RgbValue.COLOR, data, "Colour saved")


DEBOUNCE_CHOICES = (0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50)
IDLE_CHOICES = (60, 120, 180, 300, 600, 900, 1200, 1800)
SLEEP_CHOICES = (300, 600, 900, 1800, 3600, 7200, 10800)


def _minutes(seconds: int) -> str:
    return f"{seconds // 60} min" if seconds % 60 == 0 else f"{seconds} s"


class KeychronSettingsController(FeatureController):
    """Polling rate, debounce and the low-power timers, in the format of SettingsController."""

    session: KeychronSession
    itemsChanged = Signal()
    busyChanged = Signal()

    def __init__(self, session: KeychronSession):
        super().__init__(session)
        self._items: list[dict[str, Any]] = []
        self._busy = False

    @classmethod
    def supports(cls, state: KeyboardState) -> bool:
        settings = state.settings
        return any(part is not None for part in (settings.polling, settings.debounce, settings.sleep))

    def update(self, state: KeyboardState) -> None:
        items = self._build(state)
        if items != self._items:
            self._items = items
            self.itemsChanged.emit()

    @staticmethod
    def _choice(key: str, title: str, value: int, options: list[tuple[int, str]]) -> dict[str, Any]:
        if value not in {v for v, _ in options}:  # keep a value set elsewhere selectable
            options = sorted([*options, (value, str(value))])
        return {"key": key, "title": title, "kind": "choice", "value": value, "min": 0, "max": 0, "enabled": True,
                "options": [{"value": v, "text": text} for v, text in options]}

    def _build(self, state: KeyboardState) -> list[dict[str, Any]]:
        settings, items = state.settings, []
        polling = settings.polling
        if polling is not None:
            items.append(self._choice("pollingUsb", "Polling rate (USB)", polling.usb,
                                      [(div, f"{POLLING_RATES[div]} Hz") for div in polling.usb_supported]))
            if polling.wireless is not None:
                items.append(self._choice("pollingWireless", "Polling rate (2.4 GHz)", polling.wireless,
                                          [(div, f"{POLLING_RATES[div]} Hz") for div in polling.wireless_supported]))
        if settings.debounce is not None:
            low, high = DEBOUNCE_PRESS
            items.append(self._choice("debouncePress", "Debounce on press", settings.debounce.press,
                                      [(ms, f"{ms} ms") for ms in DEBOUNCE_CHOICES if low <= ms <= high]))
            low, high = DEBOUNCE_RELEASE
            items.append(self._choice("debounceRelease", "Debounce on release", settings.debounce.release,
                                      [(ms, f"{ms} ms") for ms in DEBOUNCE_CHOICES if low <= ms <= high]))
        if settings.sleep is not None:
            items.append(self._choice("idle", "Idle after", settings.sleep.idle,
                                      [(s, _minutes(s)) for s in IDLE_CHOICES]))
            items.append(self._choice("sleep", "Sleep after", settings.sleep.sleep,
                                      [(s, _minutes(s)) for s in SLEEP_CHOICES]))
        return items

    @Property("QVariantList", notify=itemsChanged)
    def items(self) -> list[dict[str, Any]]:
        return self._items

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot(str, "QVariant")
    def apply(self, key: str, value: Any) -> None:
        item = next((i for i in self._items if i["key"] == key), None)
        if item is None:
            self.session.report_message(f"{key} is not supported by this keyboard", error=True)
            return
        value = int(value)
        if value == item["value"]:
            return
        if value not in {o["value"] for o in item["options"]}:
            self.session.report_message(f"Invalid value for {item['title']}", error=True)
            return
        call = self._call(key, value)
        if isinstance(call, str):
            self.session.report_message(call, error=True)
            return
        self._set_busy(True)
        self.write(call, f"{item['title']} updated", done=self._applied)

    def _call(self, key: str, value: int) -> Callable[[], None] | str:
        """The write for ``key``, or why it cannot be made."""
        client, settings = self.session.client, self.session.state.settings
        polling, debounce, sleep = settings.polling, settings.debounce, settings.sleep
        # Each request carries both values of a pair, so the other one is sent as it is.
        if key == "pollingUsb" and polling:
            return lambda: client.set_polling_rate(value, polling.wireless)
        if key == "pollingWireless" and polling:
            return lambda: client.set_polling_rate(polling.usb, value)
        if key == "debouncePress" and debounce:
            return lambda: client.set_debounce(value, debounce.release)
        if key == "debounceRelease" and debounce:
            return lambda: client.set_debounce(debounce.press, value)
        if key == "idle" and sleep:
            if not MIN_IDLE_S <= value <= sleep.sleep:
                return "The idle time must be shorter than the sleep time"
            return lambda: client.set_sleep_time(value, sleep.sleep)
        if key == "sleep" and sleep:
            if not max(MIN_SLEEP_S, sleep.idle) <= value:
                return "The sleep time must be longer than the idle time"
            return lambda: client.set_sleep_time(sleep.idle, value)
        return f"{key} is not supported by this keyboard"

    def _applied(self, ok: bool) -> None:
        self._set_busy(False)
        if not ok:  # the controls show the rejected value; rebuild them from the keyboard's
            self.itemsChanged.emit()

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()
