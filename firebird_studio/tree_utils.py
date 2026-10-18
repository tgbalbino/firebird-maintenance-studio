from __future__ import annotations

GROUP_LABELS = {
    "TABLE": "Tabelas", "VIEW": "Views", "PROCEDURE": "Procedures", "FUNCTION": "Functions",
    "TRIGGER": "Triggers", "DOMAIN": "Domínios", "INDEX": "Índices", "CONSTRAINT": "Restrições",
    "SEQUENCE": "Sequências", "GENERATOR": "Generators", "EXCEPTION": "Exceções", "PACKAGE": "Packages",
}

# Keep the catalog tree in the same order used by Firebird administration
# tools. Types not listed here are appended alphabetically afterwards.
GROUP_ORDER = (
    "Domínios", "Tabelas", "Views", "Procedures", "Triggers", "Generators",
    "Exceções", "Functions", "Roles", "Índices", "Scripts", "Restrições",
    "Sequências", "Packages",
)


def object_group_label(kind: str) -> str:
    clean_kind = str(kind or "").upper()
    return GROUP_LABELS.get(clean_kind, clean_kind.title())


def group_objects(objects):
    """Group schema objects by display label in stable name order."""
    groups = {}
    for obj in objects:
        groups.setdefault(object_group_label(getattr(obj, "kind", "")), []).append(obj)
    ordered_labels = [label for label in GROUP_ORDER if label in groups]
    ordered_labels.extend(sorted(label for label in groups if label not in GROUP_ORDER))
    return {
        label: sorted(groups[label], key=lambda item: str(getattr(item, "name", "")).casefold())
        for label in ordered_labels
    }


def make_database_icon(connected: bool):
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#188038" if connected else "#80868b"))
    painter.setPen(QColor("#0f5132" if connected else "#5f6368"))
    painter.drawEllipse(2, 2, 12, 12)
    painter.end()
    return QIcon(pixmap)


def make_group_icon(label: str):
    """Create a small category marker without requiring image assets."""
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

    colors = {
        "Tabelas": ("#2563eb", "#1d4ed8"),
        "Views": ("#0891b2", "#0e7490"),
        "Procedures": ("#7c3aed", "#6d28d9"),
        "Functions": ("#9333ea", "#7e22ce"),
        "Índices": ("#d97706", "#b45309"),
        "Restrições": ("#dc2626", "#b91c1c"),
        "Triggers": ("#ea580c", "#c2410c"),
    }
    fill, outline = colors.get(label, ("#64748b", "#475569"))
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(fill))
    painter.setPen(QColor(outline))
    painter.drawRoundedRect(2, 2, 12, 12, 3, 3)
    painter.end()
    return QIcon(pixmap)


def populate_profile_children(profile_item, objects) -> None:
    from PySide6.QtWidgets import QTreeWidgetItem
    from PySide6.QtGui import QFont

    groups = group_objects(objects)
    for label in groups:
        parent = QTreeWidgetItem([f"{label} ({len(groups[label])})"])
        parent.setIcon(0, make_group_icon(label))
        font = QFont(parent.font(0))
        font.setBold(True)
        parent.setFont(0, font)
        parent.setToolTip(0, f"{len(groups[label])} objeto(s) em {label}. Duplo clique para abrir.")
        profile_item.addChild(parent)
        for obj in groups[label]:
            child = QTreeWidgetItem([obj.name])
            child.setData(0, 32, obj)
            child.setToolTip(0, f"{label}: {obj.name}")
            parent.addChild(child)
        parent.setExpanded(True)
