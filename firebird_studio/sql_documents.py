from __future__ import annotations

from typing import Any


class SqlDocumentManager:
    """Owns the lifecycle and presentation metadata of SQL editor documents."""

    def __init__(self, tabs: Any):
        self.tabs = tabs

    def add(self, editor: Any, title: str, profile_name: str = "") -> int:
        index = self.tabs.addTab(editor, title)
        self.tabs.setCurrentIndex(index)
        self.update_title(index, editor, title, profile_name)
        return index

    def update_title(self, index: int, editor: Any | None = None, base_title: str | None = None, profile_name: str | None = None) -> None:
        if index < 0 or index >= self.tabs.count():
            return
        editor = editor or self.tabs.widget(index)
        base = base_title if base_title is not None else (editor.property("document_title") if editor is not None else "")
        base = base or f"SQL {index + 1}"
        profile = profile_name if profile_name is not None else (editor.property("query_profile") if editor is not None else "")
        modified = bool(
            editor is not None
            and hasattr(editor, "document")
            and editor.document().isModified()
        )
        display = f"{base} •" if modified else base
        # The selected database is already visible in the per-window Banco
        # selector. Keep the tab compact and use the tooltip for full context.
        self.tabs.setTabText(index, display)
        # The database name is already in the connection box and the window
        # bar; the tooltip only adds the unsaved state.
        self.tabs.setTabToolTip(index, f"Consulta {base}{' (não salva)' if modified else ''}")

    def titles(self) -> list[str]:
        return [self.tabs.tabText(index) for index in range(self.tabs.count())]

    def _remove_at(self, index: int) -> bool:
        """Remove one document and release its Qt widget."""
        if index < 0 or index >= self.tabs.count():
            return False
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        return True

    def close(self, index: int, create_editor) -> None:
        self._remove_at(index)

    def close_all(self, create_editor) -> None:
        while self.tabs.count() > 0:
            self._remove_at(0)
