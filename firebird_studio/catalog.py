from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from .connection import _client_library, _dsn
from .models import ConnectionProfile
from .schema import SchemaObject


@contextmanager
def open_database(profile: ConnectionProfile, password: str | None = None) -> Iterator[Any]:
    errors = profile.validate()
    if errors:
        raise ValueError(" ".join(errors))
    kwargs = {"dsn": _dsn(profile), "user": profile.user, "password": password or "", "charset": profile.charset}
    client_library = _client_library(profile)
    if client_library:
        kwargs["fb_library_name"] = client_library
    if profile.role:
        kwargs["role"] = profile.role
    if profile.version == "2.5":
        import fdb
        connect = fdb.connect
    else:
        from firebird.driver import connect
    with connect(**kwargs) as connection:
        yield connection


def _rows(connection: Any, query: str) -> list[tuple]:
    cursor = connection.cursor()
    cursor.execute(query)
    return list(cursor.fetchall())


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _field_type(field_type: int, length: int, scale: int, precision: int | None) -> str:
    names = {7: "SMALLINT", 8: "INTEGER", 10: "FLOAT", 12: "DATE", 13: "TIME", 14: "CHAR", 16: "BIGINT", 23: "BOOLEAN", 24: "DECFLOAT(16)", 25: "DECFLOAT(34)", 26: "INT128", 27: "DOUBLE PRECISION", 28: "TIME WITH TIME ZONE", 29: "TIMESTAMP WITH TIME ZONE", 35: "TIMESTAMP", 37: "VARCHAR", 261: "BLOB"}
    name = names.get(field_type, "BLOB")
    if name in {"CHAR", "VARCHAR"}:
        return f"{name}({length})"
    if precision and field_type in {7, 8, 16} and scale:
        return f"DECIMAL({precision},{abs(scale)})"
    return name


