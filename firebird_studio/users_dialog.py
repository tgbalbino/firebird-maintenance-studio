"""Dialog for Firebird users, roles and privileges."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .users import (
    PRIVILEGES,
    change_user_password,
    create_role,
    create_user,
    delete_user,
    grant_privilege,
    grant_role,
    list_users,
    revoke_privilege,
    revoke_role,
)


def show_users_dialog(parent, profiles, profile, password_for, show_message, log_event, set_status):
    """Run the modal dialog for ``profile``; the user may switch connection inside it.

    ``password_for(profile)`` returns the admin password, ``show_message(title, text, warning=...)``
    reports problems, ``log_event(message, **details)`` records actions and ``set_status(text)``
    updates the main status line.
    """
    admin_password = password_for(profile)
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"Usuários · {profile.name}")
    dialog.resize(640, 420)
    layout = QVBoxLayout(dialog)
    connection_row = QHBoxLayout()
    connection_row.addWidget(QLabel("Conexão"))
    connection_combo = QComboBox()
    connection_combo.addItems([item.name for item in profiles])
    connection_combo.setCurrentText(profile.name)
    connection_combo.setToolTip("Banco usado para as operações administrativas")
    connection_row.addWidget(connection_combo, 1)
    layout.addLayout(connection_row)
    layout.addWidget(QLabel("As operações exigem uma conta administrativa. Senhas nunca são salvas nem registradas no log."))
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["Usuário", "Nome", "Sobrenome", "Ativo"])
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    layout.addWidget(table)
    actions = QHBoxLayout()
    refresh = QPushButton("Atualizar")
    create = QPushButton("Criar usuário")
    change = QPushButton("Alterar senha")
    sysdba = QPushButton("Alterar senha SYSDBA")
    remove = QPushButton("Excluir usuário")
    actions.addWidget(refresh); actions.addWidget(create); actions.addWidget(change); actions.addWidget(sysdba); actions.addWidget(remove)
    layout.addLayout(actions)
    role_row = QHBoxLayout()
    role_name = QLineEdit(); role_name.setPlaceholderText("Nome da role")
    create_role_button = QPushButton("Criar role")
    grant_role_button = QPushButton("Conceder role ao usuário selecionado")
    revoke_role_button = QPushButton("Remover role do usuário selecionado")
    role_row.addWidget(role_name); role_row.addWidget(create_role_button); role_row.addWidget(grant_role_button); role_row.addWidget(revoke_role_button)
    layout.addLayout(role_row)
    privilege_row = QHBoxLayout()
    privilege_combo = QComboBox(); privilege_combo.addItems(PRIVILEGES)
    object_name = QLineEdit(); object_name.setPlaceholderText("Tabela, view ou procedure")
    grant_privilege_button = QPushButton("Conceder privilégio")
    revoke_privilege_button = QPushButton("Remover privilégio")
    privilege_row.addWidget(privilege_combo); privilege_row.addWidget(object_name); privilege_row.addWidget(grant_privilege_button); privilege_row.addWidget(revoke_privilege_button)
    layout.addLayout(privilege_row)
    close = QDialogButtonBox(QDialogButtonBox.Close)
    close.rejected.connect(dialog.reject)
    layout.addWidget(close)

    def selected_user() -> str:
        row = table.currentRow()
        return table.item(row, 0).text() if row >= 0 and table.item(row, 0) else ""

    def select_connection(name: str):
        nonlocal profile, admin_password
        selected = next((item for item in profiles if item.name == name), None)
        if selected is None:
            return
        profile = selected
        admin_password = password_for(profile)
        dialog.setWindowTitle(f"Usuários · {profile.name}")
        reload_users()

    def ask_secret(title: str) -> tuple[str, str] | None:
        first, accepted = QInputDialog.getText(dialog, title, "Nova senha:", QLineEdit.Password)
        if not accepted:
            return None
        second, accepted = QInputDialog.getText(dialog, title, "Confirme a nova senha:", QLineEdit.Password)
        return (first, second) if accepted else None

    def reload_users():
        try:
            users = list_users(profile, admin_password)
        except Exception as exc:
            show_message("Gestão de usuários", str(exc), warning=True)
            return
        table.setRowCount(0)
        for user in users:
            row = table.rowCount(); table.insertRow(row)
            for column, value in enumerate((user.name, user.first_name, user.last_name, "Sim" if user.active in (None, 1, "1", True) else "Não")):
                table.setItem(row, column, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()

    def role_value() -> str:
        return role_name.text().strip()

    def create_role_action():
        target = role_value()
        if not target:
            show_message("Criar role", "Informe o nome da role.", warning=True); return
        try:
            create_role(profile, admin_password, target)
            log_event("Role criada", profile=profile.name, role=target)
            set_status(f"Role {target} criada.")
        except Exception as exc:
            show_message("Criar role", str(exc), warning=True)

    def change_role_action(revoke: bool):
        target_user = selected_user(); target_role = role_value()
        if not target_user or not target_role:
            show_message("Permissão de role", "Selecione um usuário e informe a role.", warning=True); return
        try:
            (revoke_role if revoke else grant_role)(profile, admin_password, target_role, target_user)
            action = "removida" if revoke else "concedida"
            log_event("Role alterada", profile=profile.name, role=target_role, user=target_user, action=action)
            set_status(f"Role {target_role} {action} para {target_user}.")
        except Exception as exc:
            show_message("Permissão de role", str(exc), warning=True)

    def change_privilege_action(revoke: bool):
        target_user = selected_user(); target_object = object_name.text().strip(); privilege = privilege_combo.currentText()
        if not target_user or not target_object:
            show_message("Privilégio", "Selecione um usuário e informe o objeto.", warning=True); return
        if revoke:
            answer = QMessageBox.question(dialog, "Remover privilégio", f"Remover {privilege} de {target_user} no objeto {target_object}?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        try:
            (revoke_privilege if revoke else grant_privilege)(profile, admin_password, privilege, target_object, target_user)
            action = "removido" if revoke else "concedido"
            log_event("Privilégio alterado", profile=profile.name, privilege=privilege, object=target_object, user=target_user, action=action)
            set_status(f"Privilégio {privilege} {action} para {target_user}.")
        except Exception as exc:
            show_message("Privilégio", str(exc), warning=True)

    def create_user_action():
        username, accepted = QInputDialog.getText(dialog, "Criar usuário", "Nome do usuário:")
        if not accepted or not username.strip():
            return
        secrets = ask_secret("Criar usuário")
        if secrets is None:
            return
        try:
            create_user(profile, admin_password, username, secrets[0], secrets[1])
            log_event("Usuário criado", profile=profile.name, user=username.strip())
            reload_users()
        except Exception as exc:
            show_message("Criar usuário", str(exc), warning=True)

    def change_user_action(username: str | None = None):
        target = username or selected_user()
        if not target:
            show_message("Alterar senha", "Selecione um usuário.", warning=True); return
        secrets = ask_secret(f"Alterar senha · {target}")
        if secrets is None:
            return
        try:
            change_user_password(profile, admin_password, target, secrets[0], secrets[1])
            log_event("Senha de usuário alterada", profile=profile.name, user=target)
            reload_users()
        except Exception as exc:
            show_message("Alterar senha", str(exc), warning=True)

    def change_sysdba_action():
        answer = QMessageBox.question(dialog, "Alterar senha SYSDBA", "Essa operação altera a senha administrativa do banco. Continuar?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            change_user_action("SYSDBA")

    def delete_user_action():
        target = selected_user()
        if not target:
            show_message("Excluir usuário", "Selecione um usuário.", warning=True); return
        answer = QMessageBox.question(dialog, "Excluir usuário", f"Excluir o usuário {target}?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            delete_user(profile, admin_password, target)
            log_event("Usuário excluído", profile=profile.name, user=target)
            reload_users()
        except Exception as exc:
            show_message("Excluir usuário", str(exc), warning=True)

    connection_combo.currentTextChanged.connect(select_connection)
    refresh.clicked.connect(reload_users); create.clicked.connect(create_user_action); change.clicked.connect(lambda: change_user_action()); sysdba.clicked.connect(change_sysdba_action); remove.clicked.connect(delete_user_action)
    create_role_button.clicked.connect(create_role_action); grant_role_button.clicked.connect(lambda: change_role_action(False)); revoke_role_button.clicked.connect(lambda: change_role_action(True))
    grant_privilege_button.clicked.connect(lambda: change_privilege_action(False)); revoke_privilege_button.clicked.connect(lambda: change_privilege_action(True))
    reload_users()
    dialog.exec()
