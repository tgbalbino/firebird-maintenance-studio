import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent

from firebird_studio.ui import SqlExecutionApplication


class SqlShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = SqlExecutionApplication.instance() or SqlExecutionApplication([])

    def test_f5_dispatches_full_query_and_selection(self):
        calls = []
        self.app._sql_execution_handler = lambda selection: calls.append(selection)
        receiver = QObject()

        self.app.notify(receiver, QKeyEvent(QEvent.KeyPress, Qt.Key_F5, Qt.NoModifier))
        self.app.processEvents()
        self.app.notify(
            receiver,
            QKeyEvent(QEvent.KeyPress, Qt.Key_F5, Qt.ControlModifier | Qt.ShiftModifier),
        )
        self.app.processEvents()

        self.assertEqual(calls, [False, True])
        self.app._sql_execution_handler = None


if __name__ == "__main__":
    unittest.main()
