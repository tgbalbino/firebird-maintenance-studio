import unittest

from firebird_studio.sql_documents import SqlDocumentManager


class _Widget:
    def __init__(self, **properties):
        self.properties = properties
        self.deleted = False

    def property(self, name):
        return self.properties.get(name)

    def deleteLater(self):
        self.deleted = True


class _Tabs:
    def __init__(self, *widgets):
        self.widgets = list(widgets)
        self.titles = ["" for _ in self.widgets]
        self.tooltips = ["" for _ in self.widgets]

    def addTab(self, widget, title):
        self.widgets.append(widget)
        self.titles.append(title)
        self.tooltips.append("")
        return len(self.widgets) - 1

    def count(self):
        return len(self.widgets)

    def widget(self, index):
        return self.widgets[index]

    def removeTab(self, index):
        self.widgets.pop(index)
        self.titles.pop(index)
        self.tooltips.pop(index)

    def tabText(self, index):
        return self.titles[index]

    def setTabText(self, index, text):
        self.titles[index] = text

    def setTabToolTip(self, index, text):
        self.tooltips[index] = text

    def setCurrentIndex(self, _index):
        pass


class SqlDocumentManagerTests(unittest.TestCase):
    def test_update_title_keeps_tab_compact_and_tooltip_context(self):
        editor = _Widget(document_title="SQL 1", query_profile="HOMOLOG")
        tabs = _Tabs(editor)

        SqlDocumentManager(tabs).update_title(0)

        self.assertEqual(tabs.tabText(0), "SQL 1")
        self.assertIn("Banco: HOMOLOG", tabs.tooltips[0])

    def test_close_releases_widget_without_recreating_editor(self):
        editor = _Widget()
        tabs = _Tabs(editor)
        created = []

        SqlDocumentManager(tabs).close(0, lambda: created.append(True))

        self.assertTrue(editor.deleted)
        self.assertEqual(tabs.count(), 0)
        self.assertEqual(created, [])

    def test_close_all_releases_every_widget(self):
        first = _Widget()
        second = _Widget()
        tabs = _Tabs(first, second)
        created = []

        SqlDocumentManager(tabs).close_all(lambda: created.append(True))

        self.assertTrue(first.deleted)
        self.assertTrue(second.deleted)
        self.assertEqual(tabs.count(), 0)
        self.assertEqual(created, [])


if __name__ == "__main__":
    unittest.main()
