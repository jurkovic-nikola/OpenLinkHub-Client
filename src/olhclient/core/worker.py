"""Run blocking API calls off the GUI thread.

Callbacks are always invoked on the thread that owns the :class:`Worker`
(the GUI thread), so they can touch models and QML freely. Pass ``owner`` to
drop the callbacks when that object was deleted in the meantime (e.g. the user
switched to another device while a request was in flight).
"""

from __future__ import annotations

from typing import Any, Callable

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot

Callback = Callable[[Any], None]


class _Job(QRunnable):
    def __init__(self, worker: Worker, fn: Callable[..., Any], args: tuple, on_done: Callback | None,
                 on_error: Callback | None, owner: QObject | None):
        super().__init__()
        self._worker = worker
        self._fn = fn
        self._args = args
        self._on_done = on_done
        self._on_error = on_error
        self._owner = owner

    def run(self) -> None:
        try:
            result = self._fn(*self._args)
        except Exception as exc:  # delivered to on_error / Worker.failed
            self._worker._deliver.emit((self._on_error, self._owner), exc, True)
        else:
            self._worker._deliver.emit((self._on_done, self._owner), result, False)


class Worker(QObject):
    #: Emitted for errors that have no explicit ``on_error`` handler.
    failed = Signal(object)
    busyChanged = Signal()

    _deliver = Signal(object, object, bool)

    def __init__(self, parent: QObject | None = None, *, synchronous: bool = False):
        super().__init__(parent)
        self._synchronous = synchronous
        self._pending = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(4)
        self._deliver.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    @property
    def busy(self) -> bool:
        return self._pending > 0

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_done: Callback | None = None,
        on_error: Callback | None = None,
        owner: QObject | None = None,
    ) -> None:
        if self._synchronous:  # used by tests: run inline, deliver immediately
            try:
                result = fn(*args)
            except Exception as exc:
                self._handle((on_error, owner), exc, True)
            else:
                self._handle((on_done, owner), result, False)
            return
        self._set_pending(self._pending + 1)
        self._pool.start(_Job(self, fn, args, on_done, on_error, owner))

    def wait(self) -> None:
        self._pool.waitForDone()

    @Slot(object, object, bool)
    def _dispatch(self, target: tuple[Callback | None, QObject | None], value: Any, is_error: bool) -> None:
        self._set_pending(self._pending - 1)
        self._handle(target, value, is_error)

    def _handle(self, target: tuple[Callback | None, QObject | None], value: Any, is_error: bool) -> None:
        callback, owner = target
        if owner is not None and not shiboken6.isValid(owner):
            return
        if callback is not None:
            callback(value)
        elif is_error:
            self.failed.emit(value)

    def _set_pending(self, value: int) -> None:
        was_busy = self.busy
        self._pending = value
        if was_busy != self.busy:
            self.busyChanged.emit()
