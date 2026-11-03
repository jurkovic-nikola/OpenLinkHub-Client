"""An in-memory Keychron keyboard that answers raw HID reports like Keychron's ZMK firmware."""

from __future__ import annotations

from collections import deque

from olhclient.keychron.boards import BOARDS, Board
from olhclient.keychron.device import KeychronDevice
from olhclient.keychron.hidraw import HidInterface

V3_ANSI = BOARDS[0x0C30]
SERIAL = "keychron-0c30-usb-0000:00:14.0-2/input1"
RECEIVER = 0xD028
RECEIVER_SERIAL = "keychron-d028-usb-0000:00:14.0-3/input2"


def interface(product_id: int = 0x0C30) -> HidInterface:
    return HidInterface(path="/dev/hidraw7", vendor_id=0x3434, product_id=product_id,
                        name="Keychron Keychron V3 Ultra 8K", uniq="", phys="usb-0000:00:14.0-2/input1")


def device(board: Board = V3_ANSI) -> KeychronDevice:
    return KeychronDevice(SERIAL, interface(board.product_id), board)


def receiver() -> KeychronDevice:
    """The Ultra-Link 8K receiver; the keyboard behind it is not known until it answers."""
    return KeychronDevice(RECEIVER_SERIAL, interface(RECEIVER), None)


class FakeKeyboard:
    """Answers each written report on the next read, the way ``raw_hid_receive`` does."""

    def __init__(self, board: Board = V3_ANSI, *, layers: int = 4, separate_wireless: bool = True):
        self.board = board
        self.layers = layers
        self.separate_wireless = separate_wireless
        # layers 0 and 2 get letters, numbers... in matrix order; the Fn layers are transparent.
        # Matrix positions without a key hold 0, as the firmware generates them.
        keys = {(key.row, key.col) for key in board.keys}
        self.keymap = {
            (layer, row, col): 0 if (row, col) not in keys
            else (0x04 + (row * board.cols + col) % 0x60) if layer % 2 == 0 else 0x0001
            for layer in range(layers) for row in range(board.rows) for col in range(board.cols)
        }
        self.encoders = {(layer, 0, cw): 0x00A9 if cw else 0x00AA for layer in range(layers) for cw in (True, False)}
        self.rgb = {1: [200], 2: [5], 3: [128], 4: [0, 255]}
        self.rgb_saved = 0
        self.usb_div, self.ppt_div = 3, 2
        self.debounce = [10, 50]
        self.sleep = [600, 7200]
        self.active_layer = 2
        self.features = 0xA1 | 1 << 5  # default layer, dynamic debounce, Keychron RGB
        self.answers: deque[bytes] = deque()
        #: reports the keyboard sends before its next answer (state notifications)
        self.unsolicited: list[bytes] = []
        self.requests: list[bytes] = []
        self.silent = False
        self.closed = False

    # -- Transport ---------------------------------------------------------

    def write(self, report: bytes) -> None:
        assert not self.closed
        assert len(report) == 32
        self.requests.append(report)
        if self.silent:
            return
        self.answers.extend(self.unsolicited)
        self.unsolicited = []
        self.answers.append(bytes(self._answer(bytearray(report))))

    def read(self, timeout: float) -> bytes | None:
        return self.answers.popleft() if self.answers else None

    def close(self) -> None:
        self.closed = True

    # -- firmware ------------------------------------------------------------

    def _flat(self) -> bytes:
        board = self.board
        data = bytearray()
        for layer in range(self.layers):
            for row in range(board.rows):
                for col in range(board.cols):
                    code = self.keymap[(layer, row, col)]
                    data += bytes((code >> 8, code & 0xFF))
        return bytes(data)

    def _answer(self, data: bytearray) -> bytearray:
        command = data[0]
        if command == 0x01:
            data[1:3] = b"\x00\x0c"
        elif command == 0xA1:
            text = b"v1.0.2-ZK May 24 2025 10:00:00"
            data[1:1 + len(text)] = text
        elif command == 0xA2:
            data[1] = self.features
        elif command == 0xA3:
            data[1] = self.active_layer
        elif command == 0x11:
            data[1] = self.layers
        elif command == 0x12:
            offset, size = data[1] << 8 | data[2], data[3]
            chunk = self._flat()[offset:offset + size]
            data[4:4 + len(chunk)] = chunk
        elif command == 0x04:
            code = self.keymap[(data[1], data[2], data[3])]
            data[4:6] = bytes((code >> 8, code & 0xFF))
        elif command == 0x05:
            key = (data[1], data[2], data[3])
            if key in self.keymap:
                self.keymap[key] = data[4] << 8 | data[5]
        elif command == 0x14:
            code = self.encoders[(data[1], data[2], bool(data[3]))]
            data[4:6] = bytes((code >> 8, code & 0xFF))
        elif command == 0x15:
            self.encoders[(data[1], data[2], bool(data[3]))] = data[4] << 8 | data[5]
        elif command in (0x07, 0x08, 0x09) and data[1] == 0x03:
            if command == 0x07:
                self.rgb[data[2]] = list(data[3:3 + len(self.rgb[data[2]])])
            elif command == 0x08:
                values = self.rgb[data[2]]
                data[3:3 + len(values)] = bytes(values)
            else:
                self.rgb_saved += 1
        elif command == 0xA7:
            self._keychron(data)
        else:
            data[0] = 0xFF
        return data

    def _keychron(self, data: bytearray) -> None:
        command = data[1]
        if command == 0x01:
            data[2:5] = bytes((0, 3 if self.separate_wireless else 1, 0))
        elif command == 0x05:
            data[2:6] = bytes((0, 1, *self.debounce))
        elif command == 0x06:
            if data[2] > 50 or not 0 < data[3] <= 50:
                data[2] = 1
            else:
                self.debounce = [data[2], data[3]]
                data[2] = 0
        elif command == 0x0B:
            idle, sleep = self.sleep
            data[2:7] = bytes((0, idle & 0xFF, idle >> 8, sleep & 0xFF, sleep >> 8))
        elif command == 0x0C:
            idle, sleep = data[2] | data[3] << 8, data[4] | data[5] << 8
            if idle < 5 or sleep < 60:
                data[2] = 1
            else:
                self.sleep = [idle, sleep]
                data[2] = 0
        elif command == 0x0D:
            if self.separate_wireless:
                data[2:18] = bytes((0, 0x40, 0x1F, 0x7F, self.usb_div, 0, 0x40, 0x1F, 0x7F, self.ppt_div, 0,
                                    125, 0, 0x40, 0x40, 1))
            else:
                data[2:5] = bytes((0, self.usb_div, 0x7F))
        elif command == 0x0E:
            if max(data[2:5]) <= 6:
                self.usb_div, self.ppt_div = data[2], data[3]
                data[2] = 0
            else:
                data[2] = 1
