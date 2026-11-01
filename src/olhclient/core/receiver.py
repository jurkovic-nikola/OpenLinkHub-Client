"""The Slipstream receiver shown in the UI (iCUE: Settings > Device Settings)."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from olhclient.api.client import ApiClient, ApiError
from olhclient.api.models import ReceiverState
from olhclient.core.worker import Worker

#: A new polling rate makes the receiver restart: it drops off USB, and OpenLinkHub only
#: lists it again ~9 s later (measured on a Slipstream 2b00). This long after a change the
#: client keeps the receiver page open instead of moving to another device.
#: OpenLinkHub answers "OK" once the command is sent; it does not check that the receiver took it.
RESTART_GRACE_S = 20.0


class ReceiverSession(QObject):
    stateChanged = Signal()
    busyChanged = Signal()
    #: text, is_error
    message = Signal(str, bool)

    def __init__(self, api: ApiClient, worker: Worker, state: ReceiverState, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.worker = worker
        self.state = state
        self._reloading = False
        self._busy = False
        self._changed_at: float | None = None

    @property
    def serial(self) -> str:
        return self.state.serial

    @property
    def may_be_restarting(self) -> bool:
        """The polling rate changed moments ago, so the receiver may be briefly unlisted."""
        return self._changed_at is not None and time.monotonic() - self._changed_at < RESTART_GRACE_S

    def reload(self) -> None:
        if self._reloading:
            return
        self._reloading = True
        serial = self.serial

        def fetch() -> ReceiverState:
            return ReceiverState.from_json(self.api.get_receiver(serial))

        self.worker.submit(fetch, on_done=self._reloaded, on_error=self._reload_failed, owner=self)

    def _reloaded(self, state: ReceiverState) -> None:
        self._reloading = False
        self._apply(state)

    def _reload_failed(self, exc: Exception) -> None:
        self._reloading = False
        self.report_error(exc)

    def _apply(self, state: ReceiverState) -> None:
        self.state = state
        self.stateChanged.emit()

    def report_error(self, exc: Exception) -> None:
        self.message.emit(exc.message if isinstance(exc, ApiError) else str(exc), True)

    # -- QML API -----------------------------------------------------------

    @Property(str, notify=stateChanged)
    def serialNumber(self) -> str:
        return self.state.serial

    @Property(str, notify=stateChanged)
    def product(self) -> str:
        return self.state.product or "SLIPSTREAM receiver"

    @Property(str, notify=stateChanged)
    def firmware(self) -> str:
        return self.state.firmware

    @Property(int, notify=stateChanged)
    def pollingRate(self) -> int:
        return self.state.polling_rate

    @Property("QVariantList", notify=stateChanged)
    def pollingRates(self) -> list[dict[str, Any]]:
        return [{"value": value, "text": text} for value, text in self.state.polling_rates.items()]

    @Property("QVariantList", notify=stateChanged)
    def pairedDevices(self) -> list[dict[str, Any]]:
        return [{"productId": d.product_id, "product": d.product, "serial": d.serial} for d in self.state.paired]

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot()
    def refresh(self) -> None:
        self.reload()

    @Slot(int)
    def setPollingRate(self, value: int) -> None:
        if self._busy or value == self.state.polling_rate:
            return
        text = self.state.polling_rates.get(value)
        if text is None:
            self.message.emit("Invalid polling rate", True)
            return
        serial = self.serial
        self._set_busy(True)

        def done(_: Any) -> None:
            self._set_busy(False)
            self._changed_at = time.monotonic()
            # Show the new value right away: a receiver that restarts cannot be read for a while.
            self._apply(replace(self.state, polling_rate=value))
            self.message.emit(f"Polling rate {text} sent to the receiver", False)

        def failed(exc: Exception) -> None:
            self._set_busy(False)
            self.report_error(exc)
            self.stateChanged.emit()  # the combo box shows the rejected value
            self.reload()

        self.worker.submit(
            lambda: self.api.set_setting(serial, "mouse/pollingRate", {"pollingRate": value}),
            on_done=done, on_error=failed, owner=self
        )

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()
