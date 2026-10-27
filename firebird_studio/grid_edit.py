"""Editing a simple single-table SELECT result and turning edits into UPDATEs.

Everything here is pure (no Qt, no database) so it can be tested directly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

_NUMBER = re.compile(r"-?(?:\d+(?:\.\d*)?|\.\d+)")
_IDENT = r'(?:"[^"]+"|[A-Za-z_][A-Za-z0-9_$]*)'
_SELECT = re.compile(
    r"^\s*SELECT\s+(?:(?:FIRST|SKIP)\s+\d+\s+)*(?P<columns>.+?)\s+FROM\s+(?P<table>" + _IDENT + r")"
    r"(?P<tail>\s+(?:WHERE|ORDER\s+BY|ROWS)\b.*)?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_FORBIDDEN = re.compile(r"\b(?:JOIN|UNION|GROUP\s+BY|HAVING|DISTINCT|INTERSECT|EXCEPT|FOR\s+UPDATE|WITH\s+LOCK)\b|\(\s*SELECT\b", re.IGNORECASE)


@dataclass(frozen=True)
class SimpleSelect:
    """A SELECT over one table whose rows map 1:1 to table rows."""

    table: str
    columns: tuple[str, ...] | None  # ``None`` means ``*``


def _strip_noise(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql or "", flags=re.DOTALL)
    sql = re.sub(r"--[^\r\n]*", " ", sql)
    return sql.strip().rstrip(";").strip()


def _identifier(raw: str) -> str:
    raw = raw.strip()
    return raw[1:-1].replace('""', '"') if raw.startswith('"') else raw.upper()


def parse_simple_select(sql: str) -> SimpleSelect | None:
    """Return the table/columns of an editable SELECT, or ``None`` if it is not simple.

    Rejected: joins, unions, grouping, DISTINCT, subqueries, several statements,
    aliases, expressions, functions and aggregates in the column list.
    """
    text = _strip_noise(sql)
    if ";" in re.sub(r"'(?:''|[^'])*'", "''", text):
        return None
    without_strings = re.sub(r"'(?:''|[^'])*'", "''", text)
    if _FORBIDDEN.search(without_strings):
        return None
    match = _SELECT.match(text)
    if not match:
        return None
    column_text = match.group("columns").strip()
    if column_text == "*":
        columns = None
    else:
        parts = [part.strip() for part in column_text.split(",")]
        pattern = re.compile(r"^(?:" + _IDENT + r"\.)?(" + _IDENT + r")$")
        columns_list = []
        for part in parts:
            found = pattern.match(part)
            if not found:
                return None
            columns_list.append(_identifier(found.group(1)))
        columns = tuple(columns_list)
    return SimpleSelect(_identifier(match.group("table")), columns)


def quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def sql_literal(text: str | None, original=None) -> str:
    """Render the edited cell text as a Firebird literal typed after the original value."""
    if text is None:
        return "NULL"
    text = str(text)
    if text.strip() == "":
        return "''" if original == "" else "NULL"
    if isinstance(original, bool):
        return "TRUE" if text.strip().casefold() in {"1", "true", "t", "sim", "s"} else "FALSE"
    if isinstance(original, (int, float, Decimal)) and _NUMBER.fullmatch(text.strip()):
        return text.strip()
    return "'" + text.replace("'", "''") + "'"


def _display(value) -> str:
    return "" if value is None else str(value)


@dataclass(frozen=True)
class RowChange:
    """One edited row: the original values and the texts now shown in the grid."""

    original: tuple
    current: tuple[str, ...]

    def changed_columns(self) -> list[int]:
        return [i for i, text in enumerate(self.current) if text != _display(self.original[i])]


def build_update(table: str, columns: list[str], key_columns: list[str], change: RowChange) -> str | None:
    """UPDATE for one edited row keyed by its original primary-key values, or ``None``."""
    changed = change.changed_columns()
    if not changed:
        return None
    lookup = {name.casefold(): index for index, name in enumerate(columns)}
    key_indexes = [lookup[key.casefold()] for key in key_columns]
    assignments = ", ".join(
        f"{quote_identifier(columns[i])} = {sql_literal(change.current[i], change.original[i])}" for i in changed
    )
    predicates = []
    for index in key_indexes:
        value = change.original[index]
        name = quote_identifier(columns[index])
        predicates.append(f"{name} IS NULL" if value is None else f"{name} = {sql_literal(_display(value), value)}")
    return f"UPDATE {quote_identifier(table)} SET {assignments} WHERE {' AND '.join(predicates)}"


def editable_key(select: SimpleSelect | None, result_columns: list[str], primary_key: tuple[str, ...]) -> list[str] | None:
    """Primary-key columns when every key column is in the result; otherwise ``None``.

    Without the full key an edit could not target exactly one row, so the
    result stays read-only.
    """
    if select is None or not primary_key:
        return None
    present = {name.casefold() for name in result_columns}
    if not all(key.casefold() in present for key in primary_key):
        return None
    return list(primary_key)


def coerce_like(original, text: str):
    """Typed value for ``text`` after the type of ``original`` (so later edits keep quoting right)."""
    text = (text or "").strip()
    if text == "":
        return None
    try:
        if isinstance(original, bool):
            return text.casefold() in {"1", "true", "t", "sim", "s"}
        if isinstance(original, int):
            return int(text)
        if isinstance(original, Decimal):
            return Decimal(text)
        if isinstance(original, float):
            return float(text)
    except (ValueError, ArithmeticError):
        pass
    return text
