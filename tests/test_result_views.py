import os
import unittest
from datetime import date, datetime
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QTableWidget
except ImportError:  # pragma: no cover - UI extras are optional
    QTableWidget = None


@unittest.skipIf(QTableWidget is None, "PySide6 não instalado")
class ResultGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def grid(self, rows, columns=("V",)):
        from firebird_studio.result_views import configure_result_table, fill_table

        table = configure_result_table(QTableWidget())
        fill_table(table, list(columns), rows)
        self.addCleanup(table.deleteLater)
        return table

    def column(self, table, index=0):
        return [table.item(row, index).text() for row in range(table.rowCount())]

    def test_numbers_sort_by_value_not_by_text(self):
        from PySide6.QtCore import Qt

        table = self.grid([(10,), (2,), (33,), (None,), (1.5,), (Decimal("7.25"),)])
        table.sortItems(0)
        self.assertEqual(self.column(table), ["", "1.5", "2", "7.25", "10", "33"])
        table.sortItems(0, Qt.DescendingOrder)
        self.assertEqual(self.column(table), ["33", "10", "7.25", "2", "1.5", ""])

    def test_dates_sort_chronologically(self):
        table = self.grid([(date(2026, 3, 1),), (date(2025, 12, 31),), (datetime(2026, 1, 2, 3, 4),)])
        table.sortItems(0)
        self.assertEqual(self.column(table)[0], "2025-12-31")

    def test_text_and_mixed_columns_still_sort_without_error(self):
        table = self.grid([("beta",), ("alfa",), (3,), (None,)])
        table.sortItems(0)
        self.assertEqual(self.column(table)[0], "")
        self.assertEqual(table.rowCount(), 4)

    def test_numbers_align_right_and_text_keeps_default(self):
        from PySide6.QtCore import Qt

        table = self.grid([(5, "x", True)], ("N", "T", "B"))
        self.assertTrue(table.item(0, 0).textAlignment() & Qt.AlignRight)
        self.assertFalse(table.item(0, 1).textAlignment() & Qt.AlignRight)
        self.assertFalse(table.item(0, 2).textAlignment() & Qt.AlignRight)  # bool is not a number

    def test_null_is_flagged_but_text_stays_empty_for_export(self):
        from firebird_studio.result_views import NULL_ROLE

        table = self.grid([(None, "")], ("A", "B"))
        self.assertTrue(table.item(0, 0).data(NULL_ROLE))
        self.assertEqual(table.item(0, 0).text(), "")
        self.assertIsNone(table.item(0, 1).data(NULL_ROLE))

    def option_for(self, table, row, column, selected=False):
        from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

        option = QStyleOptionViewItem()
        option.palette = table.palette()
        option.font = table.font()
        if selected:
            option.state |= QStyle.State_Selected
        delegate = table.itemDelegate()
        delegate.initStyleOption(option, table.model().index(row, column))
        return option

    def test_null_cell_is_drawn_as_a_muted_italic_marker(self):
        from PySide6.QtGui import QPalette

        table = self.grid([(None, "x")], ("A", "B"))
        null = self.option_for(table, 0, 0)
        value = self.option_for(table, 0, 1)
        self.assertEqual((null.text, null.font.italic()), ("NULL", True))
        self.assertEqual((value.text, value.font.italic()), ("x", False))
        self.assertNotEqual(null.palette.color(QPalette.Text), value.palette.color(QPalette.Text))

    def test_null_keeps_normal_color_when_selected(self):
        from PySide6.QtGui import QPalette

        table = self.grid([(None,)])
        selected = self.option_for(table, 0, 0, selected=True)
        self.assertEqual(selected.text, "NULL")
        self.assertEqual(selected.palette.color(QPalette.Text), table.palette().color(QPalette.Text))

    def test_refilling_keeps_a_single_delegate(self):
        from firebird_studio.result_views import fill_table, result_delegate_class

        table = self.grid([(1,)])
        delegate = table.itemDelegate()
        fill_table(table, ["V"], [(2,)])
        self.assertIs(table.itemDelegate(), delegate)
        self.assertIsInstance(delegate, result_delegate_class())


if __name__ == "__main__":
    unittest.main()
