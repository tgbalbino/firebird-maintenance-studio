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
            QTabWidget,
            QTreeWidget,
            QTreeWidgetItem,
            QSizePolicy,
            QThread,
            QObject,
            Signal,
            Slot,
        )

        self._window = QMainWindow()
        self.show = self._window.show
        self._window.setWindowTitle("Firebird Maintenance Studio")
        self._window.resize(1100, 700)
        self.store = store
        self._open_thread = None
        self._open_worker = None
        self.profiles = store.load()
        self.profile_list = QListWidget()
        self.name = QLineEdit()
        self.host = QLineEdit("localhost")
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(3050)
        self.database = QLineEdit()
        self.version = QComboBox(); self.version.addItems(SUPPORTED_VERSIONS)
        self.target_profile = QComboBox()
        self.user = QLineEdit("SYSDBA")
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.password.setPlaceholderText("Senha temporária; não é salva no perfil")
        self.charset = QLineEdit("UTF8")
        self.isql_path = QLineEdit(); self.isql_path.setPlaceholderText("C:\\Firebird\\Firebird_5_0\\isql.exe")
        self.gbak_path = QLineEdit(); self.gbak_path.setPlaceholderText("C:\\Firebird\\Firebird_5_0\\gbak.exe")
        self.status = QLabel("Pronto. Nenhum banco conectado.")
        self.object_tree = QTreeWidget(); self.object_tree.setHeaderLabels(["Objetos do banco"])
        self.object_tree.itemDoubleClicked.connect(self.open_object)
        self.object_tree.setMinimumWidth(240)
        self.object_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sql_tabs = QTabWidget(); self.sql_tabs.setTabsClosable(True); self.sql_tabs.tabCloseRequested.connect(self.close_sql_tab)
        self.sql_tabs.currentChanged.connect(self._sync_editor)
        self.editor = None
        self._new_sql_tab()
        self.result_table = QTableWidget(); self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)

        left = QWidget(); left_layout = QVBoxLayout(left); left.setMinimumWidth(280)
        left_layout.addWidget(QLabel("Bancos configurados (duplo clique para abrir)")); left_layout.addWidget(self.profile_list, 1)
        left_layout.addWidget(QLabel("Objetos do banco")); left_layout.addWidget(self.object_tree, 1)
        new_button = QPushButton("Novo perfil"); new_button.clicked.connect(self.new_profile); left_layout.addWidget(new_button)
        save_button = QPushButton("Salvar perfil"); save_button.clicked.connect(self.save_profile); left_layout.addWidget(save_button)
        left_layout.addStretch()

        form = QFormLayout(); form.addRow("Nome", self.name); form.addRow("Host", self.host)
        form.addRow("Porta", self.port); form.addRow("Caminho ou alias", self.database)
        form.addRow("Firebird", self.version); form.addRow("Usuário", self.user); form.addRow("Senha", self.password); form.addRow("Charset", self.charset); form.addRow("Caminho isql", self.isql_path); form.addRow("Caminho gbak", self.gbak_path); form.addRow("Comparar com", self.target_profile)
        box = QGroupBox("Perfil selecionado"); box.setLayout(form)
        right = QWidget(); right_layout = QVBoxLayout(right); right_layout.addWidget(box)
        right_layout.addWidget(QLabel("Janelas SQL")); right_layout.addWidget(self.sql_tabs, 1)
        action_row = QHBoxLayout(); test_button = QPushButton("Testar conexão"); test_button.clicked.connect(self.test_selected)
        new_sql_button = QPushButton("Nova janela SQL"); new_sql_button.clicked.connect(self._new_sql_tab)
        execute_button = QPushButton("Executar SQL"); execute_button.clicked.connect(self.execute_selected)
        script_button = QPushButton("Executar arquivo SQL"); script_button.clicked.connect(self.execute_script_file)
        backup_button = QPushButton("Backup"); backup_button.clicked.connect(self.execute_backup)
        restore_button = QPushButton("Restore"); restore_button.clicked.connect(self.execute_restore)
        schema_button = QPushButton("Ler estrutura"); schema_button.clicked.connect(self.inspect_schema)
        plan_button = QPushButton("Ver plano"); plan_button.clicked.connect(self.inspect_plan)
        health_button = QPushButton("Saúde"); health_button.clicked.connect(self.inspect_health)
        compare_button = QPushButton("Comparar"); compare_button.clicked.connect(self.compare_selected)
        action_row.addWidget(test_button); action_row.addWidget(new_sql_button); action_row.addWidget(execute_button); action_row.addWidget(script_button); action_row.addWidget(backup_button); action_row.addWidget(restore_button); action_row.addWidget(schema_button); action_row.addWidget(plan_button); action_row.addWidget(health_button); action_row.addWidget(compare_button); action_row.addStretch(); right_layout.addLayout(action_row)
        right_layout.addWidget(self.result_table); right_layout.addWidget(self.status)
        splitter = QSplitter(); splitter.addWidget(left); splitter.addWidget(right); splitter.setSizes([260, 840])
        self._window.setCentralWidget(splitter)
        self.profile_list.currentRowChanged.connect(self.select_profile)
        self.profile_list.itemDoubleClicked.connect(lambda _item: self.open_profile())
        self.refresh_profiles()
        splitter.setSizes([360, 1040])

    def _sync_editor(self, index: int):
        self.editor = self.sql_tabs.widget(index) if index >= 0 else None

    def _new_sql_tab(self):
        from PySide6.QtWidgets import QTextEdit
        editor = QTextEdit()
        editor.setPlaceholderText("Execute uma instrução SQL...")
        index = self.sql_tabs.addTab(editor, f"SQL {self.sql_tabs.count() + 1}")
        self.sql_tabs.setCurrentIndex(index)
        self.editor = editor

    def close_sql_tab(self, index: int):
        if self.sql_tabs.count() == 1:
            return
        widget = self.sql_tabs.widget(index)
        self.sql_tabs.removeTab(index)
        widget.deleteLater()

    def open_profile(self):
        """Open the selected database, like opening a connection in IBExpert."""
        if self.profile_list.currentRow() < 0:
            self.status.setText("Selecione um banco configurado.")
            return
        if self._open_thread is not None and self._open_thread.isRunning():
            self.status.setText("Já existe uma conexão em andamento.")
            return

        class OpenWorker(QObject):
            finished = Signal(object, object, str)

            def __init__(self, profile, password):
                super().__init__()
                self.profile = profile
                self.password = password

            @Slot()
            def run(self):
                from .catalog import load_schema
                from .connection import test_connection

                result = test_connection(self.profile, self.password)
                if not result.ok:
                    self.finished.emit(result, [], "")
                    return
                try:
                    objects = load_schema(self.profile, self.password)
                    self.finished.emit(result, objects, "")
                except Exception as exc:
                    self.finished.emit(result, [], str(exc))

        from .credentials import CredentialStore

        profile = self._profile_from_form()
        password = self.password.text() or CredentialStore().get(self.name.text())
        self.status.setText("Conectando e carregando objetos do banco...")
        self._open_thread = QThread()
        self._open_worker = OpenWorker(profile, password)
        self._open_worker.moveToThread(self._open_thread)
        self._open_thread.started.connect(self._open_worker.run)
        self._open_worker.finished.connect(self._on_profile_opened)
        self._open_worker.finished.connect(self._open_thread.quit)
        self._open_worker.finished.connect(self._open_worker.deleteLater)
        self._open_thread.finished.connect(self._open_thread.deleteLater)
        self._open_thread.finished.connect(self._clear_open_worker)
        self._open_thread.start()

    def _clear_open_worker(self):
        self._open_thread = None
        self._open_worker = None

    def _on_profile_opened(self, result, objects, schema_error):
        if not result.ok:
            self.status.setText(result.message)
            return
        self._populate_object_tree(objects)
        if schema_error:
            self.status.setText(f"{result.message} Conectado, mas não foi possível ler objetos: {schema_error}")
        else:
            self.status.setText(f"{result.message} Objetos carregados: {len(objects)}.")

    def _populate_object_tree(self, objects):
        from PySide6.QtWidgets import QTreeWidgetItem

        self.object_tree.clear()
        groups = {}
        for obj in objects:
            label = {"TABLE": "Tabelas", "VIEW": "Views", "PROCEDURE": "Procedures", "TRIGGER": "Triggers"}.get(obj.kind, obj.kind.title())
            groups.setdefault(label, []).append(obj)
        for label in sorted(groups):
            parent = QTreeWidgetItem([f"{label} ({len(groups[label])})"])
            self.object_tree.addTopLevelItem(parent)
            for obj in groups[label]:
                item = QTreeWidgetItem([obj.name])
                item.setData(0, 32, obj)
                parent.addChild(item)
            parent.setExpanded(True)

    def open_object(self, item, _column=0):
        obj = item.data(0, 32)
        if obj is None:
            return
        self._new_sql_tab()
        self.editor.setPlainText(obj.ddl)
        self.sql_tabs.setTabText(self.sql_tabs.currentIndex(), obj.name)

    def refresh_profiles(self):
        self.profile_list.clear()
        self.profile_list.addItems([f"{p.name} · FB {p.version}" for p in self.profiles])
        self.target_profile.clear()
        self.target_profile.addItems([p.name for p in self.profiles])

    def new_profile(self):
        self.profile_list.clearSelection(); self.name.clear(); self.database.clear(); self.status.setText("Novo perfil.")

    def select_profile(self, index: int):
        if index < 0 or index >= len(self.profiles): return
        p = self.profiles[index]
        for widget, value in ((self.name, p.name), (self.host, p.host), (self.database, p.database), (self.user, p.user), (self.charset, p.charset), (self.isql_path, p.isql_path), (self.gbak_path, p.gbak_path)):
            widget.setText(value)
        self.password.clear()
        self.port.setValue(p.port); self.version.setCurrentText(p.version)

    def _profile_from_form(self):
        return ConnectionProfile(self.name.text(), self.host.text(), self.port.value(), self.database.text(), self.version.currentText(), self.user.text(), charset=self.charset.text(), isql_path=self.isql_path.text(), gbak_path=self.gbak_path.text())

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
        if result.ok:
            try:
                from .catalog import load_schema
                objects = load_schema(self._profile_from_form(), self.password.text() or CredentialStore().get(self.name.text()))
                self._populate_object_tree(objects)
                self.status.setText(f"{result.message} Objetos carregados: {len(objects)}.")
            except Exception as exc:
                self.status.setText(f"{result.message} Conectado, mas não foi possível ler objetos: {exc}")

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

    def execute_backup(self):
        from .backup import run_gbak
        from .credentials import CredentialStore

        source = Path(self.database.text())
        filename, _ = QFileDialog.getSaveFileName(self._window, "Salvar backup Firebird", "", "Backup Firebird (*.fbk);;Todos (*.*)")
        if not filename:
            return
        result = run_gbak(self._profile_from_form(), "backup", source, Path(filename), self.password.text() or CredentialStore().get(self.name.text()), Path(self.gbak_path.text()))
        self.editor.setPlainText(result.output + ("\n" + result.error if result.error else ""))
        self.status.setText("Backup concluído." if result.ok else f"Backup falhou: {result.error}")

    def execute_restore(self):
        from .backup import run_gbak
        from .credentials import CredentialStore

        source, _ = QFileDialog.getOpenFileName(self._window, "Selecionar backup Firebird", "", "Backup Firebird (*.fbk *.gbk);;Todos (*.*)")
        if not source:
            return
        target, _ = QFileDialog.getSaveFileName(self._window, "Criar banco restaurado", "", "Banco Firebird (*.fdb *.gdb);;Todos (*.*)")
        if not target:
            return
        result = run_gbak(self._profile_from_form(), "restore", Path(source), Path(target), self.password.text() or CredentialStore().get(self.name.text()), Path(self.gbak_path.text()))
        self.editor.setPlainText(result.output + ("\n" + result.error if result.error else ""))
        self.status.setText("Restore concluído." if result.ok else f"Restore falhou: {result.error}")

    def inspect_schema(self):
        from .catalog import load_schema
        from .credentials import CredentialStore

        try:
            objects = load_schema(self._profile_from_form(), self.password.text() or CredentialStore().get(self.name.text()))
        except Exception as exc:
            self.status.setText(f"Falha ao ler estrutura: {exc}")
            return
        self.editor.setPlainText("\n".join(f"{obj.kind}: {obj.name}\n{obj.ddl}" for obj in objects))
        self._populate_object_tree(objects)
        self.status.setText(f"Estrutura lida: {len(objects)} objeto(s).")

    def inspect_plan(self):
        from .credentials import CredentialStore
        from .plan import explain_query

        profile = self._profile_from_form()
        if not profile.isql_path:
            self.status.setText("Configure o caminho do isql no perfil antes de analisar o plano.")
            return
        result = explain_query(profile, self.editor.toPlainText(), self.password.text() or CredentialStore().get(self.name.text()), Path(profile.isql_path))
        if not result.ok:
            self.status.setText(result.error)
            return
        lines = ["ÁRVORE DO PLANO", ""]
        def visit(node, depth=0):
            if node.label != "Plano de acesso": lines.append("  " * depth + "• " + node.label)
            for child in node.children: visit(child, depth + (0 if node.label == "Plano de acesso" else 1))
        visit(result.tree)
        lines.extend(["", "SUGESTÕES", ""])
        lines.extend(f"- {item}" for item in result.suggestions)
        self.editor.setPlainText("\n".join(lines) + "\n\nSAÍDA ISQL\n" + result.raw)
        self.status.setText("Plano analisado sem executar a consulta.")

    def inspect_health(self):
        from .credentials import CredentialStore
        from .health import inspect_health

        try:
            report = inspect_health(self._profile_from_form(), self.password.text() or CredentialStore().get(self.name.text()))
        except Exception as exc:
            self.status.setText(f"Falha ao ler saúde: {exc}")
            return
        lines = ["INDICADORES", ""] + [f"{key}: {value}" for key, value in report.metrics.items()]
        lines.extend(["", "RECOMENDAÇÕES", ""])
        for finding in report.findings:
            lines.extend([f"[{finding.severity.upper()}] {finding.title}", f"Evidência: {finding.evidence}", f"Ação sugerida: {finding.recommendation}", ""])
        self.editor.setPlainText("\n".join(lines))
        self.status.setText(f"Saúde analisada: {len(report.findings)} recomendação(ões).")

    def compare_selected(self):
        from .catalog import load_schema
        from .credentials import CredentialStore
        from .schema import compare_schema, generate_migration

        target_name = self.target_profile.currentText()
        source = self._profile_from_form()
        target = next((profile for profile in self.profiles if profile.name == target_name), None)
        if target is None or target.name == source.name:
            self.status.setText("Cadastre e selecione um perfil de destino diferente da origem.")
            return
        try:
            password = self.password.text() or CredentialStore().get(self.name.text())
            target_password = CredentialStore().get(target.name) or password
            source_objects = load_schema(source, password)
            target_objects = load_schema(target, target_password)
            changes = compare_schema(source_objects, target_objects)
        except Exception as exc:
            self.status.setText(f"Falha ao comparar estruturas: {exc}")
            return
        lines = [f"ORIGEM: {source.name}", f"DESTINO: {target.name}", "", f"Diferenças: {len(changes)}", ""]
        for change in changes:
            marker = "REVISAR" if change.destructive else change.action
            lines.append(f"[{marker}] {change.object.kind} {change.object.name}")
        lines.extend(["", "PRÉVIA DE MIGRAÇÃO", "", generate_migration(changes)])
        self.editor.setPlainText("\n".join(lines))
        self.status.setText(f"Comparação concluída: {len(changes)} diferença(s). Nenhuma alteração foi aplicada.")
