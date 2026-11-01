"""Reusable widgets and population helpers for SQL result views.

Keeping the table setup here makes the main window responsible for orchestration
while this module owns the repetitive presentation details.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal


def configure_result_table(table, *, selection_mode=None, sorting=True, minimum_height=180):
    """Apply the standard read-only result table behavior."""
    from PySide6.QtWidgets import QAbstractItemView, QTableWidget

    table.setMinimumHeight(minimum_height)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionMode(selection_mode or QAbstractItemView.ExtendedSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.horizontalHeader().setHighlightSections(False)
    table.verticalHeader().setDefaultSectionSize(26)
    table.setSortingEnabled(sorting)
    return table


NULL_ROLE = 0x0100 + 2  # Qt.UserRole + 2: True on cells whose value is SQL NULL
_NUMBER_TYPES = (int, float, Decimal)


def _is_number(value) -> bool:
    return isinstance(value, _NUMBER_TYPES) and not isinstance(value, bool)


def _sort_family(value):
    """Values of one family compare by value; anything else falls back to text."""
    if _is_number(value):
        return "number"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, (date, time, bool)):
        return type(value).__name__
    return None


def _build_item_class():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTableWidgetItem

    class ResultItem(QTableWidgetItem):
        """Cell that sorts by its real value: 10 after 2, NULL first, dates by date."""

        def __lt__(self, other):
            mine, theirs = self.data(NULL_ROLE) is True, other.data(NULL_ROLE) is True
            if mine or theirs:
                return mine and not theirs
            left, right = self.data(Qt.UserRole), other.data(Qt.UserRole)
            family = _sort_family(left)
            if family is not None and family == _sort_family(right):
                try:
                    return left < right
                except TypeError:
                    pass
            # super().__lt__ would call straight back into this override.
            return self.text() < other.text()

    return ResultItem


def _build_delegate_class():
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QStyle, QStyledItemDelegate

    class ResultCellDelegate(QStyledItemDelegate):
        """Paint SQL NULL as a muted italic marker; the cell text stays empty."""

        def initStyleOption(self, option, index):
            super().initStyleOption(option, index)
            if index.data(NULL_ROLE) is not True:
                return
            option.text = "NULL"
            option.font.setItalic(True)
            if not option.state & QStyle.State_Selected:
                text, base = option.palette.color(QPalette.Text), option.palette.color(QPalette.Base)
                option.palette.setColor(
                    QPalette.Text,
                    QColor(*(round(t * 0.62 + b * 0.38) for t, b in zip(text.getRgb()[:3], base.getRgb()[:3]))),
                )

    return ResultCellDelegate


_item_class = None
_delegate_class = None


def result_item_class():
    global _item_class
    if _item_class is None:
        _item_class = _build_item_class()
    return _item_class


def result_delegate_class():
    global _delegate_class
    if _delegate_class is None:
        _delegate_class = _build_delegate_class()
    return _delegate_class


def fill_table(table, columns, rows, *, resize=True, sorting=True, preserve_values=True):
    """Replace a table's contents while preserving a predictable sort state.

    The raw value is kept on each cell (Qt.UserRole) so NULL can be told from an
    empty string, the full value of a cell can be shown and columns sort by
    value.  Numbers are right-aligned and NULL is drawn as a muted marker.
    """
    from PySide6.QtCore import Qt

    cell = result_item_class() if preserve_values else None
    if cell is None:
        from PySide6.QtWidgets import QTableWidgetItem as cell
    elif not isinstance(table.itemDelegate(), result_delegate_class()):
        table.setItemDelegate(result_delegate_class()(table))
    table.setSortingEnabled(False)
    table.clear()
    table.setColumnCount(len(columns))
    table.setRowCount(len(rows))
    table.setHorizontalHeaderLabels([str(column) for column in columns])
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            item = cell("" if value is None else str(value))
            if preserve_values:
                item.setData(Qt.UserRole, value)
                if value is None:
                    item.setData(NULL_ROLE, True)
                elif _is_number(value):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row_index, column_index, item)
    if resize:
        table.resizeColumnsToContents()
    table.setSortingEnabled(sorting)


def clear_table(table):
    """Clear both headers and rows from a result table."""
    table.clear()
    table.setRowCount(0)
    table.setColumnCount(0)

