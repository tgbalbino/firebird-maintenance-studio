from __future__ import annotations

GROUP_LABELS = {
    "TABLE": "Tabelas", "VIEW": "Views", "PROCEDURE": "Procedures", "FUNCTION": "Functions",
    "TRIGGER": "Triggers", "DOMAIN": "Domínios", "INDEX": "Índices", "CONSTRAINT": "Restrições",
    "SEQUENCE": "Sequências", "GENERATOR": "Generators", "EXCEPTION": "Exceções", "PACKAGE": "Packages",
}


def object_group_label(kind: str) -> str:
    clean_kind = str(kind or "").upper()
    return GROUP_LABELS.get(clean_kind, clean_kind.title())


def group_objects(objects):
    """Group schema objects by display label in stable name order."""
    groups = {}
    for obj in objects:
        groups.setdefault(object_group_label(getattr(obj, "kind", "")), []).append(obj)
    return {label: sorted(items, key=lambda item: str(getattr(item, "name", "")).casefold()) for label, items in groups.items()}


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


def populate_profile_children(profile_item, objects) -> None:
    from PySide6.QtWidgets import QTreeWidgetItem

    groups = group_objects(objects)
    for label in sorted(groups):
        parent = QTreeWidgetItem([f"{label} ({len(groups[label])})"])
        profile_item.addChild(parent)
        for obj in groups[label]:
            child = QTreeWidgetItem([obj.name])
            child.setData(0, 32, obj)
            parent.addChild(child)
        parent.setExpanded(True)
