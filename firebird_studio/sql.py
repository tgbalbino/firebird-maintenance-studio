from __future__ import annotations

from dataclasses import dataclass

from .connection import _dsn
from .models import ConnectionProfile


@dataclass(slots=True)
class QueryResult:
    ok: bool
    columns: list[str]
    rows: list[tuple]
    message: str


DEFAULT_MAX_RESULT_ROWS = 10_000


def execute_sql(
    profile: ConnectionProfile,
    sql: str,
    password: str | None = None,
    commit: bool = False,
    max_rows: int = DEFAULT_MAX_RESULT_ROWS,
) -> QueryResult:
    """Execute one DSQL statement and return a bounded in-memory result.

    Multi-statement files and ISQL commands such as SET TERM are deliberately
    handled by the future isql runner, not by this direct statement executor.
    """
    if not sql.strip():
        return QueryResult(False, [], [], "Informe uma instrução SQL.")
    if max_rows < 1:
        return QueryResult(False, [], [], "O limite de linhas deve ser maior que zero.")
    errors = profile.validate()
    if errors:
        return QueryResult(False, [], [], " ".join(errors))
    kwargs = {"dsn": _dsn(profile), "user": profile.user, "password": password or "", "charset": profile.charset}
    if profile.role:
        kwargs["role"] = profile.role
    try:
        if profile.version == "2.5":
            import fdb
            connect = fdb.connect
        else:
            from firebird.driver import connect
        with connect(**kwargs) as con:
            cursor = con.cursor()
            cursor.execute(sql)
            columns = [item[0] for item in (cursor.description or [])]
            truncated = False
            if columns:
                # Read one extra row so the UI can clearly report truncation
                # without keeping an unbounded result in memory.
                rows = list(cursor.fetchmany(max_rows + 1))
                truncated = len(rows) > max_rows
                if truncated:
                    rows = rows[:max_rows]
            else:
                rows = []
            if commit:
                con.commit()
            else:
                con.rollback()
            if not columns:
                affected = f"{cursor.rowcount} linha(s) afetada(s)."
            elif truncated:
                affected = f"Primeiras {len(rows)} linha(s) exibidas; resultado limitado a {max_rows}."
            else:
                affected = f"{len(rows)} linha(s) retornada(s)."
            return QueryResult(True, columns, rows, affected)
    except Exception as exc:  # driver-specific exceptions differ by version
        return QueryResult(False, [], [], f"Falha ao executar SQL: {exc}")
