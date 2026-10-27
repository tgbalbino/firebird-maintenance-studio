import os
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from firebird_studio.activity_views import activity_metrics_lines

try:
    from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
except ImportError:  # pragma: no cover - UI extras are optional
    QApplication = None


class ActivityMetricsTests(unittest.TestCase):
    def test_lines_summarize_metrics_and_state(self):
        metrics = {"estimated_size_mb": 12.34, "page_size": 8192, "pages": 100, "ods_major": 13, "ods_minor": 0,
                   "attachments": 3, "oldest_transaction": 1, "oldest_active": 2, "next_transaction": 3}
        lines = activity_metrics_lines("Vendas", metrics, 2, datetime(2026, 10, 27, 9, 5, 7))
        self.assertEqual(lines[0], "Banco: Vendas")
        self.assertEqual(lines[1], "Tamanho estimado: 12.3 MB")
        self.assertIn("ODS: 13.0 · conexões: 3", lines[3])
        self.assertIn("Consultas em execução: 2", lines)
        self.assertIn("Estado: consultas em execução encontradas", lines)
        self.assertIn("Última atualização: 27/10/2026 09:05:07", lines)

    def test_missing_metrics_show_placeholders_and_idle_state(self):
        lines = activity_metrics_lines("X", {}, 0, datetime(2026, 1, 1))
        self.assertEqual(lines[1], "Tamanho estimado: indisponível")
        self.assertIn("Página: N/D bytes · páginas: N/D", lines)
        self.assertIn("Estado: nenhuma consulta em execução neste instante", lines)


@unittest.skipIf(QApplication is None, "PySide6 não instalado")
class ActivityTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Must be the application class the rest of the suite shares (it routes F5).
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def statements(self):
        return [
            {"id": 1, "attachment_id": 10, "user": "SYSDBA", "address": "pc1", "application": "app", "started": datetime(2026, 1, 1, 8, 0, 0), "elapsed_seconds": 2.0, "sql": "select 1"},
            {"id": 2, "attachment_id": 11, "user": "ANA", "address": "pc2", "application": "app", "started": None, "elapsed_seconds": 30.5, "sql": "select slow"},
            {"id": 3, "attachment_id": 12, "user": "BRUNO", "address": "pc3", "application": "app", "started": None, "elapsed_seconds": None, "sql": None},
        ]

    def test_fill_orders_longest_first_and_formats_cells(self):
        from firebird_studio.activity_views import ACTIVITY_HEADERS, fill_activity_table

        table = QTableWidget()
        fill_activity_table(table, self.statements())
        self.assertEqual(table.rowCount(), 3)
        self.assertEqual(table.horizontalHeaderItem(6).text(), ACTIVITY_HEADERS[6])
        self.assertEqual(table.item(0, 0).text(), "2")  # 30.5 s first
        self.assertEqual(table.item(0, 6).text(), "30.5 s")
        by_id = {table.item(r, 0).text(): r for r in range(3)}
        self.assertEqual(table.item(by_id["1"], 5).text(), "2026-01-01 08:00:00")
        self.assertEqual(table.item(by_id["3"], 5).text(), "N/D")
        self.assertEqual(table.item(by_id["3"], 6).text(), "N/D")
        self.assertEqual(table.item(by_id["3"], 7).text(), "")

    def test_duration_column_sorts_numerically(self):
        from PySide6.QtCore import Qt

        from firebird_studio.activity_views import fill_activity_table

        table = QTableWidget()
        rows = [{"id": i, "elapsed_seconds": value} for i, value in enumerate((9.0, 100.0, 20.0))]
        fill_activity_table(table, rows)
        table.sortItems(6, Qt.AscendingOrder)
        self.assertEqual([table.item(r, 6).text() for r in range(3)], ["9.0 s", "20.0 s", "100.0 s"])

    def test_filter_hides_non_matching_rows_and_restores_them(self):
        from firebird_studio.activity_views import filter_table_rows

        table = QTableWidget(3, 2)
        for row, (a, b) in enumerate((("ANA", "select"), ("BRUNO", "update"), ("CARLA", "select"))):
            table.setItem(row, 0, QTableWidgetItem(a))
            table.setItem(row, 1, QTableWidgetItem(b))
        filter_table_rows(table, "  UPDATE ")
        self.assertEqual([table.isRowHidden(r) for r in range(3)], [True, False, True])
        filter_table_rows(table, "")
        self.assertEqual([table.isRowHidden(r) for r in range(3)], [False, False, False])


if __name__ == "__main__":
    unittest.main()
