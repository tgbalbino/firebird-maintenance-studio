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


@unittest.skipIf(QSettings is None, "PySide6 não instalado")
class SqlExecutionFlowTests(WindowTestCase):
    """Characterizes execute -> pending transaction -> commit/rollback with no database."""

    def open_window(self, select_result=None):
        from unittest import mock

        from firebird_studio.models import ConnectionProfile, ProfileStore
        from firebird_studio.sql import QueryResult
        from firebird_studio.ui import MainWindow

        path = Path(self._tmp.name) / "flow_profiles.json"
        ProfileStore(path).save([ConnectionProfile(name="Vendas", database="C:/db/v.fdb")])
        window = MainWindow(ProfileStore(path))
        window._window.show()
        self.addCleanup(self._dispose, window)
        window._new_sql_tab()
        window.editor.setProperty("query_profile", "Vendas")
        self.messages = []
        window._show_message = lambda title, text, warning=False: self.messages.append(title)
        result = select_result or QueryResult(True, ["ID", "NOME"], [(1, "Ana"), (2, "Bruno")], "2 linha(s) retornada(s).", 1.5)
        from PySide6.QtWidgets import QMessageBox

        for patcher in (
            mock.patch("firebird_studio.sql.execute_sql", lambda *a, **k: result),
            mock.patch("firebird_studio.transaction.TransactionSession", _FakeSession),
            mock.patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        return window

    def test_select_fills_result_grid_and_summary(self):
        window = self.open_window()
        window._execute_sql_text("select id, nome from cliente")
        self.assertEqual(window.result_table.rowCount(), 2)
        self.assertEqual(window.result_table.columnCount(), 2)
        self.assertIn("2 linha(s)", window.result_summary.text())
        self.assertIsNone(window._transaction_session)

    def test_empty_sql_is_rejected_without_executing(self):
        window = self.open_window()
        window._execute_sql_text("   ")
        self.assertIn("Digite uma instrução SQL", window.status.text())
        self.assertEqual(window.result_table.rowCount(), 0)

    def test_failed_select_reports_error_and_keeps_window_alive(self):
        from firebird_studio.sql import QueryResult

        window = self.open_window(QueryResult(False, [], [], "Table unknown: X", 0.0))
        window._execute_sql_text("select * from x")
        self.assertIn("Falha ao executar SQL", self.messages)
        self.assertIn("falha", window.result_summary.text())

    def test_update_opens_pending_transaction_and_blocks_next_command(self):
        window = self.open_window()
        window._execute_sql_text("update cliente set nome = 'X' where id = 1")
        self.assertTrue(window._transaction_session.dirty)
        self.assertIn("Transação pendente", window.status.text())
        window._execute_sql_text("select 1 from rdb$database")
        self.assertIn("Transação não finalizada", self.messages)

    def test_rollback_discards_and_allows_new_commands(self):
        window = self.open_window()
        window._execute_sql_text("delete from cliente where id = 1")
        session = _FakeSession.last
        window._rollback_transaction()
        self.assertTrue(session.rolled_back)
        self.assertIn("Rollback concluído", window.status.text())
        self.assertIsNone(window._transaction_session)

    def test_commit_confirms_and_closes_transaction(self):
        window = self.open_window()
        window._execute_sql_text("insert into cliente (id) values (9)")
        session = _FakeSession.last
        window._commit_transaction()
        self.assertTrue(session.committed)
        self.assertIn("Commit confirmado", window.status.text())
        self.assertIsNone(window._transaction_session)

    def test_read_only_mode_blocks_mutating_statements(self):
        window = self.open_window()
        _controls = window.editor.property("execution_controls")
        _controls[1].setChecked(True)
        window._execute_sql_text("drop table cliente")
        self.assertIn("somente leitura", window.status.text())
        self.assertIsNone(window._transaction_session)



@unittest.skipIf(QSettings is None, "PySide6 não instalado")
class SqlAutocompleteTests(WindowTestCase):
    def open_editor(self):
        from PySide6.QtWidgets import QTextEdit

        from firebird_studio.models import ConnectionProfile, ProfileStore
        from firebird_studio.schema import SchemaObject
        from firebird_studio.ui import MainWindow

        path = Path(self._tmp.name) / "ac_profiles.json"
        ProfileStore(path).save([ConnectionProfile(name="A", database="a"), ConnectionProfile(name="B", database="b")])
        window = MainWindow(ProfileStore(path))
        window._window.show()
        self.addCleanup(self._dispose, window)
        window._new_sql_tab()
        window.profile_objects = {
            "A": [SchemaObject("TABLE", "CLIENTES", "")],
            "B": [SchemaObject("TABLE", "SO_NO_B", "")],
        }
        editor = window.sql_tabs.activeSubWindow().widget().findChild(QTextEdit, "sqlEditor")
        window._set_current_query_profile("A", editor)
        self.app.processEvents()
        return window, editor

    def test_suggestions_come_only_from_the_query_database(self):
        window, editor = self.open_editor()
        words = editor.property("completion_model").stringList()
        self.assertIn("CLIENTES", words)
        self.assertNotIn("SO_NO_B", words)
        window._set_current_query_profile("B", editor)
        words = editor.property("completion_model").stringList()
        self.assertIn("SO_NO_B", words)
        self.assertNotIn("CLIENTES", words)

    def test_typing_opens_popup_and_accepting_replaces_dollar_names_whole(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        window, editor = self.open_editor()
        popup = editor.property("completion").popup()
        QTest.keyClicks(editor, "select * from rdb$rel")
        self.app.processEvents()
        self.assertTrue(popup.isVisible())
        window._insert_completion(editor, "RDB$RELATIONS")
        self.assertEqual(editor.toPlainText(), "select * from RDB$RELATIONS")
        self.assertFalse(popup.isVisible())

    def test_dot_after_alias_lists_that_tables_columns(self):
        from PySide6.QtGui import QTextCursor
        from PySide6.QtTest import QTest

        from firebird_studio.schema import SchemaObject

        window, editor = self.open_editor()
        window.profile_objects["A"] = [SchemaObject("TABLE", "CLIENTES", "", columns=(("NOME", "V", "", "", ""), ("LIMITE", "N", "", "", "")))]
        window._refresh_sql_completer(editor)
        editor.setPlainText("select  from clientes c")
        cursor = editor.textCursor()
        cursor.setPosition(len("select "))
        editor.setTextCursor(cursor)
        QTest.keyClicks(editor, "c.")
        self.app.processEvents()
        completer = editor.property("completion")
        self.assertTrue(completer.popup().isVisible())
        self.assertEqual(sorted(editor.property("completion_model").stringList()), ["LIMITE", "NOME"])
        QTest.keyClicks(editor, "no")
        self.assertEqual(completer.completionCount(), 1)
        window._insert_completion(editor, "NOME")
        self.assertEqual(editor.toPlainText(), "select c.NOME from clientes c")
        # Back to a plain word: the full vocabulary returns.
        QTest.keyClicks(editor, " sel")
        self.assertIn("SELECT", editor.property("completion_model").stringList())

    def test_popup_does_not_open_when_text_is_loaded_programmatically(self):
        window, editor = self.open_editor()
        popup = editor.property("completion").popup()
        editor.setPlainText("select nome from clientes")
        self.app.processEvents()
        self.assertFalse(popup.isVisible())



@unittest.skipIf(QSettings is None, "PySide6 não instalado")
class TreeContextMenuTests(WindowTestCase):
    """Characterizes which commands the navigator offers per item."""

    def open_window(self):
        from firebird_studio.models import ConnectionProfile, ProfileStore
        from firebird_studio.schema import SchemaObject
        from firebird_studio.ui import MainWindow

        path = Path(self._tmp.name) / "tree_profiles.json"
        ProfileStore(path).save([ConnectionProfile(name="Vendas", database="C:/db/v.fdb")])
        window = MainWindow(ProfileStore(path))
        window._window.show()
        self.addCleanup(self._dispose, window)
        window.profile_objects = {"Vendas": [SchemaObject("TABLE", "CLIENTES", "")]}
        window.refresh_profiles()
        self.app.processEvents()
        self.menus = []
        window._popup_menu_fitting = lambda menu, origin, reference=None: self.menus.append(menu)
        return window

    def labels(self, menu):
        return [a.text() for a in menu.actions() if not a.isSeparator()]

    def open_menu_for(self, window, item):
        window.profile_list.scrollToItem(item)
        window._tree_context_menu(window.profile_list.visualItemRect(item).center())
        return self.menus[-1]

    def test_database_item_offers_profile_commands(self):
        window = self.open_window()
        root = window.profile_list.topLevelItem(0)
        labels = self.labels(self.open_menu_for(window, root))
        for expected in ("Alterar cadastro...", "Copiar nome do banco", "Copiar caminho ou alias",
                         "Monitorar consultas", "Manutenção do banco", "Recolher todos os bancos"):
            self.assertIn(expected, labels)
        self.assertNotIn("Desconectar banco", labels)

    def test_disconnect_is_offered_only_for_connected_databases(self):
        window = self.open_window()
        window.connected_profiles.add("Vendas")
        root = window.profile_list.topLevelItem(0)
        self.assertIn("Desconectar banco", self.labels(self.open_menu_for(window, root)))

    def test_expand_and_collapse_follow_item_state(self):
        window = self.open_window()
        root = window.profile_list.topLevelItem(0)
        root.setExpanded(True)
        labels = self.labels(self.open_menu_for(window, root))
        self.assertIn("Recolher objetos", labels)
        self.assertNotIn("Expandir objetos", labels)
        root.setExpanded(False)
        self.assertIn("Expandir objetos", self.labels(self.open_menu_for(window, root)))

    def test_table_object_offers_new_table_script(self):
        # Current behavior: the command is offered on objects inside the
        # "Tabelas" folder, not on the folder item itself.
        window = self.open_window()
        root = window.profile_list.topLevelItem(0)
        root.setExpanded(True)
        category = next(root.child(i) for i in range(root.childCount()) if root.child(i).text(0).startswith("Tabelas"))
        category.setExpanded(True)
        self.assertGreater(category.childCount(), 0)
        self.assertIn("Nova tabela...", self.labels(self.open_menu_for(window, category.child(0))))
        self.assertNotIn("Nova tabela...", self.labels(self.open_menu_for(window, category)))

    def test_empty_area_opens_no_menu(self):
        from PySide6.QtCore import QPoint

        window = self.open_window()
        window._tree_context_menu(QPoint(5, window.profile_list.viewport().height() - 3))
        self.assertEqual(self.menus, [])



if __name__ == "__main__":
    unittest.main()
