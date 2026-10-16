from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
import json
import shutil


SUPPORTED_VERSIONS = ("2.5", "3", "4", "5")


@dataclass(slots=True)
class ConnectionProfile:
    name: str
    host: str = "localhost"
    port: int = 3050
    database: str = ""
    version: str = "5"
    user: str = "SYSDBA"
    role: str = ""
    charset: str = "UTF8"
    favorite: bool = False
    trusted: bool = False
    isql_path: str = ""
    gbak_path: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name.strip():
            errors.append("O nome do perfil é obrigatório.")
        if self.version not in SUPPORTED_VERSIONS:
            errors.append(f"Versão não suportada: {self.version}.")
        if not 1 <= self.port <= 65535:
            errors.append("A porta deve estar entre 1 e 65535.")
        if not self.database.strip():
            errors.append("Informe o caminho ou alias do banco.")
        if not self.trusted and not self.user.strip():
            errors.append("Informe o usuário ou use autenticação confiável.")
        return errors


class ProfileStore:
    """Stores connection metadata only; passwords are intentionally excluded."""

    def __init__(self, path: Path):
        self.path = path

    def _temporary_path(self) -> Path:
        return self.path.with_name(f".{self.path.name}.tmp")

    def load(self) -> list[ConnectionProfile]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        allowed = {item.name for item in fields(ConnectionProfile)}
        profiles: list[ConnectionProfile] = []
        names: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            data = {key: value for key, value in item.items() if key in allowed}
            data.setdefault("isql_path", "")
            data.setdefault("gbak_path", "")
            try:
                profile = ConnectionProfile(**data)
            except (TypeError, ValueError):
                continue
            normalized_name = profile.name.strip().casefold()
            if not normalized_name or normalized_name in names:
                continue
            names.add(normalized_name)
            profiles.append(profile)
        return profiles

    def save(self, profiles: list[ConnectionProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(profile) for profile in profiles]
        temporary = self._temporary_path()
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        try:
            if self.path.exists():
                shutil.copy2(self.path, backup)
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()
