"""MDI workspace used by the SQL document area."""

from __future__ import annotations


try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import QVBoxLayout, QMdiArea, QMdiSubWindow, QWidget

    class _SqlSubWindow(QMdiSubWindow):
        closed = Signal(object)

        def closeEvent(self, event):
            owner = self.parent()
            if owner is not None and not getattr(owner, "_removing", False):
                self.closed.emit(self)
                event.ignore()
                return
            super().closeEvent(event)


    class SqlMdiArea(QMdiArea):
        """QTabWidget-compatible facade backed by movable MDI sub-windows."""

        # The application has its own SQL document bar with the title and
        # close button.  Keeping the native MDI title bar as well duplicates
        # every document name and wastes vertical space.
        _SUBWINDOW_FLAGS = Qt.SubWindow | Qt.FramelessWindowHint

        currentChanged = Signal(int)
        tabCloseRequested = Signal(int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._removing = False
            self.setViewMode(QMdiArea.SubWindowView)
            self.setActivationOrder(QMdiArea.ActivationHistoryOrder)
            self.subWindowActivated.connect(self._on_activated)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            # Frameless SQL children do not receive the native MDI maximize
            # relayout automatically. Fit every document to the new viewport
            # whenever the main window is resized or maximized.
            viewport_rect = self.viewport().rect()
            for sub in self._sql_subwindows():
                sub.setGeometry(viewport_rect)

        def setTabsClosable(self, _enabled):
            return None

        def _new_subwindow(self, title, sql_document, delete_on_close):
            """Create a consistently configured MDI child window."""
            sub = _SqlSubWindow(self)
            sub.setAttribute(Qt.WA_DeleteOnClose, delete_on_close)
            sub.setWindowTitle(title)
            sub.setProperty("sql_document", sql_document)
            sub.setWindowFlags(self._SUBWINDOW_FLAGS)
            self.addSubWindow(sub)
            return sub

        def addTab(self, widget, title):
            sub = self._new_subwindow(title, True, True)
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(widget, 1)
            container.setProperty("sql_editor", widget.property("sql_editor") or widget)
            sub.setWidget(container)
            sub.closed.connect(self._on_close_requested)
            sub.resize(760, 480)
            sub.showMaximized()
            sub.setGeometry(self.viewport().rect())
            self.setActiveSubWindow(sub)
            # ``widget`` is the document tab container.  SQL indexes are
            # identified by the editor stored on that container, so returning
            # ``indexOf(widget)`` would yield -1 and leave per-window
            # toolbars parentless (and immediately destroyed by Qt).
            return self.indexOf(container.property("sql_editor"))

        def add_panel(self, widget, title, width=820, height=360):
            """Add a non-SQL form to the MDI workspace without affecting SQL indexes."""
            sub = self._new_subwindow(title, False, False)
            sub.setWidget(widget)
            sub.resize(width, height)
            sub.closed.connect(lambda closed_sub: closed_sub.hide())
            # Auxiliary panels are shown explicitly by the action that owns
            # them; keeping them hidden here prevents an empty result panel
            # from reappearing when the main window is restored.
            return sub

        def removeTab(self, index):
            sub = self._subwindow(index)
            if sub is None:
                return
            self._removing = True
            try:
                self.removeSubWindow(sub)
                sub.close()
                sub.deleteLater()
            finally:
                self._removing = False
            self._on_activated(self.activeSubWindow())

        def count(self):
            return len(self._sql_subwindows())

        def widget(self, index):
            sub = self._subwindow(index)
            return self._editor_for_subwindow(sub)

        def indexOf(self, widget):
            for index, sub in enumerate(self._sql_subwindows()):
                if self._editor_for_subwindow(sub) is widget:
                    return index
            return -1

        @staticmethod
        def _editor_for_subwindow(sub):
            container = sub.widget() if sub is not None else None
            return container.property("sql_editor") if container is not None else None

        def _subwindow(self, index):
            windows = self._sql_subwindows()
            return windows[index] if 0 <= index < len(windows) else None

        def _sql_subwindows(self):
            return [sub for sub in self.subWindowList() if sub.property("sql_document")]

        def currentIndex(self):
            active = self.activeSubWindow()
            if active is None or not active.property("sql_document"):
                return -1
            try:
                return self._sql_subwindows().index(active)
            except ValueError:
                return -1

        def setCurrentIndex(self, index):
            sub = self._subwindow(index)
            if sub is not None:
                self.setActiveSubWindow(sub)
                sub.showMaximized()
                sub.raise_()

        def setCurrentWidget(self, widget):
            index = self.indexOf(widget)
            if index >= 0:
                self.setCurrentIndex(index)

        def setTabText(self, index, title):
            sub = self._subwindow(index)
            if sub is not None:
                if sub.property("sql_document") and " · " in title:
                    title = title.split(" · ", 1)[0]
                sub.setWindowTitle(title)

        def tabText(self, index):
            sub = self._subwindow(index)
            return sub.windowTitle() if sub is not None else ""

        def setTabToolTip(self, index, text):
            sub = self._subwindow(index)
            if sub is not None:
                sub.setToolTip(text)

        def add_toolbar(self, index, toolbar):
            sub = self._subwindow(index)
            container = sub.widget() if sub is not None else None
            if container is not None and container.layout() is not None:
                container.layout().insertWidget(0, toolbar)

        def cascade_windows(self):
            self.cascadeSubWindows()

        def tile_windows(self):
            self.tileSubWindows()

        def maximize_current(self):
            active = self.activeSubWindow()
            if active is not None:
                active.showMaximized()

        def toggle_maximize_current(self):
            active = self.activeSubWindow()
            if active is None:
                return
            if active.isMaximized():
                active.showNormal()
            else:
                active.showMaximized()

        def restore_windows(self):
            for sub in self.subWindowList():
                if sub.property("sql_document"):
                    sub.showMaximized()
            self._on_activated(self.activeSubWindow())

        def activate_next(self):
            self.activateNextSubWindow()

        def activate_previous(self):
            self.activatePreviousSubWindow()

        def _on_close_requested(self, sub):
            widget = self._editor_for_subwindow(sub)
            index = self.indexOf(widget)
            if index >= 0:
                self.tabCloseRequested.emit(index)

        def _on_activated(self, _sub):
            if _sub is not None and _sub.property("sql_document"):
                _sub.showMaximized()
            self.currentChanged.emit(self.currentIndex())

except ImportError:  # pragma: no cover - allows headless model imports
    SqlMdiArea = None

