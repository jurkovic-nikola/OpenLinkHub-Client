from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QObject

from olhclient.api.models import MouseState

if TYPE_CHECKING:
    from olhclient.core.session import DeviceSession


class FeatureController(QObject):
    """State and actions for one feature of the selected device."""

    def __init__(self, session: DeviceSession):
        super().__init__(session)
        self.session = session

    def update(self, state: MouseState) -> None:
        """Called whenever fresh device data arrived."""
        raise NotImplementedError

    def write(self, call: Callable[[], Any], success: str, *, done: Callable[[bool], None] | None = None) -> None:
        """Run a write on the worker, report the outcome and reload the device.

        The reload also runs after a failure, so the UI falls back to what the
        device really has. ``done(ok)`` is called before the reload.
        """

        def finished(_: Any) -> None:
            if done:
                done(True)
            self.session.report_message(success)
            self.session.reload()

        def failed(exc: Exception) -> None:
            if done:
                done(False)
            self.session.report_error(exc)
            self.session.reload()

        self.session.worker.submit(call, on_done=finished, on_error=failed, owner=self)
