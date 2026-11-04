"""A graphics card shown in the UI, its lighting driven over I2C instead of through OpenLinkHub.

:class:`GpuSession` offers the QML API of :class:`DeviceSession`, like
:class:`~olhclient.core.keychron.KeychronSession`. The card cannot be read, so it
shows what the client last set, kept in a :class:`LightingStore`.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from olhclient.api.models import DeviceKind
from olhclient.core.features.base import FeatureController
from olhclient.core.features.gpu import GpuLightingController
from olhclient.core.session import QML_DIR, file_url, kind_icon
from olhclient.core.worker import Worker
from olhclient.gpu.device import GpuDevice, LightingStore
from olhclient.gpu.fusion2 import Fusion2Gpu, Lighting

#: feature id -> (title, controller, list QML, editor QML), in display order
FEATURES = {
    "lighting": ("Lighting", GpuLightingController, "features/LightingList.qml", "features/GpuLightingEditor.qml"),
}


def error_text(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc)


class GpuSession(QObject):
    stateChanged = Signal()
    selectedButtonChanged = Signal()
    profileBusyChanged = Signal()
    #: text, is_error
    message = Signal(str, bool)

    def __init__(self, client: Fusion2Gpu, worker: Worker, device: GpuDevice, store: LightingStore,
                 parent: QObject | None = None):
        super().__init__(parent)
        self.client = client
        self.worker = worker
        self.device = device
        self.store = store
        self.lighting = store.load(device.serial) or Lighting()
        self._selected = ""
        self._controllers: dict[str, FeatureController] = {
            feature_id: controller(self) for feature_id, (_, controller, _, _) in FEATURES.items()
        }
        self._apply(self.lighting)

    @property
    def serial(self) -> str:
        return self.device.serial

    # -- state -------------------------------------------------------------

    def reload(self) -> None:
        """Nothing to read: the card cannot report its lighting."""

    def apply(self, lighting: Lighting) -> None:
        """Show and remember ``lighting``, after the card took it."""
        self.store.save(self.serial, lighting)
        self._apply(lighting)

    def _apply(self, lighting: Lighting) -> None:
        self.lighting = lighting
        for controller in self._controllers.values():
            controller.update(lighting)
        self.stateChanged.emit()

    # -- messages ----------------------------------------------------------

    def report_message(self, text: str, *, error: bool = False) -> None:
        self.message.emit(text, error)

    def report_error(self, exc: Exception) -> None:
        self.message.emit(error_text(exc), True)

    # -- QML API (that of DeviceSession) -------------------------------------

    @Property(str, constant=True)
    def serialNumber(self) -> str:
        return self.serial

    @Property(str, constant=True)
    def product(self) -> str:
        return self.device.name

    @Property(str, constant=True)
    def moduleId(self) -> str:
        return "gpu"

    @Property(str, constant=True)
    def kind(self) -> str:
        return DeviceKind.GPU.value

    @Property(str, constant=True)
    def kindTitle(self) -> str:
        return DeviceKind.GPU.title

    @Property(str, constant=True)
    def firmware(self) -> str:
        return ""

    @Property(bool, constant=True)
    def hasArtwork(self) -> bool:
        return False

    @Property(bool, constant=True)
    def hasKeyboardLayout(self) -> bool:
        return False

    @Property(bool, constant=True)
    def hasWebPage(self) -> bool:
        """OpenLinkHub does not know this card."""
        return False

    @Slot()
    def openInBrowser(self) -> None:
        pass

    @Property(str, constant=True)
    def profileName(self) -> str:
        return ""

    @Property("QStringList", constant=True)
    def profiles(self) -> list[str]:
        return []

    @Property(bool, constant=True)
    def connected(self) -> bool:
        return True

    @Property(int, constant=True)
    def battery(self) -> int:
        return -1

    @Property(str, constant=True)
    def connectionMode(self) -> str:
        return "PCI Express"

    @Property(str, constant=True)
    def thumbnail(self) -> str:
        return file_url(kind_icon(DeviceKind.GPU))

    @Property("QVariantList", constant=True)
    def views(self) -> list[dict[str, Any]]:
        return []

    @Property("QVariantList", constant=True)
    def buttonList(self) -> list[dict[str, Any]]:
        return []

    @Property("QVariantList", constant=True)
    def features(self) -> list[dict[str, Any]]:
        return [
            {"id": feature_id, "title": title, "listQml": file_url(QML_DIR / list_qml),
             "editorQml": file_url(QML_DIR / editor_qml)}
            for feature_id, (title, _, list_qml, editor_qml) in FEATURES.items()
        ]

    # QVariant, not QObject: PySide hands QML an invalid object for None, which crashes QML.
    @Slot(str, result="QVariant")
    def controller(self, feature_id: str) -> FeatureController | None:
        return self._controllers.get(feature_id)

    def _get_selected(self) -> str:
        return self._selected

    def _set_selected(self, name: str) -> None:
        if name != self._selected:
            self._selected = name
            self.selectedButtonChanged.emit()

    selectedButton = Property(str, _get_selected, _set_selected, notify=selectedButtonChanged)

    @Slot(str, result=bool)
    def isLocked(self, name: str) -> bool:
        return False

    @Slot()
    def refresh(self) -> None:
        self.reload()

    # The card has no OpenLinkHub user profiles; ProfilesPanel stays hidden.

    @Property(bool, constant=True)
    def profileBusy(self) -> bool:
        return False

    @Slot(str, result=str)
    def profileNameProblem(self, name: str) -> str:
        return "Not supported on this card"

    @Slot(str, result=bool)
    def canDeleteProfile(self, name: str) -> bool:
        return False

    @Slot(str)
    def switchProfile(self, name: str) -> None:
        pass

    @Slot(str)
    def createProfile(self, name: str) -> None:
        pass

    @Slot(str)
    def deleteProfile(self, name: str) -> None:
        pass
