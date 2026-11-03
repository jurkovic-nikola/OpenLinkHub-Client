"""Finding Keychron keyboards and reading everything the client shows."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import groupby
from typing import Callable

from olhclient.keychron.boards import BOARDS, RECEIVERS, VENDOR_ID, Board
from olhclient.keychron.hidraw import HidInterface, HidrawDevice, enumerate_devices
from olhclient.keychron.protocol import (
    FEATURE_DYNAMIC_DEBOUNCE,
    Debounce,
    KeychronClient,
    KeychronError,
    PollingRate,
    Rgb,
    SleepTime,
    Unsupported,
)


#: matrix positions that may differ from a board's layout and still identify it (keys set to "None")
MAX_LAYOUT_MISMATCH = 4


@dataclass(frozen=True)
class KeychronDevice:
    """A keyboard on USB the client has a board definition for, or a 2.4 GHz receiver."""

    serial: str
    interface: HidInterface
    board: Board | None  # None for a receiver: the keyboard behind it is identified when opened

    @property
    def receiver(self) -> bool:
        return self.interface.product_id in RECEIVERS


def scan(enumerate_fn: Callable[..., list[HidInterface]] = enumerate_devices) -> dict[str, KeychronDevice]:
    """Known Keychron keyboards and receivers on USB, by a serial made up from their USB port."""
    devices = {}
    for interface in enumerate_fn(VENDOR_ID):
        board = BOARDS.get(interface.product_id)
        if board is None and interface.product_id not in RECEIVERS:
            continue
        serial = f"keychron-{interface.product_id:04x}-{interface.uniq or interface.phys}"
        devices[serial] = KeychronDevice(serial, interface, board)
    return devices


def identify(client: KeychronClient, layers: int) -> tuple[Board, list[int]]:
    """The board behind a receiver, and its keymap.

    A receiver does not tell which keyboard it serves. Matrix positions without a key hold
    keycode 0 on every layer, so the board is the one whose key positions match the used ones.
    """
    best: tuple[int, Board, list[int]] | None = None
    for (rows, cols), boards in groupby(sorted(BOARDS.values(), key=lambda b: (b.rows, b.cols)),
                                        key=lambda b: (b.rows, b.cols)):
        codes = client.keymap(layers, rows, cols)
        used = {(row, col) for row in range(rows) for col in range(cols)
                if any(codes[(layer * rows + row) * cols + col] for layer in range(layers))}
        for board in boards:
            mismatch = len(used ^ {(key.row, key.col) for key in board.keys})
            if best is None or mismatch < best[0]:
                best = (mismatch, board, codes)
    if best is None or best[0] > MAX_LAYOUT_MISMATCH:
        raise KeychronError("The keyboard behind the Keychron receiver is not supported")
    return best[1], best[2]


def connect(device: KeychronDevice) -> KeychronClient:
    return KeychronClient(HidrawDevice(device.interface.path))


@dataclass(frozen=True)
class Settings:
    """What changes outside the client too (Fn shortcuts, the OS switch); ``None`` when unsupported."""

    active_layer: int
    rgb: Rgb | None
    polling: PollingRate | None
    debounce: Debounce | None
    sleep: SleepTime | None


@dataclass(frozen=True)
class KeyboardState:
    serial: str
    board: Board
    receiver: bool  # connected through a 2.4 GHz receiver
    firmware: str
    layers: int
    #: (layer, row, col) -> keycode
    keymap: dict[tuple[int, int, int], int]
    #: (layer, encoder, clockwise) -> keycode
    encoders: dict[tuple[int, int, bool], int]
    settings: Settings

    def with_key(self, layer: int, row: int, col: int, keycode: int) -> KeyboardState:
        return replace(self, keymap={**self.keymap, (layer, row, col): keycode})

    def with_encoder(self, layer: int, encoder: int, clockwise: bool, keycode: int) -> KeyboardState:
        return replace(self, encoders={**self.encoders, (layer, encoder, clockwise): keycode})


def _optional(read: Callable[[], object]) -> object | None:
    """``read()``, or None when the firmware lacks the command; no answer at all still raises."""
    try:
        return read()
    except Unsupported:
        return None


def read_settings(client: KeychronClient) -> Settings:
    features = _optional(client.features) or 0
    return Settings(
        active_layer=_optional(client.default_layer) or 0,
        rgb=_optional(client.rgb),
        polling=_optional(client.polling_rate),
        debounce=_optional(client.debounce) if features & FEATURE_DYNAMIC_DEBOUNCE else None,
        sleep=_optional(client.sleep_time),
    )


def read_state(client: KeychronClient, device: KeychronDevice) -> KeyboardState:
    layers = client.layer_count()
    if not 0 < layers <= 16:
        raise KeychronError(f"The keyboard reports {layers} layers")
    if device.board is None:
        board, codes = identify(client, layers)
    else:
        board = device.board
        codes = client.keymap(layers, board.rows, board.cols)
    keymap = {
        (layer, row, col): codes[(layer * board.rows + row) * board.cols + col]
        for layer in range(layers) for row in range(board.rows) for col in range(board.cols)
    }
    encoders = {
        (layer, encoder, clockwise): client.encoder(layer, encoder, clockwise)
        for layer in range(layers) for encoder in range(board.encoders) for clockwise in (True, False)
    }
    return KeyboardState(
        serial=device.serial, board=board, receiver=device.receiver,
        firmware=_optional(client.firmware_version) or "", layers=layers, keymap=keymap, encoders=encoders,
        settings=read_settings(client),
    )
