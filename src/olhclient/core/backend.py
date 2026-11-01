"""Root object exposed to QML: connection, device list and the selected device."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from olhclient.api.client import ApiClient, ApiError
from olhclient.api.models import MouseState, ReceiverState
from olhclient.core.artwork import lit, zone_colors
from olhclient.core.listmodel import DictListModel
from olhclient.core.receiver import ReceiverSession
from olhclient.core.session import QML_DIR, DeviceSession, file_url
from olhclient.core.worker import Worker
from olhclient.devices.base import DeviceModule
from olhclient.devices.registry import Registry

DEVICE_ROLES = ("serial", "product", "name", "thumbnail", "battery")
RECEIVER_THUMBNAIL = QML_DIR / "images" / "slipstream.svg"


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
        # serial -> thumbnail in the mouse's lighting colours, as last seen
        self._thumbnails: dict[str, str] = {}
        self._receivers: dict[str, str] = {}
        self._session: DeviceSession | None = None
        self._receiver: ReceiverSession | None = None
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
            try:
                receivers = self.api.list_receivers()
            except ApiError:
                receivers = {}
            return {"mice": mice, "new": new, "battery": battery, "receivers": receivers}

        self.worker.submit(poll, on_done=self._polled, on_error=self._poll_failed)

    def _polled(self, result: dict[str, Any]) -> None:
        self._refreshing = False
        self._set_connected(True, f"Connected to {self.api.base_url}")
        mice: dict[str, str] = result["mice"]
        self._receivers = result["receivers"]

        for serial, device in sorted(result["new"].items()):
            try:
                self._modules[serial] = self.registry.match(device)
            except LookupError:
                continue
            colors = zone_colors(MouseState.from_json(device))
            module = self._modules[serial]
            self._thumbnails[serial] = file_url(lit(module.layout.thumbnail, colors, module.missing_buttons))
            if self._session is None and self._receiver is None:
                self._open_session(serial, device)
        for gone in set(self._modules) - set(mice):
            del self._modules[gone]
            self._thumbnails.pop(gone, None)

        mouse_items = [
            {
                "serial": serial,
                "product": product,
                "name": self._modules[serial].name,
                "thumbnail": self._thumbnails[serial],
                "battery": result["battery"].get(serial, -1),
            }
            for serial, product in sorted(mice.items())
            if serial in self._modules
        ]
        receiver_items = [
            {
                "serial": serial,
                "product": f"{product} RECEIVER",
                "name": "Slipstream receiver",
                "thumbnail": file_url(RECEIVER_THUMBNAIL),
                "battery": -1,
            }
            for serial, product in sorted(self._receivers.items())
        ]
        self._devices.set_items(mouse_items + receiver_items)

        if self._session is not None:
            if self._session.serial in self._modules:
                self._session.reload()
            else:
                self._select_first()
        elif self._receiver is not None:
            if self._receiver.serial in self._receivers:
                self._receiver.reload()
            elif not self._receiver.restarting:  # while restarting it is briefly unlisted
                self._select_first()
        elif self._devices.count:  # no mouse session was opened, e.g. only a receiver is connected
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
        session.stateChanged.connect(lambda: self._update_thumbnail(serial, session.thumbnail))
        self._set_session(session)
        if macros is None:
            session.reload()  # also loads macro names

    def _update_thumbnail(self, serial: str, thumbnail: str) -> None:
        """Show the selected mouse's tile in its current lighting colours right away."""
        if self._thumbnails.get(serial) == thumbnail or serial not in self._modules:
            return
        self._thumbnails[serial] = thumbnail
        self._devices.set_items(
            {**item, "thumbnail": thumbnail} if item["serial"] == serial else item for item in self._devices.items()
        )

    def _open_receiver(self, data: dict[str, Any]) -> None:
        receiver = ReceiverSession(self.api, self.worker, ReceiverState.from_json(data), self)
        receiver.message.connect(self.notify)
        self._set_session(None, receiver)

    def _set_session(self, session: DeviceSession | None, receiver: ReceiverSession | None = None) -> None:
        """Show ``session`` (a mouse) or ``receiver``; at most one is selected."""
        for old in (self._session, self._receiver):
            if old is not None:
                old.deleteLater()
        self._session = session
        self._receiver = receiver
        self.sessionChanged.emit()

    def _select_first(self) -> None:
        self._set_session(None)
        if self._devices.count:
            self.selectDevice(self._devices.get(0)["serial"])

    @Slot(str)
    def selectDevice(self, serial: str) -> None:
        if serial == self.selectedSerial:
            return
        if serial in self._receivers:
            self.worker.submit(self.api.get_receiver, serial, on_done=self._open_receiver)
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

    @Property(QObject, notify=sessionChanged)
    def receiver(self) -> ReceiverSession | None:
        return self._receiver

    @Property(str, notify=sessionChanged)
    def selectedSerial(self) -> str:
        current = self._session or self._receiver
        return current.serial if current is not None else ""

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
