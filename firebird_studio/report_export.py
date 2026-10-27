"""HTML documents for the shareable health and comparison reports."""
from __future__ import annotations

from html import escape

_STYLE = (
    "body{font-family:Segoe UI,Arial,sans-serif;margin:2rem;color:#202124}"
    "pre{white-space:pre-wrap;background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:1rem}"
    "h1{font-size:1.4rem}"
)


def _document(page_title: str, heading: str, report: str) -> str:
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        f"<title>{page_title}</title><style>{_STYLE}</style></head>"
        f"<body><h1>{heading}</h1><pre>{escape(report)}</pre></body></html>"
    )


def health_html(database_name: str, report: str) -> str:
    title = escape(database_name.strip() or "Banco Firebird")
    return _document(f"Saúde - {title}", f"Relatório de saúde: {title}", report)


def compare_html(report: str) -> str:
    return _document("Comparação Firebird", "Comparação de estruturas Firebird", report)
