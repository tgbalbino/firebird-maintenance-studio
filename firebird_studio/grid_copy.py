"""Copy result-grid rows as CSV, Markdown, JSON or INSERT statements."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, time
from decimal import Decimal

FORMATS = {
    "csv": "CSV",
    "markdown": "Markdown",
    "json": "JSON",
    "insert": "INSERT",
}


def grid_rows(table):
    """Columns and raw rows for the selected rows, or every visible row if none are selected."""
    from PySide6.QtCore import Qt

    from .result_views import NULL_ROLE

    columns = []
    for column in range(table.columnCount()):
        header = table.horizontalHeaderItem(column)
        columns.append(header.text() if header is not None else str(column + 1))
    selected = sorted({index.row() for index in table.selectedIndexes()})
    chosen = [row for row in selected if not table.isRowHidden(row)]
    if not chosen:
        chosen = [row for row in range(table.rowCount()) if not table.isRowHidden(row)]
    rows = []
    for row in chosen:
        values = []
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is None or item.data(NULL_ROLE) is True:
                values.append(None)
                continue
            raw = item.data(Qt.UserRole)
            values.append(item.text() if raw is None else raw)
        rows.append(values)
    return columns, rows


def _plain(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def as_csv(columns, rows) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_plain(value) for value in row])
    return buffer.getvalue()


def as_markdown(columns, rows) -> str:
    def cell(value) -> str:
        text = "NULL" if value is None else _plain(value)
        return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", "").replace("\n", "<br>")

    lines = ["| " + " | ".join(cell(column) for column in columns) + " |"]
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def _json_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def as_json(columns, rows) -> str:
    return json.dumps(
        [{column: _json_value(value) for column, value in zip(columns, row)} for row in rows],
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def sql_literal(value) -> str:
    """Firebird literal for a raw cell value."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return f"x'{value.hex()}'"
    if isinstance(value, datetime):
        return "'" + value.isoformat(sep=" ") + "'"
    if isinstance(value, (date, time)):
        return "'" + value.isoformat() + "'"
    return "'" + str(value).replace("'", "''") + "'"


def as_insert(columns, rows, table_name: str) -> str:
    """One INSERT per row.  A grid can hold any query, so the table name is a placeholder."""
    names = ", ".join(quote_identifier(column) for column in columns)
    target = quote_identifier(table_name)
    return "".join(
        f"INSERT INTO {target} ({names}) VALUES ({', '.join(sql_literal(value) for value in row)});\n"
        for row in rows
    )


def format_rows(kind: str, columns, rows, table_name: str = "TABELA") -> str:
    if kind == "csv":
        return as_csv(columns, rows)
    if kind == "markdown":
        return as_markdown(columns, rows)
    if kind == "json":
        return as_json(columns, rows)
    if kind == "insert":
        return as_insert(columns, rows, table_name)
    raise ValueError(f"Formato de cópia desconhecido: {kind}")
