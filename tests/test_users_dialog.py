import os
import unittest
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog, QTableWidget
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 não instalado")
class UsersDialogTests(unittest.TestCase):
    def test_lists_users_for_selected_profile_and_closes(self):
        from firebird_studio import users_dialog
        from firebird_studio.models import ConnectionProfile

        from firebird_studio.ui import create_application

        app = create_application()
        profile = ConnectionProfile(name="Vendas", database="C:/db/v.fdb")
        users = [SimpleNamespace(name="SYSDBA", first_name="", last_name="", active=1)]
        seen = {}

        def close_dialog():
            dialog = next(w for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible())
            seen["title"] = dialog.windowTitle()
            seen["rows"] = dialog.findChild(QTableWidget).rowCount()
            dialog.reject()

        QTimer.singleShot(50, close_dialog)
        with mock.patch.object(users_dialog, "list_users", return_value=users) as list_users:
            users_dialog.show_users_dialog(None, [profile], profile, lambda _p: "pw", mock.Mock(), mock.Mock(), mock.Mock())
        list_users.assert_called_with(profile, "pw")
        self.assertEqual(seen, {"title": "Usuários · Vendas", "rows": 1})


if __name__ == "__main__":
    unittest.main()
