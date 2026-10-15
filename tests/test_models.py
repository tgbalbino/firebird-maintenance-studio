from pathlib import Path
import tempfile
import unittest

from firebird_studio.models import ConnectionProfile, ProfileStore
from firebird_studio.sql import execute_sql
from firebird_studio.script_runner import build_isql_args, run_script
from firebird_studio.backup import build_gbak_args, run_gbak
from firebird_studio.schema import SchemaObject, compare_schema, generate_migration
from firebird_studio.catalog import _field_type
from firebird_studio.plan import build_plan_script, parse_plan, suggest_improvements


class ProfileTests(unittest.TestCase):
    def test_profile_validation_and_round_trip(self):
        profile = ConnectionProfile("Local", database="sample.fdb", version="2.5")
        self.assertEqual(profile.validate(), [])
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore(Path(directory) / "profiles.json")
            store.save([profile])
            self.assertEqual(store.load(), [profile])

    def test_invalid_profile_is_reported(self):
        errors = ConnectionProfile("", database="", version="6", port=0).validate()
        self.assertEqual(len(errors), 4)

    def test_empty_sql_is_rejected_without_connection(self):
        result = execute_sql(ConnectionProfile("Local", database="sample.fdb"), " ")
        self.assertFalse(result.ok)
        self.assertIn("SQL", result.message)

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
