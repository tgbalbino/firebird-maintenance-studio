"""Visual components for plan analysis and diagnostic output."""

from __future__ import annotations


def create_plan_panel():
    """Create a compact plan view and keep raw isql output out of the way."""
    from PySide6.QtWidgets import QTreeWidget, QTextEdit, QVBoxLayout, QWidget, QLabel, QPushButton, QHBoxLayout

    tree = QTreeWidget()
    tree.setObjectName("planTree")
    tree.setHeaderLabels(["Plano de acesso"])
    tree.setRootIsDecorated(True)
    tree.setAlternatingRowColors(True)
    tree.setUniformRowHeights(True)
    tree.setMinimumHeight(180)
    output = QTextEdit()
    output.setReadOnly(True)
    output.setObjectName("planTechnicalOutput")
    output.setPlaceholderText("Os detalhes técnicos do isql aparecerão aqui.")
    output.setVisible(False)
    summary = QLabel("Execute Ver plano para analisar a consulta sem executá-la.")
    summary.setObjectName("planSummary")
    summary.setWordWrap(True)
    details_button = QPushButton("Mostrar detalhes técnicos")
    details_button.setObjectName("secondaryAction")
    details_button.setEnabled(False)
    details_button.clicked.connect(lambda: _toggle_plan_details(details_button, output))
    actions = QHBoxLayout()
    actions.addWidget(summary, 1)
    actions.addWidget(details_button)
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    layout.addLayout(actions)
    layout.addWidget(tree)
    layout.addWidget(output, 1)
    output.setProperty("planSummary", summary)
    output.setProperty("planDetailsButton", details_button)
    output._plan_summary = summary
    output._plan_details_button = details_button
    return panel, tree, output


def _toggle_plan_details(button, output):
    visible = not output.isVisible()
    output.setVisible(visible)
    button.setText("Ocultar detalhes técnicos" if visible else "Mostrar detalhes técnicos")


def render_plan(tree_widget, output_widget, result):
    """Render only decision-useful information, with raw output on demand."""
    from PySide6.QtWidgets import QTreeWidgetItem

    tree_widget.clear()

    def fill_tree(node, parent=None):
        target = QTreeWidgetItem(parent, [node.label]) if parent is not None else QTreeWidgetItem(tree_widget, [node.label])
        for child in node.children:
            fill_tree(child, target)

    if result.tree is not None:
        fill_tree(result.tree)
    tree_widget.expandToDepth(2)
    tree_widget.resizeColumnToContents(0)

    summary = getattr(output_widget, "_plan_summary", None) or output_widget.property("planSummary")
    details_button = getattr(output_widget, "_plan_details_button", None) or output_widget.property("planDetailsButton")
    natural = "NATURAL" in result.raw.upper()
    access = "varredura natural" if natural else "índice ou acesso otimizado"
    suggestion_lines = "\n".join(f"• {item}" for item in result.suggestions) or "• Nenhuma recomendação adicional."
    summary_text = f"Acesso identificado: {access}.\n\nRecomendações\n{suggestion_lines}"
    if summary is not None:
        summary.setText(summary_text)
    output_widget.setPlainText(result.raw.strip())
    output_widget.setVisible(False)
    if details_button is not None:
        details_button.setEnabled(bool(result.raw.strip()))
        details_button.setText("Mostrar detalhes técnicos")



COMPARE_HEADERS = ["Ação", "Tipo", "Nome", "Destrutiva", "DDL de origem"]
ALL_ACTIONS = "Todas as ações"


def health_report_text(report) -> str:
    """Plain-text rendering of a health report (metrics, then findings)."""
    lines = ["INDICADORES", ""] + [f"{key}: {value}" for key, value in report.metrics.items()]
    lines.extend(["", "RECOMENDAÇÕES", ""])
    for finding in report.findings:
        lines.extend([f"[{finding.severity.upper()}] {finding.title}", f"Evidência: {finding.evidence}", f"Ação sugerida: {finding.recommendation}", ""])
    return "\n".join(lines)


def compare_report_text(changes, source_name: str, target_name: str) -> str:
    """Plain-text comparison report including the migration preview."""
    from .schema import generate_migration

    lines = [f"ORIGEM: {source_name}", f"DESTINO: {target_name}", "", f"Diferenças: {len(changes)}", ""]
    for change in changes:
        marker = "REVISAR" if change.destructive else change.action
        lines.append(f"[{marker}] {change.object.kind} {change.object.name}")
    lines.extend(["", "PRÉVIA DE MIGRAÇÃO", "", generate_migration(changes)])
    return "\n".join(lines)


def fill_compare_table(table, changes) -> None:
    from PySide6.QtWidgets import QTableWidgetItem

    table.setSortingEnabled(False)
    table.clear()
    table.setColumnCount(len(COMPARE_HEADERS))
    table.setRowCount(len(changes))
    table.setHorizontalHeaderLabels(COMPARE_HEADERS)
    for row, change in enumerate(changes):
        values = [change.action, change.object.kind, change.object.name, "SIM" if change.destructive else "NÃO", change.object.ddl]
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(str(value)))
    table.resizeColumnsToContents()
    table.setSortingEnabled(True)


def filter_compare_rows(table, text: str, action: str) -> None:
    needle = (text or "").strip().casefold()
    for row in range(table.rowCount()):
        values = [table.item(row, col).text() if table.item(row, col) else "" for col in range(table.columnCount())]
        matches_text = not needle or needle in " ".join(values).casefold()
        matches_action = action == ALL_ACTIONS or values[0] == action
        table.setRowHidden(row, not (matches_text and matches_action))
