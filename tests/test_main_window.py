import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QPushButton
except ImportError:  # pragma: no cover - UI extras are optional
    QSettings = None


@unittest.skipIf(QSettings is None, "PySide6 não instalado")
class WindowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, cls._tmp.name)
        # Windows under test must never reach the network for update checks.
        QSettings("TGBalbino", "FirebirdMaintenanceStudio").setValue("auto_update_check", False)
        from firebird_studio.ui import create_application

        cls.app = create_application()

    @classmethod
    def tearDownClass(cls):
        # Other test modules share the QApplication; drop the F5 handler a
        # MainWindow installed so it cannot swallow their key events.
        cls.app._sql_execution_handler = None
        cls._tmp.cleanup()

    def make_window(self):
        from firebird_studio.models import ProfileStore
        from firebird_studio.ui import MainWindow

        window = MainWindow(ProfileStore(Path(self._tmp.name) / "profiles.json"))
        window._window.show()
        self.app.processEvents()
        self.addCleanup(self._dispose, window)
        return window

    def _dispose(self, window):
        window._window.close()
        window._window.deleteLater()
        self.app.processEvents()



@unittest.skipIf(QSettings is None, "PySide6 não instalado")
class MainWindowLayoutTests(WindowTestCase):

    def test_empty_workspace_shows_only_welcome_page(self):
        window = self.make_window()
        self.assertTrue(window.welcome_page.isVisible())
        self.assertFalse(window.workspace_tools.isVisible())
        self.assertFalse(window.sql_window_bar.isVisible())

    def test_empty_navigator_explains_next_step(self):
        window = self.make_window()
        self.assertEqual(window.profile_list.topLevelItemCount(), 0)
        self.assertTrue(window.tree_empty_hint.isVisible())
        self.assertIn("Nenhum banco cadastrado", window.tree_empty_hint.text())

    def test_sql_editor_has_single_frame(self):
        window = self.make_window()
        window._new_sql_tab()
        from PySide6.QtWidgets import QTextEdit
        editor = window.sql_tabs.activeSubWindow().widget().findChild(QTextEdit, "sqlEditor")
        self.assertIsNotNone(editor)
        self.assertEqual(editor.frameShape(), editor.Shape.NoFrame)

    def _leaf_actions(self, menu):
        for action in menu.actions():
            if action.menu() is not None:
                yield from self._leaf_actions(action.menu())
            elif not action.isSeparator():
                yield action

    def test_every_menu_action_has_a_handler(self):
        """Refactor guard: an extraction must not leave a menu entry unconnected."""
        from PySide6.QtCore import SIGNAL

        window = self.make_window()
        orphans = []
        for top in window._window.menuBar().actions():
            for action in self._leaf_actions(top.menu()):
                if action.receivers(SIGNAL("triggered(bool)")) == 0 and action.receivers(SIGNAL("triggered()")) == 0:
                    orphans.append(f"{top.text()} > {action.text()}")
        self.assertEqual(orphans, [])

    def test_sql_tabs_open_and_close_cleanly(self):
        window = self.make_window()
        for _ in range(3):
            window._new_sql_tab()
        self.assertEqual(window.sql_tabs.count(), 3)
        self.assertFalse(window.welcome_page.isVisible())
        while window.sql_tabs.count():
            window.close_sql_tab(0)
            self.app.processEvents()
        self.assertTrue(window.welcome_page.isVisible())

    def test_theme_switch_keeps_window_usable(self):
        window = self.make_window()
        window._new_sql_tab()
        for theme in ("dark", "blue", "gray", "light"):
            window._set_theme(theme)
            self.app.processEvents()
            self.assertEqual(window._settings.value("theme"), theme)
            self.assertTrue(window.sql_tabs.isVisible())

    def test_sql_document_replaces_welcome_page(self):
        window = self.make_window()
        window._new_sql_tab()
        self.app.processEvents()
        self.assertFalse(window.welcome_page.isVisible())
        self.assertTrue(window.workspace_tools.isVisible())
        self.assertFalse(window.pagination_bar.isVisible())
        window.close_sql_tab(0)
        self.app.processEvents()
        self.assertTrue(window.welcome_page.isVisible())

    def test_sql_toolbar_keeps_theme_styling(self):
        """The MDI viewport rule must not cascade into the SQL command bar."""
        window = self.make_window()
        window._new_sql_tab()
        self.app.processEvents()
        self.assertIn("QWidget#mdiViewport", window.sql_tabs.viewport().styleSheet())

    def test_welcome_lists_saved_connections_and_breadcrumb_names_database(self):
        from firebird_studio.models import ConnectionProfile, ProfileStore
        from firebird_studio.ui import MainWindow

        path = Path(self._tmp.name) / "with_profiles.json"
        ProfileStore(path).save([ConnectionProfile(name="Vendas", database="C:/db/v.fdb", favorite=True)])
        window = MainWindow(ProfileStore(path))
        window._window.show()
        self.addCleanup(self._dispose, window)
        self.app.processEvents()
        self.assertEqual(window.welcome_recent_layout.count(), 1)
        window._new_sql_tab()
        self.assertEqual(window.object_breadcrumb.text(), "localhost:3050 > consulta SQL")
        self.assertTrue(window._window.windowTitle().startswith("Vendas (desconectado)"))
        self.assertEqual(window.sql_window_bar.tabText(0), "SQL 1 · Vendas")
        self.assertFalse(window.sql_window_bar.tabIcon(0).isNull())
        window.connected_profiles.add("Vendas")
        window._update_query_connection_status()
        self.assertTrue(window._window.windowTitle().startswith("Vendas (conectado)"))
        window.close_sql_tab(0)
        self.app.processEvents()
        self.assertTrue(window._window.windowTitle().startswith("Firebird Maintenance Studio"))

    def test_menu_bar_holds_data_database_and_analysis_commands(self):
        window = self.make_window()
        menus = {a.text(): a.menu() for a in window._window.menuBar().actions()}
        for title in ("Banco", "Dados", "Segurança", "Análise"):
            self.assertIn(title, menus)
        texts = [a.text() for a in menus["Banco"].actions()]
        self.assertEqual(texts.count("Backup"), 1)
        self.assertIn("Exportar banco para SQL", texts)
        self.assertIn("Exportar CSV", [a.text() for a in menus["Dados"].actions()])
        self.assertIn("Comparar estruturas", [a.text() for a in menus["Análise"].actions()])

    SIZES = ((1280, 720), (1920, 1080))

    def test_sql_toolbar_is_styled_in_every_theme(self):
        """Guards the unscoped-viewport-stylesheet regression (flattened buttons)."""
        from PySide6.QtWidgets import QFrame

        window = self.make_window()
        window._new_sql_tab()
        for theme in ("light", "dark", "gray", "blue"):
            for width, height in self.SIZES:
                with self.subTest(theme=theme, size=(width, height)):
                    window._set_theme(theme)
                    window._window.resize(width, height)
                    self.app.processEvents()
                    execute = window.editor.property("execution_controls")  # keeps editor alive
                    bar = window._window.findChildren(QFrame, "sqlCommandBar")[-1]
                    button = bar.property("execute_button")
                    # The primary action must keep its filled (non-flat) background:
                    # a flat button shares the toolbar's own pixel color.
                    image = button.grab().toImage()
                    corner = image.pixelColor(6, image.height() // 2)
                    toolbar_image = bar.grab().toImage()
                    toolbar_color = toolbar_image.pixelColor(2, toolbar_image.height() // 2)
                    self.assertNotEqual(corner.name(), toolbar_color.name())
                    self.assertGreater(corner.blue(), corner.red() + 40)
                    self.assertIsNotNone(execute)

    def test_main_window_fits_small_screens(self):
        window = self.make_window()
        window._new_sql_tab()
        self.assertLessEqual(window._window.minimumSizeHint().height(), 600)
        self.assertLessEqual(window._window.minimumSizeHint().width(), 640)


class _FakeSession:
    """Stands in for TransactionSession: records SQL, no database."""

    last = None

    def __init__(self, profile, password=None):
        self.statements, self.dirty, self.committed, self.rolled_back = [], False, False, False
        self.connection = object()
        _FakeSession.last = self

    active = property(lambda self: self.connection is not None)

    def execute(self, sql, max_rows=0):
        from firebird_studio.sql import QueryResult

        self.statements.append(sql)
        self.dirty = True
        return QueryResult(True, [], [], "1 linha(s) afetada(s).")

    def commit(self):
        self.committed, self.dirty = True, False

    def rollback(self):
        self.rolled_back, self.dirty = True, False

    def close(self, rollback=True):
        self.connection = None


@unittest.skipIf(QSettings is None, "PySide6 não instalado")
class GridEditingFlowTests(WindowTestCase):
    """Simple SELECT -> edit cell -> save into a transaction -> commit / rollback."""

    def open_window(self):
        from unittest import mock

        from firebird_studio.models import ConnectionProfile, ProfileStore
        from firebird_studio.sql import QueryResult
        from firebird_studio.ui import MainWindow

        path = Path(self._tmp.name) / "grid_profiles.json"
        ProfileStore(path).save([ConnectionProfile(name="Vendas", database="C:/db/v.fdb")])
        window = MainWindow(ProfileStore(path))
        window._window.show()
        self.addCleanup(self._dispose, window)
        window._new_sql_tab()
        window._table_primary_key = lambda profile, table: ("ID",)
        self.rows = [(1, "Ana"), (2, "Bruno")]
        patches = [
            mock.patch("firebird_studio.sql.execute_sql", lambda *a, **k: QueryResult(True, ["ID", "NOME"], list(self.rows), "2 linha(s) retornada(s).")),
            mock.patch("firebird_studio.transaction.TransactionSession", _FakeSession),
            mock.patch("PySide6.QtWidgets.QMessageBox.question", return_value=__import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.Yes),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        window.grid_edit._confirm = lambda count, statements: True  # bound at construction
        window._execute_sql_text("select * from cliente")
        return window

    def test_simple_select_becomes_editable_and_join_does_not(self):
        window = self.open_window()
        self.assertFalse(window.edit_grid_button.isHidden())
        window._execute_sql_text("select * from cliente c join pedido p on p.id = c.id")
        self.assertTrue(window.edit_grid_button.isHidden())
        self.assertTrue(window.save_grid_button.isHidden())

    def test_save_goes_to_pending_transaction_and_commit_finishes_it(self):
        window = self.open_window()
        window.edit_grid_button.setChecked(True)
        window.result_table.item(0, 1).setText("Ana Maria")
        window.save_grid_button.click()
        session = _FakeSession.last
        self.assertEqual(session.statements, ["UPDATE \"CLIENTE\" SET \"NOME\" = 'Ana Maria' WHERE \"ID\" = 1"])
        self.assertTrue(session.dirty and not session.committed)
        self.assertTrue(window.grid_edit.pending_commit)
        window._commit_transaction()
        self.assertTrue(session.committed)
        self.assertFalse(window.grid_edit.pending_commit)

    def test_rollback_reloads_the_grid_from_the_database(self):
        window = self.open_window()
        window.edit_grid_button.setChecked(True)
        window.result_table.item(0, 1).setText("Ana Maria")
        window.save_grid_button.click()
        window._rollback_transaction()
        self.assertTrue(_FakeSession.last.rolled_back)
        self.assertEqual(window.result_table.item(0, 1).text(), "Ana")
        self.assertFalse(window.grid_edit.pending_commit)

    def test_read_only_mode_blocks_saving(self):
        window = self.open_window()
        window.read_only_mode.setChecked(True)
        window.edit_grid_button.setChecked(True)
        window.result_table.item(0, 1).setText("x")
        before = _FakeSession.last
        window.save_grid_button.click()
        self.assertIs(_FakeSession.last, before)
        self.assertEqual(len(window.grid_edit.changes()), 1)


    def test_update_preview_for_selected_table_row_uses_primary_key(self):
        from firebird_studio.schema import SchemaObject

        window = self.open_window()
        window.selected_object = SchemaObject("TABLE", "CLIENTE", "", primary_key=("ID",))
        window._table_original_rows = list(self.rows)
        window.result_table.item(0, 1).setText("Ana Maria")
        window.result_table.selectRow(0)
        window._generate_row_update_preview()
        sql = window.editor.toPlainText()
        self.assertIn('UPDATE "CLIENTE"', sql)
        self.assertIn("\"NOME\" = 'Ana Maria'", sql)
        self.assertIn("WHERE \"ID\" = 1", sql)
        self.assertIn("chave primária foi usada", sql)


if __name__ == "__main__":
    unittest.main()
