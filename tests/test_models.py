from pathlib import Path
import tempfile
import unittest

from firebird_studio.models import ConnectionProfile, ProfileStore
from firebird_studio.sql import execute_sql
from firebird_studio.script_runner import build_isql_args, run_script
from firebird_studio.backup import build_gbak_args, run_gbak


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
