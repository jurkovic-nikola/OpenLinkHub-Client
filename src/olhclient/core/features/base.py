from __future__ import annotations

from typing import TYPE_CHECKING

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
