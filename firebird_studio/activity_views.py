"""Widget construction for database activity and session monitoring."""

from __future__ import annotations


def create_activity_panel(on_refresh, on_export, on_open_sql, on_filter, on_auto_refresh, on_double_click):
    from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTextEdit, QVBoxLayout, QWidget
    from PySide6.QtCore import Qt

    metrics = QTextEdit()
    metrics.setReadOnly(True)
    metrics.setMaximumHeight(150)
    table = QTableWidget()
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionMode(QTableWidget.ExtendedSelection)
    table.setSortingEnabled(True)
    refresh = QPushButton("Atualizar")
    refresh.setToolTip("Atualizar agora as consultas em execução")
    refresh.clicked.connect(on_refresh)
    export = QPushButton("Exportar CSV")
    export.setToolTip("Exportar a lista de atividade para CSV")
    export.clicked.connect(on_export)
    open_sql = QPushButton("Abrir SQL")
    open_sql.setToolTip("Abrir o SQL da consulta selecionada em uma janela de edição")
    open_sql.clicked.connect(on_open_sql)
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText("Filtrar usuário, endereço ou SQL...")
    filter_edit.textChanged.connect(on_filter)
    auto_refresh = QCheckBox("Auto 5 s")
    auto_refresh.setToolTip("Atualizar automaticamente a cada 5 segundos")
    auto_refresh.toggled.connect(on_auto_refresh)
    table.cellDoubleClicked.connect(on_double_click)
    controls = QHBoxLayout()
    for widget in (refresh, open_sql, export):
        controls.addWidget(widget)
    controls.addWidget(filter_edit, 1)
    controls.addWidget(auto_refresh)
    controls.addStretch()
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.addLayout(controls)
    layout.addWidget(metrics)
    layout.addWidget(table, 1)
    return panel, metrics, table, refresh, export, open_sql, filter_edit, auto_refresh


def create_sessions_panel(on_filter, on_disconnect):
    from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout, QWidget

    table = QTableWidget()
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSortingEnabled(True)
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText("Filtrar usuário, endereço ou processo...")
    filter_edit.textChanged.connect(on_filter)
    disconnect = QPushButton("Desconectar")
    disconnect.setToolTip("Encerrar a sessão selecionada")
    disconnect.clicked.connect(on_disconnect)
    controls = QHBoxLayout()
    controls.addWidget(filter_edit, 1)
    controls.addWidget(disconnect)
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.addWidget(QLabel("Conexões ativas do banco"))
    layout.addLayout(controls)
    layout.addWidget(table, 1)
    return panel, table, filter_edit, disconnect

