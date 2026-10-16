from __future__ import annotations

COMPACT_STYLE = "QToolButton, QPushButton { padding: 5px 9px; } QTabBar::tab { padding: 6px 12px; } QHeaderView::section { padding: 5px; font-weight: 600; }"
DARK_STYLE = COMPACT_STYLE + " QWidget { background: #202124; color: #e8eaed; } QLineEdit, QTextEdit, QTableWidget, QTreeWidget, QComboBox, QSpinBox { background: #292a2d; color: #f1f3f4; border: 1px solid #5f6368; } QPushButton, QToolButton { background: #303134; color: #f1f3f4; border: 1px solid #5f6368; border-radius: 3px; } QPushButton:hover, QToolButton:hover { background: #3c4043; } QTabBar::tab { background: #303134; color: #bdc1c6; } QTabBar::tab:selected { background: #8ab4f8; color: #202124; }"


def apply_theme(theme: str) -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(DARK_STYLE if theme == "dark" else COMPACT_STYLE)
