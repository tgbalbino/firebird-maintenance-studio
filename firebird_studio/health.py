from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .catalog import open_database
from .models import ConnectionProfile


@dataclass(slots=True)
class HealthFinding:
    severity: str
    title: str
    evidence: str
    recommendation: str


@dataclass(slots=True)
class HealthReport:
    metrics: dict[str, Any]
    findings: list[HealthFinding]


def _fetch_one(connection: Any, query: str) -> tuple:
    cursor = connection.cursor()
    cursor.execute(query)
    return tuple(cursor.fetchone() or ())


def _rows(connection: Any, query: str) -> list[tuple]:
    cursor = connection.cursor()
    cursor.execute(query)
    return list(cursor.fetchall())


def _optional_database_value(connection: Any, column: str) -> Any:
    """Read a version-dependent MON$DATABASE column without breaking health."""
    try:
        return _fetch_one(connection, f"SELECT {column} FROM MON$DATABASE")[0]
    except Exception:
        return None


def build_findings(metrics: dict[str, Any]) -> list[HealthFinding]:
    findings: list[HealthFinding] = []
    oldest_active = metrics.get("oldest_active")
    next_transaction = metrics.get("next_transaction")
    if isinstance(oldest_active, int) and isinstance(next_transaction, int) and next_transaction - oldest_active > 100_000:
        findings.append(HealthFinding("warning", "Transação antiga", f"Diferença entre OAT e NEXT_TRANSACTION: {next_transaction - oldest_active}", "Investigue transações longas e conexões abandonadas antes de executar sweep."))
    attachments = metrics.get("attachments")
    if isinstance(attachments, int) and attachments > 100:
        findings.append(HealthFinding("info", "Muitas conexões", f"{attachments} conexões ativas na fotografia", "Confirme o pool de conexões e encerre somente sessões identificadas como abandonadas."))
    if metrics.get("backup_state") not in (None, 0, "NORMAL"):
        findings.append(HealthFinding("warning", "Backup em andamento", f"Estado reportado: {metrics.get('backup_state')}", "Aguarde o backup terminar antes de iniciar manutenção concorrente."))
    if metrics.get("read_only") in (True, 1, "1"):
        findings.append(HealthFinding("warning", "Banco somente leitura", "MON$READ_ONLY indica que o banco não aceita alterações.", "Confirme se o modo somente leitura é intencional antes de executar scripts de atualização."))
    if metrics.get("forced_writes") in (False, 0, "0"):
        findings.append(HealthFinding("warning", "Gravação forçada desativada", "MON$FORCED_WRITES está desativado.", "Avalie ativar forced writes para reduzir o risco de perda de dados em falhas de energia."))
    if isinstance(metrics.get("page_size"), int) and isinstance(metrics.get("pages"), int):
        metrics["estimated_size_mb"] = round(metrics["page_size"] * metrics["pages"] / 1024 / 1024, 1)
    if metrics.get("sweep_interval") == 0:
        findings.append(HealthFinding("info", "Sweep automático desativado", "MON$SWEEP_INTERVAL está definido como zero.", "Monitore o crescimento do gap de transações e programe manutenção controlada se necessário."))
    if not findings:
        findings.append(HealthFinding("ok", "Sem alertas simples", "Os indicadores coletados não cruzaram os limites básicos.", "Continue acompanhando tendência, tempo de consulta e testes de restore."))
    return findings


