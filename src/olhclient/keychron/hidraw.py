"""Linux hidraw access without a native library.

A hidraw node is a character device: write an output report, read input
reports. What it is (vendor, product, report descriptor) comes from sysfs, which
needs no permissions; opening ``/dev/hidrawN`` needs a udev rule (see README).
"""

from __future__ import annotations

import errno
import os
import select
import time
from dataclasses import dataclass
from pathlib import Path

SYSFS_HIDRAW = Path("/sys/class/hidraw")
DEV_DIR = Path("/dev")

#: VIA's raw HID collection: usage page 0xFF60, usage 0x61
VIA_USAGE_PAGE = 0xFF60
VIA_USAGE = 0x61


class HidError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class HidInterface:
    """One hidraw node of a USB device."""

    path: str  # /dev/hidrawN
    vendor_id: int
    product_id: int
    name: str
    uniq: str  # serial number, often empty for keyboards
    phys: str  # e.g. usb-0000:00:14.0-2/input1; stable per USB port


def _uevent(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(errors="replace").splitlines():
        key, _, value = line.partition("=")
        values[key] = value
    return values


def has_usage(descriptor: bytes, usage_page: int, usage: int) -> bool:
    """Whether the report descriptor declares ``usage`` on ``usage_page``.

    Only short items are walked; that is all a VIA descriptor uses.
    """
    page = None
    i = 0
    while i < len(descriptor):
        prefix = descriptor[i]
        if prefix == 0xFE:  # long item: skip it
            if i + 1 >= len(descriptor):
                break
            i += 3 + descriptor[i + 1]
            continue
        size = (0, 1, 2, 4)[prefix & 0x03]
        value = int.from_bytes(descriptor[i + 1:i + 1 + size], "little")
        tag = prefix & 0xFC
        if tag == 0x04:  # Usage Page (global)
            page = value
        elif tag == 0x08 and page == usage_page and value & 0xFFFF == usage:  # Usage (local)
            # a 4-byte usage carries its own page in the high half
            if size < 4 or value >> 16 in (0, usage_page):
                return True
        i += 1 + size
    return False


def enumerate_devices(vendor_id: int | None = None, *, usage_page: int = VIA_USAGE_PAGE, usage: int = VIA_USAGE,
                      sysfs: Path = SYSFS_HIDRAW, dev_dir: Path = DEV_DIR) -> list[HidInterface]:
    """hidraw nodes with the given collection, optionally of one vendor."""
    found = []
    try:
        nodes = sorted(sysfs.iterdir(), key=lambda p: (len(p.name), p.name))
    except OSError:
        return []
    for node in nodes:
        try:
            info = _uevent(node / "device" / "uevent")
            bus, vendor, product = (int(part, 16) for part in info.get("HID_ID", "").split(":"))
        except (OSError, ValueError):
            continue
        if bus != 0x03 or (vendor_id is not None and vendor != vendor_id):  # 0x03: USB
            continue
        try:
            descriptor = (node / "device" / "report_descriptor").read_bytes()
        except OSError:
            continue
        if not has_usage(descriptor, usage_page, usage):
            continue
        found.append(HidInterface(
            path=str(dev_dir / node.name), vendor_id=vendor, product_id=product,
            name=info.get("HID_NAME", ""), uniq=info.get("HID_UNIQ", ""), phys=info.get("HID_PHYS", ""),
        ))
    return found


class HidrawDevice:
    """An open hidraw node. Reports are written with report id 0 (VIA has no report ids)."""

    def __init__(self, path: str, report_size: int = 32):
        self.path = path
        self.report_size = report_size
        try:
            self._fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        except PermissionError as exc:
            raise HidError(f"No permission to open {path}; install the udev rule for Keychron keyboards "
                           "(see the README)") from exc
        except FileNotFoundError as exc:  # the Flatpak sandbox hides /dev without --device=all
            raise HidError(f"{path} is not accessible from here") from exc
        except OSError as exc:
            raise HidError(f"Cannot open {path}: {exc.strerror}") from exc

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> HidrawDevice:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _check_open(self) -> None:
        # a closed descriptor number may already belong to another file
        if self._fd < 0:
            raise HidError(f"{self.path} is closed")

    def write(self, report: bytes) -> None:
        self._check_open()
        data = bytes([0]) + report.ljust(self.report_size, b"\0")[:self.report_size]
        try:
            os.write(self._fd, data)
        except OSError as exc:
            raise HidError(f"Cannot write to {self.path}: {exc.strerror}") from exc

    def read(self, timeout: float) -> bytes | None:
        """The next input report, or None after ``timeout`` seconds."""
        self._check_open()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            ready, _, _ = select.select([self._fd], [], [], remaining)
            if not ready:
                return None
            try:
                return os.read(self._fd, 64)
            except BlockingIOError:
                continue
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise HidError(f"Cannot read from {self.path}: {exc.strerror}") from exc
