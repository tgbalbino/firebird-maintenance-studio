"""Visual components for plan analysis and diagnostic output."""

from __future__ import annotations


def create_plan_panel():
    """Create the plan tree/output panel and return its widgets."""
    from PySide6.QtWidgets import QTreeWidget, QTextEdit, QVBoxLayout, QWidget

    tree = QTreeWidget()
    tree.setHeaderLabels(["Árvore do plano"])
    output = QTextEdit()
    output.setReadOnly(True)
    output.setPlaceholderText("O plano de acesso e as sugestões aparecerão aqui.")
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.addWidget(tree)
    layout.addWidget(output, 1)
    return panel, tree, output


def render_plan(tree_widget, output_widget, result):
    """Render a plan result into its tree and textual diagnostics view."""
    from PySide6.QtWidgets import QTreeWidgetItem

    lines = ["ÁRVORE DO PLANO", ""]
    tree_widget.clear()

    def fill_tree(node, parent=None):
        target = parent
        if node.label != "Plano de acesso":
            target = QTreeWidgetItem(parent, [node.label]) if parent is not None else QTreeWidgetItem(tree_widget, [node.label])
        for child in node.children:
            fill_tree(child, target)

    fill_tree(result.tree)
    tree_widget.expandAll()

    def visit(node, depth=0):
        if node.label != "Plano de acesso":
            lines.append("  " * depth + "• " + node.label)
        for child in node.children:
            visit(child, depth + (0 if node.label == "Plano de acesso" else 1))

    visit(result.tree)
    lines.extend(["", "SUGESTÕES", ""])
    lines.extend(f"- {item}" for item in result.suggestions)
    output_widget.setPlainText("\n".join(lines) + "\n\nSAÍDA ISQL\n" + result.raw)

