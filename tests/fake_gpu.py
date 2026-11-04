"""An in-memory graphics card with a Gigabyte RGB Fusion 2 controller."""

from __future__ import annotations

from olhclient.gpu.cards import CARDS
from olhclient.gpu.device import GpuDevice
from olhclient.gpu.i2c import I2cBus, I2cError

ELITE = next(card for card in CARDS if card.name == "Gigabyte AORUS Radeon RX 9070 XT Elite")
SERIAL = "gpu-0000:0a:00.0-73"


def bus(number: int = 9, name: str = "AMDGPU DM i2c OEM bus") -> I2cBus:
    return I2cBus(number, name, "0000:0a:00.0", *ELITE.ids)


def device() -> GpuDevice:
    return GpuDevice(SERIAL, ELITE, bus())


class FakeCard:
    """Records each write; answers the probe like the RX 9070 XT Elite (or echoes, like a DDC bus)."""

    def __init__(self, answer: bytes = bytes([0xAB, 0x12, 0x52, 0x03])):
        self.answer = answer
        self.writes: list[bytes] = []
        self.fail = False
        self.closed = False

    def write(self, data: bytes) -> None:
        if self.fail:
            raise I2cError("Writing to /dev/i2c-9 failed: Remote I/O error")
        self.writes.append(bytes(data))

    def read(self, size: int) -> bytes:
        return self.answer[:size]

    def close(self) -> None:
        self.closed = True
