from __future__ import annotations

from typing import Any

from .connection import _dsn
from .models import ConnectionProfile
from .sql import QueryResult


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

    def execute(self, sql: str) -> QueryResult:
        if not sql.strip():
            return QueryResult(False, [], [], "Informe uma instrução SQL.")
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql)
            columns = [item[0] for item in (cursor.description or [])]
            rows = cursor.fetchall() if columns else []
            affected = f"{cursor.rowcount} linha(s) afetada(s)." if not columns else f"{len(rows)} linha(s) retornada(s)."
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
