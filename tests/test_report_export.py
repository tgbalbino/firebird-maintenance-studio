import unittest

from firebird_studio.report_export import compare_html, health_html


class ReportExportTests(unittest.TestCase):
    def test_health_html_escapes_report_and_name(self):
        html = health_html("<Vendas>", "A < B & C")
        self.assertIn("&lt;Vendas&gt;", html)
        self.assertIn("A &lt; B &amp; C", html)
        self.assertNotIn("<Vendas>", html)

    def test_health_html_falls_back_to_default_name(self):
        self.assertIn("Saúde - Banco Firebird", health_html("  ", "ok"))

    def test_compare_html_wraps_report(self):
        html = compare_html("[ADD] TABLE X")
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn("[ADD] TABLE X", html)


if __name__ == "__main__":
    unittest.main()
