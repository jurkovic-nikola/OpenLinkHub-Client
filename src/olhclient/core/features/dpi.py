from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from olhclient.api.models import MouseState
from olhclient.core.features.base import FeatureController
from olhclient.core.listmodel import DictListModel

STAGE_ROLES = ("stageIndex", "name", "value", "color", "sniper", "active")


class DpiController(FeatureController):
    rangeChanged = Signal()
    savingChanged = Signal()

    def __init__(self, session):
        super().__init__(session)
        self._stages = DictListModel(STAGE_ROLES, self)
        self._min = 100
        self._max = 0
        self._saving = False

    def update(self, state: MouseState) -> None:
        self._stages.set_items(
            {
                "stageIndex": stage.index,
                "name": stage.name,
                "value": stage.value,
                "color": stage.color,
                "sniper": stage.sniper,
                "active": stage.index == state.active_stage,
            }
            for stage in state.stages
        )
        if (state.min_dpi, state.max_dpi) != (self._min, self._max):
            self._min, self._max = state.min_dpi, state.max_dpi
            self.rangeChanged.emit()

    @Property(QObject, constant=True)
    def stages(self) -> DictListModel:
        return self._stages

    @Property(int, notify=rangeChanged)
    def minDpi(self) -> int:
        return self._min

    @Property(int, notify=rangeChanged)
    def maxDpi(self) -> int:
        return self._max

    @Property(int, constant=True)
    def step(self) -> int:
        return self.session.module.dpi_step

    @Property(bool, notify=savingChanged)
    def saving(self) -> bool:
        return self._saving

    def changed_colors(self, colors: list[Any]) -> dict[int, str]:
        """Map of stage index -> new ``#rrggbb`` for every stage whose colour differs."""
        return {
            stage["stageIndex"]: str(color).lower()
            for stage, color in zip(self._stages.items(), colors)
            if str(color).lower() != stage["color"].lower()
        }

    def changed_stages(self, values: list[Any]) -> dict[int, int]:
        """Map of stage index -> new value for every stage that differs from the device."""
        current = self._stages.items()
        return {
            stage["stageIndex"]: int(value)
            for stage, value in zip(current, values)
            if int(value) != stage["value"]
        }

    @Slot("QVariantList", "QVariantList")
    def save(self, values: list[Any], colors: list[Any] | None = None) -> None:
        """Save stage values and colours, given in model order. Unchanged stages are not sent."""
        changes = self.changed_stages(values)
        color_changes = self.changed_colors(colors or [])
        if not changes and not color_changes:
            # The server answers "unable to change" when nothing changed; skip the round trip.
            self.session.report_message("No DPI changes to save")
            return
        out_of_range = [v for v in changes.values() if not self._min <= v <= self._max]
        if out_of_range:
            self.session.report_message(f"DPI must be between {self._min} and {self._max}", error=True)
            return
        api, serial = self.session.api, self.session.serial

        def call() -> None:
            if changes:
                api.save_dpi(serial, changes)
            if color_changes:
                api.save_dpi_colors(serial, color_changes)

        what = " and ".join(part for part, changed in (("stages", changes), ("colours", color_changes)) if changed)
        self._set_saving(True)
        self.write(call, f"DPI {what} saved", done=lambda ok: self._set_saving(False))

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()
