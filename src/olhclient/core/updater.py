"""Update check, download and install, exposed to QML as ``updater``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Property, Signal, Slot

from olhclient import __version__, update
from olhclient.core.worker import Worker

# idle -> checking -> upToDate | available -> downloading -> installing -> installed; any step may end in error


class Updater(QObject):
    changed = Signal()
    progressChanged = Signal()

    #: received, total; emitted from the download thread
    _downloaded = Signal(int, int)
    #: emitted from the download thread once the bundle is downloaded
    _installing = Signal()

    def __init__(self, worker: Worker | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.worker = worker or Worker(self)
        self._state = "idle"
        self._message = ""
        self._release: dict[str, Any] | None = None
        self._dialog_open = False
        self._quiet = False
        self._cancel = False
        self._received = 0
        self._total = 0
        self._downloaded.connect(self._set_progress)
        self._installing.connect(lambda: self._set_state("installing"))

    # -- check ---------------------------------------------------------------

    @Slot()
    def check(self) -> None:
        """Check and show the result."""
        self._start_check(quiet=False)

    @Slot()
    def checkQuietly(self) -> None:
        """Check at startup; only open the dialog when there is an update."""
        self._start_check(quiet=True)

    def _start_check(self, quiet: bool) -> None:
        if self._state in ("checking", "downloading", "installing"):
            self._open_dialog(not quiet)
            return
        self._quiet = quiet
        self._set_state("checking")
        self._open_dialog(not quiet)
        self.worker.submit(update.latest_release, on_done=self._checked, on_error=self._failed)

    def _checked(self, release: dict[str, Any]) -> None:
        self._release = release
        if not update.is_newer(release):
            self._set_state("upToDate", f"You are on the latest version ({__version__}).")
        elif self.canInstall and update.update_asset(release) is None:
            self._set_state("error", f"Version {self.latestVersion} has no Flatpak bundle; "
                                     "download it from the release page.")
        else:
            self._set_state("available")
            self._open_dialog(self._quiet)  # a manual check shows it already, unless it was closed

    # -- download and install -----------------------------------------------

    @Slot()
    def install(self) -> None:
        asset = update.update_asset(self._release or {})
        if self._state != "available" or not self.canInstall or asset is None:
            return
        self._cancel = False
        self._set_progress(0, int(asset.get("size") or 0))
        self._set_state("downloading")
        target = update.download_dir() / asset["name"]

        def run() -> None:
            bundle = update.download(asset["browser_download_url"], target, self._downloaded.emit,
                                     lambda: self._cancel)
            self._installing.emit()
            update.install(bundle)

        self.worker.submit(run, on_done=lambda _: self._set_state("installed"), on_error=self._failed)

    @Slot()
    def cancel(self) -> None:
        if self._state == "downloading":
            self._cancel = True
        self.close()

    @Slot()
    def restart(self) -> None:
        if self._state != "installed":
            return
        try:
            update.restart()
        except OSError as exc:
            self._set_state("error", f"Cannot start the new version: {exc}")
            return
        QCoreApplication.quit()

    def _failed(self, exc: Exception) -> None:
        if isinstance(exc, update.Cancelled):
            self._set_state("available")
            return
        self._set_state("error", str(exc))
        self._open_dialog(not self._quiet)

    # -- dialog ----------------------------------------------------------------

    @Slot()
    def open(self) -> None:
        self._open_dialog(True)

    @Slot()
    def close(self) -> None:
        if self._dialog_open:
            self._dialog_open = False
            self.changed.emit()

    def _open_dialog(self, value: bool) -> None:
        if value and not self._dialog_open:
            self._dialog_open = True
            self.changed.emit()

    # -- helpers -----------------------------------------------------------------

    def _set_state(self, state: str, message: str = "") -> None:
        self._state = state
        self._message = message
        self.changed.emit()

    @Slot(int, int)
    def _set_progress(self, received: int, total: int) -> None:
        self._received, self._total = received, total or self._total
        self.progressChanged.emit()

    # -- QML API -----------------------------------------------------------------

    @Property(str, notify=changed)
    def state(self) -> str:
        return self._state

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Property(bool, notify=changed)
    def dialogOpen(self) -> bool:
        return self._dialog_open

    @Property(bool, notify=changed)
    def updateAvailable(self) -> bool:
        return self._release is not None and update.is_newer(self._release)

    @Property(bool, constant=True)
    def canInstall(self) -> bool:
        return update.can_install()

    @Property(str, constant=True)
    def currentVersion(self) -> str:
        return __version__

    @Property(str, notify=changed)
    def latestVersion(self) -> str:
        return (self._release or {}).get("tag_name", "").lstrip("vV")

    @Property(str, notify=changed)
    def releaseUrl(self) -> str:
        return (self._release or {}).get("html_url") or update.RELEASES_PAGE

    @Property(float, notify=progressChanged)
    def progress(self) -> float:
        return self._received / self._total if self._total else 0.0

    @Property(str, notify=progressChanged)
    def progressText(self) -> str:
        mib = 1024 * 1024
        if self._total:
            return f"{self._received / mib:.1f} / {self._total / mib:.1f} MiB"
        return f"{self._received / mib:.1f} MiB"
