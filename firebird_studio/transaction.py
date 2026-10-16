from __future__ import annotations

from typing import Any

from .connection import _dsn
from .models import ConnectionProfile
from .sql import DEFAULT_MAX_RESULT_ROWS, QueryResult


class TransactionSession:
    """A deliberately small explicit transaction for one SQL editor profile."""

    def __init__(self, profile: ConnectionProfile, password: str | None = None):
        errors = profile.validate()
        if errors:
            raise ValueError(" ".join(errors))
        kwargs: dict[str, Any] = {
            "dsn": _dsn(profile),
            "user": profile.user,
            "password": password or "",
            "charset": profile.charset,
        }
        if profile.role:
            kwargs["role"] = profile.role
        if profile.version == "2.5":
            import fdb

            connect = fdb.connect
        else:
            from firebird.driver import connect

        self.connection = connect(**kwargs)
        self.profile_name = profile.name

    @property
    def active(self) -> bool:
        return self.connection is not None

    def execute(self, sql: str, max_rows: int = DEFAULT_MAX_RESULT_ROWS) -> QueryResult:
        if not sql.strip():
            return QueryResult(False, [], [], "Informe uma instrução SQL.")
        if max_rows < 1:
            return QueryResult(False, [], [], "O limite de linhas deve ser maior que zero.")
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql)
            columns = [item[0] for item in (cursor.description or [])]
            truncated = False
            if columns:
                fetchmany = getattr(cursor, "fetchmany", None)
                rows = list(fetchmany(max_rows + 1)) if callable(fetchmany) else list(cursor.fetchall())
                truncated = len(rows) > max_rows
                if truncated:
                    rows = rows[:max_rows]
            else:
                rows = []
            if not columns:
                affected = f"{cursor.rowcount} linha(s) afetada(s)."
            elif truncated:
                affected = f"Primeiras {len(rows)} linha(s) exibidas; resultado limitado a {max_rows}."
            else:
                affected = f"{len(rows)} linha(s) retornada(s)."
            return QueryResult(True, columns, rows, affected)
        except Exception as exc:
            return QueryResult(False, [], [], f"Falha ao executar SQL: {exc}")

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self, rollback: bool = True) -> None:
        if self.connection is None:
            return
        try:
            if rollback:
                self.connection.rollback()
        finally:
            try:
                self.connection.close()
            finally:
                self.connection = None