def inspect_health(profile: ConnectionProfile, password: str | None = None) -> HealthReport:
    with open_database(profile, password) as connection:
        try:
            database = _fetch_one(connection, "SELECT MON$OLDEST_TRANSACTION, MON$OLDEST_ACTIVE, MON$OLDEST_SNAPSHOT, MON$NEXT_TRANSACTION, MON$BACKUP_STATE FROM MON$DATABASE")
        except Exception:
            # Firebird 2.5 exposes a smaller MON$DATABASE surface.
            database = _fetch_one(connection, "SELECT MON$OLDEST_TRANSACTION, MON$OLDEST_ACTIVE, MON$OLDEST_SNAPSHOT, MON$NEXT_TRANSACTION FROM MON$DATABASE")
        try:
            attachment = _fetch_one(connection, "SELECT COUNT(*) FROM MON$ATTACHMENTS")
        except Exception:
            attachment = (0,)
    metrics = {
        "oldest_transaction": database[0] if len(database) > 0 else None,
        "oldest_active": database[1] if len(database) > 1 else None,
        "oldest_snapshot": database[2] if len(database) > 2 else None,
        "next_transaction": database[3] if len(database) > 3 else None,
        "backup_state": database[4] if len(database) > 4 else None,
        "attachments": attachment[0] if attachment else 0,
    }
    for column, key in (("MON$PAGE_SIZE", "page_size"), ("MON$PAGES", "pages"), ("MON$ODS_MAJOR", "ods_major"), ("MON$ODS_MINOR", "ods_minor"), ("MON$READ_ONLY", "read_only"), ("MON$FORCED_WRITES", "forced_writes"), ("MON$SWEEP_INTERVAL", "sweep_interval")):
        metrics[key] = _optional_database_value(connection, column)
    return HealthReport(metrics, build_findings(metrics))


def list_sessions(profile: ConnectionProfile, password: str | None = None) -> list[dict[str, Any]]:
    """Return a read-only snapshot of active attachments."""
    with open_database(profile, password) as connection:
        try:
            rows = _rows(connection, "SELECT MON$ATTACHMENT_ID, MON$USER, MON$REMOTE_ADDRESS, MON$REMOTE_PROCESS, MON$STATE FROM MON$ATTACHMENTS ORDER BY MON$ATTACHMENT_ID")
        except Exception:
            rows = _rows(connection, "SELECT MON$ATTACHMENT_ID, MON$USER, MON$REMOTE_ADDRESS, MON$REMOTE_PROCESS FROM MON$ATTACHMENTS ORDER BY MON$ATTACHMENT_ID")
    sessions = []
    for row in rows:
        sessions.append({"id": row[0] if len(row) > 0 else None, "user": row[1] if len(row) > 1 else "", "address": row[2] if len(row) > 2 else "", "process": row[3] if len(row) > 3 else "", "state": row[4] if len(row) > 4 else None})
    return sessions


def list_statements(profile: ConnectionProfile, password: str | None = None) -> list[dict[str, Any]]:
    """Return currently active statements with a best-effort elapsed time."""
    with open_database(profile, password) as connection:
        try:
            rows = _rows(connection, """
                SELECT s.MON$STATEMENT_ID, s.MON$ATTACHMENT_ID, a.MON$USER,
                       a.MON$REMOTE_ADDRESS, s.MON$STATE, s.MON$TIMESTAMP,
                       s.MON$SQL_TEXT
                FROM MON$STATEMENTS s
                LEFT JOIN MON$ATTACHMENTS a ON a.MON$ATTACHMENT_ID = s.MON$ATTACHMENT_ID
                WHERE s.MON$STATE = 1 AND s.MON$SQL_TEXT IS NOT NULL
                ORDER BY s.MON$TIMESTAMP
            """)
        except Exception:
            # Older Firebird catalogs may not expose every monitoring column.
            rows = _rows(connection, """
                SELECT MON$STATEMENT_ID, MON$ATTACHMENT_ID, NULL, NULL,
                       MON$STATE, MON$TIMESTAMP, MON$SQL_TEXT
                FROM MON$STATEMENTS
                WHERE MON$STATE = 1 AND MON$SQL_TEXT IS NOT NULL
                ORDER BY MON$TIMESTAMP
            """)
    now = datetime.now(timezone.utc)
    statements = []
    for row in rows:
        timestamp = row[5] if len(row) > 5 else None
        elapsed = None
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            elapsed = max(0.0, (now - timestamp.astimezone(timezone.utc)).total_seconds())
        statements.append({
            "id": row[0] if len(row) > 0 else None,
            "attachment_id": row[1] if len(row) > 1 else None,
            "user": row[2] if len(row) > 2 and row[2] else "N/D",
            "address": row[3] if len(row) > 3 and row[3] else "N/D",
            "state": row[4] if len(row) > 4 else None,
            "started": timestamp,
            "elapsed_seconds": elapsed,
            "sql": str(row[6] or "").strip() if len(row) > 6 else "",
        })
    return statements
