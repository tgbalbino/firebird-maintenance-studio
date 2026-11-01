import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QPalette, QColor, QTextCursor
except ImportError:  # pragma: no cover - UI extras are optional
    QPalette = None


@unittest.skipIf(QPalette is None, "PySide6 não instalado")
class CurrentLineHighlightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def editor(self, base="#ffffff"):
        from firebird_studio.sql_editor import SqlEditor

        editor = SqlEditor()
        palette = editor.palette()
        palette.setColor(QPalette.Base, QColor(base))
        editor.setPalette(palette)
        editor.setPlainText("SELECT 1\nFROM T\nWHERE 1=1")
        self.addCleanup(editor.deleteLater)
        return editor

    def highlighted_blocks(self, editor):
        return [selection.cursor.blockNumber() for selection in editor.extraSelections()]

    def move_to_line(self, editor, line):
        cursor = QTextCursor(editor.document().findBlockByNumber(line))
        editor.setTextCursor(cursor)

    def test_cursor_line_is_the_only_highlighted_line(self):
        editor = self.editor()
        self.move_to_line(editor, 1)
        self.assertEqual(self.highlighted_blocks(editor), [1])

    def test_highlight_follows_the_cursor(self):
        editor = self.editor()
        self.move_to_line(editor, 0)
        self.move_to_line(editor, 2)
        self.assertEqual(self.highlighted_blocks(editor), [2])

    def test_highlight_spans_the_whole_line_width(self):
        from PySide6.QtGui import QTextFormat

        editor = self.editor()
        selection = editor.extraSelections()[0]
        self.assertTrue(selection.format.boolProperty(QTextFormat.FullWidthSelection))

    def test_highlight_is_subtle_and_differs_from_the_background_in_both_themes(self):
        for base in ("#ffffff", "#1e1e1e"):
            editor = self.editor(base)
            selection = editor.extraSelections()[0]
            color = selection.format.background().color()
            background = QColor(base)
            distance = abs(color.lightness() - background.lightness())
            self.assertGreater(distance, 3, base)
            self.assertLess(distance, 40, base)

    def test_text_selection_does_not_leave_a_stale_line_highlight(self):
        editor = self.editor()
        editor.selectAll()
        self.assertLessEqual(len(editor.extraSelections()), 1)


if __name__ == "__main__":
    unittest.main()
