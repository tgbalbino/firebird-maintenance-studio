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


ACTIVITY_HEADERS = ["ID", "Conexão", "Usuário", "Terminal", "Aplicação", "Início", "Duração", "SQL"]
DURATION_COLUMN = 6


def activity_metrics_lines(profile_name, metrics, statement_count, updated_at):
    """Lines of the summary box above the active-statements table."""
    size = metrics.get("estimated_size_mb")

    def known(key):
        # 0 is a real value (ODS minor 0, zero pages); only None is unknown.
        value = metrics.get(key)
        return "N/D" if value is None or value == "" else value

    return [
        f"Banco: {profile_name}",
        f"Tamanho estimado: {size:.1f} MB" if isinstance(size, (int, float)) else "Tamanho estimado: indisponível",
        f"Página: {known('page_size')} bytes · páginas: {known('pages')}",
        f"ODS: {known('ods_major')}.{known('ods_minor')} · conexões: {metrics.get('attachments') or 0}",
        f"Transações: oldest={known('oldest_transaction')} · active={known('oldest_active')} · next={known('next_transaction')}",
        f"Consultas em execução: {statement_count}",
        "Escopo: consultas ativas de todas as aplicações/conexões visíveis para a conta do banco.",
        "Estado: nenhuma consulta em execução neste instante" if not statement_count else "Estado: consultas em execução encontradas",
        "Este painel é atualizado automaticamente e mostra apenas consultas ainda em execução no instante da leitura.",
        "Consultas muito rápidas podem terminar entre duas leituras; use o histórico Trace para capturar consultas concluídas.",
        "Histórico completo: use o botão 'Iniciar histórico (Trace)' para capturar consultas concluídas.",
        f"Última atualização: {updated_at:%d/%m/%Y %H:%M:%S}",
        "Senha: não exposta pelo monitoramento",
    ]


def fill_activity_table(table, statements):
    """Fill ``table`` with the running statements, longest duration first."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTableWidgetItem

    class DurationItem(QTableWidgetItem):
        def __lt__(self, other):
            # Unknown durations (no UserRole value) sort before any known
            # one; falling back to super().__lt__ would call this method again.
            left = self.data(Qt.UserRole)
            right = other.data(Qt.UserRole) if other is not None else None
            left = float(left) if isinstance(left, (int, float)) else -1.0
            right = float(right) if isinstance(right, (int, float)) else -1.0
            return left < right

    table.setSortingEnabled(False)
    table.clear()
    table.setColumnCount(len(ACTIVITY_HEADERS)); table.setRowCount(len(statements)); table.setHorizontalHeaderLabels(ACTIVITY_HEADERS)
    for row, statement in enumerate(statements):
        started = statement.get("started")
        started_text = started.strftime("%Y-%m-%d %H:%M:%S") if hasattr(started, "strftime") else "N/D"
        elapsed = statement.get("elapsed_seconds")
        duration_text = f"{elapsed:.1f} s" if isinstance(elapsed, (int, float)) else "N/D"
        values = [statement.get("id"), statement.get("attachment_id"), statement.get("user"), statement.get("address"), statement.get("application"), started_text, duration_text, statement.get("sql", "")]
        for column, value in enumerate(values):
            cell = DurationItem("" if value is None else str(value)) if column == DURATION_COLUMN else QTableWidgetItem("" if value is None else str(value))
            if column == DURATION_COLUMN and isinstance(elapsed, (int, float)):
                cell.setData(Qt.UserRole, float(elapsed))
            table.setItem(row, column, cell)
    table.resizeColumnsToContents()
    table.setSortingEnabled(True)
    # Put the longest running statement first so the expensive query is
    # visible immediately, while keeping the column sortable by the user.
    table.sortItems(DURATION_COLUMN, Qt.DescendingOrder)


def filter_table_rows(table, text: str):
    """Hide the rows of ``table`` whose cells do not contain ``text``."""
    needle = text.strip().casefold()
    for row in range(table.rowCount()):
        values = []
        for column in range(table.columnCount()):
            item = table.item(row, column)
            values.append(item.text() if item else "")
        table.setRowHidden(row, bool(needle) and needle not in " ".join(values).casefold())


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

