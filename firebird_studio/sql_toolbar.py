"""Command bar shown above each SQL editor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QMenu, QPushButton, QToolButton

from .icons import make_icon

_MORE_BUTTON_STYLE = (
    "QToolButton { padding-right: 22px; }"
    " QToolButton::menu-indicator { subcontrol-origin: padding; subcontrol-position: right center; right: 7px; }"
)


@dataclass(frozen=True)
class SqlToolbarActions:
    """Callbacks run for the editor that owns the toolbar."""

    execute: Callable[[], None]
    execute_selection: Callable[[], None]
    plan: Callable[[], None]
    save: Callable[[], None]
    commit: Callable[[], None]
    rollback: Callable[[], None]


def create_sql_toolbar(actions: SqlToolbarActions):
    """Build the bar; returns ``(toolbar, (commit, rollback), (confirm, read_only))``."""
    toolbar = QFrame()
    toolbar.setObjectName("sqlCommandBar")
    toolbar.setFrameShape(QFrame.StyledPanel)
    toolbar.setFrameShadow(QFrame.Plain)
    layout = QHBoxLayout(toolbar)
    layout.setContentsMargins(6, 5, 6, 5)
    layout.setSpacing(6)

    def button(label, object_name, tooltip, callback):
        widget = QPushButton(label)
        widget.setObjectName(object_name)
        widget.setToolTip(tooltip)
        widget.clicked.connect(lambda _checked=False: callback())
        return widget

    execute_button = button("Executar", "primaryAction", "Executar a consulta SQL completa (F5)", actions.execute)
    execute_button.setIcon(make_icon("play", False))
    execute_button.setIconSize(QSize(14, 14))
    layout.addWidget(execute_button)
    layout.addWidget(button("Executar seleção", "secondaryAction", "Executar somente o trecho selecionado (Ctrl+Shift+F5)", actions.execute_selection))
    layout.addWidget(button("Plano", "secondaryAction", "Exibir o plano da consulta", actions.plan))
    layout.addWidget(button("Salvar", "secondaryAction", "Salvar a consulta em um arquivo SQL (Ctrl+S)", actions.save))

    separator = QFrame()
    separator.setObjectName("toolbarSeparator")
    separator.setFrameShape(QFrame.VLine)
    separator.setFrameShadow(QFrame.Plain)
    separator.setFixedSize(1, 22)
    layout.addWidget(separator)

    more_button = QToolButton()
    more_button.setText("Transação")
    more_button.setObjectName("workspaceAction")
    more_button.setToolTip("Commit e rollback da transação desta consulta")
    more_button.setPopupMode(QToolButton.InstantPopup)
    more_button.setStyleSheet(_MORE_BUTTON_STYLE)
    # Run/plan/save already have buttons beside this menu, so it only holds
    # the transaction commands.
    menu = QMenu(more_button)
    menu.setMinimumWidth(220)
    commit_action = menu.addAction("Commit")
    commit_action.triggered.connect(lambda _checked=False: actions.commit())
    rollback_action = menu.addAction("Rollback")
    rollback_action.triggered.connect(lambda _checked=False: actions.rollback())
    more_button.setMenu(menu)

    commit_changes = QCheckBox("Confirmar alterações")
    commit_changes.setObjectName("toolbarOption")
    commit_changes.setToolTip("Quando marcado, confirma DDL/DML. Desmarcado, alterações são desfeitas ao terminar a execução.")
    read_only_mode = QCheckBox("Somente leitura")
    read_only_mode.setObjectName("toolbarOption")
    read_only_mode.setToolTip("Bloqueia DML, DDL, EXECUTE, GRANT e REVOKE nesta sessão SQL.")
    layout.addWidget(more_button)
    layout.addWidget(commit_changes)
    layout.addWidget(read_only_mode)
    layout.addStretch()

    toolbar.setProperty("execute_button", execute_button)
    return toolbar, (commit_action, rollback_action), (commit_changes, read_only_mode)
