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

    def changed_stages(self, values: list[Any]) -> dict[int, int]:
        """Map of stage index -> new value for every stage that differs from the device."""
        current = self._stages.items()
        return {
            stage["stageIndex"]: int(value)
            for stage, value in zip(current, values)
            if int(value) != stage["value"]
        }

    @Slot("QVariantList")
    def save(self, values: list[Any]) -> None:
        """Save stage values, given in model order. Unchanged stages are not sent."""
        changes = self.changed_stages(values)
        if not changes:
            # The server answers "unable to change" when nothing changed; skip the round trip.
            self.session.report_message("No DPI changes to save")
            return
        out_of_range = [v for v in changes.values() if not self._min <= v <= self._max]
        if out_of_range:
            self.session.report_message(f"DPI must be between {self._min} and {self._max}", error=True)
            return
        self._set_saving(True)
        self.session.worker.submit(
            lambda: self.session.api.save_dpi(self.session.serial, changes),
            on_done=lambda _: self._saved(),
            on_error=self._save_failed,
            owner=self,
        )

    def _saved(self) -> None:
        self._set_saving(False)
        self.session.report_message("DPI stages saved")
        self.session.reload()

    def _save_failed(self, exc: Exception) -> None:
        self._set_saving(False)
        self.session.report_error(exc)

    def _set_saving(self, value: bool) -> None:
        if value != self._saving:
            self._saving = value
            self.savingChanged.emit()
