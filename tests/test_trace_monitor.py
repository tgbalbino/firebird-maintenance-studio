import unittest

from firebird_studio.models import ConnectionProfile
from firebird_studio.trace_monitor import build_trace_config


class TraceMonitorTests(unittest.TestCase):
    def test_firebird_25_trace_configuration(self):
        profile = ConnectionProfile("Local", database="C:/data/test.fdb", version="2.5")
        config = build_trace_config(profile)
        self.assertIn("<database C:/data/test.fdb>", config)
        self.assertIn("log_statement_finish true", config)

    def test_modern_trace_configuration(self):
        profile = ConnectionProfile("Local", database="C:/data/test.fdb", version="5")
        config = build_trace_config(profile)
        self.assertIn("database = C:/data/test.fdb", config)
        self.assertIn("print_perf true", config)


if __name__ == "__main__":
    unittest.main()
