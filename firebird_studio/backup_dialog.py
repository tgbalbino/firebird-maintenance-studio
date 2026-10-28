"""Restore dialog for a backup file opened from Windows or the command line."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ConnectionProfile, SUPPORTED_VERSIONS


@dataclass(slots=True)
class RestoreRequest:
    profile: ConnectionProfile
    target: Path
    password: str
    gbak_path: Path
    register_profile: bool
    save_password: bool


def choose_restore_target(parent, target) -> None:
    from PySide6.QtWidgets import QFileDialog

    filename, _ = QFileDialog.getSaveFileName(parent, "Salvar banco restaurado", target.text(), "Banco Firebird (*.fdb *.gdb);;Todos (*.*)")
    if filename:
        target.setText(filename)


def ask_restore_request(parent, source: Path, profiles, stored_password) -> RestoreRequest | None:
    """Ask how to restore ``source``; return None when the user cancels.

    The returned profile is not validated: the caller reports its errors.
    ``stored_password(name)`` supplies the saved password of a known profile.
    """
    from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLineEdit, QSpinBox, QVBoxLayout, QLabel, QWidget, QPushButton

    dialog = QDialog(parent)
    dialog.setWindowTitle(f"Restaurar backup — {source.name}")
    dialog.setModal(True)
    dialog.resize(620, 430)
    form = QFormLayout()
    profile_choice = QComboBox()
    profile_choice.addItem("Nova conexão")
    profile_choice.addItems([item.name for item in profiles])
    name = QLineEdit(source.stem)
    host = QLineEdit("localhost")
    port = QSpinBox(); port.setRange(1, 65535); port.setValue(3050)
    version = QComboBox(); version.addItems(SUPPORTED_VERSIONS); version.setCurrentText("5")
    user = QLineEdit("SYSDBA")
    password = QLineEdit(); password.setEchoMode(QLineEdit.Password)
    gbak_path = QLineEdit()
    target = QLineEdit(str(source.with_suffix(".fdb")))
    target_button = QPushButton("...")
    target_button.setFixedWidth(34)
    target_row = QWidget(); target_layout = QHBoxLayout(target_row); target_layout.setContentsMargins(0, 0, 0, 0); target_layout.addWidget(target, 1); target_layout.addWidget(target_button)
    save_profile = QCheckBox("Adicionar o banco restaurado aos cadastros")
    save_password = QCheckBox("Salvar senha criptografada")
    form.addRow("Usar cadastro", profile_choice)
    for label, widget in (("Nome do cadastro", name), ("Host", host), ("Porta", port), ("Firebird", version), ("Usuário", user), ("Senha", password), ("Caminho gbak", gbak_path), ("Arquivo FDB", target_row)):
        form.addRow(label, widget)
    form.addRow("", save_profile); form.addRow("", save_password)
    hint = QLabel(f"Backup selecionado:\n{source}"); hint.setWordWrap(True)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
    target_button.clicked.connect(lambda: choose_restore_target(dialog, target))

    def load_restore_profile(profile_name):
        selected = next((item for item in profiles if item.name == profile_name), None)
        if selected is None:
            return
        name.setText(f"{selected.name} restaurado")
        host.setText(selected.host); port.setValue(selected.port); version.setCurrentText(selected.version)
        user.setText(selected.user); gbak_path.setText(selected.gbak_path)
        password.setText(stored_password(selected.name) or "")

    profile_choice.currentTextChanged.connect(load_restore_profile)
    layout = QVBoxLayout(dialog); layout.addWidget(hint); layout.addLayout(form); layout.addWidget(buttons)
    if dialog.exec() != QDialog.Accepted:
        return None
    candidate = ConnectionProfile(name=name.text(), host=host.text(), port=port.value(), database=target.text(), version=version.currentText(), user=user.text(), isql_path="", gbak_path=gbak_path.text())
    return RestoreRequest(candidate, Path(target.text()).expanduser(), password.text(), Path(gbak_path.text()), save_profile.isChecked(), save_password.isChecked())
