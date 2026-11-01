"""The Slipstream receiver shown in the UI (iCUE: Settings > Device Settings)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from olhclient.api.client import ApiClient, ApiError
from olhclient.api.models import ReceiverState
from olhclient.core.worker import Worker

#: A new polling rate restarts the receiver; OpenLinkHub needs 5-8 s to bring
#: it and its paired devices back. Until then the receiver is not listed.
RESTART_GRACE_MS = 12000


class ReceiverSession(QObject):
    stateChanged = Signal()
    busyChanged = Signal()
    restartingChanged = Signal()
    #: text, is_error
    message = Signal(str, bool)

    def __init__(self, api: ApiClient, worker: Worker, state: ReceiverState, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.worker = worker
        self.state = state
        self._reloading = False
        self._busy = False
        self._restarting = False
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.setInterval(RESTART_GRACE_MS)
        self._restart_timer.timeout.connect(self._restarted)

    @property
    def serial(self) -> str:
        return self.state.serial

    def reload(self) -> None:
        if self._reloading or self._restarting:
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

    @Property(bool, notify=restartingChanged)
    def restarting(self) -> bool:
        return self._restarting

    @Slot()
    def refresh(self) -> None:
        self.reload()

    @Slot(int)
    def setPollingRate(self, value: int) -> None:
        if self._busy or self._restarting or value == self.state.polling_rate:
            return
        text = self.state.polling_rates.get(value)
        if text is None:
            self.message.emit("Invalid polling rate", True)
            return
        serial = self.serial
        self._set_busy(True)

        def done(_: Any) -> None:
            self._set_busy(False)
            # The receiver is gone until it restarted, so show the new value right away.
            self._apply(replace(self.state, polling_rate=value))
            self._set_restarting(True)
            self._restart_timer.start()
            self.message.emit(f"USB receiver polling rate set to {text}. The receiver restarts…", False)

        def failed(exc: Exception) -> None:
            self._set_busy(False)
            self.report_error(exc)
            self.stateChanged.emit()  # the combo box shows the rejected value
            self.reload()

        self.worker.submit(
            lambda: self.api.set_setting(serial, "mouse/pollingRate", {"pollingRate": value}),
            on_done=done, on_error=failed, owner=self
        )

    def _restarted(self) -> None:
        self._set_restarting(False)
        self.reload()

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    def _set_restarting(self, value: bool) -> None:
        if value != self._restarting:
            self._restarting = value
            self.restartingChanged.emit()
