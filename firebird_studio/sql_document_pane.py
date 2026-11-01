"""Editor on top, results and history below, for one SQL document."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QTabWidget


class SqlDocumentPane(QSplitter):
    """Vertical split with the editor above a tabbed results area.

    The results area stays hidden until something needs it, so an empty grid
    never takes room from the editor.  The tab-like methods keep the calls the
    window already makes (`setCurrentWidget`, `indexOf`, `setTabText`) working.
    """

    MIN_LOWER_HEIGHT = 60

    def __init__(self, editor_frame, result_table, history_panel):
        super().__init__(Qt.Vertical)
        self.setObjectName("sqlDocumentPane")
        self.setHandleWidth(6)
        self.editor_frame = editor_frame
        self.lower_tabs = QTabWidget()
        self.lower_tabs.setObjectName("sqlDocumentTabs")
        self.lower_tabs.setDocumentMode(True)
        self.lower_tabs.setUsesScrollButtons(True)
        self.lower_tabs.addTab(result_table, "Resultado")
        self.lower_tabs.addTab(history_panel, "Histórico SQL")
        self.addWidget(editor_frame)
        self.addWidget(self.lower_tabs)
        self.setStretchFactor(0, 3)
        self.setStretchFactor(1, 2)
        self.setCollapsible(0, False)
        self.lower_tabs.hide()

    def results_visible(self) -> bool:
        return self.lower_tabs.isVisible() and self.sizes()[1] >= self.MIN_LOWER_HEIGHT

    def show_results(self) -> None:
        """Reveal the lower area, restoring a usable height if it was dragged shut."""
        self.lower_tabs.show()
        total = sum(self.sizes()) or 500
        if self.sizes()[1] < self.MIN_LOWER_HEIGHT:
            self.setSizes([total * 3 // 5, total * 2 // 5])

    def setCurrentWidget(self, widget) -> None:
        if widget is self.editor_frame:
            getattr(widget, "_child", widget).setFocus()
            return
        if self.lower_tabs.indexOf(widget) >= 0:
            self.lower_tabs.setCurrentWidget(widget)
            self.show_results()

    def currentWidget(self):
        return self.lower_tabs.currentWidget() if self.results_visible() else self.editor_frame

    def indexOf(self, widget) -> int:
        if widget is self.editor_frame:
            return 0
        index = self.lower_tabs.indexOf(widget)
        return index + 1 if index >= 0 else -1

    def setTabText(self, index: int, text: str) -> None:
        if index >= 1:
            self.lower_tabs.setTabText(index - 1, text)
