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


_OBJECT_ICON_CACHE = {}

# kind -> (accent color, shape).  Colors match the group markers above.
_OBJECT_ICON_STYLE = {
    "TABLE": ("#2563eb", "table"),
    "VIEW": ("#0891b2", "view"),
    "PROCEDURE": ("#7c3aed", "play"),
    "FUNCTION": ("#9333ea", "play_outline"),
    "TRIGGER": ("#ea580c", "bolt"),
    "INDEX": ("#d97706", "bars"),
    "CONSTRAINT": ("#dc2626", "shield"),
    "DOMAIN": ("#0d9488", "ring"),
    "GENERATOR": ("#64748b", "steps"),
    "SEQUENCE": ("#64748b", "steps"),
    "EXCEPTION": ("#dc2626", "warning"),
    "PACKAGE": ("#7c3aed", "box"),
}


def make_object_icon(kind: str):
    """Small drawn glyph per object type, cached; unknown types get a neutral dot."""
    key = str(kind or "").upper()
    if key in _OBJECT_ICON_CACHE:
        return _OBJECT_ICON_CACHE[key]
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

    accent, shape = _OBJECT_ICON_STYLE.get(key, ("#64748b", "dot"))
    pixmap = QPixmap(32, 32)  # drawn on a 16x16 grid at 2x for sharp edges on scaled screens
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    color = QColor(accent)
    pen = QPen(color, 1.4)
    painter.setPen(pen)
    painter.setBrush(QColor(accent))
    if shape == "table":
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRoundedRect(QRectF(2.5, 3.5, 11, 9), 1.5, 1.5)
        painter.drawLine(QPointF(2.5, 7.5), QPointF(13.5, 7.5))
        painter.drawLine(QPointF(7.5, 3.5), QPointF(7.5, 12.5))
    elif shape == "view":
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawEllipse(QRectF(2, 4.5, 12, 7))
        painter.setBrush(color)
        painter.drawEllipse(QRectF(6, 6.5, 4, 4))
    elif shape == "play":
        painter.drawPolygon(QPolygonF([QPointF(4.5, 3), QPointF(13, 8), QPointF(4.5, 13)]))
    elif shape == "play_outline":
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawPolygon(QPolygonF([QPointF(4.5, 3), QPointF(13, 8), QPointF(4.5, 13)]))
    elif shape == "bolt":
        painter.drawPolygon(QPolygonF([QPointF(9.5, 2), QPointF(4, 9), QPointF(7.5, 9), QPointF(6.5, 14), QPointF(12, 6.5), QPointF(8.5, 6.5)]))
    elif shape == "bars":
        for row, width in enumerate((11, 8, 5)):
            painter.drawLine(QPointF(2.5, 4 + row * 4), QPointF(2.5 + width, 4 + row * 4))
    elif shape == "shield":
        painter.drawPolygon(QPolygonF([QPointF(3.5, 3), QPointF(12.5, 3), QPointF(12.5, 8), QPointF(8, 13.5), QPointF(3.5, 8)]))
    elif shape == "ring":
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawEllipse(QRectF(3, 3, 10, 10))
    elif shape == "steps":
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawPolyline(QPolygonF([QPointF(2.5, 12.5), QPointF(2.5, 9), QPointF(7, 9), QPointF(7, 5.5), QPointF(13.5, 5.5)]))
    elif shape == "warning":
        painter.drawPolygon(QPolygonF([QPointF(8, 2.5), QPointF(14, 13), QPointF(2, 13)]))
    elif shape == "box":
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawRect(QRectF(3, 4, 10, 9))
        painter.drawLine(QPointF(3, 7), QPointF(13, 7))
    else:
        painter.drawEllipse(QRectF(5, 5, 6, 6))
    painter.end()
    icon = QIcon(pixmap)
    _OBJECT_ICON_CACHE[key] = icon
    return icon


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
            child.setIcon(0, make_object_icon(getattr(obj, "kind", "")))
            child.setToolTip(0, f"{label}: {obj.name}")
            parent.addChild(child)
        parent.setExpanded(True)
