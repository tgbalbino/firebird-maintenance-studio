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
            QMainWindow,
            QPushButton,
            QSpinBox,
            QSplitter,
            QTextEdit,
            QVBoxLayout,
            QWidget,
            QComboBox,
            QCheckBox,
            QTableWidget,
            QTableWidgetItem,
            QFileDialog,
            QTabWidget,
            QTreeWidget,
            QTreeWidgetItem,
            QSizePolicy,
            QAbstractItemView,
        )
        from PySide6.QtCore import QObject, QThread, Signal, Slot, QSettings, Qt

        self._window = QMainWindow()
        self.show = self._window.show
        self._window.setWindowTitle("Firebird Maintenance Studio")
        self._window.resize(1100, 700)
        self.store = store
        self._settings = QSettings("TGBalbino", "FirebirdMaintenanceStudio")
        self._open_thread = None
        self._open_worker = None
        self._opening_profile_name = None
        self.selected_object = None
        self.table_page = 0
        self.profiles = store.load()
        self.profile_objects = {}
        self.profile_list = QTreeWidget()
        self.profile_list.setHeaderLabels(["Bancos e objetos"])
        self.profile_list.setMinimumHeight(120)
        self.profile_list.setColumnCount(1)
        self.profile_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.name = QLineEdit()
        self.host = QLineEdit("localhost")
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(3050)
        self.database = QLineEdit()
        self.version = QComboBox(); self.version.addItems(SUPPORTED_VERSIONS)
        self.target_profile = QComboBox()
        self.user = QLineEdit("SYSDBA")
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.password.setPlaceholderText("Senha temporária; não é salva no perfil")
        self.save_password = QCheckBox("Salvar senha criptografada neste computador")
        self.show_password = QCheckBox("Mostrar senha")
        self.show_password.toggled.connect(lambda visible: self.password.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password))
        password_row = QWidget(); password_layout = QHBoxLayout(password_row); password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.addWidget(self.password, 1); password_layout.addWidget(self.save_password); password_layout.addWidget(self.show_password)
        self.charset = QLineEdit("UTF8")
        self.isql_path = QLineEdit(); self.isql_path.setPlaceholderText("C:\\Firebird\\Firebird_5_0\\isql.exe")
        self.gbak_path = QLineEdit(); self.gbak_path.setPlaceholderText("C:\\Firebird\\Firebird_5_0\\gbak.exe")
        self.status = QLabel("Pronto. Nenhum banco conectado.")
        self.object_tree = self.profile_list
        self.object_tree.setMinimumWidth(240)
        self.object_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.sql_tabs = QTabWidget(); self.sql_tabs.setMinimumHeight(320); self.sql_tabs.setTabsClosable(True); self.sql_tabs.tabCloseRequested.connect(self.close_sql_tab)
        self.sql_tabs.currentChanged.connect(self._sync_editor)
        self.query_history = []
        self.history_combo = QComboBox()
        self.history_combo.setMinimumWidth(260)
        self.history_combo.setPlaceholderText("Histórico SQL")
        self.history_combo.activated.connect(self._load_history_query)
        self.editor = None
        self._new_sql_tab()
        self.result_table = QTableWidget(); self.result_table.setMinimumHeight(180); self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)

        left = QWidget(); left_layout = QVBoxLayout(left); left.setMinimumWidth(280)
        left_layout.addWidget(QLabel("Bancos e objetos (duplo clique para abrir)")); left_layout.addWidget(self.profile_list, 1)
        self.open_data_button = QPushButton("Abrir dados da tabela")
        self.open_data_button.setEnabled(False)
        self.open_data_button.clicked.connect(self.open_table_data)
        left_layout.addWidget(self.open_data_button)
        new_button = QPushButton("Novo perfil"); new_button.clicked.connect(self.new_profile); left_layout.addWidget(new_button)
        save_button = QPushButton("Salvar perfil"); save_button.clicked.connect(self.save_profile); left_layout.addWidget(save_button)
        open_button = QPushButton("Abrir banco"); open_button.clicked.connect(self.open_profile); left_layout.addWidget(open_button)
        delete_button = QPushButton("Excluir cadastro"); delete_button.clicked.connect(self.delete_profile); left_layout.addWidget(delete_button)
        resize_row = QHBoxLayout()
        wider_button = QPushButton("Lateral +"); wider_button.clicked.connect(lambda: self._resize_sidebar(80))
        narrower_button = QPushButton("Lateral -"); narrower_button.clicked.connect(lambda: self._resize_sidebar(-80))
        resize_row.addWidget(wider_button); resize_row.addWidget(narrower_button)
        left_layout.addLayout(resize_row)
        left_layout.addStretch()

        form = QFormLayout(); form.addRow("Nome", self.name); form.addRow("Host", self.host)
        form.addRow("Porta", self.port); form.addRow("Caminho ou alias", self.database)
        form.addRow("Firebird", self.version); form.addRow("Usuário", self.user); form.addRow("Senha", password_row); form.addRow("Charset", self.charset); form.addRow("Caminho isql", self.isql_path); form.addRow("Caminho gbak", self.gbak_path); form.addRow("Comparar com", self.target_profile)
        box = QGroupBox("Perfil selecionado"); box.setLayout(form)
        self.profile_box = box
        self.profile_toggle = QPushButton("Ocultar dados do cadastro")
        self.profile_toggle.clicked.connect(self._toggle_profile_details)
        right = QWidget(); right.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(right); right_layout.addWidget(self.profile_toggle); right_layout.addWidget(box)
        history_row = QHBoxLayout(); history_row.addWidget(QLabel("Histórico SQL:")); history_row.addWidget(self.history_combo, 1)
        right_layout.addLayout(history_row)
        right_layout.addWidget(QLabel("Janelas SQL")); right_layout.addWidget(self.sql_tabs, 1)
        action_row = QHBoxLayout(); test_button = QPushButton("Testar conexão"); test_button.clicked.connect(self.test_selected)
        new_sql_button = QPushButton("Nova janela SQL"); new_sql_button.clicked.connect(self._new_sql_tab)
        execute_button = QPushButton("Executar SQL"); execute_button.clicked.connect(self.execute_selected)
        selection_button = QPushButton("Executar seleção"); selection_button.clicked.connect(self.execute_selection)
        self.commit_changes = QCheckBox("Confirmar alterações")
        self.commit_changes.setToolTip("Quando marcado, confirma DDL/DML. Desmarcado, alterações são desfeitas ao terminar a execução.")
        export_button = QPushButton("Exportar CSV"); export_button.clicked.connect(self.export_result_csv)
        script_button = QPushButton("Executar arquivo SQL"); script_button.clicked.connect(self.execute_script_file)
        backup_button = QPushButton("Backup"); backup_button.clicked.connect(self.execute_backup)
        restore_button = QPushButton("Restore"); restore_button.clicked.connect(self.execute_restore)
        schema_button = QPushButton("Ler estrutura"); schema_button.clicked.connect(self.inspect_schema)
        plan_button = QPushButton("Ver plano"); plan_button.clicked.connect(self.inspect_plan)
        health_button = QPushButton("Saúde"); health_button.clicked.connect(self.inspect_health)
        compare_button = QPushButton("Comparar"); compare_button.clicked.connect(self.compare_selected)
        self.open_data_action = QPushButton("Dados da tabela")
        self.open_data_action.setEnabled(False)
        self.open_data_action.clicked.connect(self.open_table_data)
        action_row.addWidget(test_button); action_row.addWidget(new_sql_button); action_row.addWidget(execute_button); action_row.addWidget(selection_button); action_row.addWidget(self.commit_changes); action_row.addWidget(export_button); action_row.addWidget(script_button); action_row.addWidget(backup_button); action_row.addWidget(restore_button); action_row.addWidget(schema_button); action_row.addWidget(plan_button); action_row.addWidget(health_button); action_row.addWidget(compare_button); action_row.addWidget(self.open_data_action); action_row.addStretch(); right_layout.addLayout(action_row)
        pagination_row = QHBoxLayout()
        self.previous_data_button = QPushButton("Anterior")
        self.previous_data_button.setEnabled(False)
        self.previous_data_button.clicked.connect(lambda: self._load_table_page(self.table_page - 1))
        self.data_page_label = QLabel("Dados: nenhuma tabela selecionada")
        self.next_data_button = QPushButton("Próximas 200")
        self.next_data_button.setEnabled(False)
        self.next_data_button.clicked.connect(lambda: self._load_table_page(self.table_page + 1))
        pagination_row.addWidget(self.previous_data_button); pagination_row.addWidget(self.data_page_label, 1); pagination_row.addWidget(self.next_data_button)
        right_layout.addWidget(self.result_table); right_layout.addLayout(pagination_row); right_layout.addWidget(self.status)
        splitter = QSplitter(Qt.Horizontal); splitter.addWidget(left); splitter.addWidget(right)
        self.main_splitter = splitter
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.setStyleSheet("QSplitter::handle:horizontal { background-color: #9aa3ad; border-left: 1px solid #606872; border-right: 1px solid #606872; }")
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.splitterMoved.connect(lambda _position, _index: self._save_splitter_state(splitter))
        self._window.setCentralWidget(splitter)
        self.profile_list.itemClicked.connect(self._on_profile_clicked)
        self.profile_list.itemDoubleClicked.connect(self._on_tree_activated)
        self.refresh_profiles()
        if self.profiles:
            self._hide_profile_details()
        else:
            self._show_profile_details()
        saved_splitter = self._settings.value("main_splitter_state")
        if saved_splitter and splitter.restoreState(saved_splitter):
            pass
        else:
            splitter.setSizes([360, 1040])

    def _save_splitter_state(self, splitter):
        self._settings.setValue("main_splitter_state", splitter.saveState())
        self._settings.sync()

    def _toggle_profile_details(self):
        visible = not self.profile_box.isVisible()
        self.profile_box.setVisible(visible)
        self.profile_toggle.setText("Ocultar dados do cadastro" if visible else "Mostrar dados do cadastro")

    def _hide_profile_details(self):
        self.profile_box.setVisible(False)
        self.profile_toggle.setText("Mostrar dados do cadastro")

    def _show_profile_details(self):
        self.profile_box.setVisible(True)
        self.profile_toggle.setText("Ocultar dados do cadastro")

    def _set_table_data_enabled(self, enabled: bool):
        self.open_data_button.setEnabled(enabled)
        if hasattr(self, "open_data_action"):
            self.open_data_action.setEnabled(enabled)
        self.previous_data_button.setEnabled(False)
        self.next_data_button.setEnabled(enabled)
        if not enabled:
            self.data_page_label.setText("Dados: nenhuma tabela selecionada")

    def _resize_sidebar(self, delta: int):
        sizes = self.main_splitter.sizes()
        if len(sizes) != 2:
            return
        sidebar = max(280, min(sizes[0] + delta, max(400, sum(sizes) - 360)))
        self.main_splitter.setSizes([sidebar, sum(sizes) - sidebar])
        self._save_splitter_state(self.main_splitter)

    def _sync_editor(self, index: int):
        self.editor = self.sql_tabs.widget(index) if index >= 0 else None

    def _new_sql_tab(self):
        from PySide6.QtWidgets import QTextEdit
        editor = QTextEdit()
        editor.setPlaceholderText("Execute uma instrução SQL...")
        index = self.sql_tabs.addTab(editor, f"SQL {self.sql_tabs.count() + 1}")
        self.sql_tabs.setCurrentIndex(index)
        self.editor = editor

    def _on_profile_clicked(self, item):
        """Select a database or preview one of its child objects."""
        index = self._profile_index_for_item(item)
        if 0 <= index < len(self.profiles):
            self.select_profile(index)
        obj = item.data(0, 32)
        if obj is not None:
            self.preview_object(item)
            return
        if 0 <= index < len(self.profiles):
            self.status.setText(f"Cadastro '{self.profiles[index].name}' selecionado. Use duplo clique para abrir.")

    def _on_profile_activated(self, item=None):
        """Open exactly the profile represented by the activated list item."""
        self._on_tree_activated(item or self.profile_list.currentItem())

    def _on_tree_activated(self, item, _column=0):
        index = self._profile_index_for_item(item)
        if 0 <= index < len(self.profiles):
            self.select_profile(index)
        obj = item.data(0, 32)
        if obj is not None:
            self.open_object(item, _column)
            return
        if index >= 0:
            self.open_profile()

    def _profile_index_for_item(self, item=None):
        item = item or self.profile_list.currentItem()
        if item is None:
            return -1
        while item.parent() is not None:
            item = item.parent()
        index = item.data(0, 33)
        return int(index) if index is not None else -1

    def _stored_password(self, profile_name: str) -> str | None:
        from .credentials import CredentialStore

        try:
            return CredentialStore().get(profile_name)
        except Exception:
            return None

    def _password_for(self, profile: ConnectionProfile | None = None) -> str:
        profile_name = profile.name if profile is not None else self.name.text()
        return self.password.text() or self._stored_password(profile_name) or ""

    def close_sql_tab(self, index: int):
        if self.sql_tabs.count() == 1:
            return
        widget = self.sql_tabs.widget(index)
        self.sql_tabs.removeTab(index)
        widget.deleteLater()

    def _add_query_history(self, sql: str):
        text = sql.strip()
        if not text:
            return
        self.query_history = [item for item in self.query_history if item != text]
        self.query_history.insert(0, text)
        self.query_history = self.query_history[:50]
        self.history_combo.blockSignals(True)
        self.history_combo.clear()
        for item in self.query_history:
            label = " ".join(item.split())
            self.history_combo.addItem(label[:120], item)
        self.history_combo.blockSignals(False)

    def _load_history_query(self, index: int):
        if index < 0:
            return
        query = self.history_combo.itemData(index)
        if query is not None and self.editor is not None:
            self.editor.setPlainText(str(query))

    def execute_selection(self):
        if self.editor is None:
            return
        selected = self.editor.textCursor().selectedText().replace("\u2029", "\n").strip()
        if not selected:
            self._show_message("Executar seleção", "Selecione uma instrução SQL no editor.", warning=True)
            return
        self._execute_sql_text(selected)

    def open_profile(self):
        """Open the selected database, like opening a connection in IBExpert."""
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

        selected = self._profile_index_for_item()
        # When activation comes from the list, use the saved object directly.
        # This avoids relying on the form repaint completing before the worker
        # starts, which was the reason the button appeared to have no effect.
        profile = self.profiles[selected] if 0 <= selected < len(self.profiles) else self._profile_from_form()
        if 0 <= selected < len(self.profiles):
            self.select_profile(selected)
        errors = profile.validate()
        if errors:
            message = " ".join(errors)
            self.status.setText(message)
            self._show_message("Não foi possível abrir o banco", message, warning=True)
            return
        password = self._password_for(profile)
        self._opening_profile_name = profile.name
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

    def _show_message(self, title: str, message: str, warning: bool = False):
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self._window)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(QMessageBox.Warning if warning else QMessageBox.Critical)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _on_profile_opened(self, result, objects, schema_error):
        if not result.ok:
            self.status.setText(result.message)
            self._show_message("Falha ao abrir banco", result.message)
            return
        selected = next((index for index, profile in enumerate(self.profiles) if profile.name == self._opening_profile_name), -1)
        if 0 <= selected < len(self.profiles):
            self.profile_objects[self.profiles[selected].name] = objects
        self._populate_object_tree(objects, selected)
        if schema_error:
            message = f"{result.message}\n\nConectado, mas não foi possível ler os objetos:\n{schema_error}"
            self.status.setText(message.replace("\n", " "))
            self._show_message("Banco conectado com aviso", message, warning=True)
        else:
            self.status.setText(f"{result.message} Objetos carregados: {len(objects)}.")
        self._hide_profile_details()

    def _populate_object_tree(self, objects, profile_index=-1):
        from PySide6.QtWidgets import QTreeWidgetItem

        self.selected_object = None
        self._set_table_data_enabled(False)
        if profile_index < 0:
            profile_index = self._profile_index_for_item()
        if 0 <= profile_index < len(self.profiles):
            self.profile_objects[self.profiles[profile_index].name] = objects
        self.refresh_profiles()
        profile_item = self._profile_item(profile_index)
        if profile_item is None:
            return
        profile_item.takeChildren()
        groups = {}
        for obj in objects:
            label = {"TABLE": "Tabelas", "VIEW": "Views", "PROCEDURE": "Procedures", "FUNCTION": "Functions", "TRIGGER": "Triggers"}.get(obj.kind, obj.kind.title())
            groups.setdefault(label, []).append(obj)
        for label in sorted(groups):
            parent = QTreeWidgetItem([f"{label} ({len(groups[label])})"])
            profile_item.addChild(parent)
            for obj in groups[label]:
                item = QTreeWidgetItem([obj.name])
                item.setData(0, 32, obj)
                parent.addChild(item)
            parent.setExpanded(True)
        profile_item.setExpanded(True)

    def _profile_item(self, index):
        if index < 0 or index >= self.profile_list.topLevelItemCount():
            return None
        return self.profile_list.topLevelItem(index)

    def _show_object_sql(self, obj, new_tab=False):
        if new_tab:
            self._new_sql_tab()
        dml = ""
        if obj.kind.upper() == "TABLE":
            dml = f'\n\n-- DML de consulta\nSELECT * FROM "{obj.name}";\n\n-- DML de inserção (modelo)\n-- INSERT INTO "{obj.name}" (...) VALUES (...);\n\n-- DML de alteração (modelo)\n-- UPDATE "{obj.name}" SET ... WHERE ...;\n'
        self.editor.setPlainText(obj.ddl + dml)
        self.sql_tabs.setTabText(self.sql_tabs.currentIndex(), obj.name)

    def preview_object(self, item, _column=0):
        """Show metadata for tables and DDL for every selected object."""
        from PySide6.QtWidgets import QTableWidgetItem

        obj = item.data(0, 32)
        if obj is None:
            self.selected_object = None
            self._set_table_data_enabled(False)
            return
        self.selected_object = obj
        self._set_table_data_enabled(obj.kind.upper() == "TABLE")
        if obj.kind.upper() == "TABLE":
            self.table_page = 0
            self.data_page_label.setText("Dados: tabela selecionada; clique em Dados da tabela")
            self.result_table.clear()
            self.result_table.setColumnCount(5)
            self.result_table.setHorizontalHeaderLabels(["Campo", "Tipo", "Tamanho", "Escala", "Aceita nulo"])
            self.result_table.setRowCount(len(obj.columns))
            for row, values in enumerate(obj.columns):
                for column, value in enumerate(values):
                    self.result_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.result_table.resizeColumnsToContents()
        else:
            self.result_table.clear()
            self.result_table.setColumnCount(2)
            self.result_table.setHorizontalHeaderLabels(["Objeto", "Tipo"])
            self.result_table.setRowCount(1)
            self.result_table.setItem(0, 0, QTableWidgetItem(obj.name))
            self.result_table.setItem(0, 1, QTableWidgetItem(obj.kind))
        self._show_object_sql(obj, new_tab=False)
        self.status.setText(f"{obj.kind.title()} selecionado: {obj.name}. DDL carregado na janela SQL.")

    def open_table_data(self):
        self._load_table_page(self.table_page)

    def _load_table_page(self, page: int):
        from .sql import execute_sql
        from PySide6.QtWidgets import QTableWidgetItem

        obj = self.selected_object
        if obj is None or obj.kind.upper() != "TABLE":
            self._show_message("Abrir dados", "Selecione uma tabela na árvore de objetos.", warning=True)
            return
        page = max(0, page)
        profile = self._profile_from_form()
        table_name = obj.name.replace('"', '""')
        start = page * 200 + 1
        end = start + 199
        self.status.setText(f"Carregando linhas {start} a {end} de {obj.name}...")
        result = execute_sql(profile, f'SELECT * FROM "{table_name}" ROWS {start} TO {end}', self._password_for(profile))
        if not result.ok:
            self.status.setText(result.message)
            self._show_message("Falha ao abrir dados", result.message)
            return
        self.result_table.clear()
        self.result_table.setColumnCount(len(result.columns))
        self.result_table.setRowCount(len(result.rows))
        self.result_table.setHorizontalHeaderLabels(result.columns)
        for row_index, row in enumerate(result.rows):
            for column_index, value in enumerate(row):
                self.result_table.setItem(row_index, column_index, QTableWidgetItem("" if value is None else str(value)))
        self.result_table.resizeColumnsToContents()
        self.table_page = page
        self.previous_data_button.setEnabled(page > 0)
        self.next_data_button.setEnabled(len(result.rows) == 200)
        self.data_page_label.setText(f"Página {page + 1} · linhas {start}-{start + max(0, len(result.rows) - 1)}")
        self.status.setText(f"Dados carregados: {len(result.rows)} linha(s).")

    def open_object(self, item, _column=0):
        obj = item.data(0, 32)
        if obj is None:
            return
        self._show_object_sql(obj, new_tab=True)
        self.status.setText(f"Nova janela SQL aberta para {obj.kind.lower()} {obj.name}.")

    def refresh_profiles(self):
        self.profile_list.clear()
        from PySide6.QtWidgets import QTreeWidgetItem
        for index, profile in enumerate(self.profiles):
            item = QTreeWidgetItem([f"{profile.name} · FB {profile.version}"])
            item.setData(0, 33, index)
            self.profile_list.addTopLevelItem(item)
            objects = self.profile_objects.get(profile.name, [])
            groups = {}
            for obj in objects:
                label = {"TABLE": "Tabelas", "VIEW": "Views", "PROCEDURE": "Procedures", "FUNCTION": "Functions", "TRIGGER": "Triggers"}.get(obj.kind, obj.kind.title())
                groups.setdefault(label, []).append(obj)
            for label in sorted(groups):
                parent = QTreeWidgetItem([f"{label} ({len(groups[label])})"])
                item.addChild(parent)
                for obj in groups[label]:
                    child = QTreeWidgetItem([obj.name])
                    child.setData(0, 32, obj)
                    parent.addChild(child)
                parent.setExpanded(True)
            item.setExpanded(bool(objects))
        self.target_profile.clear()
        self.target_profile.addItems([p.name for p in self.profiles])

    def new_profile(self):
        self._show_profile_details(); self.profile_list.clearSelection(); self.name.clear(); self.database.clear(); self.password.clear(); self.save_password.setChecked(False); self.status.setText("Novo perfil.")

    def delete_profile(self):
        selected = self._profile_index_for_item()
        if selected < 0 or selected >= len(self.profiles):
            self._show_message("Excluir cadastro", "Selecione um cadastro na lista lateral.", warning=True)
            return
        from PySide6.QtWidgets import QMessageBox

        profile = self.profiles[selected]
        confirmation = QMessageBox(self._window)
        confirmation.setWindowTitle("Confirmar exclusão do cadastro")
        confirmation.setText(f"Excluir o cadastro '{profile.name}'?")
        confirmation.setInformativeText("Somente o perfil salvo será removido. O arquivo do banco não será excluído.")
        confirmation.setIcon(QMessageBox.Warning)
        confirmation.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirmation.setDefaultButton(QMessageBox.No)
        if confirmation.exec() != QMessageBox.Yes:
            return
        self.profiles.pop(selected)
        self.store.save(self.profiles)
        from .credentials import CredentialStore
        try:
            CredentialStore().delete(profile.name)
        except Exception:
            pass
        self.profile_objects.pop(profile.name, None)
        self.refresh_profiles()
        self.name.clear(); self.database.clear(); self.password.clear(); self.save_password.setChecked(False)
        self.status.setText("Cadastro excluído. O arquivo do banco foi mantido.")

    def select_profile(self, index: int):
        if index < 0 or index >= len(self.profiles): return
        p = self.profiles[index]
        for widget, value in ((self.name, p.name), (self.host, p.host), (self.database, p.database), (self.user, p.user), (self.charset, p.charset), (self.isql_path, p.isql_path), (self.gbak_path, p.gbak_path)):
            widget.setText(value)
        stored_password = self._stored_password(p.name)
        self.password.setText(stored_password or "")
        self.save_password.setChecked(bool(stored_password))
        self.port.setValue(p.port); self.version.setCurrentText(p.version)

    def _profile_from_form(self):
        return ConnectionProfile(self.name.text(), self.host.text(), self.port.value(), self.database.text(), self.version.currentText(), self.user.text(), charset=self.charset.text(), isql_path=self.isql_path.text(), gbak_path=self.gbak_path.text())

    def save_profile(self):
        profile = self._profile_from_form(); errors = profile.validate()
        if errors:
            message = " ".join(errors)
            self.status.setText(message)
            self._show_message("Perfil inválido", message, warning=True)
            return
        selected = self._profile_index_for_item()
        duplicate = next((item for index, item in enumerate(self.profiles) if index != selected and item.name.casefold() == profile.name.casefold()), None)
        if duplicate is not None:
            message = f"Já existe um banco configurado com o nome '{duplicate.name}'. Escolha outro nome."
            self.status.setText(message)
            self._show_message("Nome duplicado", message, warning=True)
            return
        previous_name = self.profiles[selected].name if 0 <= selected < len(self.profiles) else None
        if 0 <= selected < len(self.profiles): self.profiles[selected] = profile
        else: self.profiles.append(profile)
        self.store.save(self.profiles)
        from .credentials import CredentialStore
        try:
            credentials = CredentialStore()
            if self.save_password.isChecked() and self.password.text():
                credentials.set(profile.name, self.password.text())
                message = "Perfil e senha criptografada salvos."
            else:
                credentials.delete(profile.name)
                message = "Perfil salvo sem senha."
            if previous_name and previous_name != profile.name:
                credentials.delete(previous_name)
        except Exception as exc:
            message = f"Perfil salvo, mas não foi possível proteger a senha: {exc}"
        self.refresh_profiles(); self.status.setText(message)

    def test_selected(self):
        from .connection import test_connection

        profile = self._profile_from_form()
        result = test_connection(profile, self._password_for(profile))
        self.status.setText(result.message)
        if not result.ok:
            self._show_message("Falha ao testar conexão", result.message)
            return
        if result.ok:
            try:
                from .catalog import load_schema
                objects = load_schema(profile, self._password_for(profile))
                self._populate_object_tree(objects)
                self.status.setText(f"{result.message} Objetos carregados: {len(objects)}.")
            except Exception as exc:
                message = f"{result.message}\n\nConectado, mas não foi possível ler os objetos:\n{exc}"
                self.status.setText(message.replace("\n", " "))
                self._show_message("Banco conectado com aviso", message, warning=True)
            self._hide_profile_details()

    def execute_selected(self):
        if self.editor is None:
            return
        self._execute_sql_text(self.editor.toPlainText())

    def _execute_sql_text(self, sql_text: str):
        from PySide6.QtWidgets import QTableWidgetItem
        from .sql import execute_sql

        statement = sql_text.lstrip().upper()
        changes_data = statement.startswith(("INSERT", "UPDATE", "DELETE", "MERGE", "EXECUTE", "ALTER", "CREATE", "DROP", "RECREATE", "GRANT", "REVOKE"))
        commit = bool(self.commit_changes.isChecked())
        if changes_data and commit:
            from PySide6.QtWidgets import QMessageBox
            answer = QMessageBox.question(
                self._window,
                "Confirmar alteração no banco",
                "A instrução pode alterar a estrutura ou os dados. Deseja confirmar a transação?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self.status.setText("Execução cancelada; nenhuma alteração foi aplicada.")
                return
        profile = self._profile_from_form()
        result = execute_sql(profile, sql_text, self._password_for(profile), commit=commit)
        self._add_query_history(sql_text)
        suffix = " Alterações confirmadas." if changes_data and commit and result.ok else (" Alterações desfeitas (modo seguro)." if changes_data and result.ok else "")
        self.status.setText(result.message + suffix)
        self.result_table.clear()
        self.result_table.setColumnCount(len(result.columns)); self.result_table.setRowCount(len(result.rows))
        self.result_table.setHorizontalHeaderLabels(result.columns)
        for row_index, row in enumerate(result.rows):
            for column_index, value in enumerate(row):
                self.result_table.setItem(row_index, column_index, QTableWidgetItem("" if value is None else str(value)))

    def export_result_csv(self):
        from PySide6.QtWidgets import QFileDialog
        import csv

        if self.result_table.columnCount() == 0:
            self._show_message("Exportar CSV", "Não há resultado para exportar.", warning=True)
            return
        filename, _ = QFileDialog.getSaveFileName(self._window, "Exportar resultado", "resultado.csv", "CSV (*.csv);;Todos (*.*)")
        if not filename:
            return
        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow([self.result_table.horizontalHeaderItem(column).text() if self.result_table.horizontalHeaderItem(column) else "" for column in range(self.result_table.columnCount())])
                for row in range(self.result_table.rowCount()):
                    writer.writerow([self.result_table.item(row, column).text() if self.result_table.item(row, column) else "" for column in range(self.result_table.columnCount())])
        except OSError as exc:
            self.status.setText(f"Falha ao exportar CSV: {exc}")
            self._show_message("Falha ao exportar CSV", str(exc))
            return
        self.status.setText(f"CSV exportado: {filename}")

    def execute_script_file(self):
        from .script_runner import run_script
        from PySide6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getOpenFileName(self._window, "Selecionar script SQL", "", "SQL (*.sql);;Todos (*.*)")
        if not filename:
            return
        profile = self._profile_from_form()
        if not profile.isql_path:
            self.status.setText("Configure o caminho do isql no perfil antes de executar um arquivo.")
            self._show_message("Executar script", "Configure o caminho do isql.exe no perfil antes de executar um arquivo.", warning=True)
            return
        result = run_script(profile, Path(filename), self._password_for(profile), Path(profile.isql_path))
        self.editor.setPlainText(result.output + ("\n" + result.error if result.error else ""))
        self.status.setText(("Script concluído. " if result.ok else "Script falhou. ") + result.error)

    def execute_backup(self):
        from .backup import run_gbak
        from PySide6.QtWidgets import QFileDialog

        self.status.setText("Selecionando arquivo para salvar o backup...")
        source = Path(self.database.text())
        filename, _ = QFileDialog.getSaveFileName(self._window, "Salvar backup Firebird", "", "Backup Firebird (*.fbk);;Todos (*.*)")
        if not filename:
            return
        profile = self._profile_from_form()
        result = run_gbak(profile, "backup", source, Path(filename), self._password_for(profile), Path(self.gbak_path.text()))
        self.editor.setPlainText(result.output + ("\n" + result.error if result.error else ""))
        if result.ok:
            self.status.setText("Backup concluído.")
        else:
            message = result.error or result.output or "O gbak retornou uma falha sem detalhes."
            self.status.setText(f"Backup falhou: {message}")
            self._show_message("Falha no backup", message)

    def execute_restore(self):
        from .backup import run_gbak
        from PySide6.QtWidgets import QFileDialog

        self.status.setText("Selecionando o backup para restauração...")
        source, _ = QFileDialog.getOpenFileName(self._window, "Selecionar backup Firebird", "", "Backup Firebird (*.fbk *.gbk);;Todos (*.*)")
        if not source:
            return
        target, _ = QFileDialog.getSaveFileName(self._window, "Criar banco restaurado", "", "Banco Firebird (*.fdb *.gdb);;Todos (*.*)")
        if not target:
            return
        profile = self._profile_from_form()
        result = run_gbak(profile, "restore", Path(source), Path(target), self._password_for(profile), Path(self.gbak_path.text()))
        self.editor.setPlainText(result.output + ("\n" + result.error if result.error else ""))
        if result.ok:
            self.status.setText("Restore concluído.")
        else:
            message = result.error or result.output or "O gbak retornou uma falha sem detalhes."
            self.status.setText(f"Restore falhou: {message}")
            self._show_message("Falha no restore", message)

    def inspect_schema(self):
        from .catalog import load_schema
        try:
            profile = self._profile_from_form()
            objects = load_schema(profile, self._password_for(profile))
        except Exception as exc:
            self.status.setText(f"Falha ao ler estrutura: {exc}")
            self._show_message("Falha ao ler estrutura", str(exc))
            return
        self.editor.setPlainText("\n".join(f"{obj.kind}: {obj.name}\n{obj.ddl}" for obj in objects))
        self._populate_object_tree(objects)
        self.status.setText(f"Estrutura lida: {len(objects)} objeto(s).")

    def inspect_plan(self):
        from .plan import explain_query

        profile = self._profile_from_form()
        if not profile.isql_path:
            self.status.setText("Configure o caminho do isql no perfil antes de analisar o plano.")
            self._show_message("Ver plano", "Configure o caminho do isql.exe no perfil antes de analisar o plano.", warning=True)
            return
        result = explain_query(profile, self.editor.toPlainText(), self._password_for(profile), Path(profile.isql_path))
        if not result.ok:
            self.status.setText(result.error)
            self._show_message("Falha ao obter plano", result.error)
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
        from .health import inspect_health

        try:
            profile = self._profile_from_form()
            report = inspect_health(profile, self._password_for(profile))
        except Exception as exc:
            self.status.setText(f"Falha ao ler saúde: {exc}")
            self._show_message("Falha ao analisar saúde", str(exc))
            return
        lines = ["INDICADORES", ""] + [f"{key}: {value}" for key, value in report.metrics.items()]
        lines.extend(["", "RECOMENDAÇÕES", ""])
        for finding in report.findings:
            lines.extend([f"[{finding.severity.upper()}] {finding.title}", f"Evidência: {finding.evidence}", f"Ação sugerida: {finding.recommendation}", ""])
        self.editor.setPlainText("\n".join(lines))
        self.status.setText(f"Saúde analisada: {len(report.findings)} recomendação(ões).")

    def compare_selected(self):
        from .catalog import load_schema
        from .schema import compare_schema, generate_migration

        target_name = self.target_profile.currentText()
        source = self._profile_from_form()
        target = next((profile for profile in self.profiles if profile.name == target_name), None)
        if target is None or target.name == source.name:
            self.status.setText("Cadastre e selecione um perfil de destino diferente da origem.")
            return
        try:
            password = self._password_for(source)
            target_password = self._stored_password(target.name) or password
            source_objects = load_schema(source, password)
            target_objects = load_schema(target, target_password)
            changes = compare_schema(source_objects, target_objects)
        except Exception as exc:
            self.status.setText(f"Falha ao comparar estruturas: {exc}")
            self._show_message("Falha ao comparar estruturas", str(exc))
            return
        lines = [f"ORIGEM: {source.name}", f"DESTINO: {target.name}", "", f"Diferenças: {len(changes)}", ""]
        for change in changes:
            marker = "REVISAR" if change.destructive else change.action
            lines.append(f"[{marker}] {change.object.kind} {change.object.name}")
        lines.extend(["", "PRÉVIA DE MIGRAÇÃO", "", generate_migration(changes)])
        self.editor.setPlainText("\n".join(lines))
        self.status.setText(f"Comparação concluída: {len(changes)} diferença(s). Nenhuma alteração foi aplicada.")
