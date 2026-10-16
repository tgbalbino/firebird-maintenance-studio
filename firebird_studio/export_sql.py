from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from .catalog import _text, load_schema, open_database
from .models import ConnectionProfile


@dataclass(slots=True)
class SqlExportResult:
    ok: bool
    filename: str
    tables: int
    rows: int
    error: str = ""


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return "'" + value.isoformat().replace("'", "''") + "'"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "X'" + bytes(value).hex().upper() + "'"
    return "'" + str(value).replace("'", "''") + "'"


def export_database_sql(
    profile: ConnectionProfile,
    password: str | None,
    filename: Path,
    mode: str = "both",
    batch_size: int = 500,
) -> SqlExportResult:
    """Export Firebird metadata, data, or both as a reviewable SQL script."""
    if mode not in {"data", "metadata", "both"}:
        return SqlExportResult(False, str(filename), 0, 0, "Modo de exportação inválido.")
    if batch_size < 1:
        return SqlExportResult(False, str(filename), 0, 0, "O tamanho do lote deve ser maior que zero.")
    errors = profile.validate()
    if errors:
        return SqlExportResult(False, str(filename), 0, 0, " ".join(errors))
    try:
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        metadata = load_schema(profile, password, detailed=True) if mode in {"metadata", "both"} else []
        tables = [obj for obj in metadata if obj.kind.upper() == "TABLE"] if metadata else []
        with open_database(profile, password) as connection, filename.open("w", encoding="utf-8", newline="\n") as output:
            output.write("-- Firebird Maintenance Studio SQL export\nSET SQL DIALECT 3;\n\n")
            if mode in {"metadata", "both"}:
                output.write("-- METADADOS\n")
                for obj in metadata:
                    ddl = obj.ddl.strip()
                    if ddl and not ddl.startswith("--"):
                        output.write(ddl.rstrip(";") + ";\n\n")
                    elif ddl:
                        output.write(ddl + "\n\n")
            if mode in {"data", "both"}:
                if mode == "data":
                    rows = connection.cursor()
                    rows.execute("""
                        SELECT TRIM(RDB$RELATION_NAME)
                        FROM RDB$RELATIONS
                        WHERE COALESCE(RDB$SYSTEM_FLAG, 0)=0 AND RDB$VIEW_BLR IS NULL
                        ORDER BY RDB$RELATION_NAME
                    """)
                    table_names = [_text(row[0]) for row in rows.fetchall()]
                else:
                    table_names = [obj.name for obj in tables]
                total_rows = 0
                for table_name in table_names:
                    safe_table = table_name.replace('"', '""')
                    columns_cursor = connection.cursor()
                    columns_cursor.execute(f"""
                        SELECT TRIM(RDB$FIELD_NAME)
                        FROM RDB$RELATION_FIELDS
                        WHERE RDB$RELATION_NAME = '{table_name.replace("'", "''")}'
                        ORDER BY RDB$FIELD_POSITION
                    """)
                    columns = [_text(row[0]) for row in columns_cursor.fetchall()]
                    if not columns:
                        continue
                    cursor = connection.cursor()
                    cursor.execute(f'SELECT "{safe_table}".* FROM "{safe_table}"')
                    quoted_columns = ", ".join(f'"{column.replace(chr(34), chr(34) * 2)}"' for column in columns)
                    output.write(f"-- DADOS: {table_name}\n")
                    while True:
                        batch = cursor.fetchmany(batch_size)
                        if not batch:
                            break
                        for row in batch:
                            values = ", ".join(_literal(value) for value in row)
                            output.write(f'INSERT INTO "{safe_table}" ({quoted_columns}) VALUES ({values});\n')
                            total_rows += 1
                    output.write("\n")
                return SqlExportResult(True, str(filename), len(table_names), total_rows)
        return SqlExportResult(True, str(filename), len(tables), 0)
    except Exception as exc:
        return SqlExportResult(False, str(filename), 0, 0, f"Falha ao exportar SQL: {exc}")
