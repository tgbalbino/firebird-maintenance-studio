import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QPixmap  # noqa: F401
except ImportError:  # pragma: no cover - UI extras are optional
    QPixmap = None

KINDS = ["TABLE", "VIEW", "PROCEDURE", "TRIGGER", "INDEX", "CONSTRAINT", "DOMAIN", "GENERATOR", "EXCEPTION", "PACKAGE"]


@unittest.skipIf(QPixmap is None, "PySide6 não instalado")
class ObjectIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from firebird_studio.ui import create_application

        cls.app = create_application()

    def image(self, kind):
        from firebird_studio.tree_utils import make_object_icon

        return make_object_icon(kind).pixmap(16, 16).toImage()

    def painted(self, image):
        return any(image.pixelColor(x, y).alpha() > 0 for x in range(image.width()) for y in range(image.height()))

    def test_every_known_kind_draws_something(self):
        for kind in KINDS:
            self.assertTrue(self.painted(self.image(kind)), kind)

    def test_different_shapes_are_distinguishable(self):
        images = {kind: self.image(kind) for kind in ("TABLE", "VIEW", "PROCEDURE", "FUNCTION", "TRIGGER", "INDEX", "DOMAIN", "EXCEPTION")}
        kinds = list(images)
        for index, first in enumerate(kinds):
            for second in kinds[index + 1:]:
                self.assertNotEqual(images[first], images[second], f"{first} vs {second}")

    def test_unknown_and_empty_kinds_get_a_neutral_marker(self):
        self.assertTrue(self.painted(self.image("COISA_NOVA")))
        self.assertTrue(self.painted(self.image(None)))

    def test_icons_are_cached_per_kind_case_insensitively(self):
        from firebird_studio.tree_utils import make_object_icon

        self.assertIs(make_object_icon("table"), make_object_icon("TABLE"))

    def test_icons_stay_crisp_on_scaled_screens(self):
        from firebird_studio.tree_utils import make_object_icon

        pixmap = make_object_icon("TABLE").pixmap(16, 16)
        self.assertGreaterEqual(pixmap.devicePixelRatio() * 16, 16)
        self.assertFalse(make_object_icon("TABLE").availableSizes() == [])

    def test_tree_children_carry_their_kind_icon(self):
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

        from firebird_studio.schema import SchemaObject
        from firebird_studio.tree_utils import populate_profile_children

        root = QTreeWidgetItem(["db"])
        tree = QTreeWidget()
        tree.addTopLevelItem(root)
        populate_profile_children(root, [SchemaObject("TABLE", "CLIENTE", ""), SchemaObject("VIEW", "V_X", "")])
        self.addCleanup(tree.deleteLater)
        for group in (root.child(i) for i in range(root.childCount())):
            self.assertFalse(group.child(0).icon(0).isNull(), group.text(0))
        self.assertNotEqual(root.child(0).child(0).icon(0).pixmap(16, 16).toImage(), root.child(1).child(0).icon(0).pixmap(16, 16).toImage())


if __name__ == "__main__":
    unittest.main()
