"""Finding graphics cards with RGB lighting, and remembering what the client set on them."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from olhclient.gpu.cards import AMD, AMD_BUS_NAMES, CARDS, Card
from olhclient.gpu.fusion2 import MODE_BY_VALUE, Fusion2Gpu, Lighting
from olhclient.gpu.i2c import I2cBus, I2cDevice, I2cError, enumerate_buses

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GpuDevice:
    """A known card whose lighting controller answered on ``bus``."""

    serial: str
    card: Card
    bus: I2cBus

    @property
    def name(self) -> str:
        return self.card.name


def _candidate(card: Card, bus: I2cBus) -> bool:
    if card.ids != (bus.vendor_id, bus.device_id, bus.subsystem_vendor_id, bus.subsystem_device_id):
        return False
    return card.vendor_id != AMD or bus.name.startswith(AMD_BUS_NAMES)


def scan(enumerate_fn: Callable[[], list[I2cBus]] = enumerate_buses,
         open_fn: Callable[[str, int], Fusion2Gpu] | None = None) -> dict[str, GpuDevice]:
    """Known cards whose controller answers the probe, by a serial made up from the PCI slot.

    Probing writes to the bus, so this runs once, not on every poll.
    """
    open_fn = open_fn or (lambda path, address: Fusion2Gpu(I2cDevice(path, address)))
    devices = {}
    for bus in enumerate_fn():
        for card in CARDS:
            serial = f"gpu-{bus.pci_slot}-{card.address:02x}"
            if serial in devices or not _candidate(card, bus):
                continue
            try:
                gpu = open_fn(bus.path, card.address)
            except I2cError as exc:
                log.debug("%s: %s", card.name, exc)
                continue
            try:
                if gpu.probe():
                    devices[serial] = GpuDevice(serial, card, bus)
            except I2cError as exc:
                log.debug("%s did not answer: %s", card.name, exc)
            finally:
                gpu.close()
    return devices


def connect(device: GpuDevice) -> Fusion2Gpu:
    return Fusion2Gpu(I2cDevice(device.bus.path, device.card.address))


def default_store_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "olh-client" / "gpu-lighting.json"


class LightingStore:
    """The lighting the client last set on each card, in a JSON file: the cards cannot be read."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_store_path()

    def _read(self) -> dict[str, dict]:
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}

    def load(self, serial: str) -> Lighting | None:
        data = self._read().get(serial)
        if not isinstance(data, dict):
            return None
        try:
            lighting = Lighting(
                mode=int(data["mode"]), brightness=int(data["brightness"]), speed=int(data["speed"]),
                zones=tuple(tuple(int(c) for c in color) for color in data["zones"]),
                palette=tuple(tuple(int(c) for c in color) for color in data["palette"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        default = Lighting()
        colors = lighting.zones + lighting.palette
        if (lighting.mode not in MODE_BY_VALUE or len(lighting.zones) != len(default.zones)
                or len(lighting.palette) != len(default.palette)
                or not all(len(color) == 3 and all(0 <= c <= 255 for c in color) for color in colors)):
            return None
        return lighting

    def save(self, serial: str, lighting: Lighting) -> None:
        data = self._read()
        data[serial] = asdict(lighting)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=1))
        except OSError as exc:
            log.warning("Cannot store the lighting in %s: %s", self.path, exc)
