"""Controller of a graphics card's lighting (see core/gpu.py).

LightingList binds to the same properties as on other devices; the editor is
``features/GpuLightingEditor.qml``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.core.features.base import FeatureController
from olhclient.core.listmodel import DictListModel
from olhclient.gpu.fusion2 import BRIGHTNESS_MAX, MODE_BY_VALUE, MODES, SPEED_MAX, Color, Lighting, Mode

if TYPE_CHECKING:
    from olhclient.core.gpu import GpuSession


def _hex(color: Color) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def _color(text: str) -> Color | None:
    value = text.lstrip("#")
    if len(value) != 6:
        return None
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return None


class GpuLightingController(FeatureController):
    """Mode, brightness, speed and colours. Every change applies at once; :meth:`saveToCard` keeps it."""

    session: GpuSession
    changed = Signal()

    def __init__(self, session: GpuSession):
        super().__init__(session)
        self._zones = DictListModel(("zoneIndex", "name", "color"), self)
        self._lighting: Lighting | None = None

    @classmethod
    def supports(cls, state: Any) -> bool:
        return True

    def update(self, lighting: Lighting) -> None:
        if lighting != self._lighting:
            self._lighting = lighting
            self._zones.set_items(
                {"zoneIndex": i, "name": name, "color": color} for i, (name, color) in enumerate(self._named_colors())
            )
            self.changed.emit()

    @property
    def _mode(self) -> Mode:
        return MODE_BY_VALUE[self._lighting.mode]

    def _named_colors(self) -> list[tuple[str, str]]:
        mode = self._mode
        if mode.zone_colors:
            return [(f"Zone {i + 1}", _hex(color)) for i, color in enumerate(self._lighting.zones)]
        return [(f"Colour {i + 1}", _hex(color)) for i, color in enumerate(self._lighting.palette[:mode.palette])]

    def _set(self, lighting: Lighting, success: str) -> None:
        """Always writes, even when nothing changed: the card may show something else than the client knows."""
        client = self.session.client

        def done(ok: bool) -> None:
            if ok:
                self.session.apply(lighting)
            else:  # nothing changed: drop what the user picked
                self.changed.emit()

        self.write(lambda: client.apply(lighting), success, done=done)

    # -- QML API (LightingList's part matches LightingController) -----------------

    @Property(bool, constant=True)
    def available(self) -> bool:
        return True

    @Property(QObject, constant=True)
    def zones(self) -> DictListModel:
        return self._zones

    @Property(int, notify=changed)
    def effect(self) -> int:
        return self._lighting.mode

    @Property(str, notify=changed)
    def effectTitle(self) -> str:
        return self._mode.title

    @Property("QVariantList", constant=True)
    def effects(self) -> list[dict[str, Any]]:
        return [{"value": int(mode.value), "text": mode.title} for mode in MODES]

    @Property(bool, notify=changed)
    def hasBrightness(self) -> bool:
        return self._mode.brightness

    @Property(int, notify=changed)
    def brightness(self) -> int:
        return round(self._lighting.brightness * 100 / BRIGHTNESS_MAX)

    @Property("QVariantList", constant=True)
    def brightnessModes(self) -> list[dict[str, Any]]:
        return []

    @Property(int, constant=True)
    def brightnessMode(self) -> int:
        return 0

    @Property(bool, notify=changed)
    def hasSpeed(self) -> bool:
        return self._mode.speed

    @Property(int, notify=changed)
    def speed(self) -> int:
        return self._lighting.speed

    @Property(int, constant=True)
    def speedMax(self) -> int:
        return SPEED_MAX

    @Property("QStringList", notify=changed)
    def colors(self) -> list[str]:
        """The colours the editor shows: one per zone, or the mode's own; none for cycling modes."""
        return [color for _, color in self._named_colors()]

    @Property(bool, notify=changed)
    def zoneColors(self) -> bool:
        return self._mode.zone_colors

    @Slot(int)
    def setEffect(self, value: int) -> None:
        mode = MODE_BY_VALUE.get(value)
        if mode is None:
            self.session.report_message(f"Unknown mode {value}", error=True)
            return
        self._set(replace(self._lighting, mode=mode.value), f"Mode set to {mode.title}")

    @Slot(int)
    def setBrightness(self, percent: int) -> None:
        if not 0 <= percent <= 100:
            self.session.report_message("Brightness must be between 0 and 100", error=True)
            return
        self._set(replace(self._lighting, brightness=round(percent * BRIGHTNESS_MAX / 100)),
                  f"Brightness set to {percent} %")

    @Slot(int)
    def setSpeed(self, speed: int) -> None:
        if not 0 <= speed <= SPEED_MAX:
            self.session.report_message(f"Speed must be between 0 and {SPEED_MAX}", error=True)
            return
        self._set(replace(self._lighting, speed=speed), f"Speed set to {speed}")

    @Slot(int, str)
    def setColor(self, index: int, text: str) -> None:
        """Colour ``index`` of :attr:`colors`, as ``#rrggbb``; index -1 sets them all."""
        color = _color(text)
        count = len(self.colors)
        if color is None or not -1 <= index < count:
            self.session.report_message(f"Invalid colour {text}", error=True)
            return
        indexes = range(count) if index < 0 else (index,)
        field = "zones" if self._mode.zone_colors else "palette"
        colors = list(getattr(self._lighting, field))
        for i in indexes:
            colors[i] = color
        self._set(replace(self._lighting, **{field: tuple(colors)}), "Colour set")

    @Slot()
    def saveToCard(self) -> None:
        client = self.session.client
        self.write(client.save, "Lighting saved on the card")

