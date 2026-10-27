import unittest

from firebird_studio.models import ConnectionProfile
from firebird_studio.trace_monitor import build_trace_config, parse_trace_line


class TraceMonitorTests(unittest.TestCase):
    def test_firebird_25_trace_configuration(self):
        profile = ConnectionProfile("Local", database="C:/data/test.fdb", version="2.5")
        config = build_trace_config(profile)
        self.assertIn("<database>\n", config)
        self.assertNotIn("<database C:/data/test.fdb>", config)
        self.assertIn("log_connections true", config)
        self.assertIn("log_statement_finish true", config)

    def test_modern_trace_configuration(self):
        profile = ConnectionProfile("Local", database="C:/data/test.fdb", version="5")
        config = build_trace_config(profile)
        self.assertIn("database = C:/data/test.fdb", config)
        self.assertIn("print_perf true", config)

    def test_parse_trace_line_extracts_timestamp_and_event(self):
        line = "2026-10-19T10:11:12.5 (1234:abc) EXECUTE_STATEMENT_FINISH"
        self.assertEqual(parse_trace_line("2026-10-19 10:11:12.5 (1234:abc) EXECUTE_STATEMENT_FINISH"), ("2026-10-19 10:11:12.5", "EXECUTE_STATEMENT_FINISH"))
        self.assertEqual(parse_trace_line(line)[1], "EXECUTE_STATEMENT_FINISH")

    def test_parse_trace_line_unknown_event(self):
        self.assertEqual(parse_trace_line("sem data"), ("", "Trace"))


if __name__ == "__main__":
    unittest.main()
