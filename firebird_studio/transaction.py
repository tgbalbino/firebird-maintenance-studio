from __future__ import annotations

import time

from .connection import _connect_callable, _connection_kwargs
from .models import ConnectionProfile
from .sql import DEFAULT_MAX_RESULT_ROWS, QueryResult
from .sql import is_mutating_statement
from .sql_script import is_script, split_script


class TransactionSession:
    """A deliberately small explicit transaction for one SQL editor profile."""

    def __init__(self, profile: ConnectionProfile, password: str | None = None):
        errors = profile.validate()
        if errors:
            raise ValueError(" ".join(errors))
        connect = _connect_callable(profile)
        self.connection = connect(**_connection_kwargs(profile, password))
        self.profile_name = profile.name
        self.dirty = False

    @property
    def active(self) -> bool:
        return self.connection is not None

    def execute(self, sql: str, max_rows: int = DEFAULT_MAX_RESULT_ROWS) -> QueryResult:
        if not sql.strip():
            return QueryResult(False, [], [], "Informe uma instrução SQL.")
        if max_rows < 1:
            return QueryResult(False, [], [], "O limite de linhas deve ser maior que zero.")
        if is_script(sql):
            return self._execute_script(sql, max_rows)
        return self._execute_statement(sql, max_rows)

    def _execute_script(self, sql: str, max_rows: int) -> QueryResult:
        """Run an isql-style script statement by statement in this transaction."""
        started = time.perf_counter()
        executed = 0
        last = QueryResult(True, [], [], "")
        for item in split_script(sql):
            if item.kind == "sql":
                result = self._execute_statement(item.text, max_rows)
                executed += 1
                if not result.ok:
                    pending = " As instruções anteriores continuam pendentes na transação." if self.dirty else ""
                    return QueryResult(False, [], [], f"Instrução {executed} do script falhou: {result.message}{pending}",
                                       (time.perf_counter() - started) * 1000)
                if result.columns:
                    last = result
            elif item.kind in ("commit", "rollback"):
                try:
                    (self.commit if item.kind == "commit" else self.rollback)()
                except Exception as exc:
                    return QueryResult(False, [], [], f"Falha no {item.kind.upper()} do script: {exc}",
                                       (time.perf_counter() - started) * 1000)
        message = f"Script executado: {executed} instrução(ões)."
        if last.columns:
            message += f" Último resultado: {len(last.rows)} linha(s)."
        return QueryResult(True, last.columns, last.rows, message, (time.perf_counter() - started) * 1000)

    def _execute_statement(self, sql: str, max_rows: int) -> QueryResult:
        started = time.perf_counter()
        cursor = None
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
            result = QueryResult(True, columns, rows, affected, (time.perf_counter() - started) * 1000)
            if is_mutating_statement(sql):
                self.dirty = True
            return result
        except Exception as exc:
            return QueryResult(False, [], [], f"Falha ao executar SQL: {exc}", (time.perf_counter() - started) * 1000)
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass

    def commit(self) -> None:
        if self.connection is None:
            return
        self.connection.commit()
        self.dirty = False

    def rollback(self) -> None:
        if self.connection is None:
            return
        self.connection.rollback()
        self.dirty = False

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
