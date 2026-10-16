from pathlib import Path
import sys
import tempfile
import types
import unittest

from firebird_studio.models import ConnectionProfile, ProfileStore
from firebird_studio.sql import execute_sql
from firebird_studio.script_runner import build_isql_args, run_script
from firebird_studio.backup import build_gbak_args, run_gbak
from firebird_studio.schema import SchemaChange, SchemaObject, compare_schema, generate_migration
from firebird_studio.catalog import _field_type
from firebird_studio.plan import build_plan_script, parse_plan, suggest_improvements
from firebird_studio.health import build_findings, inspect_health, _optional_database_values
from unittest.mock import patch


class ProfileTests(unittest.TestCase):
    def test_profile_validation_and_round_trip(self):
        profile = ConnectionProfile("Local", database="sample.fdb", version="2.5", role="RDB$ADMIN", favorite=True)
        self.assertEqual(profile.validate(), [])
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore(Path(directory) / "profiles.json")
            store.save([profile])
            self.assertEqual(store.load(), [profile])
            self.assertTrue(store.load()[0].favorite)

    def test_invalid_profile_is_reported(self):
        errors = ConnectionProfile("", database="", version="6", port=0).validate()
        self.assertEqual(len(errors), 4)

    def test_empty_sql_is_rejected_without_connection(self):
        result = execute_sql(ConnectionProfile("Local", database="sample.fdb"), " ")
        self.assertFalse(result.ok)
        self.assertIn("SQL", result.message)

    def test_sql_result_is_bounded_and_reports_truncation(self):
        class Cursor:
            description = [("ID",)]
            rowcount = -1

            def execute(self, _sql):
                pass

            def fetchmany(self, count):
                return [(1,), (2,), (3,)][:count]

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def cursor(self):
                return Cursor()

            def rollback(self):
                pass

        fake_driver = types.ModuleType("firebird.driver")
        fake_driver.connect = lambda **_kwargs: Connection()
        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with patch.dict(sys.modules, {"firebird.driver": fake_driver}):
            result = execute_sql(profile, "SELECT ID FROM CUSTOMER", max_rows=2)
        self.assertTrue(result.ok)
        self.assertEqual(result.rows, [(1,), (2,)])
        self.assertIn("limitado", result.message)

    def test_sql_rejects_invalid_result_limit(self):
        result = execute_sql(ConnectionProfile("Local", database="sample.fdb"), "SELECT 1", max_rows=0)
        self.assertFalse(result.ok)
        self.assertIn("maior que zero", result.message)

    def test_isql_arguments_never_include_password(self):
        profile = ConnectionProfile("Local", database="sample.fdb", user="SYSDBA")
        args = build_isql_args(profile, Path("script.sql"), Path("isql.exe"))
        self.assertNotIn("password", " ".join(args).lower())

    def test_missing_script_is_reported(self):
        profile = ConnectionProfile("Local", database="sample.fdb")
        result = run_script(profile, Path("missing.sql"), "secret", Path("isql.exe"))
        self.assertFalse(result.ok)
        self.assertIn("não encontrado", result.error)

    def test_gbak_arguments_do_not_include_password(self):
        profile = ConnectionProfile("Local", database="sample.fdb")
        args = build_gbak_args(profile, "backup", Path("sample.fdb"), Path("sample.fbk"), Path("gbak.exe"))
        self.assertNotIn("secret", " ".join(args))

    def test_restore_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = root / "sample.fbk"; backup.write_text("x")
            target = root / "sample.fdb"; target.write_text("x")
            profile = ConnectionProfile("Local", database="sample.fdb")
            result = run_gbak(profile, "restore", backup, target, "secret", root / "gbak.exe")
            self.assertFalse(result.ok)
            self.assertIn("já existe", result.error)

    def test_backup_refuses_missing_destination_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "sample.fdb"
            database.write_text("db")
            profile = ConnectionProfile("Local", database=str(database))
            result = run_gbak(profile, "backup", database, root / "missing" / "sample.fbk", "secret", root / "gbak.exe")
            self.assertFalse(result.ok)
            self.assertIn("pasta de destino não existe", result.error)

    def test_backup_refuses_same_source_and_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "sample.fdb"
            database.write_text("db")
            profile = ConnectionProfile("Local", database=str(database))
            result = run_gbak(profile, "backup", database, database, "secret", database.parent / "gbak.exe")
            self.assertFalse(result.ok)
            self.assertIn("diferente do banco", result.error)

    def test_schema_diff_and_migration_preview(self):
        source = [
            SchemaObject("TABLE", "CUSTOMER", "CREATE TABLE CUSTOMER (ID INTEGER NOT NULL)"),
            SchemaObject("TABLE", "ORDERS", "CREATE TABLE ORDERS (ID INTEGER)"),
        ]
        target = [SchemaObject("TABLE", "CUSTOMER", "CREATE TABLE CUSTOMER (ID INTEGER)")]
        changes = compare_schema(source, target)
        self.assertEqual([change.action for change in changes], ["ADD", "ALTER"])
        migration = generate_migration(changes)
        self.assertIn("CREATE TABLE ORDERS", migration)
        self.assertIn("REVIEW", migration)

    def test_removed_objects_are_not_generated_as_drop(self):
        changes = compare_schema([], [SchemaObject("TABLE", "OLD_TABLE", "CREATE TABLE OLD_TABLE (ID INTEGER)")])
        migration = generate_migration(changes)
        self.assertIn("NOT GENERATED", migration)
        self.assertNotIn("DROP TABLE", migration)

    def test_schema_diff_includes_domains_and_indexes(self):
        source = [
            SchemaObject("DOMAIN", "DM_CODE", 'CREATE DOMAIN "DM_CODE" AS INTEGER'),
            SchemaObject("INDEX", "IX_CUSTOMER_CODE", 'CREATE INDEX "IX_CUSTOMER_CODE" ON "CUSTOMER" ("CODE")'),
        ]
        changes = compare_schema(source, [])
        migration = generate_migration(changes)
        self.assertEqual({change.object.kind for change in changes}, {"DOMAIN", "INDEX"})
        self.assertIn('CREATE DOMAIN "DM_CODE"', migration)
        self.assertIn('CREATE INDEX "IX_CUSTOMER_CODE"', migration)

    def test_migration_orders_dependencies_before_consumers(self):
        migration = generate_migration([
            SchemaChange("ADD", SchemaObject("TRIGGER", "TR_CUSTOMER", "CREATE TRIGGER TR_CUSTOMER")),
            SchemaChange("ADD", SchemaObject("TABLE", "CUSTOMER", "CREATE TABLE CUSTOMER (ID INTEGER)")),
            SchemaChange("ADD", SchemaObject("DOMAIN", "DM_ID", "CREATE DOMAIN DM_ID AS INTEGER")),
        ])
        self.assertLess(migration.index("CREATE DOMAIN DM_ID"), migration.index("CREATE TABLE CUSTOMER"))
        self.assertLess(migration.index("CREATE TABLE CUSTOMER"), migration.index("CREATE TRIGGER TR_CUSTOMER"))

    def test_catalog_type_mapping_is_conservative(self):
        self.assertEqual(_field_type(8, 4, 0, None), "INTEGER")
        self.assertEqual(_field_type(14, 20, 0, None), "CHAR(20)")
        self.assertEqual(_field_type(261, 0, 0, None), "BLOB")

    def test_plan_is_plan_only_and_tree_has_nodes(self):
        script = build_plan_script("select * from CUSTOMER where ID = 1", "5")
        self.assertIn("SET PLANONLY ON", script)
        self.assertIn("SET EXPLAIN ON", script)
        tree = parse_plan("PLAN (CUSTOMER INDEX (PK_CUSTOMER))")
        self.assertEqual(tree.children[0].label, "CUSTOMER INDEX (PK_CUSTOMER")
        self.assertTrue(suggest_improvements("PLAN (CUSTOMER NATURAL)", "select * from CUSTOMER"))

    def test_health_flags_old_transaction(self):
        findings = build_findings({"oldest_active": 1, "next_transaction": 200_000, "attachments": 2, "backup_state": 0})
        self.assertEqual(findings[0].severity, "warning")
        self.assertIn("transações longas", findings[0].recommendation)

    def test_health_flags_unsafe_database_modes(self):
        findings = build_findings({"oldest_active": 10, "next_transaction": 10, "attachments": 2, "backup_state": 0, "read_only": 1, "forced_writes": 0, "sweep_interval": 0, "page_size": 8192, "pages": 128})
        titles = {item.title for item in findings}
        self.assertIn("Banco somente leitura", titles)
        self.assertIn("Gravação forçada desativada", titles)
        self.assertIn("Sweep automático desativado", titles)

    def test_health_reads_optional_metrics_before_closing_connection(self):
        class HealthConnection:
            closed = False

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.closed = True

        connection = HealthConnection()
        optional = {"MON$PAGE_SIZE": 8192, "MON$PAGES": 10, "MON$ODS_MAJOR": 13, "MON$ODS_MINOR": 0,
                    "MON$READ_ONLY": 0, "MON$FORCED_WRITES": 1, "MON$SWEEP_INTERVAL": 20}

        def read_optional(current, column):
            self.assertIs(current, connection)
            self.assertFalse(current.closed)
            return optional[column]

        with patch("firebird_studio.health.open_database", return_value=connection), \
             patch("firebird_studio.health._fetch_one", side_effect=[(1, 2, 3, 4, 0), (2,)]), \
             patch("firebird_studio.health._optional_database_value", side_effect=read_optional):
            report = inspect_health(ConnectionProfile("Local", database="sample.fdb"))

        self.assertEqual(report.metrics["page_size"], 8192)
        self.assertEqual(report.metrics["pages"], 10)
        self.assertTrue(connection.closed)

    def test_health_optional_metrics_use_one_projection(self):
        connection = object()
        values = (8192, 10, 13, 0, 0, 1, 20)
        with patch("firebird_studio.health._fetch_one", return_value=values) as fetch, \
             patch("firebird_studio.health._optional_database_value") as fallback:
            result = _optional_database_values(connection)
        self.assertEqual(result["page_size"], 8192)
        self.assertEqual(result["sweep_interval"], 20)
        fetch.assert_called_once()
        fallback.assert_not_called()
