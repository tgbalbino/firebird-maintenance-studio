from __future__ import annotations

from pathlib import Path

from .models import ConnectionProfile


def find_trace_manager(profile: ConnectionProfile) -> Path | None:
    """Locate fbtracemgr beside the configured client or common installs."""
    candidates: list[Path] = []
    if profile.isql_path:
        candidates.append(Path(profile.isql_path.strip().strip('"')).parent / "fbtracemgr.exe")
    candidates.extend(
        Path(root) / "bin" / "fbtracemgr.exe"
        for root in (
            r"C:\Program Files\Firebird\Firebird_2_5",
            r"C:\Program Files\Firebird\Firebird_3_0",
            r"C:\Program Files\Firebird\Firebird_4_0",
            r"C:\Program Files\Firebird\Firebird_5_0",
            r"C:\Program Files (x86)\Firebird\Firebird_2_5",
        )
    )
    return next((path for path in candidates if path.exists()), None)


def build_trace_config(profile: ConnectionProfile) -> str:
    """Return a trace configuration compatible with Firebird 2.5 and newer."""
    database = profile.database.strip().replace("\\", "/")
    if profile.version == "2.5":
        # Firebird 2.5 interprets a database selector as a regular expression
        # (the examples use %[\\\\/] to match either Windows separator).
        # Escape the configured path so dots and other filename characters do
        # not change the selector, while accepting both slash styles emitted
        # by the server.
        # Firebird 2.5 resolves aliases and server-side paths before tracing.
        # A path-specific selector can therefore silently miss the database
        # when the client profile uses a different alias or slash style. Use
        # the default database section so every database event reaches the
        # monitor; the selected connection remains the scope shown by the UI.
        return (
            "<database>\n"
            "    enabled true\n"
            "    log_connections true\n"
            "    log_statement_start true\n"
            "    log_statement_finish true\n"
            "    print_perf true\n"
            "    time_threshold 0\n"
            "</database>\n"
        )
    return (
        f"database = {database}\n"
        "{\n"
        "    enabled true\n"
        "    log_statement_start true\n"
        "    log_statement_finish true\n"
        "    print_perf true\n"
        "    time_threshold 0\n"
        "}\n"
    )
