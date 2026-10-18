"""Widget construction for database activity and session monitoring."""

from __future__ import annotations


def create_activity_panel(on_refresh, on_export, on_open_sql, on_filter, on_auto_refresh, on_double_click, on_interval_changed, on_export_trace, on_clear_trace):
    from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTabWidget, QTextEdit, QVBoxLayout, QWidget
    from PySide6.QtCore import Qt

    metrics = QTextEdit()
    metrics.setReadOnly(True)
    metrics.setMaximumHeight(150)
    table = QTableWidget()
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionMode(QTableWidget.ExtendedSelection)
    table.setSortingEnabled(True)
    trace_table = QTableWidget()
    trace_table.setEditTriggers(QTableWidget.NoEditTriggers)
    trace_table.setSelectionBehavior(QTableWidget.SelectRows)
    trace_table.setSortingEnabled(True)
    trace_table.setColumnCount(3)
    trace_table.setHorizontalHeaderLabels(["Data/hora", "Evento", "SQL / detalhes"])
    trace_table.horizontalHeader().setStretchLastSection(True)
    refresh = QPushButton("Atualizar")
    refresh.setToolTip("Atualizar agora as consultas em execução")
    refresh.clicked.connect(on_refresh)
    export = QPushButton("Exportar CSV")
    export.setToolTip("Exportar a lista de atividade para CSV")
    export.clicked.connect(on_export)
    export_trace = QPushButton("Exportar Trace")
    export_trace.setToolTip("Salvar o histórico Trace em CSV")
    export_trace.clicked.connect(on_export_trace)
    clear_trace = QPushButton("Limpar Trace")
    clear_trace.setToolTip("Limpar os eventos exibidos sem parar o monitoramento")
    clear_trace.clicked.connect(on_clear_trace)
    open_sql = QPushButton("Abrir SQL")
    open_sql.setToolTip("Abrir o SQL da consulta selecionada em uma janela de edição")
    open_sql.clicked.connect(on_open_sql)
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText("Filtrar usuário, terminal, aplicação ou SQL...")
    filter_edit.textChanged.connect(on_filter)
    auto_refresh = QCheckBox("Auto 1 s")
    auto_refresh.setToolTip("Atualizar automaticamente a cada segundo")
    auto_refresh.toggled.connect(on_auto_refresh)
    interval = QComboBox()
    interval.addItem("1 s", 1000)
    interval.addItem("5 s", 5000)
    interval.addItem("10 s", 10000)
    interval.addItem("30 s", 30000)
    interval.setToolTip("Intervalo da atualização automática")
    interval.currentIndexChanged.connect(lambda _index: on_interval_changed(interval.currentData()))
    table.cellDoubleClicked.connect(on_double_click)
    controls = QHBoxLayout()
    for widget in (refresh, open_sql, export, export_trace, clear_trace):
        controls.addWidget(widget)
    controls.addWidget(filter_edit, 1)
    controls.addWidget(auto_refresh)
    controls.addWidget(QLabel("Intervalo:"))
    controls.addWidget(interval)
    controls.addStretch()
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.addLayout(controls)
    layout.addWidget(metrics)
    tabs = QTabWidget()
    tabs.addTab(table, "Consultas ativas")
    tabs.addTab(trace_table, "Histórico Trace")
    layout.addWidget(tabs, 1)
    return panel, metrics, table, trace_table, refresh, export, export_trace, clear_trace, open_sql, filter_edit, auto_refresh, interval


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

