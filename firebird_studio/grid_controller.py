"""Edit-in-grid for a simple single-table SELECT result.

Edits stay local until "Salvar alterações": the changes become UPDATE
statements run inside a transaction, which the user then commits or rolls back.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QTableWidget

from .grid_edit import RowChange, build_update, coerce_like

ORIGINAL_ROLE = Qt.UserRole + 1  # full original row tuple, stored on column 0
EDITED_COLOR = QColor("#f59e0b")


@dataclass
class GridContext:
    profile_name: str
    table: str
    columns: list[str]
    key: list[str]
    sql: str


class GridEditController:
    """Owns edit mode, change tracking and saving for the result grid.

    ``execute(context, statements)`` runs the UPDATEs in the user's
    transaction and returns ``(ok, message)``; ``confirm(count, statements)``
    asks the user; ``set_status`` reports on the main status line.
    """

    def __init__(self, edit_button, save_button, *, execute, confirm, set_status):
        self.edit_button = edit_button
        self.save_button = save_button
        self._execute = execute
        self._confirm = confirm
        self._set_status = set_status
        self.table: QTableWidget | None = None
        self.context: GridContext | None = None
        self.pending_commit = False
        self._loading = False
        self._connected_table = None
        edit_button.toggled.connect(self._toggle_edit)
        save_button.clicked.connect(self.save)
        self.reset()

    # -- setup -----------------------------------------------------------
    def reset(self):
        """Leave edit mode and hide the controls (new result, new connection...)."""
        self._set_editing(False)
        self.context = None
        self.pending_commit = False
        self.edit_button.blockSignals(True)
        self.edit_button.setChecked(False)
        self.edit_button.blockSignals(False)
        self.edit_button.setVisible(False)
        self.save_button.setVisible(False)

    def attach(self, table: QTableWidget, context: GridContext, rows):
        """Make a freshly filled ``table`` editable; remembers each row's original values."""
        self.reset()
        self.table = table
        self.context = context
        self._set_editing(False)  # read-only until the user turns editing on
        self._loading = True
        for row_index, row in enumerate(rows):
            item = table.item(row_index, 0)
            if item is not None:
                item.setData(ORIGINAL_ROLE, tuple(row))
        self._loading = False
        if self._connected_table is not table:
            table.itemChanged.connect(self._item_changed)
            self._connected_table = table
        self.edit_button.setVisible(True)
        self.save_button.setVisible(True)
        self._refresh_save_button()

    def _set_editing(self, enabled: bool):
        table = self.table
        if table is None:
            return
        table.setSortingEnabled(not enabled)  # row positions must stay stable while editing
        table.setEditTriggers(
            (QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed) if enabled else QAbstractItemView.NoEditTriggers
        )

    def _toggle_edit(self, enabled: bool):
        if self.context is None:
            return
        self._set_editing(enabled)
        if enabled:
            self._set_status("Edição ativada: altere as células e use 'Salvar alterações'. Nada é gravado até o Commit.")
        else:
            self._set_status("Edição desativada; a grade voltou a ficar protegida.")

    # -- tracking ---------------------------------------------------------
    def _row_change(self, row: int) -> RowChange | None:
        table = self.table
        first = table.item(row, 0)
        original = first.data(ORIGINAL_ROLE) if first is not None else None
        if original is None:
            return None
        current = tuple(
            (table.item(row, column).text() if table.item(row, column) is not None else "")
            for column in range(table.columnCount())
        )
        return RowChange(tuple(original), current)

    def _item_changed(self, item):
        if self._loading or self.table is None or item.tableWidget() is not self.table:
            return
        change = self._row_change(item.row())
        if change is None:
            return
        edited = item.column() in change.changed_columns()
        self._loading = True  # styling the cell emits itemChanged again
        try:
            item.setBackground(QBrush(EDITED_COLOR if edited else Qt.transparent))
            if edited:
                item.setForeground(QBrush(QColor("#111827")))
            else:
                item.setData(Qt.ForegroundRole, None)
        finally:
            self._loading = False
        self._refresh_save_button()

    def changes(self) -> list[tuple[int, str]]:
        """``(row, UPDATE)`` for every edited row."""
        if self.table is None or self.context is None:
            return []
        out = []
        for row in range(self.table.rowCount()):
            change = self._row_change(row)
            if change is None:
                continue
            sql = build_update(self.context.table, self.context.columns, self.context.key, change)
            if sql:
                out.append((row, sql))
        return out

    def _refresh_save_button(self):
        count = len(self.changes())
        self.save_button.setText(f"Salvar alterações ({count})" if count else "Salvar alterações")
        self.save_button.setEnabled(count > 0)

    # -- saving -----------------------------------------------------------
    def save(self):
        pending = self.changes()
        if not pending or self.context is None:
            return
        statements = [sql for _row, sql in pending]
        if not self._confirm(len(statements), statements):
            self._set_status("Salvamento cancelado; as edições continuam na grade.")
            return
        ok, message = self._execute(self.context, statements)
        if not ok:
            self._set_status(message)
            return
        self.pending_commit = True
        self._accept_saved([row for row, _sql in pending])
        self._set_status(message)

    def _accept_saved(self, rows):
        """The edited rows are now the baseline; highlight is cleared."""
        table = self.table
        self._loading = True
        try:
            for row in rows:
                change = self._row_change(row)
                if change is None:
                    continue
                new_original = tuple(coerce_like(old, text) for old, text in zip(change.original, change.current))
                table.item(row, 0).setData(ORIGINAL_ROLE, new_original)
                for column in range(table.columnCount()):
                    cell = table.item(row, column)
                    if cell is not None:
                        cell.setBackground(QBrush(Qt.transparent))
                        cell.setData(Qt.ForegroundRole, None)
        finally:
            self._loading = False
        self._refresh_save_button()

    def committed(self):
        self.pending_commit = False

    def discard_pending(self) -> bool:
        """After a rollback the grid no longer matches the database: report whether to reload."""
        was_pending = self.pending_commit
        self.pending_commit = False
        return was_pending
