"""MDI workspace used by the SQL document area."""

from __future__ import annotations


try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import QMdiArea, QMdiSubWindow

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

        currentChanged = Signal(int)
        tabCloseRequested = Signal(int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._removing = False
            self.setViewMode(QMdiArea.SubWindowView)
            self.setActivationOrder(QMdiArea.ActivationHistoryOrder)
            self.subWindowActivated.connect(self._on_activated)

        def setTabsClosable(self, _enabled):
            return None

        def addTab(self, widget, title):
            sub = _SqlSubWindow(self)
            sub.setAttribute(Qt.WA_DeleteOnClose, True)
            sub.setWindowTitle(title)
            sub.setWindowFlags(Qt.SubWindow | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
            sub.setWidget(widget)
            sub.closed.connect(self._on_close_requested)
            self.addSubWindow(sub)
            sub.resize(760, 480)
            sub.show()
            self.setActiveSubWindow(sub)
            return self.indexOf(widget)

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
            return len(self.subWindowList())

        def widget(self, index):
            sub = self._subwindow(index)
            return sub.widget() if sub is not None else None

        def indexOf(self, widget):
            for index, sub in enumerate(self.subWindowList()):
                if sub.widget() is widget:
                    return index
            return -1

        def _subwindow(self, index):
            windows = self.subWindowList()
            return windows[index] if 0 <= index < len(windows) else None

        def currentIndex(self):
            active = self.activeSubWindow()
            return self.indexOf(active.widget()) if active is not None else -1

        def setCurrentIndex(self, index):
            sub = self._subwindow(index)
            if sub is not None:
                self.setActiveSubWindow(sub)
                sub.showNormal()
                sub.raise_()

        def setCurrentWidget(self, widget):
            index = self.indexOf(widget)
            if index >= 0:
                self.setCurrentIndex(index)

        def setTabText(self, index, title):
            sub = self._subwindow(index)
            if sub is not None:
                sub.setWindowTitle(title)

        def tabText(self, index):
            sub = self._subwindow(index)
            return sub.windowTitle() if sub is not None else ""

        def setTabToolTip(self, index, text):
            sub = self._subwindow(index)
            if sub is not None:
                sub.setToolTip(text)

        def cascade_windows(self):
            self.cascadeSubWindows()

        def tile_windows(self):
            self.tileSubWindows()

        def maximize_current(self):
            active = self.activeSubWindow()
            if active is not None:
                active.showMaximized()

        def restore_windows(self):
            for sub in self.subWindowList():
                sub.showNormal()
            self._on_activated(self.activeSubWindow())

        def activate_next(self):
            self.activateNextSubWindow()

        def activate_previous(self):
            self.activatePreviousSubWindow()

        def _on_close_requested(self, sub):
            widget = sub.widget()
            index = self.indexOf(widget)
            if index >= 0:
                self.tabCloseRequested.emit(index)

        def _on_activated(self, _sub):
            self.currentChanged.emit(self.currentIndex())

except ImportError:  # pragma: no cover - allows headless model imports
    SqlMdiArea = None

