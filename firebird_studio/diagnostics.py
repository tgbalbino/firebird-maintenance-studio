from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .models import ConnectionProfile


def create_support_package(
    output: Path,
    profile: ConnectionProfile,
    health_report: str = "",
    comparison_report: str = "",
    event_log: Path | None = None,
) -> Path:
    """Create a support archive without credentials, passwords or database files."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    profile_lines = [
        "Firebird Maintenance Studio - pacote de suporte",
        f"Gerado em: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Nome: {profile.name}",
        f"Host: {profile.host}",
        f"Porta: {profile.port}",
        f"Banco/alias: {profile.database}",
        f"Firebird configurado: {profile.version}",
        f"Usuário: {profile.user}",
        f"Charset: {profile.charset}",
        "Senha: omitida",
    ]
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("perfil.txt", "\n".join(profile_lines) + "\n")
        if health_report.strip():
            archive.writestr("saude.txt", health_report.strip() + "\n")
        if comparison_report.strip():
            archive.writestr("comparacao.txt", comparison_report.strip() + "\n")
        if event_log and event_log.exists():
            archive.writestr("eventos.txt", event_log.read_text(encoding="utf-8", errors="replace"))
        archive.writestr("LEIA-ME.txt", "O pacote não contém senhas, arquivos FDB/FBK ou dados de tabelas.\n")
    return output