def load_schema(profile: ConnectionProfile, password: str | None = None, detailed: bool = True) -> list[SchemaObject]:
    """Extract a conservative schema snapshot using common Firebird catalog tables."""
    objects: list[SchemaObject] = []
    with open_database(profile, password) as connection:
        if not detailed:
            queries = (
                ("TABLE", "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 AND RDB$VIEW_BLR IS NULL ORDER BY RDB$RELATION_NAME"),
                ("VIEW", "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS WHERE RDB$VIEW_BLR IS NOT NULL AND COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$RELATION_NAME"),
                ("PROCEDURE", "SELECT TRIM(RDB$PROCEDURE_NAME) FROM RDB$PROCEDURES WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$PROCEDURE_NAME"),
                ("TRIGGER", "SELECT TRIM(RDB$TRIGGER_NAME) FROM RDB$TRIGGERS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$TRIGGER_NAME"),
                ("DOMAIN", "SELECT TRIM(RDB$FIELD_NAME) FROM RDB$FIELDS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 AND RDB$FIELD_NAME NOT LIKE 'RDB$%' ORDER BY RDB$FIELD_NAME"),
                ("INDEX", "SELECT TRIM(RDB$INDEX_NAME) FROM RDB$INDICES WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$INDEX_NAME"),
            )
            for kind, query in queries:
                try:
                    for (name,) in _rows(connection, query):
                        clean_name = _text(name)
                        objects.append(SchemaObject(kind, clean_name, f"-- {kind} {clean_name}\n-- Use 'Ler estrutura' para carregar o DDL completo."))
                except Exception:
                    continue
            if profile.version != "2.5":
                try:
                    for (name,) in _rows(connection, "SELECT TRIM(RDB$FUNCTION_NAME) FROM RDB$FUNCTIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0 ORDER BY RDB$FUNCTION_NAME"):
                        clean_name = _text(name)
                        objects.append(SchemaObject("FUNCTION", clean_name, f"-- FUNCTION {clean_name}\n-- Use 'Ler estrutura' para carregar o DDL completo."))
                except Exception:
                    pass
            return objects
        table_rows = _rows(connection, """
            SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS
            WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0 AND RDB$VIEW_BLR IS NULL
            ORDER BY RDB$RELATION_NAME
        """)
        for (table_name,) in table_rows:
            columns = _rows(connection, f"""
                SELECT TRIM(rf.RDB$FIELD_NAME), f.RDB$FIELD_TYPE, f.RDB$FIELD_LENGTH,
                       f.RDB$FIELD_SCALE, f.RDB$FIELD_PRECISION, rf.RDB$NULL_FLAG
                FROM RDB$RELATION_FIELDS rf JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
                WHERE rf.RDB$RELATION_NAME = '{_text(table_name).replace("'", "''")}'
                ORDER BY rf.RDB$FIELD_POSITION
            """)
            definitions = []
            column_details = []
            for name, field_type, length, scale, precision, null_flag in columns:
                type_name = _field_type(int(field_type), int(length), int(scale), int(precision) if precision is not None else None)
                column_details.append((_text(name), type_name, str(length or ""), str(abs(scale or 0)), "NÃO" if null_flag else "SIM"))
                definitions.append(f'  "{_text(name)}" {type_name}')
            ddl = f'CREATE TABLE "{_text(table_name)}" (\n' + ",\n".join(definitions) + "\n)"
            objects.append(SchemaObject("TABLE", _text(table_name), ddl, columns=tuple(column_details)))

        for name, source in _rows(connection, "SELECT TRIM(RDB$RELATION_NAME), RDB$VIEW_SOURCE FROM RDB$RELATIONS WHERE RDB$VIEW_BLR IS NOT NULL AND COALESCE(RDB$SYSTEM_FLAG,0)=0"):
            objects.append(SchemaObject("VIEW", _text(name), f'CREATE VIEW "{_text(name)}" AS\n{_text(source)}'))
        for name, source in _rows(connection, "SELECT TRIM(RDB$PROCEDURE_NAME), RDB$PROCEDURE_SOURCE FROM RDB$PROCEDURES WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0"):
            objects.append(SchemaObject("PROCEDURE", _text(name), f'CREATE PROCEDURE "{_text(name)}"\n{_text(source)}'))
        # Firebird 2.5 does not expose RDB$FUNCTION_SOURCE. Keep the
        # connection usable and list functions only when their source column
        # exists (Firebird 3+). External/UDF functions on 2.5 remain usable
        # through SQL, but their source cannot be reconstructed from the
        # system tables.
        if profile.version != "2.5":
            try:
                function_rows = _rows(connection, "SELECT TRIM(RDB$FUNCTION_NAME), RDB$FUNCTION_SOURCE FROM RDB$FUNCTIONS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0")
            except Exception:
                function_rows = []
            for name, source in function_rows:
                objects.append(SchemaObject("FUNCTION", _text(name), f'CREATE FUNCTION "{_text(name)}"\n{_text(source)}'))
        for name, source in _rows(connection, "SELECT TRIM(RDB$TRIGGER_NAME), RDB$TRIGGER_SOURCE FROM RDB$TRIGGERS WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0"):
            objects.append(SchemaObject("TRIGGER", _text(name), f'CREATE TRIGGER "{_text(name)}"\n{_text(source)}'))
    return objects


def load_table_metadata(profile: ConnectionProfile, password: str | None, table_name: str) -> SchemaObject:
    """Load one table's columns on demand after the fast catalog scan."""
    safe_name = _text(table_name).replace("'", "''")
    with open_database(profile, password) as connection:
        rows = _rows(connection, f"""
            SELECT TRIM(rf.RDB$FIELD_NAME), f.RDB$FIELD_TYPE, f.RDB$FIELD_LENGTH,
                   f.RDB$FIELD_SCALE, f.RDB$FIELD_PRECISION, rf.RDB$NULL_FLAG
            FROM RDB$RELATION_FIELDS rf JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
            WHERE rf.RDB$RELATION_NAME = '{safe_name}'
            ORDER BY rf.RDB$FIELD_POSITION
        """)
    columns = []
    definitions = []
    for name, field_type, length, scale, precision, null_flag in rows:
        type_name = _field_type(int(field_type), int(length), int(scale), int(precision) if precision is not None else None)
        columns.append((_text(name), type_name, str(length or ""), str(abs(scale or 0)), "NÃO" if null_flag else "SIM"))
        definitions.append(f'  "{_text(name)}" {type_name}')
    ddl = f'CREATE TABLE "{_text(table_name)}" (\n' + ",\n".join(definitions) + "\n)"
    return SchemaObject("TABLE", _text(table_name), ddl, columns=tuple(columns))
