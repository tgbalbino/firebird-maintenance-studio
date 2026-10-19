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

