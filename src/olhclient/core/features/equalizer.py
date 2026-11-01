from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from olhclient.api.models import DeviceState
from olhclient.core.features.base import FeatureController

#: dB range OpenLinkHub accepts per band; values outside become 0
MIN_DB, MAX_DB = -12, 12


def band_title(name: str) -> str:
    """OpenLinkHub names bands by frequency ("32", "1K"); add the unit."""
    if name[:-1].isdigit() and name[-1:].upper() == "K":
        return f"{name[:-1]} kHz"
    return f"{name} Hz" if name.isdigit() else name


class EqualizerController(FeatureController):
    """Headset equalizer bands, edited as a draft and saved together."""

    bandsChanged = Signal()
    savingChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._bands: list[dict[str, Any]] = []
        self._saving = False

    @classmethod
    def supports(cls, state: DeviceState) -> bool:
        return bool(state.equalizer) and state.kind.api == "headset"

    def update(self, state: DeviceState) -> None:
        bands = [{"index": b.index, "name": band_title(b.name), "value": b.value} for b in state.equalizer]
        if bands != self._bands:
            self._bands = bands
            self.bandsChanged.emit()

    @Property("QVariantList", notify=bandsChanged)
    def bands(self) -> list[dict[str, Any]]:
        return self._bands

    @Property(int, constant=True)
    def minDb(self) -> int:
        return MIN_DB

    @Property(int, constant=True)
    def maxDb(self) -> int:
        return MAX_DB

    @Property(bool, notify=savingChanged)
    def saving(self) -> bool:
        return self._saving

    @Slot("QVariantList")
    def save(self, values: list[Any]) -> None:
        """New dB per band, in band order. All bands are sent: the server wants the full set."""
        if len(values) != len(self._bands):
            return
        new = {band["index"]: round(float(v), 1) for band, v in zip(self._bands, values)}
        if all(new[b["index"]] == b["value"] for b in self._bands):
            self.session.report_message("No equalizer changes to save")
            return
        if any(not MIN_DB <= v <= MAX_DB for v in new.values()):
            self.session.report_message(f"Bands must be between {MIN_DB} and {MAX_DB} dB", error=True)
            return
        serial = self.session.serial
        self._set_saving(True)
        self.write(lambda: self.session.api.set_equalizer(serial, new), "Equalizer saved",
                   done=lambda ok: self._set_saving(False))

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()
