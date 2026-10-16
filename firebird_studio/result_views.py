"""Reusable widgets and population helpers for SQL result views.

Keeping the table setup here makes the main window responsible for orchestration
while this module owns the repetitive presentation details.
"""

from __future__ import annotations


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


def fill_table(table, columns, rows, *, resize=True, sorting=True, preserve_values=False):
    """Replace a table's contents while preserving a predictable sort state."""
    from PySide6.QtWidgets import QTableWidgetItem

    table.setSortingEnabled(False)
    table.clear()
    table.setColumnCount(len(columns))
    table.setRowCount(len(rows))
    table.setHorizontalHeaderLabels([str(column) for column in columns])
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            item = QTableWidgetItem("" if value is None else str(value))
            if preserve_values:
                from PySide6.QtCore import Qt
                item.setData(Qt.UserRole, value)
            table.setItem(row_index, column_index, item)
    if resize:
        table.resizeColumnsToContents()
    table.setSortingEnabled(sorting)


def clear_table(table):
    """Clear both headers and rows from a result table."""
    table.clear()
    table.setRowCount(0)
    table.setColumnCount(0)

