"""A list model of plain dicts, usable from QML as ``model.<key>``."""

from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, Qt, Property, Signal, Slot


class DictListModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, roles: Iterable[str], parent: QObject | None = None):
        super().__init__(parent)
        self._roles = list(roles)
        self._items: list[dict[str, Any]] = []

    # -- Qt model API ------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        offset = role - Qt.ItemDataRole.UserRole - 1
        if 0 <= offset < len(self._roles):
            return self._items[index.row()].get(self._roles[offset])
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + 1 + i: QByteArray(name.encode()) for i, name in enumerate(self._roles)}

    # -- Python / QML helpers ---------------------------------------------

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._items)

    @Slot(int, result="QVariant")
    def get(self, row: int) -> dict[str, Any] | None:
        return dict(self._items[row]) if 0 <= row < len(self._items) else None

    @Slot(str, "QVariant", result=int)
    def indexOf(self, key: str, value: Any) -> int:
        return next((i for i, item in enumerate(self._items) if item.get(key) == value), -1)

    def items(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._items]

    def set_items(self, items: Iterable[dict[str, Any]]) -> None:
        """Replace the content, emitting fine-grained signals when the shape is unchanged.

        Keeping row identity avoids resetting views (and editors bound to the
        current row) on every poll.
        """
        new = [dict(item) for item in items]
        if len(new) == len(self._items):
            for row, (old, item) in enumerate(zip(self._items, new)):
                if old != item:
                    self._items[row] = item
                    idx = self.index(row)
                    self.dataChanged.emit(idx, idx)
            return
        self.beginResetModel()
        self._items = new
        self.endResetModel()
        self.countChanged.emit()
