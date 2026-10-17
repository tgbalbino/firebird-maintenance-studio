"""Non-blocking update metadata lookup for the public GitHub repository."""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen


REPOSITORY_URL = "https://github.com/tgbalbino/firebird-maintenance-studio"


def _version_key(value: str) -> tuple[int, int, int]:
    """Normalize release labels such as ``v0.1.1`` for safe comparison."""
    match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(value))
    if not match:
        raise ValueError(f"Versão inválida: {value}")
    return tuple(int(part or 0) for part in match.groups())


def _json(url: str):
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "FirebirdMaintenanceStudio"})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "FirebirdMaintenanceStudio"})
    with urlopen(request, timeout=5) as response:
        return response.read().decode("utf-8")


def check_latest(current: str) -> dict:
    """Return current/latest version data or raise a network/format error."""
    api_url = f"https://api.github.com/repos/tgbalbino/firebird-maintenance-studio/releases/latest"
    tags_url = f"https://api.github.com/repos/tgbalbino/firebird-maintenance-studio/tags?per_page=10"
    source = "release"
    try:
        payload = _json(api_url)
    except HTTPError as release_error:
        if release_error.code != 404:
            raise
        try:
            tags = _json(tags_url)
        except HTTPError as tags_error:
            if tags_error.code != 404:
                raise
            tags = []
        if isinstance(tags, list) and tags:
            payload, source = tags[0], "tag"
        else:
            raw_url = "https://raw.githubusercontent.com/tgbalbino/firebird-maintenance-studio/main/firebird_studio/__init__.py"
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)', _text(raw_url))
            if not match:
                raise ValueError("Não foi encontrada uma versão publicada.")
            payload, source = {"tag_name": match.group(1), "html_url": REPOSITORY_URL}, "arquivo de versão"
    tag = str(payload.get("tag_name", "") or payload.get("name", "")).strip()
    latest = tag[1:] if tag.lower().startswith("v") else tag
    if not latest:
        raise ValueError("A versão publicada está vazia.")
    return {"current": current, "latest": latest, "source": source, "url": str(payload.get("html_url", f"{REPOSITORY_URL}/releases")), "is_newer": _version_key(latest) > _version_key(current)}
