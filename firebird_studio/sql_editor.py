"""SQL editor widgets and the application class that routes F5.

Qt is imported lazily so headless model tests can import ``firebird_studio.ui``
without PySide6; every name below is ``None`` when Qt is unavailable.
"""
from __future__ import annotations

try:
    from PySide6.QtCore import QObject, Signal, Slot, QEvent, Qt, QTimer, QAbstractNativeEventFilter
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat
    from PySide6.QtWidgets import QApplication, QWidget

    class SqlEditor(__import__("PySide6.QtWidgets", fromlist=["QTextEdit"]).QTextEdit):
        """SQL editor with a direct keyboard path for the execution commands."""

        execute_requested = Signal(bool)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._gutter = _LineNumberGutter(self)
            self.document().blockCountChanged.connect(self._update_gutter_width)
            self.verticalScrollBar().valueChanged.connect(lambda _value: self._gutter.update())
            self.textChanged.connect(self._gutter.update)
            self.cursorPositionChanged.connect(self._gutter.update)
            self._update_gutter_width()

        def gutter_width(self) -> int:
            digits = max(2, len(str(self.document().blockCount())))
            return 12 + self.fontMetrics().horizontalAdvance("9") * digits

        def _update_gutter_width(self, *_args):
            self.setViewportMargins(self.gutter_width(), 0, 0, 0)
            self._gutter.update()

        def resizeEvent(self, event):
            super().resizeEvent(event)
            rect = self.contentsRect()
            self._gutter.setGeometry(QRect(rect.left(), rect.top(), self.gutter_width(), rect.height()))

        def paint_gutter(self, painter):
            dark = self.palette().base().color().lightness() < 128
            painter.fillRect(painter.viewport(), QColor("#232a36" if dark else "#eef2f7"))
            muted, active = QColor("#7f8ea3"), QColor("#e5e7eb" if dark else "#1f2937")
            current = self.textCursor().blockNumber()
            painter.setFont(self.font())
            block = self.document().begin()
            layout = self.document().documentLayout()
            offset = self.verticalScrollBar().value()
            height = self.viewport().height()
            while block.isValid():
                rect = layout.blockBoundingRect(block)
                top = rect.top() - offset
                if top > height:
                    break
                if top + rect.height() >= 0 and block.isVisible():
                    painter.setPen(active if block.blockNumber() == current else muted)
                    painter.drawText(0, int(top), self._gutter.width() - 6, int(rect.height()),
                                     Qt.AlignRight | Qt.AlignTop, str(block.blockNumber() + 1))
                block = block.next()

        def keyPressEvent(self, event):
            if event.key() == Qt.Key_F5:
                modifiers = event.modifiers()
                if modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier:
                    self.execute_requested.emit(True)
                    event.accept()
                    return
                if not modifiers & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier):
                    self.execute_requested.emit(False)
                    event.accept()
                    return
            super().keyPressEvent(event)

    class _LineNumberGutter(QWidget):
        def __init__(self, editor):
            super().__init__(editor)
            self._editor = editor
            self.setAttribute(Qt.WA_TransparentForMouseEvents)

        def paintEvent(self, event):
            painter = QPainter(self)
            self._editor.paint_gutter(painter)
            painter.end()

    class SqlExecutionApplication(QApplication):
        """Route SQL execution keys before any editor or MDI child handles them."""

        def notify(self, receiver, event):
            if event.type() == QEvent.KeyPress and event.key() == Qt.Key_F5:
                # Let the editor receive its own key event.  SqlEditor has a
                # direct keyPressEvent path so completion popups and the
                # focused MDI document keep the normal Qt event flow.  The
                # application level route is only for focus outside an
                # editor (menus, result panels and other SQL subviews).
                if isinstance(receiver, SqlEditor):
                    return super().notify(receiver, event)
                handler = getattr(self, "_sql_execution_handler", None)
                if handler is not None:
                    modifiers = event.modifiers()
                    selection = None
                    if modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier:
                        selection = True
                    elif not modifiers & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier):
                        selection = False
                    if selection is not None:
                        if not getattr(self, "_sql_execution_pending", False):
                            self._sql_execution_pending = True

                            def dispatch():
                                self._sql_execution_pending = False
                                current_handler = getattr(self, "_sql_execution_handler", None)
                                if current_handler is not None:
                                    current_handler(selection)

                            QTimer.singleShot(0, dispatch)
                        event.accept()
                        return True
            return super().notify(receiver, event)

    class WindowsF5Filter(QAbstractNativeEventFilter):
        """Catch the physical F5 message before Windows/Qt can consume it."""

        def nativeEventFilter(self, event_type, message):
            if event_type not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
                return False, 0
            try:
                import ctypes
                from ctypes import wintypes

                msg = wintypes.MSG.from_address(int(message))
                if msg.message not in (0x0100, 0x0104) or msg.wParam != 0x74:
                    return False, 0
                app = QApplication.instance()
                handler = getattr(app, "_sql_execution_handler", None) if app is not None else None
                if handler is None:
                    return False, 0
                ctrl = bool(ctypes.windll.user32.GetKeyState(0x11) & 0x8000)
                shift = bool(ctypes.windll.user32.GetKeyState(0x10) & 0x8000)
                alt = bool(ctypes.windll.user32.GetKeyState(0x12) & 0x8000)
                if alt or (ctrl and not shift):
                    return False, 0
                selection = bool(ctrl and shift)
                if not getattr(app, "_sql_execution_pending", False):
                    app._sql_execution_pending = True

                    def dispatch():
                        app._sql_execution_pending = False
                        current_handler = getattr(app, "_sql_execution_handler", None)
                        if current_handler is not None:
                            current_handler(selection)

                    QTimer.singleShot(0, dispatch)
                return True, 0
            except (AttributeError, TypeError, ValueError, OSError):
                return False, 0

    class SqlHighlighter(QSyntaxHighlighter):
        """Lightweight SQL highlighting that works offline in the packaged app."""

        def __init__(self, document):
            super().__init__(document)
            self._keyword_format = QTextCharFormat()
            self._keyword_format.setForeground(QColor("#005cc5"))
            self._keyword_format.setFontWeight(QFont.Bold)
            self._type_format = QTextCharFormat()
            self._type_format.setForeground(QColor("#7b3f00"))
            self._string_format = QTextCharFormat()
            self._string_format.setForeground(QColor("#008000"))
            self._comment_format = QTextCharFormat()
            self._comment_format.setForeground(QColor("#6a737d"))
            self._number_format = QTextCharFormat()
            self._number_format.setForeground(QColor("#8b008b"))
            from .sql_completion import FIREBIRD_RESERVED_WORDS, FIREBIRD_TYPES
            self._keywords = FIREBIRD_RESERVED_WORDS
            self._types = FIREBIRD_TYPES

        def set_theme(self, dark: bool):
            """Use readable syntax colors in both the light and dark themes."""
            colors = {
                "keyword": "#7db7ff" if dark else "#005cc5",
                "type": "#f2b880" if dark else "#7b3f00",
                "string": "#98d89c" if dark else "#008000",
                "comment": "#9aa4b2" if dark else "#6a737d",
                "number": "#d9a1ff" if dark else "#8b008b",
            }
            self._keyword_format.setForeground(QColor(colors["keyword"]))
            self._type_format.setForeground(QColor(colors["type"]))
            self._string_format.setForeground(QColor(colors["string"]))
            self._comment_format.setForeground(QColor(colors["comment"]))
            self._number_format.setForeground(QColor(colors["number"]))
            self.rehighlight()

        def highlightBlock(self, text):
            import re

            protected: list[tuple[int, int]] = []
            for match in re.finditer(r"--[^\n]*|/\*.*?\*/", text):
                self.setFormat(match.start(), match.end() - match.start(), self._comment_format)
                protected.append((match.start(), match.end()))
            for match in re.finditer(r"'(?:''|[^'])*'", text):
                self.setFormat(match.start(), match.end() - match.start(), self._string_format)
                protected.append((match.start(), match.end()))

            def is_protected(start: int, end: int) -> bool:
                return any(start < protected_end and end > protected_start for protected_start, protected_end in protected)

            for match in re.finditer(r"\b\d+(?:\.\d+)?\b", text):
                if is_protected(match.start(), match.end()):
                    continue
                self.setFormat(match.start(), match.end() - match.start(), self._number_format)
            for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", text):
                if is_protected(match.start(), match.end()):
                    continue
                word = match.group(0).upper()
                if word in self._keywords:
                    self.setFormat(match.start(), match.end() - match.start(), self._keyword_format)
                elif word in self._types:
                    self.setFormat(match.start(), match.end() - match.start(), self._type_format)


    __all__ = ["SqlEditor", "SqlHighlighter", "SqlExecutionApplication", "WindowsF5Filter"]
except ImportError:  # pragma: no cover - allows headless model tests
    SqlHighlighter = None
    SqlExecutionApplication = None
    SqlEditor = None
    WindowsF5Filter = None
