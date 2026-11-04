"""Gigabyte RGB Fusion 2 lighting on graphics cards.

Ported from OpenRGB's ``Controllers/GigabyteRGBFusion2GPUController``. The
controller takes 8-byte writes and cannot be read back, except for the probe.
Changes last until the card loses power; :meth:`Fusion2Gpu.save` keeps them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol

#: registers (first byte of a write)
REG_COLOR = 0x40
REG_MODE = 0x88
REG_COLOR_LEFT_MID = 0xB0  # zones 1 and 2
REG_COLOR_RIGHT = 0xB1  # zone 3
REG_PALETTE = 0xB0  # 0xB0 + 4 * zone: four banks of two colours

PROBE = bytes([0xAB, 0, 0, 0, 0, 0, 0, 0])
SAVE = bytes([0xAA, 0, 0, 0, 0, 0, 0, 0])
PROBE_ANSWER = 0xAB

ZONES = 5
BRIGHTNESS_MAX = 0x63
SPEED_MAX = 5
SPEED_NORMAL = 2
PALETTE_SIZE = 8

Color = tuple[int, int, int]


class ModeValue(IntEnum):
    STATIC = 0x01
    BREATHING = 0x02
    COLOR_CYCLE = 0x03
    FLASHING = 0x04
    GRADIENT = 0x05
    COLOR_SHIFT = 0x06
    WAVE = 0x07
    DUAL_FLASHING = 0x08
    TRICOLOR = 0x0B


@dataclass(frozen=True)
class Mode:
    value: ModeValue
    title: str
    brightness: bool  # breathing always runs at full brightness
    speed: bool
    zone_colors: bool  # a colour per zone
    palette: int = 0  # colours shared by all zones instead


#: in OpenRGB's order
MODES = (
    Mode(ModeValue.STATIC, "Static", brightness=True, speed=False, zone_colors=True),
    Mode(ModeValue.BREATHING, "Pulse", brightness=False, speed=True, zone_colors=True),
    Mode(ModeValue.FLASHING, "Flash", brightness=True, speed=True, zone_colors=True),
    Mode(ModeValue.DUAL_FLASHING, "Double flash", brightness=True, speed=True, zone_colors=True),
    Mode(ModeValue.COLOR_CYCLE, "Colour cycle", brightness=True, speed=True, zone_colors=False),
    Mode(ModeValue.GRADIENT, "Gradient", brightness=True, speed=True, zone_colors=True),
    Mode(ModeValue.WAVE, "Wave", brightness=True, speed=True, zone_colors=False),
    Mode(ModeValue.COLOR_SHIFT, "Colour shift", brightness=True, speed=True, zone_colors=False, palette=PALETTE_SIZE),
    Mode(ModeValue.TRICOLOR, "Tricolour", brightness=True, speed=True, zone_colors=False, palette=3),
)
MODE_BY_VALUE = {mode.value: mode for mode in MODES}

WHITE: Color = (255, 255, 255)
DEFAULT_PALETTE: tuple[Color, ...] = (
    (255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0),
    (0, 255, 255), (0, 0, 255), (128, 0, 255), (255, 0, 255),
)


@dataclass(frozen=True)
class Lighting:
    """What the card shows. It cannot be read from the card, so the client keeps what it last set."""

    mode: int = ModeValue.STATIC
    brightness: int = BRIGHTNESS_MAX  # 0..BRIGHTNESS_MAX
    speed: int = SPEED_NORMAL  # 0..SPEED_MAX
    zones: tuple[Color, ...] = (WHITE,) * ZONES
    palette: tuple[Color, ...] = DEFAULT_PALETTE


def _mode_packet(mode: int, speed: int, brightness: int, flag: int, zone: int) -> bytes:
    return bytes([REG_MODE, mode, speed, brightness, flag, zone + 1, 0, 0])


def packets(lighting: Lighting) -> list[bytes]:
    """The writes that show ``lighting``: OpenRGB's ``DeviceUpdateLEDs``, zone by zone."""
    mode = MODE_BY_VALUE.get(lighting.mode)
    if mode is None:
        raise ValueError(f"Unknown mode {lighting.mode}")
    speed = max(0, min(SPEED_MAX, lighting.speed))
    brightness = max(0, min(BRIGHTNESS_MAX, lighting.brightness)) if mode.brightness else BRIGHTNESS_MAX
    zones = lighting.zones
    palette = (tuple(lighting.palette[:mode.palette]) + ((0, 0, 0),) * PALETTE_SIZE)[:PALETTE_SIZE]

    writes = []
    for zone in range(ZONES):
        if mode.value == ModeValue.COLOR_CYCLE:
            writes.append(_mode_packet(mode.value, speed, brightness, 0, zone))
        elif mode.palette:
            flag = mode.palette if mode.value == ModeValue.COLOR_SHIFT else 0x08
            writes.append(_mode_packet(mode.value, speed, brightness, flag, zone))
            bank = REG_PALETTE + zone * 4
            for i in range(4):
                writes.append(bytes([bank + i, mode.value, *palette[2 * i], *palette[2 * i + 1]]))
        else:
            flag = 0x08 if mode.value == ModeValue.GRADIENT else 0
            writes.append(_mode_packet(mode.value, speed, brightness, flag, zone))
            if zone < 2:
                writes.append(bytes([REG_COLOR_LEFT_MID, mode.value, *zones[0], *zones[1]]))
            elif zone == 2:
                writes.append(bytes([REG_COLOR_RIGHT, mode.value, *zones[2], 0, 0, 0]))
            else:
                writes.append(bytes([REG_COLOR, *zones[zone], zone + 1, 0, 0, 0]))
    return writes


class Transport(Protocol):
    def write(self, data: bytes) -> None: ...

    def read(self, size: int) -> bytes: ...

    def close(self) -> None: ...


class Fusion2Gpu:
    """The lighting controller of one card (an :class:`~olhclient.gpu.i2c.I2cDevice`)."""

    def __init__(self, transport: Transport):
        self.transport = transport

    def probe(self) -> bool:
        """Whether a Fusion 2 controller answers. OpenRGB's ``TestForGigabyteRGBFusion2GPUController``.

        Every controller seen answers 0xAB and version bytes; a bus that echoes the command
        back answers 0xAB only.
        """
        self.transport.write(PROBE)
        answer = self.transport.read(4)
        return len(answer) == 4 and answer[0] == PROBE_ANSWER and answer[1:] != bytes([PROBE_ANSWER] * 3)

    def apply(self, lighting: Lighting) -> None:
        for data in packets(lighting):
            self.transport.write(data)

    def save(self) -> None:
        """Store what the card shows, so it comes back after a power cycle."""
        self.transport.write(SAVE)

    def close(self) -> None:
        self.transport.close()
