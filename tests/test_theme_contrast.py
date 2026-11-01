import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit, QTableWidget
except ImportError:  # pragma: no cover - UI extras are optional
    QTableWidget = None

MIN_CONTRAST = 4.5  # WCAG AA for normal text


def _luminance(color):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.red()) + 0.7152 * channel(color.green()) + 0.0722 * channel(color.blue())


def _contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@unittest.skipIf(QTableWidget is None, "PySide6 não instalado")
class GridContrastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def cell_contrast(self, state):
        """Contrast between a cell's background and its text in the given state."""
        from firebird_studio.result_views import fill_table

        table = QTableWidget()
        fill_table(table, ["A", "B"], [("11941017630", "x"), ("22222222", "y"), ("3333", "z")])
        table.resize(360, 160)
        other = QLineEdit()
        other.show()
        table.show()
        self.app.processEvents()
        if state == "hover_unselected":
            table.clearSelection()
            row = 2
        else:
            table.setCurrentCell(1, 0)
            table.selectRow(1)
            row = 1
        if state == "selected_inactive":
            other.setFocus()
        else:
            table.setFocus()
            table.activateWindow()
        self.app.processEvents()
        rect = table.visualItemRect(table.item(row, 0))
        if state in ("selected_hover", "hover_unselected"):
            QTest.mouseMove(table.viewport(), rect.center())
            self.app.processEvents()
            QTest.mouseMove(table.viewport(), rect.center() + QPoint(1, 0))
            self.app.processEvents()
        image = table.viewport().grab(rect).toImage()
        counts = {}
        for x in range(image.width()):
            for y in range(image.height()):
                rgb = image.pixelColor(x, y).rgb()
                counts[rgb] = counts.get(rgb, 0) + 1
        background = QColor(max(counts, key=counts.get))
        text = max(counts, key=lambda rgb: abs(_luminance(QColor(rgb)) - _luminance(background)))
        return _contrast(background, QColor(text))

    def test_selected_and_hovered_cells_stay_readable_in_every_theme(self):
        from firebird_studio.ui_theme import apply_theme

        for theme in ("light", "gray", "dark", "blue"):
            apply_theme(theme)
            for state in ("selected_active", "selected_inactive", "selected_hover", "hover_unselected"):
                with self.subTest(theme=theme, state=state):
                    self.assertGreaterEqual(self.cell_contrast(state), MIN_CONTRAST)
        apply_theme("light")


@unittest.skipIf(QTableWidget is None, "PySide6 não instalado")
class MenuIconSpacingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def test_item_icons_do_not_touch_the_menu_border(self):
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtWidgets import QMenu

        from firebird_studio.ui_theme import apply_theme

        marker = QColor(255, 0, 0)
        pixmap = QPixmap(16, 16)
        pixmap.fill(marker)
        for theme in ("light", "gray", "dark", "blue"):
            apply_theme(theme)
            menu = QMenu()
            menu.addAction(QIcon(pixmap), "Colar")
            menu.addAction("Selecionar tudo")
            menu.show()
            self.app.processEvents()
            image = menu.grab().toImage()
            leftmost = min(
                (x for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x, y) == marker),
                default=None,
            )
            with self.subTest(theme=theme):
                self.assertIsNotNone(leftmost)
                self.assertGreaterEqual(leftmost, 6)
            menu.close()
        apply_theme("light")


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(QTableWidget is None, "PySide6 não instalado")
class TabCloseHoverTests(unittest.TestCase):
    """The tab close button must react to the mouse in every theme."""

    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def changed_pixels(self, theme):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication, QTabBar

        from firebird_studio.ui_theme import apply_theme

        apply_theme(theme)
        bar = QTabBar()
        bar.setTabsClosable(True)
        bar.addTab("SQL 1")
        bar.addTab("SQL 2")
        bar.setCurrentIndex(1)
        bar.resize(300, 40)
        bar.show()
        self.addCleanup(bar.deleteLater)
        self.app.processEvents()
        button = bar.tabButton(0, QTabBar.RightSide)
        QTest.mouseMove(bar, QPoint(290, 35))
        self.app.processEvents()
        idle = button.grab().toImage()
        QTest.mouseMove(button, button.rect().center())
        QApplication.sendEvent(button, QEvent(QEvent.Enter))
        self.app.processEvents()
        hover = button.grab().toImage()
        return sum(
            1 for x in range(idle.width()) for y in range(idle.height()) if idle.pixel(x, y) != hover.pixel(x, y)
        )

    def test_close_button_shows_hover_in_every_theme(self):
        for theme in ("light", "gray", "dark", "blue"):
            self.assertGreater(self.changed_pixels(theme), 50, theme)

    def tearDown(self):
        from firebird_studio.ui_theme import apply_theme

        apply_theme("light")


@unittest.skipIf(QTableWidget is None, "PySide6 não instalado")
class QtTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def test_built_in_qt_texts_are_portuguese(self):
        from PySide6.QtWidgets import QTabBar

        bar = QTabBar()
        bar.setTabsClosable(True)
        bar.addTab("SQL 1")
        self.addCleanup(bar.deleteLater)
        self.assertEqual(bar.tabButton(0, QTabBar.RightSide).toolTip(), "Fechar aba")

    def test_translator_is_installed_only_once(self):
        from firebird_studio.ui import create_application

        translator = self.app._qt_translator
        self.assertIs(create_application(), self.app)
        self.assertIs(self.app._qt_translator, translator)
