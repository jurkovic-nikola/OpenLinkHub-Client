"""Linux I2C access through ``/dev/i2c-N`` (the ``i2c-dev`` module), without a native library.

Which PCI device a bus belongs to comes from sysfs, which needs no permissions;
opening ``/dev/i2c-N`` needs the ``i2c`` group or a udev rule (see README).
"""

from __future__ import annotations

import errno
import fcntl
import os
from dataclasses import dataclass
from pathlib import Path

SYSFS_I2C = Path("/sys/bus/i2c/devices")
DEV_DIR = Path("/dev")

#: ioctl that sets the address later reads and writes go to (linux/i2c-dev.h)
I2C_SLAVE = 0x0703


class I2cError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class I2cBus:
    """An I2C adapter, with the PCI device it belongs to."""

    number: int
    name: str  # e.g. "AMDGPU DM i2c OEM bus"
    pci_slot: str  # e.g. 0000:0a:00.0
    vendor_id: int
    device_id: int
    subsystem_vendor_id: int
    subsystem_device_id: int

    @property
    def path(self) -> str:
        return str(DEV_DIR / f"i2c-{self.number}")


def _hex(path: Path) -> int:
    return int(path.read_text().strip(), 16)


def _pci_ancestor(path: Path) -> Path | None:
    """The nearest directory above ``path`` that is a PCI device (has vendor and device ids)."""
    for parent in path.parents:
        if (parent / "vendor").is_file() and (parent / "device").is_file():
            return parent
    return None


def enumerate_buses(sysfs: Path = SYSFS_I2C) -> list[I2cBus]:
    """I2C buses that belong to a PCI device, as OpenRGB finds them."""
    buses = []
    entries = [entry for entry in sysfs.glob("i2c-*") if entry.name[4:].isdigit()]
    for entry in sorted(entries, key=lambda entry: int(entry.name[4:])):
        number = entry.name[4:]
        try:
            name = (entry / "name").read_text().strip()
            if name == "DPMST":  # DisplayPort MST hubs come and go
                continue
            pci = _pci_ancestor(entry.resolve())
            if pci is None:
                continue
            buses.append(I2cBus(int(number), name, pci.name, _hex(pci / "vendor"), _hex(pci / "device"),
                                _hex(pci / "subsystem_vendor"), _hex(pci / "subsystem_device")))
        except (OSError, ValueError):
            continue
    return buses


class I2cDevice:
    """One device on a bus; reads and writes are plain I2C transfers, as OpenRGB's ``i2c_write_block``."""

    def __init__(self, path: str, address: int):
        try:
            self._fd = os.open(path, os.O_RDWR)
        except PermissionError:
            raise I2cError(f"No permission to open {path}; see the README (Graphics cards)") from None
        except FileNotFoundError:
            raise I2cError(f"{path} does not exist; load the i2c-dev module") from None
        except OSError as exc:
            raise I2cError(f"Cannot open {path}: {exc.strerror}") from None
        self.path = path
        self.address = address
        try:
            fcntl.ioctl(self._fd, I2C_SLAVE, address)
        except OSError as exc:
            os.close(self._fd)
            if exc.errno == errno.EBUSY:
                raise I2cError(f"Address 0x{address:02x} on {path} is in use by a kernel driver") from None
            raise I2cError(f"Cannot select address 0x{address:02x} on {path}: {exc.strerror}") from None

    def write(self, data: bytes) -> None:
        try:
            os.write(self._fd, data)
        except OSError as exc:
            raise I2cError(f"Writing to {self.path} failed: {exc.strerror}") from None

    def read(self, size: int) -> bytes:
        try:
            return os.read(self._fd, size)
        except OSError as exc:
            raise I2cError(f"Reading from {self.path} failed: {exc.strerror}") from None

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1
