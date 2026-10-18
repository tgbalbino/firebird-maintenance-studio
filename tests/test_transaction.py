import sys
import types
import unittest
import tempfile
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from firebird_studio.models import ConnectionProfile
from firebird_studio.connection import _connection_kwargs
from firebird_studio.transaction import TransactionSession
from firebird_studio.plan import explain_query
from firebird_studio.health import list_statements, terminate_session


class _Cursor:
    description = [("VALUE",)]
    rowcount = -1

    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql):
        self.connection.statements.append(sql)

    def fetchall(self):
        return [(1,)]


class _Connection:
    def __init__(self):
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class TransactionTests(unittest.TestCase):
    def test_shared_connection_arguments_include_profile_settings(self):
        profile = ConnectionProfile(
            "Local",
            host="db.example",
            port=3051,
            database="/srv/data.fdb",
            user="APP",
            role="RDB$ADMIN",
            charset="WIN1252",
            version="5",
        )
        kwargs = _connection_kwargs(profile, "secret")
        self.assertEqual(kwargs["dsn"], "db.example/3051:/srv/data.fdb")
        self.assertEqual(kwargs["user"], "APP")
        self.assertEqual(kwargs["password"], "secret")
        self.assertEqual(kwargs["role"], "RDB$ADMIN")
        self.assertEqual(kwargs["charset"], "WIN1252")

    def test_transaction_result_is_bounded(self):
        class BoundedCursor(_Cursor):
            description = [("VALUE",)]

            def fetchmany(self, count):
                return [(1,), (2,), (3,)][:count]

        class BoundedConnection(_Connection):
            def cursor(self):
                return BoundedCursor(self)

        connection = BoundedConnection()
        fake_driver = types.ModuleType("firebird.driver")
        fake_driver.connect = lambda **kwargs: connection
        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with patch.dict(sys.modules, {"firebird.driver": fake_driver}):
            session = TransactionSession(profile)
            result = session.execute("SELECT VALUE FROM T", max_rows=2)
            session.close()
        self.assertEqual(result.rows, [(1,), (2,)])
        self.assertIn("limitado", result.message)

    def test_commands_wait_for_commit_and_close(self):
        connection = _Connection()
        fake_driver = types.ModuleType("firebird.driver")
        fake_driver.connect = lambda **kwargs: connection
        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with patch.dict(sys.modules, {"firebird.driver": fake_driver}):
            session = TransactionSession(profile, "secret")
            result = session.execute("UPDATE CUSTOMER SET NAME = 'A'")
            self.assertTrue(result.ok)
            self.assertEqual(connection.commits, 0)
            session.commit()
            session.close(rollback=False)
        self.assertEqual(connection.commits, 1)
        self.assertTrue(connection.closed)

    def test_rollback_discards_pending_work(self):
        connection = _Connection()
        fake_driver = types.ModuleType("firebird.driver")
        fake_driver.connect = lambda **kwargs: connection
        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with patch.dict(sys.modules, {"firebird.driver": fake_driver}):
            session = TransactionSession(profile)
            self.assertTrue(session.execute("DELETE FROM CUSTOMER").ok)
            session.rollback()
            session.close(rollback=False)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)

    def test_plan_supplies_connect_through_stdin(self):
        completed = types.SimpleNamespace(returncode=0, stdout="PLAN (T NATURAL)", stderr="")
        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with tempfile.TemporaryDirectory() as directory:
            isql = Path(directory) / "isql.exe"
            isql.write_text("stub")
            with patch("firebird_studio.plan.subprocess.run", return_value=completed) as run:
                result = explain_query(profile, "SELECT * FROM T", "secret", isql)
        self.assertTrue(result.ok)
        stdin = run.call_args.kwargs["input"]
        self.assertIn("CONNECT 'localhost:sample.fdb' USER 'SYSDBA' PASSWORD 'secret';", stdin)
        self.assertIn("SET PLANONLY ON", stdin)

    def test_active_statements_include_elapsed_time(self):
        class Cursor:
            description = None

            def execute(self, query):
                self.query = query

            def fetchall(self):
                return [(7, 3, "SYSDBA", "10.0.0.5", 1, datetime.now() - timedelta(seconds=4), "SELECT * FROM CUSTOMER")]

        class Connection:
            def cursor(self):
                return Cursor()

        @contextmanager
        def fake_database(*_args, **_kwargs):
            yield Connection()

        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with patch("firebird_studio.health.open_database", fake_database):
            statements = list_statements(profile)
        self.assertEqual(statements[0]["id"], 7)
        self.assertEqual(statements[0]["user"], "SYSDBA")
        self.assertGreaterEqual(statements[0]["elapsed_seconds"], 3)

    def test_terminate_session_uses_attachment_id_and_commits(self):
        class Cursor:
            def execute(self, query, params):
                self.query = query
                self.params = params

            def close(self):
                pass

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()
                self.committed = False

            def cursor(self):
                return self.cursor_instance

            def commit(self):
                self.committed = True

        connection = Connection()

        @contextmanager
        def fake_database(*_args, **_kwargs):
            yield connection

        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with patch("firebird_studio.health.open_database", fake_database):
            terminate_session(profile, None, 42)
        self.assertIn("MON$ATTACHMENTS", connection.cursor_instance.query)
        self.assertEqual(connection.cursor_instance.params, (42,))
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
