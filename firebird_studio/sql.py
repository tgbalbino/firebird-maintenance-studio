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


def execute_sql(profile: ConnectionProfile, sql: str, password: str | None = None, commit: bool = False) -> QueryResult:
    """Execute one DSQL statement and return a bounded in-memory result.

    Multi-statement files and ISQL commands such as SET TERM are deliberately
    handled by the future isql runner, not by this direct statement executor.
    """
    if not sql.strip():
        return QueryResult(False, [], [], "Informe uma instrução SQL.")
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
            rows = cursor.fetchall() if columns else []
            if commit:
                con.commit()
            else:
                con.rollback()
            affected = f"{cursor.rowcount} linha(s) afetada(s)." if not columns else f"{len(rows)} linha(s) retornada(s)."
            return QueryResult(True, columns, rows, affected)
    except Exception as exc:  # driver-specific exceptions differ by version
        return QueryResult(False, [], [], f"Falha ao executar SQL: {exc}")
