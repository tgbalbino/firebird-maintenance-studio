"""Modal dialog used to create or edit a connection profile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ConnectionProfile, SUPPORTED_VERSIONS


@dataclass(slots=True)
class ProfileEdit:
    profile: ConnectionProfile
    password: str
    save_password: bool


def ask_profile(parent, profile: ConnectionProfile, title: str, stored_password: str | None) -> ProfileEdit | None:
    """Show the dialog for ``profile``; return None when the user cancels."""
    from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QFileDialog, QWidget

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.resize(560, 520)
    form = QFormLayout()

    name = QLineEdit(profile.name)
    host = QLineEdit(profile.host)
    port = QSpinBox(); port.setRange(1, 65535); port.setValue(profile.port)
    database = QLineEdit(profile.database)
    database_browse = QPushButton("...")
    database_browse.setFixedWidth(34)
    database_browse.setToolTip("Selecionar arquivo de banco Firebird")
    database_row = QWidget()
    database_layout = QHBoxLayout(database_row)
    database_layout.setContentsMargins(0, 0, 0, 0)
    database_layout.setSpacing(6)
    database_layout.addWidget(database, 1)
    database_layout.addWidget(database_browse)
    version = QComboBox(); version.addItems(SUPPORTED_VERSIONS); version.setCurrentText(profile.version)
    user = QLineEdit(profile.user)
    role = QLineEdit(profile.role)
    password = QLineEdit(stored_password or ""); password.setEchoMode(QLineEdit.Password)
    save_password = QCheckBox("Salvar senha criptografada no Windows")
    save_password.setChecked(bool(password.text()))
    charset = QLineEdit(profile.charset)
    isql_path = QLineEdit(profile.isql_path)
    gbak_path = QLineEdit(profile.gbak_path)
    favorite = QCheckBox("Favorito"); favorite.setChecked(profile.favorite)
    for label, widget in (("Nome", name), ("Host", host), ("Porta", port), ("Caminho ou alias", database_row), ("Firebird", version), ("Usuário", user), ("Role", role), ("Senha", password), ("Charset", charset), ("Caminho isql", isql_path), ("Caminho gbak", gbak_path)):
        form.addRow(label, widget)
    form.addRow("", save_password)
    form.addRow("", favorite)
    buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
    test_button = QPushButton("Testar conexão")
    buttons.addButton(test_button, QDialogButtonBox.ActionRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    output = QPlainTextEdit(); output.setReadOnly(True); output.setPlaceholderText("O resultado do teste aparecerá aqui.")

    def candidate() -> ConnectionProfile:
        return ConnectionProfile(
            name=name.text(), host=host.text(), port=port.value(), database=database.text(),
            version=version.currentText(), user=user.text(), role=role.text(),
            charset=charset.text(), favorite=favorite.isChecked(),
            isql_path=isql_path.text(), gbak_path=gbak_path.text(),
        )

    def browse_dialog_database():
        start_dir = database.text().strip()
        if start_dir and not Path(start_dir).is_dir():
            start_dir = str(Path(start_dir).parent)
        filename, _ = QFileDialog.getOpenFileName(
            dialog,
            "Selecionar arquivo do banco Firebird",
            start_dir or str(Path.home()),
            "Bancos Firebird (*.fdb *.FDB *.gdb *.GDB);;Todos os arquivos (*.*)",
        )
        if filename:
            database.setText(filename)

    def test_dialog_connection():
        from .connection import test_connection

        result = test_connection(candidate(), password.text())
        output.setPlainText(result.message + (f"\nVersão detectada: {result.server_version}" if result.server_version else ""))

    database_browse.clicked.connect(browse_dialog_database)
    test_button.clicked.connect(test_dialog_connection)
    layout = QVBoxLayout(dialog); layout.addLayout(form); layout.addWidget(output, 1); layout.addWidget(buttons)
    if dialog.exec() != QDialog.Accepted:
        return None
    return ProfileEdit(candidate(), password.text(), save_password.isChecked())
