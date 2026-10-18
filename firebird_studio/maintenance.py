"""Safe database-wide maintenance operations exposed by the tree menu."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess

from .connection import _dsn
from .catalog import open_database
from .models import ConnectionProfile
from .process_utils import resolve_tool_path, run_command


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    output: str
    error: str


def validate_database(profile: ConnectionProfile, password: str | None, gfix_path: Path, timeout_seconds: int = 300) -> ValidationResult:
    errors = profile.validate()
    if errors:
        return ValidationResult(False, "", " ".join(errors))
    tool = resolve_tool_path(gfix_path, "gfix.exe")
    if not tool.exists() or not tool.is_file():
        return ValidationResult(False, "", f"Executável gfix não encontrado: {tool}")
    database = _dsn(profile)
    args = [str(tool), "-v", "-full", "-user", profile.user, database]
    execution = run_command(subprocess.run, args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds, cwd=str(tool.parent), env={**os.environ, "ISC_USER": profile.user, "ISC_PASSWORD": password or ""}, check=False)
    if execution.timed_out:
        return ValidationResult(False, "", "A validação excedeu o limite de tempo.")
    if execution.error is not None:
        return ValidationResult(False, "", f"Não foi possível iniciar o gfix: {execution.error}")
    completed = execution.completed
    return ValidationResult(completed.returncode == 0, completed.stdout or "", completed.stderr or "")


@dataclass(slots=True)
class MaintenanceResult:
    operation: str
    processed: int
    failed: tuple[str, ...] = ()


def _identifier(value: str) -> str:
    return '"' + str(value).strip().replace('"', '""') + '"'


def _field_type(values) -> str:
    field_type, subtype, length, scale, precision = values
    field_type = int(field_type or 0)
    subtype = int(subtype or 0)
    length = int(length or 0)
    scale = int(scale or 0)
    precision = int(precision or 0)
    names = {7: "SMALLINT", 8: "INTEGER", 9: "QUAD", 10: "FLOAT", 11: "D_FLOAT", 12: "DATE", 13: "TIME", 14: "CHAR", 16: "BIGINT", 27: "DOUBLE PRECISION", 35: "TIMESTAMP", 37: "VARCHAR", 261: "BLOB"}
    if field_type in (14, 37):
        return f"{names[field_type]}({length})"
    if field_type == 16 and subtype in (1, 2) and precision:
        kind = "NUMERIC" if subtype == 1 else "DECIMAL"
        return f"{kind}({precision}, {-scale})"
    return names.get(field_type, "BLOB")


def _run_ddl_batch(profile: ConnectionProfile, password: str | None, operation: str, query: str, source_index: int = 0) -> MaintenanceResult:
    failed: list[str] = []
    processed = 0
    with open_database(profile, password) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                name = str(row[0]).strip()
                source = row[source_index] if len(row) > source_index else None
                if not name or not source:
                    continue
                body = str(source).strip()
                statement = f'{operation} {_identifier(name)} '
                if operation == "ALTER PROCEDURE" and not body.upper().startswith(("AS ", "AS\n", "AS\r")):
                    statement += "AS\n"
                statement += body
                try:
                    cursor.execute(statement)
                    processed += 1
                except Exception as exc:
                    failed.append(f"{name}: {exc}")
            connection.commit()
        finally:
            cursor.close()
    return MaintenanceResult(operation, processed, tuple(failed))


def recompute_index_selectivity(profile: ConnectionProfile, password: str | None = None) -> MaintenanceResult:
    """Recalculate selectivity for every user index in the database."""
    processed = 0
    failed: list[str] = []
    with open_database(profile, password) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT TRIM(RDB$INDEX_NAME)
                FROM RDB$INDICES
                WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
                ORDER BY RDB$INDEX_NAME
            """)
            names = [str(row[0]).strip() for row in cursor.fetchall() if row and row[0]]
            for name in names:
                try:
                    cursor.execute(f"SET STATISTICS INDEX {_identifier(name)}")
                    processed += 1
                except Exception as exc:
                    failed.append(f"{name}: {exc}")
            connection.commit()
        finally:
            cursor.close()
    return MaintenanceResult("Recomputar seletividade dos índices", processed, tuple(failed))


def recompile_procedures(profile: ConnectionProfile, password: str | None = None) -> MaintenanceResult:
    failed: list[str] = []
    processed = 0
    with open_database(profile, password) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("""
                SELECT TRIM(RDB$PROCEDURE_NAME), RDB$PROCEDURE_SOURCE
                FROM RDB$PROCEDURES
                WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
                ORDER BY RDB$PROCEDURE_NAME
            """)
            procedures = [(str(row[0]).strip(), row[1]) for row in cursor.fetchall() if row and row[0] and row[1]]
            for name, source in procedures:
                try:
                    cursor.execute("""
                        SELECT pp.RDB$PARAMETER_TYPE, TRIM(pp.RDB$PARAMETER_NAME),
                               f.RDB$FIELD_TYPE, f.RDB$FIELD_SUB_TYPE,
                               f.RDB$FIELD_LENGTH, f.RDB$FIELD_SCALE,
                               f.RDB$FIELD_PRECISION
                        FROM RDB$PROCEDURE_PARAMETERS pp
                        JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = pp.RDB$FIELD_SOURCE
                        WHERE pp.RDB$PROCEDURE_NAME = ?
                        ORDER BY pp.RDB$PARAMETER_TYPE, pp.RDB$PARAMETER_NUMBER
                    """, (name,))
                    params = cursor.fetchall()
                    inputs = [row for row in params if int(row[0] or 0) == 0]
                    outputs = [row for row in params if int(row[0] or 0) == 1]
                    header = f'ALTER PROCEDURE {_identifier(name)}'
                    if inputs:
                        header += " (" + ", ".join(f"{row[1]} {_field_type(row[2:])}" for row in inputs) + ")"
                    if outputs:
                        header += " RETURNS (" + ", ".join(f"{row[1]} {_field_type(row[2:])}" for row in outputs) + ")"
                    body = str(source).strip()
                    if not body.upper().startswith(("AS ", "AS\n", "AS\r")):
                        body = "AS\n" + body
                    cursor.execute(header + "\n" + body)
                    processed += 1
                except Exception as exc:
                    failed.append(f"{name}: {exc}")
            connection.commit()
        finally:
            cursor.close()
    return MaintenanceResult("Recompilar todas as procedures", processed, tuple(failed))


def recompile_triggers(profile: ConnectionProfile, password: str | None = None) -> MaintenanceResult:
    return _run_ddl_batch(
        profile,
        password,
        "ALTER TRIGGER",
        """
            SELECT TRIM(RDB$TRIGGER_NAME), RDB$TRIGGER_SOURCE
            FROM RDB$TRIGGERS
            WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0
            ORDER BY RDB$TRIGGER_NAME
        """,
        1,
    )
