"""Crisp vector toolbar icons drawn with QPainter (no font glyphs, no image files)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

SIZE = 32  # drawn at 2x and scaled down by the button for sharp edges
LIGHT_INK = "#1f2a44"
DARK_INK = "#e5edff"


def _canvas():
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    return pixmap, painter


def _pen(color: str, width: float = 3.2) -> QPen:
    return QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def _refresh(color: str) -> QPixmap:
    pixmap, painter = _canvas()
    painter.setPen(_pen(color))
    rect = QRectF(7, 7, 18, 18)
    # 280 degree arc starting at the top-right, leaving a gap for the arrow.
    painter.drawArc(rect, 40 * 16, 280 * 16)
    head = QPainterPath()
    tip = QPointF(24.5, 7.0)
    head.moveTo(tip)
    head.lineTo(QPointF(24.5, 14.0))
    head.moveTo(tip)
    head.lineTo(QPointF(17.5, 7.0))
    painter.drawPath(head)
    painter.end()
    return pixmap


def _collapse_all(color: str) -> QPixmap:
    pixmap, painter = _canvas()
    painter.setPen(_pen(color))
    for offset in (0, 9):
        path = QPainterPath()
        path.moveTo(8, 14 + offset - 1)
        path.lineTo(16, 6 + offset - 1)
        path.lineTo(24, 14 + offset - 1)
        painter.drawPath(path)
    painter.end()
    return pixmap


def _play(color: str) -> QPixmap:
    pixmap, painter = _canvas()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    path = QPainterPath()
    path.moveTo(10, 6)
    path.lineTo(26, 16)
    path.lineTo(10, 26)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return pixmap


_DRAWERS = {"refresh": _refresh, "collapse": _collapse_all, "play": _play}
# Icons that sit on a colored (primary) button stay white in every theme.
_FIXED_INK = {"play": "#ffffff"}


def make_icon(name: str, dark: bool) -> QIcon:
    color = _FIXED_INK.get(name, DARK_INK if dark else LIGHT_INK)
    return QIcon(_DRAWERS[name](color))


class ThemedIcons:
    """Keeps icons in sync with the light/dark theme."""

    def __init__(self):
        self._buttons: list[tuple[object, str]] = []
        self._dark = False

    def attach(self, button, name: str):
        self._buttons.append((button, name))
        button.setIcon(make_icon(name, self._dark))

    def set_dark(self, dark: bool):
        self._dark = dark
        alive = []
        for button, name in self._buttons:
            try:
                button.setIcon(make_icon(name, dark))
            except RuntimeError:
                continue  # the button was destroyed with its window
            alive.append((button, name))
        self._buttons = alive
