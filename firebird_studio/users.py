from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .catalog import open_database
from .models import ConnectionProfile


@dataclass(slots=True)
class UserAccount:
    name: str
    first_name: str = ""
    last_name: str = ""
    active: Any = None


def _identifier(value: str) -> str:
    clean = value.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$]{0,62}", clean):
        raise ValueError("O nome do usuário deve começar com letra e conter somente letras, números, _ ou $.")
    return '"' + clean.replace('"', '""') + '"'


def _password(value: str, confirmation: str | None = None) -> str:
    if not value:
        raise ValueError("Informe uma senha.")
    if confirmation is not None and value != confirmation:
        raise ValueError("A confirmação da senha não confere.")
    if len(value) < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")
    return value.replace("'", "''")


def _execute_security(profile: ConnectionProfile, password: str | None, statement: str) -> None:
    with open_database(profile, password) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(statement)
            connection.commit()
        finally:
            cursor.close()


def list_users(profile: ConnectionProfile, password: str | None = None) -> list[UserAccount]:
    """List users from the security catalog, with Firebird 2.5 fallback."""
    queries = (
        "SELECT TRIM(SEC$USER_NAME), TRIM(SEC$FIRST_NAME), TRIM(SEC$LAST_NAME), SEC$ACTIVE FROM SEC$USERS ORDER BY SEC$USER_NAME",
        "SELECT TRIM(RDB$USER), TRIM(RDB$FIRST_NAME), TRIM(RDB$LAST_NAME), NULL FROM RDB$USERS ORDER BY RDB$USER",
    )
    with open_database(profile, password) as connection:
        rows = None
        for query in queries:
            try:
                cursor = connection.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                break
            except Exception:
                continue
    if rows is None:
        raise RuntimeError("Não foi possível ler o catálogo de usuários. Verifique a permissão administrativa.")
    return [UserAccount(str(row[0] or "").strip(), str(row[1] or "").strip(), str(row[2] or "").strip(), row[3] if len(row) > 3 else None) for row in rows if row and row[0]]


def create_user(profile: ConnectionProfile, admin_password: str | None, username: str, new_password: str, confirmation: str | None = None) -> None:
    user = _identifier(username)
    secret = _password(new_password, confirmation)
    _execute_security(profile, admin_password, f"CREATE USER {user} PASSWORD '{secret}'")


def change_user_password(profile: ConnectionProfile, admin_password: str | None, username: str, new_password: str, confirmation: str | None = None) -> None:
    user = _identifier(username)
    secret = _password(new_password, confirmation)
    _execute_security(profile, admin_password, f"ALTER USER {user} PASSWORD '{secret}'")


def delete_user(profile: ConnectionProfile, admin_password: str | None, username: str) -> None:
    if username.strip().upper() == "SYSDBA":
        raise ValueError("O usuário SYSDBA não pode ser excluído.")
    _execute_security(profile, admin_password, f"DROP USER {_identifier(username)}")
