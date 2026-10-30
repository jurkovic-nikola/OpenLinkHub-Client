"""Root object exposed to QML: connection, device list and the selected device."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from olhclient.api.client import ApiClient, ApiError
from olhclient.api.models import MouseState
from olhclient.core.listmodel import DictListModel
from olhclient.core.session import DeviceSession, file_url
from olhclient.core.worker import Worker
from olhclient.devices.base import DeviceModule
from olhclient.devices.registry import Registry

DEVICE_ROLES = ("serial", "product", "name", "thumbnail", "battery")


class Backend(QObject):
    connectedChanged = Signal()
    statusChanged = Signal()
    sessionChanged = Signal()
    authRequiredChanged = Signal()
    busyChanged = Signal()
    #: text, is_error
    notify = Signal(str, bool)

    def __init__(self, api: ApiClient, registry: Registry, *, poll_interval: float = 5.0,
                 worker: Worker | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.api = api
        self.registry = registry
        self.worker = worker or Worker(self)
        self.worker.failed.connect(self._report_error)
        self.worker.busyChanged.connect(self.busyChanged)
        self._devices = DictListModel(DEVICE_ROLES, self)
        self._modules: dict[str, DeviceModule] = {}
        self._session: DeviceSession | None = None
        self._connected = False
        self._status = "Connecting…"
        self._auth_required = False
        self._refreshing = False
        self._timer = QTimer(self)
        self._timer.setInterval(int(poll_interval * 1000))
        self._timer.timeout.connect(self.refresh)

    def start(self) -> None:
        self.refresh()
        self._timer.start()

    # -- polling -----------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        if self._refreshing or self._auth_required:
            return
        self._refreshing = True
        known = set(self._modules)

        def poll() -> dict[str, Any]:
            mice = self.api.list_mice()
            # Only new devices need their full JSON to pick a module.
            new = {serial: self.api.get_device(serial) for serial in mice if serial not in known}
            try:
                battery = self.api.battery_levels()
            except ApiError:
                battery = {}
            return {"mice": mice, "new": new, "battery": battery}

        self.worker.submit(poll, on_done=self._polled, on_error=self._poll_failed)

    def _polled(self, result: dict[str, Any]) -> None:
        self._refreshing = False
        self._set_connected(True, f"Connected to {self.api.base_url}")
        mice: dict[str, str] = result["mice"]

        for serial, device in sorted(result["new"].items()):
            try:
                self._modules[serial] = self.registry.match(device)
            except LookupError:
                continue
            if self._session is None:
                self._open_session(serial, device)
        for gone in set(self._modules) - set(mice):
            del self._modules[gone]

        self._devices.set_items(
            {
                "serial": serial,
                "product": product,
                "name": self._modules[serial].name,
                "thumbnail": file_url(self._modules[serial].layout.thumbnail),
                "battery": result["battery"].get(serial, -1),
            }
            for serial, product in sorted(mice.items())
            if serial in self._modules
        )

        if self._session is not None:
            if self._session.serial in self._modules:
                self._session.reload()
            else:
                self._set_session(None)
                if self._devices.count:
                    self.selectDevice(self._devices.get(0)["serial"])

    def _poll_failed(self, exc: Exception) -> None:
        self._refreshing = False
        if isinstance(exc, ApiError) and exc.auth_required:
            self._set_auth_required(True)
            self._set_connected(False, "Login required")
            return
        self._set_connected(False, exc.message if isinstance(exc, ApiError) else str(exc))

    # -- sessions ----------------------------------------------------------

    def _open_session(self, serial: str, device: dict[str, Any], macros: dict[int, str] | None = None) -> None:
        session = DeviceSession(self.api, self.worker, self._modules[serial], MouseState.from_json(device), macros, self)
        session.message.connect(self.notify)
        self._set_session(session)
        if macros is None:
            session.reload()  # also loads macro names

    def _set_session(self, session: DeviceSession | None) -> None:
        if self._session is not None:
            self._session.deleteLater()
        self._session = session
        self.sessionChanged.emit()

    @Slot(str)
    def selectDevice(self, serial: str) -> None:
        if self._session is not None and self._session.serial == serial:
            return
        if serial not in self._modules:
            return

        def fetch() -> tuple[dict[str, Any], dict[int, str]]:
            return self.api.get_device(serial), self.api.macros()

        self.worker.submit(fetch, on_done=lambda r: self._open_session(serial, *r))

    # -- auth --------------------------------------------------------------

    @Slot(str, str)
    def login(self, username: str, password: str) -> None:
        def done(_: Any) -> None:
            self._set_auth_required(False)
            self.notify.emit("Logged in", False)
            self.refresh()

        self.worker.submit(self.api.login, username, password, on_done=done)

    # -- helpers -----------------------------------------------------------

    def _report_error(self, exc: Exception) -> None:
        self.notify.emit(exc.message if isinstance(exc, ApiError) else str(exc), True)

    def _set_connected(self, connected: bool, status: str) -> None:
        if connected != self._connected:
            self._connected = connected
            self.connectedChanged.emit()
        if status != self._status:
            self._status = status
            self.statusChanged.emit()

    def _set_auth_required(self, value: bool) -> None:
        if value != self._auth_required:
            self._auth_required = value
            self.authRequiredChanged.emit()

    # -- QML API -----------------------------------------------------------

    @Property(QObject, constant=True)
    def devices(self) -> DictListModel:
        return self._devices

    @Property(QObject, notify=sessionChanged)
    def session(self) -> DeviceSession | None:
        return self._session

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=authRequiredChanged)
    def authRequired(self) -> bool:
        return self._auth_required

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self.worker.busy

    @Property(str, constant=True)
    def serverUrl(self) -> str:
        return self.api.base_url
