"""The raw HID protocol of Keychron's ZMK firmware (``app/src/launcher`` in Keychron/zmk).

It is VIA protocol 12 (keymap, encoders, macros, lighting as "custom values")
plus Keychron's own commands (0xA0-0xA8) for polling rate, debounce and sleep.
Every request is one 32-byte report; the keyboard answers with the same report,
values filled in. An unknown command comes back with 0xFF as its first byte.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

REPORT_SIZE = 32
#: bytes of keymap/macro data per buffer request (32 minus the 4-byte header)
CHUNK = 28
TIMEOUT_S = 1.0
#: resends of a request that got no answer; over a 2.4 GHz receiver the first report after a quiet
#: spell can get lost. Every request is safe to repeat: reads, and writes of absolute values.
RETRIES = 1
UNHANDLED = 0xFF


class Command(IntEnum):
    PROTOCOL_VERSION = 0x01
    GET_KEYCODE = 0x04
    SET_KEYCODE = 0x05
    CUSTOM_SET = 0x07
    CUSTOM_GET = 0x08
    CUSTOM_SAVE = 0x09
    LAYER_COUNT = 0x11
    KEYMAP_BUFFER = 0x12
    GET_ENCODER = 0x14
    SET_ENCODER = 0x15
    # Keychron
    FIRMWARE_VERSION = 0xA1
    SUPPORT_FEATURE = 0xA2
    DEFAULT_LAYER = 0xA3
    KEYCHRON = 0xA7


class KeychronCommand(IntEnum):
    """Second byte of a 0xA7 request (``kc_user_cmd`` in launcher.c)."""

    PROTOCOL = 0x01
    DEBOUNCE = 0x05
    SET_DEBOUNCE = 0x06
    SLEEP_TIME = 0x0B
    SET_SLEEP_TIME = 0x0C
    POLLING_RATE = 0x0D
    SET_POLLING_RATE = 0x0E


#: lighting is VIA's "rgb matrix" channel
RGB_CHANNEL = 0x03


class RgbValue(IntEnum):
    BRIGHTNESS = 1  # 0-255
    EFFECT = 2  # 0 is off
    SPEED = 3  # 0-255
    COLOR = 4  # hue, saturation (0-255 each)


#: ``kc_get_support_feature`` bits
FEATURE_DYNAMIC_DEBOUNCE = 1 << 5

#: polling rate n is 8000 Hz >> n
POLLING_RATES = {div: 8000 >> div for div in range(7)}
#: firmware limits of ``kc_user_cmd_set_debounce`` (ms)
DEBOUNCE_PRESS = (0, 50)
DEBOUNCE_RELEASE = (1, 50)
#: firmware minimums of ``kc_user_cmd_set_sleep_time`` (s)
MIN_IDLE_S = 5
MIN_SLEEP_S = 60


class KeychronError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NoAnswer(KeychronError):
    """The keyboard did not answer: unplugged, or asleep behind a receiver."""


class Unsupported(KeychronError):
    """The firmware does not know the command."""


class Transport(Protocol):
    def write(self, report: bytes) -> None: ...

    def read(self, timeout: float) -> bytes | None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class Rgb:
    brightness: int
    effect: int
    speed: int
    hue: int
    saturation: int


@dataclass(frozen=True)
class PollingRate:
    """Polling rate as divider of 8000 Hz, per connection; ``None`` where there is none."""

    usb: int
    wireless: int | None
    usb_supported: tuple[int, ...]
    wireless_supported: tuple[int, ...]


@dataclass(frozen=True)
class Debounce:
    press: int  # ms
    release: int  # ms


@dataclass(frozen=True)
class SleepTime:
    idle: int  # s
    sleep: int  # s


def _supported(mask: int) -> tuple[int, ...]:
    return tuple(div for div in POLLING_RATES if mask & (1 << div))


class KeychronClient:
    """Requests to one keyboard. Thread-safe: the worker may run calls in parallel."""

    def __init__(self, transport: Transport, *, timeout: float = TIMEOUT_S, retries: int = RETRIES):
        self._transport = transport
        self._timeout = timeout
        self._retries = retries
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            self._transport.close()

    # -- low level ---------------------------------------------------------

    def request(self, *payload: int, match: int = 1) -> bytes:
        """Send ``payload`` and return the answer, whose first ``match`` bytes repeat the request."""
        report = bytes(payload).ljust(REPORT_SIZE, b"\0")
        with self._lock:
            for _ in range(1 + self._retries):
                self._transport.write(report)
                while (answer := self._transport.read(self._timeout)) is not None:
                    answer = answer.ljust(REPORT_SIZE, b"\0")
                    if answer[:match] == report[:match]:
                        return answer
                    if answer[0] == UNHANDLED and answer[1:match] == report[1:match]:
                        raise Unsupported(f"The keyboard does not support command 0x{payload[0]:02x}")
                    # anything else is a report the keyboard sent on its own; skip it
            raise NoAnswer("The keyboard did not answer")

    def _keychron(self, command: KeychronCommand, *args: int) -> bytes:
        answer = self.request(Command.KEYCHRON, command, *args, match=2)
        if command in (KeychronCommand.SET_DEBOUNCE, KeychronCommand.SET_SLEEP_TIME,
                       KeychronCommand.SET_POLLING_RATE) and answer[2] != 0:
            raise KeychronError("The keyboard refused the setting")
        return answer

    # -- device ------------------------------------------------------------

    def protocol_version(self) -> int:
        answer = self.request(Command.PROTOCOL_VERSION)
        return answer[1] << 8 | answer[2]

    def firmware_version(self) -> str:
        """E.g. ``v1.0.2-ZK May 24 2025 10:00:00`` (version, build date and time)."""
        text = self.request(Command.FIRMWARE_VERSION)[1:].split(b"\0", 1)[0]
        return text.decode("ascii", errors="replace").strip()

    def features(self) -> int:
        return self.request(Command.SUPPORT_FEATURE)[1]

    def default_layer(self) -> int:
        """The highest active layer: the macOS or Windows base layer, from the OS switch."""
        return self.request(Command.DEFAULT_LAYER)[1]

    # -- keymap ------------------------------------------------------------

    def layer_count(self) -> int:
        return self.request(Command.LAYER_COUNT)[1]

    def keymap(self, layers: int, rows: int, cols: int) -> list[int]:
        """Every keycode, layer by layer, row by row (``layers * rows * cols`` values)."""
        size = layers * rows * cols * 2
        data = bytearray()
        for offset in range(0, size, CHUNK):
            length = min(CHUNK, size - offset)
            answer = self.request(Command.KEYMAP_BUFFER, offset >> 8, offset & 0xFF, length, match=4)
            data += answer[4:4 + length]
        return [data[i] << 8 | data[i + 1] for i in range(0, size, 2)]

    def keycode(self, layer: int, row: int, col: int) -> int:
        answer = self.request(Command.GET_KEYCODE, layer, row, col, match=4)
        return answer[4] << 8 | answer[5]

    def set_keycode(self, layer: int, row: int, col: int, keycode: int) -> None:
        """Takes effect at once; the keyboard writes it to flash a moment later."""
        self.request(Command.SET_KEYCODE, layer, row, col, keycode >> 8, keycode & 0xFF, match=4)

    def encoder(self, layer: int, encoder: int, clockwise: bool) -> int:
        answer = self.request(Command.GET_ENCODER, layer, encoder, int(clockwise), match=4)
        return answer[4] << 8 | answer[5]

    def set_encoder(self, layer: int, encoder: int, clockwise: bool, keycode: int) -> None:
        self.request(Command.SET_ENCODER, layer, encoder, int(clockwise), keycode >> 8, keycode & 0xFF, match=4)

    # -- lighting ----------------------------------------------------------

    def rgb(self) -> Rgb:
        def get(value: RgbValue) -> bytes:
            return self.request(Command.CUSTOM_GET, RGB_CHANNEL, value, match=3)[3:5]

        color = get(RgbValue.COLOR)
        return Rgb(brightness=get(RgbValue.BRIGHTNESS)[0], effect=get(RgbValue.EFFECT)[0],
                   speed=get(RgbValue.SPEED)[0], hue=color[0], saturation=color[1])

    def set_rgb(self, value: RgbValue, *data: int, save: bool = True) -> None:
        """Set one lighting value; ``save`` stores the lighting in flash, like Keychron Launcher does."""
        self.request(Command.CUSTOM_SET, RGB_CHANNEL, value, *data, match=3)
        if save:
            self.request(Command.CUSTOM_SAVE, RGB_CHANNEL, match=2)

    # -- settings (Keychron commands) -----------------------------------------

    def keychron_protocol(self) -> int:
        """3 when the keyboard has a separate 2.4 GHz polling rate."""
        return self._keychron(KeychronCommand.PROTOCOL)[3]

    def polling_rate(self) -> PollingRate:
        answer = self._keychron(KeychronCommand.POLLING_RATE)
        if self.keychron_protocol() < 3:  # a7 0d result div mask
            return PollingRate(usb=answer[3], wireless=None, usb_supported=_supported(answer[4]),
                               wireless_supported=())
        # a7 0d result | max(2) mask div read-only | the same for 2.4 GHz | Bluetooth (fixed)
        return PollingRate(usb=answer[6], wireless=answer[11], usb_supported=_supported(answer[5]),
                           wireless_supported=_supported(answer[10]))

    def set_polling_rate(self, usb: int, wireless: int | None) -> None:
        """Both rates go in one request: send the current one for the connection that stays."""
        self._keychron(KeychronCommand.SET_POLLING_RATE, usb, wireless or 0, 0)

    def debounce(self) -> Debounce:
        answer = self._keychron(KeychronCommand.DEBOUNCE)
        return Debounce(press=answer[4], release=answer[5])

    def set_debounce(self, press: int, release: int) -> None:
        self._keychron(KeychronCommand.SET_DEBOUNCE, press, release)

    def sleep_time(self) -> SleepTime:
        answer = self._keychron(KeychronCommand.SLEEP_TIME)
        return SleepTime(idle=answer[3] | answer[4] << 8, sleep=answer[5] | answer[6] << 8)

    def set_sleep_time(self, idle: int, sleep: int) -> None:
        self._keychron(KeychronCommand.SET_SLEEP_TIME, idle & 0xFF, idle >> 8, sleep & 0xFF, sleep >> 8)
