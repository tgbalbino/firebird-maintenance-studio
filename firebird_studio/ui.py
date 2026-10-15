from __future__ import annotations

from pathlib import Path

from .models import ConnectionProfile, ProfileStore, SUPPORTED_VERSIONS


def create_application():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Firebird Maintenance Studio")
    return app


class MainWindow:
    """Initial shell; keeps Qt imports out of headless validation."""

    def __init__(self, store: ProfileStore):
        from PySide6.QtWidgets import (
            QFormLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QPushButton,
            QSpinBox,
            QSplitter,
            QTextEdit,
            QVBoxLayout,
            QWidget,
            QComboBox,
            QTableWidget,
            QTableWidgetItem,
            QFileDialog,
        )

        self._window = QMainWindow()
        self.show = self._window.show
        self._window.setWindowTitle("Firebird Maintenance Studio")
        self._window.resize(1100, 700)
        self.store = store
        self.profiles = store.load()
        self.profile_list = QListWidget()
        self.name = QLineEdit()
        self.host = QLineEdit("localhost")
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(3050)
        self.database = QLineEdit()
        self.version = QComboBox(); self.version.addItems(SUPPORTED_VERSIONS)
        self.user = QLineEdit("SYSDBA")
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.password.setPlaceholderText("Senha temporária; não é salva no perfil")
        self.charset = QLineEdit("UTF8")
        self.isql_path = QLineEdit(); self.isql_path.setPlaceholderText("C:\\Firebird\\Firebird_5_0\\isql.exe")
        self.status = QLabel("Pronto. Nenhum banco conectado.")
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Execute uma instrução SQL. Scripts com múltiplos comandos usarão o runner isql em uma próxima etapa.")
        self.result_table = QTableWidget(); self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)

        left = QWidget(); left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Bancos configurados")); left_layout.addWidget(self.profile_list)
        new_button = QPushButton("Novo perfil"); new_button.clicked.connect(self.new_profile); left_layout.addWidget(new_button)
        save_button = QPushButton("Salvar perfil"); save_button.clicked.connect(self.save_profile); left_layout.addWidget(save_button)
        left_layout.addStretch()

        form = QFormLayout(); form.addRow("Nome", self.name); form.addRow("Host", self.host)
        form.addRow("Porta", self.port); form.addRow("Caminho ou alias", self.database)
        form.addRow("Firebird", self.version); form.addRow("Usuário", self.user); form.addRow("Senha", self.password); form.addRow("Charset", self.charset); form.addRow("Caminho isql", self.isql_path)
        box = QGroupBox("Perfil selecionado"); box.setLayout(form)
        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.addWidget(box)
        right_layout.addWidget(QLabel("Editor SQL")); right_layout.addWidget(self.editor)
        action_row = QHBoxLayout(); test_button = QPushButton("Testar conexão"); test_button.clicked.connect(self.test_selected)
        execute_button = QPushButton("Executar SQL"); execute_button.clicked.connect(self.execute_selected)
        script_button = QPushButton("Executar arquivo SQL"); script_button.clicked.connect(self.execute_script_file)
        action_row.addWidget(test_button); action_row.addWidget(execute_button); action_row.addWidget(script_button); action_row.addStretch(); right_layout.addLayout(action_row)
        right_layout.addWidget(self.result_table); right_layout.addWidget(self.status)
        splitter = QSplitter(); splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([260, 840])
        self._window.setCentralWidget(splitter)
        self.profile_list.currentRowChanged.connect(self.select_profile)
        self.refresh_profiles()

    def refresh_profiles(self):
        self.profile_list.clear()
        self.profile_list.addItems([f"{p.name} · FB {p.version}" for p in self.profiles])

    def new_profile(self):
        self.profile_list.clearSelection(); self.name.clear(); self.database.clear(); self.status.setText("Novo perfil.")

    def select_profile(self, index: int):
        if index < 0 or index >= len(self.profiles): return
        p = self.profiles[index]
        for widget, value in ((self.name, p.name), (self.host, p.host), (self.database, p.database), (self.user, p.user), (self.charset, p.charset), (self.isql_path, p.isql_path)):
            widget.setText(value)
        self.password.clear()
        self.port.setValue(p.port); self.version.setCurrentText(p.version)

    def _profile_from_form(self):
        return ConnectionProfile(self.name.text(), self.host.text(), self.port.value(), self.database.text(), self.version.currentText(), self.user.text(), charset=self.charset.text(), isql_path=self.isql_path.text())

    def save_profile(self):
        profile = self._profile_from_form(); errors = profile.validate()
        if errors: self.status.setText(" ".join(errors)); return
        selected = self.profile_list.currentRow()
        if 0 <= selected < len(self.profiles): self.profiles[selected] = profile
        else: self.profiles.append(profile)
        self.store.save(self.profiles); self.refresh_profiles(); self.status.setText("Perfil salvo sem senha.")

    def test_selected(self):
        from .connection import test_connection

        from .credentials import CredentialStore
        result = test_connection(self._profile_from_form(), self.password.text() or CredentialStore().get(self.name.text()))
        self.status.setText(result.message)

    def execute_selected(self):
        from .credentials import CredentialStore
        from .sql import execute_sql

        result = execute_sql(self._profile_from_form(), self.editor.toPlainText(), self.password.text() or CredentialStore().get(self.name.text()))
        self.status.setText(result.message)
        self.result_table.clear()
        self.result_table.setColumnCount(len(result.columns)); self.result_table.setRowCount(len(result.rows))
        self.result_table.setHorizontalHeaderLabels(result.columns)
        for row_index, row in enumerate(result.rows):
            for column_index, value in enumerate(row):
                self.result_table.setItem(row_index, column_index, QTableWidgetItem("" if value is None else str(value)))

    def execute_script_file(self):
        from .credentials import CredentialStore
        from .script_runner import run_script
        from PySide6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getOpenFileName(self._window, "Selecionar script SQL", "", "SQL (*.sql);;Todos (*.*)")
        if not filename:
            return
        profile = self._profile_from_form()
        if not profile.isql_path:
            self.status.setText("Configure o caminho do isql no perfil antes de executar um arquivo.")
            return
        result = run_script(profile, Path(filename), self.password.text() or CredentialStore().get(self.name.text()), Path(profile.isql_path))
        self.editor.setPlainText(result.output + ("\n" + result.error if result.error else ""))
        self.status.setText(("Script concluído. " if result.ok else "Script falhou. ") + result.error)
