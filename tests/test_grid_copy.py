import json
import os
import unittest
from datetime import date, datetime
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from firebird_studio import grid_copy

COLUMNS = ["ID", "NOME", "SALDO"]
ROWS = [
    [1, "Ana", Decimal("10.50")],
    [2, None, None],
    [3, "O'Brien | \"Jr\"\nlinha 2", 7.0],
]


class FormatTests(unittest.TestCase):
    def test_csv_quotes_and_leaves_null_empty(self):
        text = grid_copy.as_csv(COLUMNS, ROWS)
        self.assertEqual(text.splitlines()[:3], ["ID,NOME,SALDO", "1,Ana,10.50", "2,,"])
        self.assertIn('"O\'Brien | ""Jr""', text)

    def test_markdown_escapes_pipes_and_newlines_and_marks_null(self):
        lines = grid_copy.as_markdown(COLUMNS, ROWS).splitlines()
        self.assertEqual(lines[0], "| ID | NOME | SALDO |")
        self.assertEqual(lines[1], "| --- | --- | --- |")
        self.assertEqual(lines[3], "| 2 | NULL | NULL |")
        self.assertIn("O'Brien \\| \"Jr\"<br>linha 2", lines[4])

    def test_json_keeps_types_and_null(self):
        data = json.loads(grid_copy.as_json(COLUMNS, ROWS))
        self.assertEqual(data[0], {"ID": 1, "NOME": "Ana", "SALDO": "10.50"})
        self.assertEqual(data[1], {"ID": 2, "NOME": None, "SALDO": None})
        self.assertEqual(data[2]["SALDO"], 7.0)

    def test_insert_renders_firebird_literals(self):
        rows = [[1, "O'Brien", None, True, date(2026, 1, 2), datetime(2026, 1, 2, 3, 4, 5), b"\x01\xff", Decimal("1.5")]]
        sql = grid_copy.as_insert(list("ABCDEFGH"), rows, 'Minha "Tabela"')
        self.assertEqual(
            sql,
            'INSERT INTO "Minha ""Tabela""" ("A", "B", "C", "D", "E", "F", "G", "H") '
            "VALUES (1, 'O''Brien', NULL, TRUE, '2026-01-02', '2026-01-02 03:04:05', x'01ff', 1.5);\n",
        )

    def test_insert_has_one_statement_per_row(self):
        self.assertEqual(grid_copy.as_insert(COLUMNS, ROWS, "T").count("INSERT INTO"), 3)

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValueError):
            grid_copy.format_rows("xml", COLUMNS, ROWS)

    def test_every_menu_format_is_supported(self):
        for kind in grid_copy.FORMATS:
            self.assertTrue(grid_copy.format_rows(kind, COLUMNS, ROWS))


try:
    from PySide6.QtWidgets import QTableWidget
except ImportError:  # pragma: no cover - UI extras are optional
    QTableWidget = None


@unittest.skipIf(QTableWidget is None, "PySide6 não instalado")
class GridRowsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def table(self):
        from firebird_studio.result_views import configure_result_table, fill_table

        table = configure_result_table(QTableWidget())
        fill_table(table, COLUMNS, [tuple(row) for row in ROWS[:2]] + [(3, "c", 1)])
        self.addCleanup(table.deleteLater)
        return table

    def test_no_selection_copies_every_visible_row_with_raw_values(self):
        table = self.table()
        table.setRowHidden(2, True)
        columns, rows = grid_copy.grid_rows(table)
        self.assertEqual(columns, COLUMNS)
        self.assertEqual(rows, [[1, "Ana", Decimal("10.50")], [2, None, None]])

    def test_selection_limits_the_rows_and_keeps_screen_order(self):
        table = self.table()
        table.selectRow(2)
        _, rows = grid_copy.grid_rows(table)
        self.assertEqual([row[0] for row in rows], [3])

    def test_sorted_grid_is_copied_in_the_order_shown(self):
        from PySide6.QtCore import Qt

        table = self.table()
        table.sortItems(0, Qt.DescendingOrder)
        _, rows = grid_copy.grid_rows(table)
        self.assertEqual([row[0] for row in rows], [3, 2, 1])

    def test_edited_cell_without_raw_value_falls_back_to_text(self):
        from PySide6.QtWidgets import QTableWidgetItem

        table = self.table()
        table.setItem(0, 1, QTableWidgetItem("novo"))
        _, rows = grid_copy.grid_rows(table)
        self.assertEqual(rows[0][1], "novo")


if __name__ == "__main__":
    unittest.main()
