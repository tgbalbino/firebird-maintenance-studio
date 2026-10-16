import sys
import types
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from firebird_studio.models import ConnectionProfile
from firebird_studio.transaction import TransactionSession
from firebird_studio.plan import explain_query


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


if __name__ == "__main__":
    unittest.main()
