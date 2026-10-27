import os
import unittest
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 não instalado")
class GridEditControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Same application class the other UI tests share (it routes F5).
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def build(self, confirm=True, execute_ok=True):
        from firebird_studio.grid_controller import GridContext, GridEditController
        from firebird_studio.result_views import fill_table

        columns = ["CODIGO", "NOME", "LIMITE"]
        rows = [(1, "Ana", Decimal("10.5")), (2, "Bruno", None)]
        table = QTableWidget()
        fill_table(table, columns, rows, sorting=False)
        self.calls, self.status = [], []
        edit, save = QPushButton("Editar"), QPushButton("Salvar")
        edit.setCheckable(True)

        def execute(context, statements):
            self.calls.append(list(statements))
            return execute_ok, "ok" if execute_ok else "falhou"

        controller = GridEditController(edit, save, execute=execute, confirm=lambda *_: confirm, set_status=self.status.append)
        controller.attach(table, GridContext("Vendas", "CLIENTE", columns, ["CODIGO"], "select * from cliente"), rows)
        return controller, table, edit, save

    def test_attach_shows_controls_and_disables_save_until_edited(self):
        controller, table, edit, save = self.build()
        self.assertFalse(edit.isHidden())
        self.assertFalse(save.isHidden())
        self.assertFalse(save.isEnabled())
        self.assertEqual(controller.changes(), [])

    def test_edit_mode_toggles_triggers_and_sorting(self):
        controller, table, edit, save = self.build()
        self.assertEqual(table.editTriggers(), QTableWidget.NoEditTriggers)
        edit.setChecked(True)
        self.assertNotEqual(table.editTriggers(), QTableWidget.NoEditTriggers)
        self.assertFalse(table.isSortingEnabled())
        edit.setChecked(False)
        self.assertEqual(table.editTriggers(), QTableWidget.NoEditTriggers)

    def test_edit_builds_update_and_counts_on_button(self):
        controller, table, edit, save = self.build()
        table.item(0, 1).setText("Ana Maria")
        table.item(1, 2).setText("7")
        self.assertEqual(save.text(), "Salvar alterações (2)")
        self.assertTrue(save.isEnabled())
        self.assertEqual(
            [sql for _row, sql in controller.changes()],
            [
                'UPDATE "CLIENTE" SET "NOME" = \'Ana Maria\' WHERE "CODIGO" = 1',
                "UPDATE \"CLIENTE\" SET \"LIMITE\" = '7' WHERE \"CODIGO\" = 2",
            ],
        )

    def test_reverting_a_cell_removes_the_change(self):
        controller, table, edit, save = self.build()
        table.item(0, 1).setText("x")
        table.item(0, 1).setText("Ana")
        self.assertEqual(controller.changes(), [])
        self.assertFalse(save.isEnabled())

    def test_save_sends_statements_then_becomes_baseline(self):
        controller, table, edit, save = self.build()
        table.item(0, 0).setText("5")  # editing the key itself
        save.click()
        self.assertEqual(self.calls, [['UPDATE "CLIENTE" SET "CODIGO" = 5 WHERE "CODIGO" = 1']])
        self.assertTrue(controller.pending_commit)
        self.assertEqual(controller.changes(), [])
        # A further edit is keyed by the new value and typed like the original (int).
        table.item(0, 1).setText("Z")
        self.assertEqual(controller.changes()[0][1], 'UPDATE "CLIENTE" SET "NOME" = \'Z\' WHERE "CODIGO" = 5')

    def test_declined_confirmation_keeps_edits(self):
        controller, table, edit, save = self.build(confirm=False)
        table.item(0, 1).setText("x")
        save.click()
        self.assertEqual(self.calls, [])
        self.assertEqual(len(controller.changes()), 1)
        self.assertFalse(controller.pending_commit)

    def test_failed_save_keeps_edits_and_reports(self):
        controller, table, edit, save = self.build(execute_ok=False)
        table.item(0, 1).setText("x")
        save.click()
        self.assertEqual(len(controller.changes()), 1)
        self.assertEqual(self.status[-1], "falhou")
        self.assertFalse(controller.pending_commit)

    def test_discard_pending_reports_once_and_reset_hides(self):
        controller, table, edit, save = self.build()
        table.item(0, 1).setText("x")
        save.click()
        self.assertTrue(controller.discard_pending())
        self.assertFalse(controller.discard_pending())
        controller.reset()
        self.assertTrue(edit.isHidden() and save.isHidden())

    def test_reset_discards_unsaved_edits_and_says_so(self):
        controller, table, edit, save = self.build()
        table.item(0, 1).setText("x")
        controller.reset()
        self.assertEqual(table.item(0, 1).text(), "Ana")
        self.assertIn("1 linha(s) editada(s)", self.status[-1])

    def test_controls_follow_the_visible_table(self):
        controller, table, edit, save = self.build()
        controller.sync_visibility(QTableWidget())
        self.assertTrue(edit.isHidden() and save.isHidden())
        controller.sync_visibility(table)
        self.assertFalse(edit.isHidden() or save.isHidden())


if __name__ == "__main__":
    unittest.main()
