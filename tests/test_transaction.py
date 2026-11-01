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
        self.assertEqual(kwargs["database"], "db.example/3051:/srv/data.fdb")
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

    def test_transaction_uses_shared_driver_arguments(self):
        connection = _Connection()
        received = {}
        fake_driver = types.ModuleType("firebird.driver")

        def connect(**kwargs):
            received.update(kwargs)
            return connection

        fake_driver.connect = connect
        profile = ConnectionProfile("Local", database="sample.fdb", version="5", role="RDB$ADMIN")
        with patch.dict(sys.modules, {"firebird.driver": fake_driver}):
            session = TransactionSession(profile, "secret")
            session.close()
        self.assertEqual(received["database"], "localhost:sample.fdb")
        self.assertEqual(received["password"], "secret")
        self.assertEqual(received["role"], "RDB$ADMIN")

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

    def test_commit_and_rollback_are_safe_after_close(self):
        connection = _Connection()
        fake_driver = types.ModuleType("firebird.driver")
        fake_driver.connect = lambda **kwargs: connection
        profile = ConnectionProfile("Local", database="sample.fdb", version="5")
        with patch.dict(sys.modules, {"firebird.driver": fake_driver}):
            session = TransactionSession(profile)
            session.close()
            session.commit()
            session.rollback()
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
                Cursor.last_query = query

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
        self.assertLess(statements[0]["elapsed_seconds"], 10)
        self.assertIn("MON$STATE = 1", Cursor.last_query)
        self.assertIn("NOT LIKE '%MON$STATEMENTS%'", Cursor.last_query)

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


class _ScriptCursor(_Cursor):
    description = None

    def execute(self, sql):
        self.connection.statements.append(sql)
        if "BOOM" in sql:
            raise RuntimeError("erro de teste")


class _ScriptConnection(_Connection):
    def cursor(self):
        return _ScriptCursor(self)


class ScriptExecutionTests(unittest.TestCase):
    def session(self):
        connection = _ScriptConnection()
        fake_driver = types.ModuleType("firebird.driver")
        fake_driver.connect = lambda **kwargs: connection
        patcher = patch.dict(sys.modules, {"firebird.driver": fake_driver})
        patcher.start()
        self.addCleanup(patcher.stop)
        session = TransactionSession(ConnectionProfile("Local", database="s.fdb", version="5"))
        return session, connection

    def test_script_runs_each_statement_and_honours_commit_and_quit(self):
        session, connection = self.session()
        result = session.execute(
            "SET TERM ^;\nEXECUTE BLOCK AS BEGIN INSERT INTO T VALUES (1); END^\nSET TERM ;^\nCOMMIT;\nQUIT;\nDROP TABLE T;"
        )
        self.assertTrue(result.ok, result.message)
        self.assertEqual(connection.statements, ["EXECUTE BLOCK AS BEGIN INSERT INTO T VALUES (1); END"])
        self.assertEqual(connection.commits, 1)
        self.assertFalse(session.dirty)
        self.assertIn("1 instrução", result.message)

    def test_changes_after_the_last_commit_stay_pending(self):
        session, connection = self.session()
        session.execute("INSERT INTO T VALUES (1); COMMIT; UPDATE T SET A = 2;")
        self.assertEqual(connection.statements, ["INSERT INTO T VALUES (1)", "UPDATE T SET A = 2"])
        self.assertTrue(session.dirty)

    def test_rollback_in_script_undoes_pending_changes(self):
        session, connection = self.session()
        session.execute("INSERT INTO T VALUES (1); ROLLBACK;")
        self.assertEqual(connection.rollbacks, 1)
        self.assertFalse(session.dirty)

    def test_failure_stops_the_script_and_names_the_statement(self):
        session, connection = self.session()
        result = session.execute("INSERT INTO T VALUES (1); UPDATE BOOM SET A = 1; DELETE FROM T;")
        self.assertFalse(result.ok)
        self.assertIn("Instrução 2", result.message)
        self.assertIn("erro de teste", result.message)
        self.assertEqual(len(connection.statements), 2)

    def test_single_statement_with_trailing_semicolon_is_sent_untouched(self):
        session, connection = self.session()
        session.execute("INSERT INTO T VALUES (1);")
        self.assertEqual(connection.statements, ["INSERT INTO T VALUES (1);"])


if __name__ == "__main__":
    unittest.main()
