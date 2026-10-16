from __future__ import annotations

from pathlib import Path
import time
import traceback

from .models import ConnectionProfile, ProfileStore, SUPPORTED_VERSIONS
from . import __version__


def create_application():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    import sys

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Firebird Maintenance Studio")
    asset_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    icon_path = asset_root / "assets" / "firebird-maintenance-studio.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyleSheet("QToolButton, QPushButton { padding: 5px 9px; } QTabBar::tab { padding: 6px 12px; } QHeaderView::section { padding: 5px; font-weight: 600; }")
    return app


try:
    from PySide6.QtCore import QObject, Signal, Slot
    from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

    class SqlHighlighter(QSyntaxHighlighter):
        """Lightweight SQL highlighting that works offline in the packaged app."""

        def __init__(self, document):
            super().__init__(document)
            self._keyword_format = QTextCharFormat()
            self._keyword_format.setForeground(QColor("#005cc5"))
            self._keyword_format.setFontWeight(QFont.Bold)
            self._type_format = QTextCharFormat()
            self._type_format.setForeground(QColor("#7b3f00"))
            self._string_format = QTextCharFormat()
            self._string_format.setForeground(QColor("#008000"))
            self._comment_format = QTextCharFormat()
            self._comment_format.setForeground(QColor("#6a737d"))
            self._number_format = QTextCharFormat()
            self._number_format.setForeground(QColor("#8b008b"))
            from .sql_completion import FIREBIRD_RESERVED_WORDS, FIREBIRD_TYPES
            self._keywords = FIREBIRD_RESERVED_WORDS
            self._types = FIREBIRD_TYPES

        def set_theme(self, dark: bool):
            """Use readable syntax colors in both the light and dark themes."""
            colors = {
                "keyword": "#7db7ff" if dark else "#005cc5",
                "type": "#f2b880" if dark else "#7b3f00",
                "string": "#98d89c" if dark else "#008000",
                "comment": "#9aa4b2" if dark else "#6a737d",
                "number": "#d9a1ff" if dark else "#8b008b",
            }
            self._keyword_format.setForeground(QColor(colors["keyword"]))
            self._type_format.setForeground(QColor(colors["type"]))
            self._string_format.setForeground(QColor(colors["string"]))
            self._comment_format.setForeground(QColor(colors["comment"]))
            self._number_format.setForeground(QColor(colors["number"]))
            self.rehighlight()

        def highlightBlock(self, text):
            import re

            protected: list[tuple[int, int]] = []
            for match in re.finditer(r"--[^\n]*|/\*.*?\*/", text):
                self.setFormat(match.start(), match.end() - match.start(), self._comment_format)
                protected.append((match.start(), match.end()))
            for match in re.finditer(r"'(?:''|[^'])*'", text):
                self.setFormat(match.start(), match.end() - match.start(), self._string_format)
                protected.append((match.start(), match.end()))

            def is_protected(start: int, end: int) -> bool:
                return any(start < protected_end and end > protected_start for protected_start, protected_end in protected)

            for match in re.finditer(r"\b\d+(?:\.\d+)?\b", text):
                if is_protected(match.start(), match.end()):
                    continue
                self.setFormat(match.start(), match.end() - match.start(), self._number_format)
            for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", text):
                if is_protected(match.start(), match.end()):
                    continue
                word = match.group(0).upper()
                if word in self._keywords:
                    self.setFormat(match.start(), match.end() - match.start(), self._keyword_format)
                elif word in self._types:
                    self.setFormat(match.start(), match.end() - match.start(), self._type_format)

    from .workers import OperationWorker, OpenConnectionWorker
except ImportError:  # pragma: no cover - allows headless model tests
    SqlHighlighter = None
    OpenConnectionWorker = None
    OperationWorker = None


class MainWindow:
    """Initial shell; keeps Qt imports out of headless validation."""

    def __init__(self, store: ProfileStore):
        from PySide6.QtWidgets import (
            QApplication,
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
            QProgressBar,
            QFileDialog,
            QTabWidget,
            QTreeWidget,
            QTreeWidgetItem,
            QSizePolicy,
            QAbstractItemView,
            QToolButton,
            QMenu,
            QFrame,
        )
        from PySide6.QtCore import QObject, QThread, Signal, Slot, QSettings, Qt, QTimer, QSize
        from PySide6.QtGui import QAction, QKeySequence, QShortcut

        self._window = QMainWindow()
        self.show = self._window.show
        self._window.setWindowTitle("Firebird Maintenance Studio")
        self._window.resize(1100, 700)
        self.store = store
        self._event_log_path = Path.home() / ".firebird-maintenance-studio" / "events.txt"
        self._log_event("Aplicação iniciada", executable=str(Path(__file__).resolve()))
        self._settings = QSettings("TGBalbino", "FirebirdMaintenanceStudio")
        saved_geometry = self._settings.value("window_geometry")
        if saved_geometry:
            self._window.restoreGeometry(saved_geometry)
        self._apply_theme(str(self._settings.value("theme", "light")))
        self.backup_history = self._restore_backup_history()
        self._open_thread = None
        self._open_worker = None
        self._open_timeout_timer = None
        self._opening_profile_name = None
        self._operation_thread = None
        self._operation_worker = None
        self._operation_name = ""
        self._operation_started_at = 0.0
        self.connected_profiles = set()
        self._last_tree_activation_key = None
        self._last_tree_activation_time = 0.0
        self.selected_object = None
        self.edit_data_mode = False
        self._table_original_rows = []
        self.table_page = 0
        self.profiles = store.load()
        self._log_event("Perfis carregados", profile_store=str(store.path), count=len(self.profiles))
        self.profile_objects = {}
        self.profile_list = QTreeWidget()
        self.profile_list.setHeaderLabels(["Bancos e objetos"])
        self.profile_list.setHeaderHidden(True)
        self.profile_list.setMinimumHeight(120)
        self.profile_list.setColumnCount(1)
        self.profile_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.profile_list.setIconSize(QSize(16, 16))
        self.profile_list.setIndentation(20)
        self.profile_list.setUniformRowHeights(True)
        self.profile_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.profile_list.customContextMenuRequested.connect(self._tree_context_menu)
        self.profile_list.itemExpanded.connect(lambda item: self._save_tree_expansion(item, True))
        self.profile_list.itemCollapsed.connect(lambda item: self._save_tree_expansion(item, False))
        self.tree_filter = QLineEdit()
        self.tree_filter.setPlaceholderText("Filtrar bancos e objetos...")
        self.tree_filter.textChanged.connect(self._filter_tree)
        # A stale filter can make a restored profile look missing.  Start a
        # session with the complete catalog; the user can filter again as
        # needed without losing any saved profile.
        self.tree_filter.setText("")
        self._settings.setValue("tree_filter", "")
        self.tree_filter.textChanged.connect(lambda value: self._settings.setValue("tree_filter", value))
        self.tree_connected_only = QCheckBox("Conectados")
        self.tree_connected_only.setToolTip("Mostrar somente bancos conectados")
        # Connections are not restored between application sessions, so a
        # persisted "connected only" flag would hide every profile at start.
        self.tree_connected_only.setChecked(False)
        self._settings.setValue("tree_connected_only", False)
        self.tree_connected_only.toggled.connect(self._tree_connected_filter_changed)
        self.name = QLineEdit()
        self.favorite = QCheckBox("Favorito")
        self.host = QLineEdit("localhost")
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(3050)
        self.database = QLineEdit()
        self.version = QComboBox(); self.version.addItems(SUPPORTED_VERSIONS)
        self.target_profile = QComboBox()
        self.user = QLineEdit("SYSDBA")
        self.role = QLineEdit()
        self.role.setPlaceholderText("Opcional, por exemplo RDB$ADMIN")
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
        self.status.setObjectName("workspaceStatusMessage")
        self.object_tree = self.profile_list
        self.object_tree.setMinimumWidth(240)
        self.object_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        from .sql_documents import SqlDocumentManager
        from .mdi import SqlMdiArea
        self.sql_tabs = SqlMdiArea(); self.sql_tabs.setMinimumHeight(320); self.sql_tabs.setTabsClosable(True); self.sql_tabs.tabCloseRequested.connect(self.close_sql_tab)
        self._mdi_next_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self._window)
        self._mdi_next_shortcut.activated.connect(self.sql_tabs.activate_next)
        self._mdi_previous_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self._window)
        self._mdi_previous_shortcut.activated.connect(self.sql_tabs.activate_previous)
        self.sql_documents = SqlDocumentManager(self.sql_tabs)
        self.sql_tabs.currentChanged.connect(self._sync_editor)
        # These controls belong to each SQL MDI form.  The active form is
        # exposed through the aliases below so existing actions keep using
        # the selected document without duplicating connection information.
        self._query_profile_combos = []
        self._history_combos = []
        self.query_profile_combo = None
        self.query_connection_status = None
        self.connection_badge = None
        self.query_cursor_status = None
        self.object_breadcrumb = None
        self.workspace_status = None
        self.workspace_connection = None
        self.query_history = []
        self._transaction_session = None
        self._transaction_profile_name = ""
        self.last_compare_report = ""
        self.last_health_report = ""
        self.history_combo = None
        self._restore_query_history()
        self.editor = None
        self._new_sql_tab()
        self.structure_table = QTableWidget(); self.structure_table.setMinimumHeight(180); self.structure_table.setEditTriggers(QTableWidget.NoEditTriggers); self.structure_table.setAlternatingRowColors(True); self.structure_table.setShowGrid(False)
        self.structure_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.structure_table.setSortingEnabled(True)
        self.index_table = QTableWidget(); self.index_table.setEditTriggers(QTableWidget.NoEditTriggers); self.index_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.index_table.setAlternatingRowColors(True); self.index_table.setShowGrid(False); self.index_table.setSortingEnabled(True)
        self.constraint_table = QTableWidget(); self.constraint_table.setEditTriggers(QTableWidget.NoEditTriggers); self.constraint_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.constraint_table.setAlternatingRowColors(True); self.constraint_table.setShowGrid(False); self.constraint_table.setSortingEnabled(True)
        from .diagnostic_views import create_plan_panel
        plan_panel, self.plan_tree, self.plan_output = create_plan_panel()
        self.plan_panel = plan_panel
        from .activity_views import create_activity_panel
        (
            activity_panel,
            self.activity_metrics,
            self.activity_table,
            self.activity_refresh_button,
            self.activity_export_button,
            self.activity_open_sql_button,
            self.activity_filter,
            self.activity_auto_refresh,
        ) = create_activity_panel(self.inspect_activity, self.export_activity_csv, self.open_activity_sql, self._filter_activity_rows, self._toggle_activity_auto_refresh, self._open_activity_sql_at)
        self.activity_refresh_timer = QTimer(self._window); self.activity_refresh_timer.setInterval(5000); self.activity_refresh_timer.timeout.connect(self.inspect_activity)
        self.activity_panel = activity_panel
        from .activity_views import create_sessions_panel
        sessions_panel, self.sessions_table, self.sessions_filter, self.disconnect_session_button = create_sessions_panel(self._filter_session_rows, self.terminate_selected_session)
        self.sessions_panel = sessions_panel
        self.backup_history_table = QTableWidget(); self.backup_history_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.backup_history_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.backup_history_table.setAlternatingRowColors(True); self.backup_history_table.setShowGrid(False); self.backup_history_table.setSortingEnabled(True)
        backup_history_panel = QWidget(); backup_history_layout = QVBoxLayout(backup_history_panel); backup_history_layout.addWidget(QLabel("Histórico local de backup e restore")); backup_history_layout.addWidget(self.backup_history_table, 1)
        self.backup_history_panel = backup_history_panel
        self.compare_changes = []
        self.compare_filter = QLineEdit(); self.compare_filter.setPlaceholderText("Filtrar tipo ou nome..."); self.compare_filter.textChanged.connect(self._filter_compare_rows)
        self.compare_action_filter = QComboBox(); self.compare_action_filter.addItems(["Todas as ações", "ADD", "ALTER", "REMOVE"]); self.compare_action_filter.currentTextChanged.connect(self._filter_compare_rows)
        self.compare_table = QTableWidget(); self.compare_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.compare_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.compare_table.setAlternatingRowColors(True); self.compare_table.setShowGrid(False); self.compare_table.setSortingEnabled(True)
        compare_controls = QHBoxLayout(); compare_controls.addWidget(self.compare_filter, 1); compare_controls.addWidget(self.compare_action_filter)
        compare_panel = QWidget(); compare_layout = QVBoxLayout(compare_panel); compare_layout.addLayout(compare_controls); compare_layout.addWidget(self.compare_table, 1)
        self.compare_panel = compare_panel
        self.result_tabs = QTabWidget(); self.result_tabs.setDocumentMode(True); self.result_tabs.setUsesScrollButtons(True); self.result_tabs.addTab(self.structure_table, "Estrutura"); self.result_tabs.addTab(self.index_table, "Índices"); self.result_tabs.addTab(self.constraint_table, "Restrições"); self.result_tabs.addTab(plan_panel, "Plano e sugestões"); self.result_tabs.addTab(activity_panel, "Banco e atividade"); self.result_tabs.addTab(sessions_panel, "Sessões"); self.result_tabs.addTab(backup_history_panel, "Histórico de backup"); self.result_tabs.addTab(compare_panel, "Comparação")
        self.result_mdi_window = self.sql_tabs.add_panel(self.result_tabs, "Resultados e diagnóstico", width=860, height=330)
        self.result_tabs.currentChanged.connect(lambda _index: self._show_result_window())
        self.sql_tabs.setCurrentIndex(0)

        left = QWidget(); left_layout = QVBoxLayout(left); left.setMinimumWidth(280); left.setObjectName("sidebarPanel"); left.setProperty("panelRole", "sidebar")
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        sidebar_title = QLabel("BANCOS E OBJETOS")
        sidebar_title.setObjectName("sectionTitle")
        self.sidebar_status = QLabel("Nenhum banco conectado")
        self.sidebar_status.setObjectName("sidebarStatus")
        tree_filter_row = QHBoxLayout(); tree_filter_row.setSpacing(6); tree_filter_row.addWidget(self.tree_filter, 1); tree_filter_row.addWidget(self.tree_connected_only)
        left_layout.addWidget(sidebar_title); left_layout.addWidget(self.sidebar_status); left_layout.addLayout(tree_filter_row); left_layout.addWidget(self.profile_list, 1)
        self.open_data_button = QPushButton("Abrir dados da tabela")
        self.open_data_button.setEnabled(False)
        self.open_data_button.clicked.connect(self.open_table_data)
        left_layout.addWidget(self.open_data_button)
        profile_button = QToolButton(); profile_button.setText("Perfil"); profile_button.setObjectName("profileMenuButton"); profile_button.setToolTip("Criar, salvar, abrir ou excluir o cadastro selecionado")
        profile_button.setPopupMode(QToolButton.InstantPopup)
        profile_menu = QMenu(profile_button)
        for label, callback in (("Novo perfil", self.new_profile), ("Salvar perfil", self.save_profile), ("Abrir banco", self.open_profile), ("Desconectar banco", self.disconnect_selected), ("Excluir cadastro", self.delete_profile)):
            profile_action = profile_menu.addAction(label)
            profile_action.triggered.connect(callback)
        profile_button.setMenu(profile_menu)
        left_layout.addWidget(profile_button)
        left_layout.addStretch()

        form = QFormLayout(); form.addRow("Nome", self.name); form.addRow("", self.favorite); form.addRow("Host", self.host)
        form.addRow("Porta", self.port); form.addRow("Caminho ou alias", self.database)
        form.addRow("Firebird", self.version); form.addRow("Usuário", self.user); form.addRow("Role", self.role); form.addRow("Senha", password_row); form.addRow("Charset", self.charset); form.addRow("Caminho isql", self.isql_path); form.addRow("Caminho gbak", self.gbak_path); form.addRow("Comparar com", self.target_profile)
        box = QGroupBox("Perfil selecionado"); box.setLayout(form)
        self.profile_box = box
        self.profile_toggle = QPushButton("Ocultar dados do cadastro")
        self.profile_toggle.clicked.connect(self._toggle_profile_details)
        self.profile_test_button = QPushButton("Testar conexão")
        self.profile_test_button.clicked.connect(self.test_selected)
        # Profile data is edited from the database tree context menu.  Keep
        # the fields alive for validation and credential handling, but do not
        # place the old profile form in the main workspace.
        self.profile_toggle.setVisible(False)
        self.profile_test_button.setVisible(False)
        self.profile_box.setVisible(False)
        self.profile_log_button = QPushButton("Abrir log")
        self.profile_log_button.clicked.connect(self.open_event_log)
        self.theme_button = QToolButton(); self.theme_button.setText("Tema"); self.theme_button.setToolTip("Escolher tema claro ou escuro")
        self.theme_button.setPopupMode(QToolButton.InstantPopup)
        theme_menu = QMenu(self.theme_button)
        light_action = theme_menu.addAction("Tema claro"); light_action.triggered.connect(lambda: self._set_theme("light"))
        dark_action = theme_menu.addAction("Tema escuro"); dark_action.triggered.connect(lambda: self._set_theme("dark"))
        self.theme_button.setMenu(theme_menu)
        # Application-level preferences live in the main menu to keep the
        # workspace toolbar focused on database work.
        self.profile_log_button.setVisible(False)
        self.theme_button.setVisible(False)
        right = QWidget(); right.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding); right.setObjectName("workspacePanel")
        profile_actions = QHBoxLayout(); profile_actions.addWidget(self.profile_toggle); profile_actions.addWidget(self.profile_test_button); profile_actions.addWidget(self.profile_log_button); profile_actions.addWidget(self.theme_button)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        self.welcome_banner = QFrame()
        self.welcome_banner.setObjectName("welcomeBanner")
        welcome_layout = QVBoxLayout(self.welcome_banner)
        welcome_heading = QHBoxLayout()
        welcome_icon = QLabel()
        welcome_icon.setPixmap(QApplication.instance().windowIcon().pixmap(40, 40))
        welcome_icon.setFixedSize(40, 40)
        welcome_title = QLabel("Comece por aqui")
        welcome_title.setObjectName("welcomeTitle")
        welcome_heading.addWidget(welcome_icon)
        welcome_heading.addWidget(welcome_title)
        welcome_heading.addStretch()
        welcome_text = QLabel("Cadastre um banco Firebird para conectar, abrir objetos e iniciar consultas SQL.")
        welcome_text.setWordWrap(True)
        welcome_actions = QHBoxLayout()
        welcome_profile = QPushButton("Criar primeiro perfil")
        welcome_profile.setObjectName("primaryAction")
        welcome_profile.clicked.connect(self.new_profile)
        welcome_sql = QPushButton("Nova janela SQL")
        welcome_sql.setObjectName("secondaryAction")
        welcome_sql.clicked.connect(self._new_sql_tab)
        welcome_log = QPushButton("Abrir log")
        welcome_log.setObjectName("secondaryAction")
        welcome_log.clicked.connect(self.open_event_log)
        welcome_actions.addWidget(welcome_profile); welcome_actions.addWidget(welcome_sql); welcome_actions.addWidget(welcome_log); welcome_actions.addStretch()
        welcome_layout.addLayout(welcome_heading); welcome_layout.addWidget(welcome_text); welcome_layout.addLayout(welcome_actions)
        right_layout.addWidget(self.welcome_banner)
        right_layout.addWidget(self.sql_tabs, 1)
        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.setContentsMargins(0, 2, 0, 0)
        def menu_button(label, entries, tooltip):
            button = QToolButton()
            button.setText(label)
            button.setObjectName("workspaceAction")
            button.setMinimumHeight(30)
            button.setToolTip(tooltip)
            button.setPopupMode(QToolButton.InstantPopup)
            menu = QMenu(button)
            menu.setMinimumWidth(300)
            for text, callback in entries:
                action = menu.addAction(text)
                action.triggered.connect(callback)
            button.setMenu(menu)
            return button

        self.open_data_action = QAction("Dados da tabela", self._window)
        self.open_data_action.setEnabled(False)
        self.open_data_action.triggered.connect(self.open_table_data)
        self.edit_data_action = QAction("Ativar edição segura (prévia)", self._window)
        self.edit_data_action.setCheckable(True)
        self.edit_data_action.setEnabled(False)
        self.edit_data_action.setToolTip("Permite editar a grade localmente. Nenhuma alteração é gravada automaticamente.")
        self.edit_data_action.toggled.connect(self._toggle_data_edit_mode)
        self.generate_update_action = QAction("Gerar UPDATE da linha", self._window)
        self.generate_update_action.setEnabled(False)
        self.generate_update_action.setToolTip("Gera uma prévia SQL usando os valores originais da linha.")
        self.generate_update_action.triggered.connect(self._generate_row_update_preview)
        self.add_data_row_action = QAction("Adicionar linha local", self._window)
        self.add_data_row_action.setEnabled(False)
        self.add_data_row_action.setToolTip("Cria uma linha vazia somente na grade para preparar um INSERT.")
        self.add_data_row_action.triggered.connect(self._add_local_data_row)
        self.generate_insert_action = QAction("Gerar INSERT da linha", self._window)
        self.generate_insert_action.setEnabled(False)
        self.generate_insert_action.triggered.connect(self._generate_insert_preview)
        self.generate_delete_action = QAction("Gerar DELETE da linha", self._window)
        self.generate_delete_action.setEnabled(False)
        self.generate_delete_action.triggered.connect(self._generate_delete_preview)
        self.apply_update_action = QAction("Aplicar UPDATE com confirmação", self._window)
        self.apply_update_action.setEnabled(False)
        self.apply_update_action.setToolTip("Executa somente o UPDATE que está no editor após confirmação explícita.")
        self.apply_update_action.triggered.connect(self._apply_update_preview)
        self.begin_transaction_action = QAction("Iniciar transação", self._window)
        self.begin_transaction_action.triggered.connect(self._start_transaction)
        self.commit_transaction_action = QAction("Commit", self._window)
        self.commit_transaction_action.setEnabled(False)
        self.commit_transaction_action.triggered.connect(self._commit_transaction)
        self.rollback_transaction_action = QAction("Rollback", self._window)
        self.rollback_transaction_action.setEnabled(False)
        self.rollback_transaction_action.triggered.connect(self._rollback_transaction)
        data_button = menu_button("Dados", [("Exportar CSV", self.export_result_csv), ("Exportar JSON", self.export_result_json)], "Exportar resultados e abrir dados de tabelas")
        data_button.menu().addAction(self.open_data_action)
        data_button.menu().addAction(self.edit_data_action)
        data_button.menu().addAction(self.add_data_row_action)
        data_button.menu().addAction(self.generate_update_action)
        data_button.menu().addAction(self.generate_insert_action)
        data_button.menu().addAction(self.generate_delete_action)
        data_button.menu().addAction(self.apply_update_action)
        database_button = menu_button("Banco", [("Backup", self.execute_backup), ("Restore", self.execute_restore), ("Exportar banco para SQL", self.export_database_sql), ("Histórico de backup/restore", self.show_backup_history)], "Operações de backup, restore e exportação SQL")
        security_button = menu_button("Segurança", [("Gestão de usuários", self.manage_users)], "Criar usuários e alterar senhas do Firebird")
        analysis_button = menu_button("Análise", [("Ler estrutura", self.inspect_schema), ("Ver plano", self.inspect_plan), ("Saúde", self.inspect_health), ("Banco e atividade", self.inspect_activity), ("Salvar relatório de saúde", self.save_health_report), ("Salvar saúde em HTML", self.save_health_html), ("Criar pacote de suporte", self.create_support_package), ("Sessões", self.inspect_sessions), ("Validar integridade", self.validate_database), ("Comparar estruturas", self.compare_selected), ("Salvar comparação", self.save_compare_report), ("Salvar comparação em HTML", self.save_compare_html)], "Estrutura, plano, saúde, atividade e comparação")
        action_row.addWidget(data_button)
        action_row.addWidget(database_button)
        action_separator = QFrame()
        action_separator.setObjectName("actionGroupSeparator")
        action_separator.setFrameShape(QFrame.VLine)
        action_separator.setFrameShadow(QFrame.Plain)
        action_row.addWidget(action_separator)
        action_row.addWidget(security_button)
        action_row.addWidget(analysis_button)
        action_row.addStretch()
        right_layout.addLayout(action_row)
        pagination_row = QHBoxLayout()
        self.previous_data_button = QPushButton("Anterior")
        self.previous_data_button.setObjectName("paginationButton")
        self.previous_data_button.setToolTip("Voltar para a página anterior da tabela")
        self.previous_data_button.setEnabled(False)
        self.previous_data_button.clicked.connect(lambda: self._load_table_page(self.table_page - 1))
        self.data_page_label = QLabel("Dados: nenhuma tabela selecionada")
        self.result_summary = QLabel("Resultado: nenhum")
        self.result_summary.setObjectName("resultSummary")
        self.result_summary.setToolTip("Resumo da última execução exibida na grade")
        self.data_filter = QLineEdit()
        self.data_filter.setPlaceholderText("Filtrar linhas...")
        self.data_filter.setToolTip("Filtra as linhas carregadas nesta página; não altera o banco.")
        self.data_filter.textChanged.connect(self._filter_data_rows)
        self.data_page_size = QComboBox()
        self.data_page_size.addItems(["50", "200", "500", "1000"])
        saved_page_size = str(self._settings.value("data_page_size", "200"))
        page_size_index = self.data_page_size.findText(saved_page_size)
        self.data_page_size.setCurrentIndex(page_size_index if page_size_index >= 0 else 1)
        self.data_page_size.setToolTip("Quantidade de linhas carregadas por página")
        self.data_page_size.currentTextChanged.connect(self._page_size_changed)
        self.next_data_button = QPushButton()
        self.next_data_button.setObjectName("paginationButton")
        self.next_data_button.setToolTip("Carregar a próxima página da tabela")
        self._update_pagination_labels()
        self.next_data_button.setEnabled(False)
        self.next_data_button.clicked.connect(lambda: self._load_table_page(self.table_page + 1))
        pagination_row.addWidget(self.previous_data_button); pagination_row.addWidget(self.data_page_label, 1); pagination_row.addWidget(self.result_summary); pagination_row.addWidget(QLabel("Linhas:")); pagination_row.addWidget(self.data_page_size); pagination_row.addWidget(self.data_filter); pagination_row.addWidget(self.next_data_button)
        right_layout.addLayout(pagination_row)
        self.operation_progress = QProgressBar()
        self.operation_progress.setObjectName("operationProgress")
        self.operation_progress.setRange(0, 0)
        self.operation_progress.setTextVisible(False)
        self.operation_progress.setFixedHeight(8)
        self.operation_progress.setVisible(False)
        right_layout.addWidget(self.operation_progress)
        right_layout.addWidget(self.status)
        splitter = QSplitter(Qt.Horizontal); splitter.addWidget(left); splitter.addWidget(right); splitter.setObjectName("mainSplitter")
        self.main_splitter = splitter
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)
        splitter.setStyleSheet("QSplitter#mainSplitter::handle:horizontal { border-left: 1px solid transparent; border-right: 1px solid transparent; }")
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.splitterMoved.connect(lambda _position, _index: self._save_splitter_state(splitter))
        self._window.setCentralWidget(splitter)
        self._setup_main_menu()
        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.aboutToQuit.connect(self._close_transaction)
            app_instance.aboutToQuit.connect(self._save_window_geometry)
        self.profile_list.itemClicked.connect(self._on_profile_clicked)
        # Use Qt's actual double-click signal. Inferring a double click from
        # itemPressed/itemClicked makes a fast single click open object data.
        self.profile_list.itemDoubleClicked.connect(self._on_tree_double_clicked)
        self.refresh_profiles()
        self.welcome_banner.setVisible(not bool(self.profiles))
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

    def _save_window_geometry(self):
        if hasattr(self, "_window") and self._window.isVisible():
            self._settings.setValue("window_geometry", self._window.saveGeometry())
            self._settings.sync()

    def _apply_theme(self, theme: str):
        from .ui_theme import apply_theme
        apply_theme(theme)

    def _set_theme(self, theme: str):
        self._settings.setValue("theme", theme)
        self._settings.sync()
        self._apply_theme(theme)
        for index in range(self.sql_tabs.count()):
            highlighter = self.sql_tabs.widget(index).property("sql_highlighter")
            if highlighter is not None and hasattr(highlighter, "set_theme"):
                highlighter.set_theme(theme == "dark")
        self.status.setText("Tema escuro aplicado." if theme == "dark" else "Tema claro aplicado.")

    def _setup_main_menu(self):
        """Create the compact application menu for global commands."""
        menu_bar = self._window.menuBar()
        # Keep the top level labels readable when the window is restored to a
        # smaller size.  The previous compact padding made adjacent labels
        # look joined together and could clip the last menu name.
        menu_bar.setMinimumHeight(32)
        menu_bar.setObjectName("mainMenuBar")
        menu_bar.setStyleSheet(
            "QMenuBar { spacing: 2px; }"
            " QMenuBar::item { padding: 6px 12px; margin: 0 1px; }"
            " QMenu { padding: 4px 0; }"
            " QMenu::item { padding: 6px 28px 6px 12px; }"
        )
        app_menu = menu_bar.addMenu("Aplicação")
        settings_action = app_menu.addAction("Configurações...")
        settings_action.setShortcut("Ctrl+," )
        settings_action.triggered.connect(self.show_app_settings)
        app_menu.addSeparator()
        self.menu_always_top_action = app_menu.addAction("Sempre no topo")
        self.menu_always_top_action.setCheckable(True)
        self.menu_always_top_action.setChecked(bool(self._settings.value("always_on_top", False, type=bool)))
        self.menu_always_top_action.toggled.connect(self._set_always_on_top)
        app_menu.addAction("Abrir log de eventos", self.open_event_log)
        app_menu.addSeparator()
        app_menu.addAction("Sair", self._window.close)

        sql_menu = menu_bar.addMenu("SQL")
        sql_menu.addAction("Nova janela SQL", self._new_sql_tab)
        sql_menu.addAction("Executar SQL", self.execute_selected)
        sql_menu.addAction("Executar seleção", self.execute_selection)
        sql_menu.addAction("Ver plano", self.inspect_plan)
        sql_menu.addAction("Histórico SQL", self._choose_history_query)
        sql_menu.addSeparator()
        sql_menu.addAction(self.begin_transaction_action)
        sql_menu.addAction(self.commit_transaction_action)
        sql_menu.addAction(self.rollback_transaction_action)

        window_menu = menu_bar.addMenu("Janelas")
        window_menu.addAction("Selecionar consulta aberta", self._choose_sql_window)
        window_menu.addAction("Mostrar resultados e diagnóstico", self._show_result_window)
        window_menu.addAction("Próxima consulta", self.sql_tabs.activate_next)
        window_menu.addAction("Consulta anterior", self.sql_tabs.activate_previous)
        window_menu.addAction("Fechar consulta atual", lambda: self.close_sql_tab(self.sql_tabs.currentIndex()))
        window_menu.addAction("Fechar todas as consultas", self._close_all_sql_tabs)
        window_menu.addSeparator()
        window_menu.addAction("Organizar em cascata", self.sql_tabs.cascade_windows)
        window_menu.addAction("Organizar lado a lado", self.sql_tabs.tile_windows)
        window_menu.addAction("Maximizar/restaurar consulta atual", self.sql_tabs.toggle_maximize_current)
        window_menu.addAction("Restaurar consultas", self.sql_tabs.restore_windows)
        window_menu.addSeparator()
        window_menu.addAction(self.menu_always_top_action)

        database_menu = menu_bar.addMenu("Banco")
        database_menu.addAction("Novo perfil", self.new_profile)
        database_menu.addAction("Salvar perfil", self.save_profile)
        database_menu.addAction("Abrir banco", self.open_profile)
        database_menu.addAction("Desconectar banco", self.disconnect_selected)
        database_menu.addSeparator()
        database_menu.addAction("Backup", self.execute_backup)
        database_menu.addAction("Restore", self.execute_restore)

        help_menu = menu_bar.addMenu("Ajuda")
        help_menu.addAction("Sobre", self.show_about)
        help_menu.addAction("Verificar atualizações...", self.check_for_updates)
        for menu in (app_menu, sql_menu, window_menu, database_menu, help_menu):
            menu.setMinimumWidth(240)

    def _choose_history_query(self):
        if self.history_combo.count() == 0:
            self._show_message("Histórico SQL", "Ainda não há consultas no histórico.", warning=True)
            return
        self.history_combo.showPopup()

    def show_app_settings(self):
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QCheckBox, QVBoxLayout

        dialog = QDialog(self._window)
        dialog.setWindowTitle("Configurações da aplicação")
        dialog.resize(460, 230)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Preferências do Studio aplicadas ao usuário atual."))
        form = QFormLayout()
        theme = QComboBox(); theme.addItem("Claro", "light"); theme.addItem("Escuro", "dark")
        theme.setCurrentIndex(1 if self._settings.value("theme", "light") == "dark" else 0)
        page_size = QComboBox(); page_size.addItems(["50", "200", "500", "1000"])
        page_size.setCurrentText(str(self._settings.value("data_page_size", "200")))
        always_top = QCheckBox("Manter a janela sempre no topo")
        always_top.setChecked(bool(self._settings.value("always_on_top", False, type=bool)))
        form.addRow("Tema", theme); form.addRow("Linhas por página", page_size); form.addRow("Janela", always_top)
        layout.addLayout(form)
        layout.addWidget(QLabel("As preferências de tamanho, posição, árvore e filtro são salvas automaticamente."))
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject); buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        theme.currentIndexChanged.connect(lambda index: self._set_theme(theme.itemData(index)))
        page_size.currentTextChanged.connect(self._page_size_changed)
        always_top.toggled.connect(self._set_always_on_top)
        dialog.exec()

    def show_about(self):
        from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QPushButton
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QDesktopServices

        dialog = QDialog(self._window)
        dialog.setWindowTitle("Sobre o Firebird Maintenance Studio")
        dialog.resize(560, 330)
        layout = QVBoxLayout(dialog)
        header = QFrame()
        header.setObjectName("appHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QApplication.instance().windowIcon().pixmap(52, 52))
        icon_label.setFixedSize(52, 52)
        header_row.addWidget(icon_label)
        title_column = QVBoxLayout()
        title = QLabel("Firebird Maintenance Studio")
        title.setObjectName("appTitle")
        subtitle = QLabel("Workspace de manutenção · SQL, dados, diagnóstico e operações")
        subtitle.setObjectName("appSubtitle")
        title_column.addWidget(title); title_column.addWidget(subtitle)
        header_row.addLayout(title_column, 1)
        header_layout.addLayout(header_row)
        description = QLabel(
            "Ferramenta open source para manutenção de bancos Firebird 2.5, 3, 4 e 5.<br>"
            "Editor SQL, múltiplos bancos, catálogo de objetos, plano, saúde, sessões, backup, restore e comparação."
        )
        description.setWordWrap(True)
        import sys
        from datetime import datetime
        build_path = Path(sys.executable if getattr(sys, "frozen", False) else __file__)
        build_date = datetime.fromtimestamp(build_path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        details = QLabel(f"Versão: {__version__}<br>Compilado em: {build_date}<br>Tecnologias: Python + PySide6<br>Distribuição: Windows x64<br>Licença: MIT")
        details.setTextFormat(Qt.RichText)
        link = QPushButton("Abrir projeto no GitHub")
        link.setObjectName("aboutLink")
        link.setToolTip("Abrir github.com/tgbalbino/firebird-maintenance-studio no navegador")
        link.setCursor(Qt.PointingHandCursor)
        link.setFlat(True)
        link.setStyleSheet("text-align: left; padding: 3px 0;")
        link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/tgbalbino/firebird-maintenance-studio")))
        layout.addWidget(header); layout.addWidget(description); layout.addWidget(details); layout.addWidget(link)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        dialog.exec()

    def check_for_updates(self):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        import json
        import re
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError, URLError

        current = __version__
        repository_url = "https://github.com/tgbalbino/firebird-maintenance-studio"
        api_url = "https://api.github.com/repos/tgbalbino/firebird-maintenance-studio/releases/latest"
        tags_url = "https://api.github.com/repos/tgbalbino/firebird-maintenance-studio/tags?per_page=10"

        def load_json(url):
            request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "FirebirdMaintenanceStudio"})
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))

        def version_key(value):
            match = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(value or ""))
            if not match:
                raise ValueError(f"Versão inválida: {value}")
            return tuple(int(part or 0) for part in match.groups())

        try:
            source = "release"
            try:
                payload = load_json(api_url)
            except HTTPError as release_error:
                if release_error.code != 404:
                    raise
                # A public repository can exist before its first Release is
                # published.  Tags are still a useful update source.
                tags = load_json(tags_url)
                if not isinstance(tags, list) or not tags:
                    self._log_event("Nenhuma versão publicada no GitHub", repository=repository_url)
                    self._show_message("Atualizações", f"O GitHub ainda não publicou uma versão para atualização.\n\nVersão instalada: {current}\n\nPublique uma Release ou uma tag no projeto para disponibilizar atualizações.")
                    return
                payload = tags[0]
                source = "tag"
            tag = str(payload.get("tag_name", "")).strip()
            if not tag:
                tag = str(payload.get("name", "")).strip()
            latest = tag[1:] if tag.lower().startswith("v") else tag
            release_url = str(payload.get("html_url", f"{repository_url}/releases"))
            if not latest:
                raise ValueError("A release não informou uma versão.")
            current_key = version_key(current)
            latest_key = version_key(latest)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, HTTPError, URLError) as exc:
            self._log_event("Falha ao verificar atualização", error=str(exc))
            self._show_message("Atualizações", f"Não foi possível consultar o GitHub.\n\nVersão instalada: {current}\n\n{exc}", warning=True)
            return
        if latest_key <= current_key:
            self._show_message("Atualizações", f"Você já está usando a versão mais recente ({current}).")
            return
        source_label = "Release" if source == "release" else "tag"
        answer = QMessageBox.question(self._window, "Atualização disponível", f"Versão instalada: {current}\nNova versão: {latest} ({source_label})\n\nAbrir a página de download?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(release_url))

    def _set_always_on_top(self, enabled: bool):
        from PySide6.QtCore import Qt

        self._settings.setValue("always_on_top", bool(enabled))
        self._settings.sync()
        menu_action = getattr(self, "menu_always_top_action", None)
        if menu_action is not None and menu_action.isChecked() != bool(enabled):
            menu_action.blockSignals(True)
            menu_action.setChecked(bool(enabled))
            menu_action.blockSignals(False)
        was_visible = self._window.isVisible()
        self._window.setWindowFlag(Qt.WindowStaysOnTopHint, bool(enabled))
        if was_visible:
            self._window.show()
        self.status.setText("Janela configurada para ficar sempre no topo." if enabled else "Modo sempre no topo desativado.")

    def _log_event(self, message: str, **details):
        """Append a diagnostic event without passwords or SQL contents."""
        from .ui_logging import log_event
        log_event(self._event_log_path, message, **details)

    def open_event_log(self):
        from .ui_logging import open_log
        try:
            open_log(self._event_log_path)
        except OSError as exc:
            self._log_event("Falha ao abrir log", error=str(exc))
            self.status.setText(f"Log: {self._event_log_path}")

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

    def _show_profile_dialog(self, index: int | None = None):
        """Create or edit a profile in a modal configuration window."""
        if index is not None and (index < 0 or index >= len(self.profiles)):
            return
        from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout

        profile = self.profiles[index] if index is not None else ConnectionProfile(name="", version="5")
        dialog = QDialog(self._window)
        dialog.setWindowTitle(f"{'Novo perfil' if index is None else 'Dados do cadastro — ' + profile.name}")
        dialog.setModal(True)
        dialog.resize(560, 520)
        form = QFormLayout()

        name = QLineEdit(profile.name)
        host = QLineEdit(profile.host)
        port = QSpinBox(); port.setRange(1, 65535); port.setValue(profile.port)
        database = QLineEdit(profile.database)
        version = QComboBox(); version.addItems(SUPPORTED_VERSIONS); version.setCurrentText(profile.version)
        user = QLineEdit(profile.user)
        role = QLineEdit(profile.role)
        password = QLineEdit(self._stored_password(profile.name) or ""); password.setEchoMode(QLineEdit.Password)
        save_password = QCheckBox("Salvar senha criptografada no Windows")
        save_password.setChecked(bool(password.text()))
        charset = QLineEdit(profile.charset)
        isql_path = QLineEdit(profile.isql_path)
        gbak_path = QLineEdit(profile.gbak_path)
        favorite = QCheckBox("Favorito"); favorite.setChecked(profile.favorite)
        for label, widget in (("Nome", name), ("Host", host), ("Porta", port), ("Caminho ou alias", database), ("Firebird", version), ("Usuário", user), ("Role", role), ("Senha", password), ("Charset", charset), ("Caminho isql", isql_path), ("Caminho gbak", gbak_path)):
            form.addRow(label, widget)
        form.addRow("", save_password)
        form.addRow("", favorite)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        test_button = QPushButton("Testar conexão")
        buttons.addButton(test_button, QDialogButtonBox.ActionRole)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        output = QPlainTextEdit(); output.setReadOnly(True); output.setPlaceholderText("O resultado do teste aparecerá aqui.")

        def test_dialog_connection():
            from .connection import test_connection
            candidate = ConnectionProfile(
                name=name.text(), host=host.text(), port=port.value(), database=database.text(),
                version=version.currentText(), user=user.text(), role=role.text(), charset=charset.text(),
                favorite=favorite.isChecked(), isql_path=isql_path.text(), gbak_path=gbak_path.text(),
            )
            result = test_connection(candidate, password.text())
            output.setPlainText(result.message + (f"\nVersão detectada: {result.server_version}" if result.server_version else ""))

        test_button.clicked.connect(test_dialog_connection)
        layout = QVBoxLayout(dialog); layout.addLayout(form); layout.addWidget(output, 1); layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        # Feed the existing validation and credential handling path so the
        # modal and the normal profile workflow behave identically.
        if index is None:
            self.profile_list.clearSelection()
            self.profile_list.setCurrentItem(None)
        else:
            self.profile_list.setCurrentItem(self.profile_list.topLevelItem(index))
        for widget, value in ((self.name, name.text()), (self.host, host.text()), (self.database, database.text()), (self.user, user.text()), (self.role, role.text()), (self.charset, charset.text()), (self.isql_path, isql_path.text()), (self.gbak_path, gbak_path.text())):
            widget.setText(value)
        self.port.setValue(port.value()); self.version.setCurrentText(version.currentText()); self.password.setText(password.text()); self.save_password.setChecked(save_password.isChecked()); self.favorite.setChecked(favorite.isChecked())
        self.save_profile()

    def _set_table_data_enabled(self, enabled: bool):
        self.open_data_button.setEnabled(enabled)
        if hasattr(self, "open_data_action"):
            self.open_data_action.setEnabled(enabled)
        if hasattr(self, "edit_data_action"):
            self.edit_data_action.setEnabled(enabled)
            if not enabled and self.edit_data_action.isChecked():
                self.edit_data_action.setChecked(False)
        if hasattr(self, "generate_update_action"):
            self.generate_update_action.setEnabled(enabled)
        for action_name in ("add_data_row_action", "generate_insert_action", "generate_delete_action"):
            action = getattr(self, action_name, None)
            if action is not None:
                action.setEnabled(enabled)
        if hasattr(self, "apply_update_action") and not enabled:
            self.apply_update_action.setEnabled(False)
        self.previous_data_button.setEnabled(False)
        self.next_data_button.setEnabled(enabled)
        if not enabled:
            self._table_original_rows = []
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
        if self.editor is not None:
            self._set_active_editor_widgets(self.editor)
            self.result_table = self.editor.property("result_table") or self.result_table
            self._table_original_rows = []
            self._refresh_sql_completer(self.editor)
            self._update_cursor_status(self.editor)
            self._set_transaction_controls_enabled()
            self._update_sql_tab_title(index)
            if hasattr(self, "object_breadcrumb") and self.selected_object is None:
                self.object_breadcrumb.setText("Banco > consulta SQL")
            self.query_profile_combo.blockSignals(True)
            profile_name = self.editor.property("query_profile") or ""
            combo_index = self.query_profile_combo.findText(profile_name)
            self.query_profile_combo.setCurrentIndex(combo_index if combo_index >= 0 else -1)
            self.query_profile_combo.blockSignals(False)
            self._update_query_connection_status()
            if self.workspace_status is not None:
                self.workspace_status.setText("Ctrl+Tab alterna as janelas")
        elif self.workspace_status is not None:
            self.workspace_status.setText("Resultados e diagnóstico · use o menu Janelas para voltar ao SQL")

    def _show_result_window(self):
        """Bring the shared result/diagnostic form back to the front."""
        if self.result_mdi_window is None:
            return
        self.result_mdi_window.showNormal()
        self.result_mdi_window.show()
        self.result_mdi_window.raise_()

    def _show_sql_result(self):
        if self.editor is None:
            return
        document_tabs = self.editor.property("document_tabs")
        result_table = self.editor.property("result_table")
        if document_tabs is not None and result_table is not None:
            document_tabs.setCurrentWidget(result_table)

    def _set_current_query_profile(self, profile_name: str, editor=None):
        target = editor or self.editor
        if target is not None and profile_name:
            target.setProperty("query_profile", profile_name)
            index = self.sql_tabs.indexOf(target)
            if index >= 0:
                self._update_sql_tab_title(index)
        self._update_query_connection_status()

    def _update_query_connection_status(self):
        profile_name = self.editor.property("query_profile") if self.editor is not None else ""
        transaction_open = self._transaction_session is not None and self._transaction_session.active
        if self.query_connection_status is None:
            return
        self.query_connection_status.setText("Transação aberta" if transaction_open else "")
        self.query_connection_status.setVisible(transaction_open)
        connected = bool(profile_name and profile_name in self.connected_profiles)
        self.connection_badge.setText("● Conectado" if connected else "● Desconectado")
        self.connection_badge.setProperty("connectionState", "connected" if connected else "disconnected")
        self.connection_badge.style().unpolish(self.connection_badge)
        self.connection_badge.style().polish(self.connection_badge)

    def _query_profile(self):
        name = self.editor.property("query_profile") if self.editor is not None else ""
        return next((profile for profile in self.profiles if profile.name == name), self._profile_from_form())

    def _configure_sql_editor(self, editor):
        from PySide6.QtWidgets import QCompleter
        from PySide6.QtCore import QStringListModel, Qt
        from PySide6.QtGui import QKeySequence, QShortcut
        editor.setFont(QFont("Consolas", 10))
        editor.setPlaceholderText("Execute uma instrução SQL...")
        highlighter = SqlHighlighter(editor.document())
        highlighter.set_theme(str(self._settings.value("theme", "light")) == "dark")
        editor.setProperty("sql_highlighter", highlighter)
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), editor)
        shortcut.activated.connect(self.execute_selected)
        editor.setProperty("execute_shortcut", shortcut)
        f5_shortcut = QShortcut(QKeySequence("F5"), editor)
        f5_shortcut.activated.connect(lambda target=editor: (self.sql_tabs.setCurrentWidget(target), self._execute_sql_text(target.toPlainText())))
        editor.setProperty("execute_f5_shortcut", f5_shortcut)
        selection_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F5"), editor)
        selection_shortcut.activated.connect(lambda target=editor: (self.sql_tabs.setCurrentWidget(target), self.execute_selection()))
        editor.setProperty("execute_selection_shortcut", selection_shortcut)
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), editor)
        save_shortcut.activated.connect(lambda target=editor: (self.sql_tabs.setCurrentWidget(target), self.save_sql_file()))
        editor.setProperty("save_shortcut", save_shortcut)
        close_shortcut = QShortcut(QKeySequence("Ctrl+W"), editor)
        close_shortcut.activated.connect(lambda target=editor: self.close_sql_tab(self.sql_tabs.indexOf(target)))
        editor.setProperty("close_shortcut", close_shortcut)
        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), editor)
        find_shortcut.activated.connect(self.find_in_sql)
        editor.setProperty("find_shortcut", find_shortcut)
        replace_shortcut = QShortcut(QKeySequence("Ctrl+H"), editor)
        replace_shortcut.activated.connect(self.replace_in_sql)
        editor.setProperty("replace_shortcut", replace_shortcut)
        completion_model = QStringListModel(editor)
        completer = QCompleter(completion_model, editor)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setWidget(editor)
        completer.activated.connect(lambda text, target=editor: self._insert_completion(target, text))
        editor.textChanged.connect(lambda target=editor: self._auto_complete_sql(target))
        completion_shortcut = QShortcut(QKeySequence("Ctrl+Space"), editor)
        completion_shortcut.activated.connect(lambda target=editor: self._show_sql_completions(target))
        editor.setProperty("completion_model", completion_model)
        editor.setProperty("completion", completer)
        editor.setProperty("completion_shortcut", completion_shortcut)

    def _create_sql_document_tabs(self, editor):
        from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QTableWidget, QTabWidget, QVBoxLayout, QWidget
        from PySide6.QtCore import Qt
        from .result_views import configure_result_table
        result_table = configure_result_table(QTableWidget())
        result_table.setContextMenuPolicy(Qt.CustomContextMenu)
        result_table.customContextMenuRequested.connect(self._table_context_menu)
        result_header = result_table.horizontalHeader()
        result_header.setContextMenuPolicy(Qt.CustomContextMenu)
        result_header.customContextMenuRequested.connect(
            lambda position, table=result_table: self._result_header_context_menu(table, position)
        )
        document_tabs = QTabWidget()
        document_tabs.setDocumentMode(True)
        document_tabs.setUsesScrollButtons(True)
        document_tabs.addTab(editor, "SQL")
        document_tabs.addTab(result_table, "Resultado")
        document_tabs.setCurrentWidget(editor)
        document_tabs.setProperty("sql_editor", editor)
        editor.setProperty("document_tabs", document_tabs)
        editor.setProperty("result_table", result_table)

        # Per-document context stays inside the MDI child so multiple SQL
        # windows never appear to share one connection or cursor status.
        profile_combo = QComboBox()
        profile_combo.setMinimumWidth(220)
        profile_combo.setPlaceholderText("Selecionar banco")
        profile_combo.addItems([profile.name for profile in self.profiles])
        profile_combo.setProperty("sql_editor", editor)
        profile_combo.currentTextChanged.connect(lambda name, target=editor: self._set_current_query_profile(name, target))
        connection_status = QLabel()
        connection_status.setObjectName("connectionStatus")
        connection_status.setVisible(False)
        connection_badge = QLabel("● Desconectado")
        connection_badge.setObjectName("connectionBadge")
        connection_badge.setToolTip("Estado da conexão do banco desta consulta")
        cursor_status = QLabel("Linha 1, coluna 1")
        cursor_status.setObjectName("cursorStatus")
        history_combo = QComboBox()
        history_combo.setMinimumWidth(260)
        history_combo.setPlaceholderText("Histórico SQL")
        for query in self.query_history:
            history_combo.addItem(" ".join(query.split())[:120], query)
        history_combo.activated.connect(lambda index, combo=history_combo, target=editor: self._load_history_query(index, combo, target))
        breadcrumb = QLabel("Banco > consulta SQL")
        breadcrumb.setObjectName("objectBreadcrumb")
        breadcrumb.setToolTip("Caminho do objeto selecionado")
        workspace_status = QLabel("Ctrl+Tab alterna as janelas")
        workspace_status.setObjectName("workspaceStatus")
        context_row = QHBoxLayout()
        context_row.setSpacing(8)
        context_row.addWidget(QLabel("Área de trabalho"))
        context_row.addWidget(breadcrumb)
        context_row.addWidget(workspace_status, 1)
        connection_row = QHBoxLayout()
        connection_row.setSpacing(8)
        connection_row.addWidget(QLabel("Banco"))
        connection_row.addWidget(profile_combo)
        connection_row.addWidget(connection_status)
        connection_row.addWidget(connection_badge)
        history_row = QHBoxLayout()
        history_row.setSpacing(8)
        history_row.addWidget(QLabel("Histórico SQL"))
        history_row.addWidget(history_combo, 1)
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.addLayout(history_row)
        shell_layout.addLayout(connection_row)
        shell_layout.addLayout(context_row)
        shell_layout.addWidget(document_tabs, 1)
        editor_footer = QHBoxLayout()
        editor_footer.addStretch()
        editor_footer.addWidget(cursor_status)
        shell_layout.addLayout(editor_footer)
        shell.setProperty("sql_editor", editor)
        editor.setProperty("profile_combo", profile_combo)
        editor.setProperty("connection_status", connection_status)
        editor.setProperty("connection_badge", connection_badge)
        editor.setProperty("cursor_status", cursor_status)
        editor.setProperty("history_combo", history_combo)
        editor.setProperty("object_breadcrumb", breadcrumb)
        editor.setProperty("workspace_status", workspace_status)
        self._query_profile_combos.append(profile_combo)
        self._history_combos.append(history_combo)
        self._set_active_editor_widgets(editor)
        return shell, result_table

    def _set_active_editor_widgets(self, editor):
        """Point compatibility aliases at the currently active SQL form."""
        if editor is None:
            return
        self.query_profile_combo = editor.property("profile_combo")
        self.query_connection_status = editor.property("connection_status")
        self.connection_badge = editor.property("connection_badge")
        self.query_cursor_status = editor.property("cursor_status")
        self.history_combo = editor.property("history_combo")
        self.object_breadcrumb = editor.property("object_breadcrumb")
        self.workspace_status = editor.property("workspace_status")
        self.workspace_connection = None
        execution_controls = editor.property("execution_controls") or ()
        self.commit_changes = execution_controls[0] if len(execution_controls) > 0 else None
        self.read_only_mode = execution_controls[1] if len(execution_controls) > 1 else None

    def _create_sql_toolbar(self, editor):
        from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QPushButton, QToolButton, QWidget, QMenu
        sql_toolbar = QWidget()
        toolbar_layout = QHBoxLayout(sql_toolbar)
        toolbar_layout.setContentsMargins(4, 4, 4, 4)
        toolbar_layout.setSpacing(6)
        execute_button = QPushButton("Executar SQL")
        execute_button.setObjectName("primaryAction")
        execute_button.setToolTip("Executar o SQL desta janela (F5 ou Ctrl+Return)")
        execute_button.clicked.connect(lambda: self._execute_sql_text(editor.toPlainText()))
        result_button = QPushButton("Resultado")
        result_button.setObjectName("secondaryAction")
        result_button.setToolTip("Mostrar o resultado desta consulta")
        result_button.clicked.connect(lambda: (self.sql_tabs.setCurrentWidget(editor), self._show_sql_result()))
        more_button = QToolButton()
        more_button.setText("Mais")
        more_button.setObjectName("workspaceAction")
        more_button.setToolTip("Ações adicionais desta consulta")
        more_button.setPopupMode(QToolButton.InstantPopup)
        more_menu = QMenu(more_button)
        selection_action = more_menu.addAction("Executar seleção")
        selection_action.setShortcut("Ctrl+Shift+F5")
        selection_action.triggered.connect(lambda: (self.sql_tabs.setCurrentWidget(editor), self.execute_selection()))
        plan_action = more_menu.addAction("Ver plano")
        plan_action.triggered.connect(lambda: (self.sql_tabs.setCurrentWidget(editor), self.inspect_plan()))
        save_action = more_menu.addAction("Salvar SQL")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(lambda: (self.sql_tabs.setCurrentWidget(editor), self.save_sql_file()))
        more_menu.addSeparator()
        commit_action = more_menu.addAction("Commit")
        commit_action.triggered.connect(lambda: (self.sql_tabs.setCurrentWidget(editor), self._commit_transaction()))
        rollback_action = more_menu.addAction("Rollback")
        rollback_action.triggered.connect(lambda: (self.sql_tabs.setCurrentWidget(editor), self._rollback_transaction()))
        more_button.setMenu(more_menu)
        commit_changes = QCheckBox("Confirmar alterações")
        commit_changes.setObjectName("toolbarOption")
        commit_changes.setToolTip("Quando marcado, confirma DDL/DML. Desmarcado, alterações são desfeitas ao terminar a execução.")
        read_only_mode = QCheckBox("Somente leitura")
        read_only_mode.setObjectName("toolbarOption")
        read_only_mode.setToolTip("Bloqueia DML, DDL, EXECUTE, GRANT e REVOKE nesta sessão SQL.")
        for button in (execute_button, result_button, more_button):
            toolbar_layout.addWidget(button)
        separator = QFrame()
        separator.setObjectName("toolbarSeparator")
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Plain)
        toolbar_layout.addWidget(separator)
        toolbar_layout.addWidget(commit_changes)
        toolbar_layout.addWidget(read_only_mode)
        toolbar_layout.addStretch()
        return sql_toolbar, (commit_action, rollback_action), (commit_changes, read_only_mode)

    def _new_sql_tab(self):
        from PySide6.QtWidgets import QTextEdit
        selected_name = self.query_profile_combo.currentText() if self.query_profile_combo is not None else (self.profiles[0].name if self.profiles else "")
        editor = QTextEdit()
        self._configure_sql_editor(editor)
        document_tabs, result_table = self._create_sql_document_tabs(editor)
        editor.setProperty("query_profile", selected_name)
        self.query_profile_combo.setCurrentText(selected_name)
        editor.setProperty("document_title", f"SQL {self.sql_tabs.count() + 1}")
        index = self.sql_documents.add(document_tabs, f"SQL {self.sql_tabs.count() + 1}", editor.property("query_profile") or "")
        sql_toolbar, transaction_controls, execution_controls = self._create_sql_toolbar(editor)
        self.sql_tabs.add_toolbar(index, sql_toolbar)
        editor.setProperty("sql_toolbar_controls", transaction_controls)
        editor.setProperty("execution_controls", execution_controls)
        self.editor = editor
        self._set_active_editor_widgets(editor)
        self.result_table = result_table
        self._table_original_rows = []
        self._set_transaction_controls_enabled()
        editor.cursorPositionChanged.connect(lambda target=editor: self._update_cursor_status(target))
        self._update_cursor_status(editor)
        self._refresh_sql_completer(editor)
        self._update_sql_tab_title(index)

    def _update_sql_tab_title(self, index=None):
        index = self.sql_tabs.currentIndex() if index is None else index
        self.sql_documents.update_title(index)

    def _close_all_sql_tabs(self):
        self.sql_documents.close_all(self._new_sql_tab)
        self.status.setText("Todas as consultas foram fechadas; uma nova consulta vazia foi criada.")

    def _choose_sql_window(self):
        from PySide6.QtWidgets import QInputDialog

        if self.sql_tabs.count() == 0:
            return
        titles = self.sql_documents.titles()
        selected, accepted = QInputDialog.getItem(self._window, "Janelas SQL", "Selecionar consulta:", titles, self.sql_tabs.currentIndex(), False)
        if accepted:
            self.sql_tabs.setCurrentIndex(titles.index(selected))

    def _update_cursor_status(self, editor=None):
        target = editor or self.editor
        if target is None or not hasattr(self, "query_cursor_status"):
            return
        cursor = target.textCursor()
        self.query_cursor_status.setText(f"Linha {cursor.blockNumber() + 1}, coluna {cursor.positionInBlock() + 1}")

    def _completion_words(self):
        from .sql_completion import completion_words
        return completion_words(self.profile_objects)

    def _refresh_sql_completer(self, editor=None):
        target = editor or self.editor
        if target is None:
            return
        model = target.property("completion_model")
        if model is not None:
            model.setStringList(self._completion_words())

    def _show_sql_completions(self, editor):
        from PySide6.QtGui import QTextCursor
        completer = editor.property("completion")
        if completer is None:
            return
        cursor = editor.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        completer.setCompletionPrefix(cursor.selectedText())
        rectangle = editor.cursorRect()
        rectangle.setWidth(completer.popup().sizeHintForColumn(0) + completer.popup().verticalScrollBar().sizeHint().width())
        completer.complete(rectangle)

    def _auto_complete_sql(self, editor):
        """Offer completion while typing, without interrupting short words."""
        from PySide6.QtGui import QTextCursor
        cursor = editor.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        prefix = cursor.selectedText()
        if len(prefix) < 2 or not prefix.replace("_", "A").replace("$", "A").isalnum():
            return
        completer = editor.property("completion")
        if completer is None:
            return
        completer.setCompletionPrefix(prefix)
        if not completer.completionCount():
            return
        rectangle = editor.cursorRect()
        rectangle.setWidth(completer.popup().sizeHintForColumn(0) + completer.popup().verticalScrollBar().sizeHint().width())
        completer.complete(rectangle)

    def _insert_completion(self, editor, text):
        from PySide6.QtGui import QTextCursor
        cursor = editor.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        cursor.insertText(text)
        editor.setTextCursor(cursor)

    def _on_profile_clicked(self, item):
        """Select a database/object; loading happens only on double click."""
        index = self._profile_index_for_item(item)
        obj = item.data(0, 32)
        is_object_item = item.parent() is not None
        self._log_event("Item da árvore clicado", index=index, item=item.text(0), object=getattr(obj, "name", ""), object_item=is_object_item, object_type=type(obj).__name__)
        typed_password = self.password.text()
        if 0 <= index < len(self.profiles):
            self.select_profile(index)
            # Selecting the tree item must not erase a password just entered
            # in the profile form before starting the connection.
            if typed_password and not self.password.text():
                self.password.setText(typed_password)
        if is_object_item and obj is not None:
            self.selected_object = obj
            self._set_object_breadcrumb(obj)
            self._set_table_data_enabled(str(getattr(obj, "kind", "")).upper() == "TABLE")
            self.status.setText(
                f"{obj.kind.title()} selecionado: {obj.name}. Duplo clique para carregar DDL e dados."
            )
            return
        if 0 <= index < len(self.profiles):
            self.status.setText(f"Perfil '{self.profiles[index].name}' selecionado. Duplo clique para conectar.")
            if hasattr(self, "object_breadcrumb"):
                self.object_breadcrumb.setText(f"{self.profiles[index].name} > banco")

    def _set_object_breadcrumb(self, obj):
        profile = self._query_profile() if hasattr(self, "_query_profile") else None
        profile_name = profile.name if profile is not None else self.name.text().strip()
        profile_name = profile_name or "Banco"
        kind = str(getattr(obj, "kind", "Objeto")).title()
        name = str(getattr(obj, "name", ""))
        group = "Tabelas" if kind.upper() == "TABLE" else f"{kind}s"
        if hasattr(self, "object_breadcrumb"):
            self.object_breadcrumb.setText(f"{profile_name} > {group} > {name}")

    def _on_tree_double_clicked(self, item, _column=0):
        """Open a profile or object only after Qt confirms a double click."""
        index = self._profile_index_for_item(item)
        obj = item.data(0, 32)
        is_object_item = item.parent() is not None
        item_key = (index, getattr(obj, "kind", ""), getattr(obj, "name", "")) if obj is not None else (index, "PROFILE")
        now = time.monotonic()
        if item_key == self._last_tree_activation_key and now - self._last_tree_activation_time < 0.4:
            return
        self._last_tree_activation_key = item_key
        self._last_tree_activation_time = now
        if 0 <= index < len(self.profiles):
            self.select_profile(index)
        if is_object_item and obj is not None:
            self.preview_object(item, _column, load_data=True)
            return
        if index >= 0:
            self.open_profile(index)

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
        self.sql_documents.close(index, self._new_sql_tab)

    def _add_query_history(self, sql: str):
        text = sql.strip()
        if not text:
            return
        self.query_history = [item for item in self.query_history if item != text]
        self.query_history.insert(0, text)
        self.query_history = self.query_history[:50]
        self._refresh_query_history()

    def _restore_query_history(self):
        import json

        raw = self._settings.value("query_history", "")
        try:
            values = json.loads(str(raw)) if raw else []
            self.query_history = [str(item).strip() for item in values if str(item).strip()][:50] if isinstance(values, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            self.query_history = []
        self._refresh_query_history()

    def _refresh_query_history(self):
        import json

        for combo in self._history_combos:
            combo.blockSignals(True)
            combo.clear()
            for item in self.query_history:
                label = " ".join(item.split())
                combo.addItem(label[:120], item)
            combo.blockSignals(False)
        self._settings.setValue("query_history", json.dumps(self.query_history, ensure_ascii=False))
        self._settings.sync()

    def _restore_backup_history(self):
        import json

        raw = self._settings.value("backup_history", "")
        try:
            values = json.loads(str(raw)) if raw else []
            return [item for item in values if isinstance(item, dict)][:100] if isinstance(values, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    def _record_backup_history(self, operation: str, profile: ConnectionProfile, source: str, target: str, ok: bool, detail: str = ""):
        import json
        from datetime import datetime

        self.backup_history.insert(0, {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operation": operation,
            "profile": profile.name,
            "source": source,
            "target": target,
            "result": "OK" if ok else "FALHA",
            "detail": detail,
        })
        self.backup_history = self.backup_history[:100]
        self._settings.setValue("backup_history", json.dumps(self.backup_history, ensure_ascii=False))
        self._settings.sync()

    def show_backup_history(self):
        from PySide6.QtWidgets import QTableWidgetItem

        headers = ["Data", "Operação", "Perfil", "Origem", "Destino", "Resultado", "Detalhe"]
        self.backup_history_table.setSortingEnabled(False)
        self.backup_history_table.clear()
        self.backup_history_table.setColumnCount(len(headers)); self.backup_history_table.setRowCount(len(self.backup_history)); self.backup_history_table.setHorizontalHeaderLabels(headers)
        for row, entry in enumerate(self.backup_history):
            values = [entry.get(key, "") for key in ("date", "operation", "profile", "source", "target", "result", "detail")]
            for column, value in enumerate(values):
                self.backup_history_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.backup_history_table.resizeColumnsToContents()
        self.backup_history_table.setSortingEnabled(True)
        self.result_tabs.setCurrentWidget(self.backup_history_panel)
        self.status.setText(f"Histórico carregado: {len(self.backup_history)} operação(ões).")

    def _load_history_query(self, index: int, combo=None, editor=None):
        if index < 0:
            return
        combo = combo or self.history_combo
        editor = editor or self.editor
        query = combo.itemData(index) if combo is not None else None
        if query is not None and editor is not None:
            editor.setPlainText(str(query))

    def find_in_sql(self):
        from PySide6.QtWidgets import QInputDialog

        if self.editor is None:
            return
        text, accepted = QInputDialog.getText(self._window, "Localizar no SQL", "Texto:", text=getattr(self, "_find_text", ""))
        if not accepted or not text:
            return
        self._find_text = text
        if not self.editor.find(text):
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.Start)
            self.editor.setTextCursor(cursor)
            if self.editor.find(text):
                self.status.setText(f"Texto localizado: {text}")
            else:
                self.status.setText(f"Texto não encontrado: {text}")
        else:
            self.status.setText(f"Texto localizado: {text}")

    def replace_in_sql(self):
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        if self.editor is None:
            return
        old_text, accepted = QInputDialog.getText(self._window, "Substituir no SQL", "Localizar:", text=getattr(self, "_find_text", ""))
        if not accepted or not old_text:
            return
        new_text, accepted = QInputDialog.getText(self._window, "Substituir no SQL", "Substituir por:")
        if not accepted:
            return
        source = self.editor.toPlainText()
        count = source.count(old_text)
        if count == 0:
            self.status.setText(f"Texto não encontrado: {old_text}")
            return
        answer = QMessageBox.question(
            self._window,
            "Confirmar substituição",
            f"Substituir {count} ocorrência(s) no editor SQL?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.editor.setPlainText(source.replace(old_text, new_text))
        self._find_text = new_text
        self.status.setText(f"{count} ocorrência(s) substituída(s) no editor.")

    def execute_selection(self):
        if self.editor is None:
            return
        selected = self.editor.textCursor().selectedText().replace("\u2029", "\n").strip()
        if not selected:
            self._show_message("Executar seleção", "Selecione uma instrução SQL no editor.", warning=True)
            return
        self._execute_sql_text(selected)

    def _set_transaction_actions(self, active: bool):
        if hasattr(self, "begin_transaction_action"):
            self.begin_transaction_action.setEnabled(not active)
            self.commit_transaction_action.setEnabled(active)
            self.rollback_transaction_action.setEnabled(active)
        self._set_transaction_controls_enabled(active)

    def _set_transaction_controls_enabled(self, active=None):
        if active is None:
            active = bool(self._transaction_session is not None and self._transaction_session.active)
        if self.editor is None:
            return
        controls = self.editor.property("sql_toolbar_controls") or ()
        if len(controls) == 2:
            controls[0].setEnabled(active)
            controls[1].setEnabled(active)

    def _start_transaction(self):
        from .transaction import TransactionSession

        if self._transaction_session is not None and self._transaction_session.active:
            self.status.setText("Já existe uma transação aberta.")
            return
        profile = self._query_profile()
        errors = profile.validate()
        if errors:
            self._show_message("Iniciar transação", " ".join(errors), warning=True)
            return
        try:
            self._transaction_session = TransactionSession(profile, self._password_for(profile))
            self._transaction_profile_name = profile.name
            self._set_transaction_actions(True)
            self._update_query_connection_status()
            self.status.setText(f"Transação iniciada para '{profile.name}'. Execute comandos e escolha Commit ou Rollback.")
            self._log_event("Transação iniciada", profile=profile.name)
        except Exception as exc:
            self._transaction_session = None
            self._transaction_profile_name = ""
            self._set_transaction_actions(False)
            self._log_event("Falha ao iniciar transação", profile=profile.name, detail=str(exc))
            self._show_message("Falha ao iniciar transação", str(exc), warning=True)

    def _commit_transaction(self):
        if self._transaction_session is None or not self._transaction_session.active:
            return
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self._window,
            "Confirmar commit",
            f"Confirmar todas as alterações da transação em '{self._transaction_profile_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.status.setText("Commit cancelado; a transação continua aberta.")
            return
        try:
            self._transaction_session.commit()
            self._log_event("Commit confirmado", profile=self._transaction_profile_name)
            self.status.setText("Commit confirmado. A transação foi encerrada.")
        except Exception as exc:
            self._log_event("Falha no commit", profile=self._transaction_profile_name, detail=str(exc))
            self._show_message("Falha no commit", str(exc), warning=True)
            return
        self._close_transaction(rollback=False)

    def _rollback_transaction(self):
        if self._transaction_session is None or not self._transaction_session.active:
            return
        try:
            profile_name = self._transaction_profile_name
            self._transaction_session.rollback()
            self._log_event("Rollback confirmado", profile=profile_name)
            self.status.setText("Rollback concluído. Nenhuma alteração da transação foi mantida.")
        except Exception as exc:
            self._log_event("Falha no rollback", profile=self._transaction_profile_name, detail=str(exc))
            self._show_message("Falha no rollback", str(exc), warning=True)
            return
        self._close_transaction(rollback=False)

    def _close_transaction(self, rollback: bool = True):
        session = self._transaction_session
        if session is None:
            self._set_transaction_actions(False)
            return
        profile_name = self._transaction_profile_name
        try:
            session.close(rollback=rollback)
        except Exception as exc:
            self._log_event("Falha ao encerrar transação", profile=profile_name, detail=str(exc))
        self._transaction_session = None
        self._transaction_profile_name = ""
        self._set_transaction_actions(False)
        self._update_query_connection_status()

    def _profile_open_request(self, selected_index: int | None):
        # Click handlers pass the already resolved index. Avoid querying the
        # tree again here because currentItem()/parent() can re-enter Qt while
        # a packaged Windows activation event is still being dispatched.
        selected = int(selected_index) if selected_index is not None else -1
        self._log_event("Perfil identificado para abrir", selected=selected, profiles=len(self.profiles))
        # When activation comes from the list, use the saved object directly.
        # This avoids relying on the form repaint completing before the worker
        # starts, which was the reason the button appeared to have no effect.
        profile = self.profiles[selected] if 0 <= selected < len(self.profiles) else self._profile_from_form()
        # The tree click already selected this profile. Calling select_profile
        # again here can block on Windows Credential Manager before the worker
        # even starts; the Testar conexão button does not repeat that lookup.
        errors = profile.validate()
        self._log_event("Perfil validado para abrir", profile=profile.name, errors=len(errors))
        if errors:
            message = " ".join(errors)
            self._log_event("Perfil inválido ao abrir", errors=message)
            return None, message
        # Selecting a tree profile already loads its stored password into the
        # form. Avoid querying Windows Credential Manager a second time here:
        # that lookup can block in packaged Windows builds before the worker
        # starts. Only use the credential fallback when no profile item was
        # selected (for example when opening directly from the form).
        password = self.password.text() if 0 <= selected < len(self.profiles) else self._password_for(profile)
        self._log_event("Senha preparada para abrir", profile=profile.name, password_present=bool(password), selected=selected)
        return (profile, password), ""

    def open_profile(self, selected_index: int | None = None):
        """Open the selected database, like opening a connection in IBExpert."""
        current_item = self.profile_list.currentItem()
        self._log_event("open_profile chamado", current_item=current_item.text(0) if current_item else "", form_name=self.name.text(), form_database=self.database.text())
        request, error = self._profile_open_request(selected_index)
        if request is None:
            self.status.setText(error)
            self._show_message("Não foi possível abrir o banco", error, warning=True)
            return
        profile, password = request
        self._opening_profile_name = profile.name
        self._log_event("Conexão iniciada", profile=profile.name, host=profile.host, database=profile.database, version=profile.version, password_present=bool(password))
        self.status.setText("Conectando e carregando objetos do banco...")
        # The Firebird client is reliable on the UI thread (the Testar
        # conexão button uses this exact path), but can block when initialized
        # inside a QThread in packaged Windows builds. Keep opening aligned
        # with the proven direct path and load the lightweight catalog next.
        from .connection import test_connection
        from .catalog import load_schema
        self._log_event("Teste de conexão direto iniciado", profile=profile.name)
        result = test_connection(profile, password)
        if not result.ok:
            self._log_event("Falha na conexão direta", profile=profile.name, detail=result.message)
            self._on_profile_opened(result, [], "")
            return
        self._log_event("Conexão direta concluída", profile=profile.name)
        self.status.setText("Conexão realizada. Lendo objetos do banco...")
        # Let Qt repaint the status before catalog queries begin. On large
        # databases this makes it clear that authentication succeeded and
        # only metadata loading is still in progress.
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            objects = load_schema(profile, password, detailed=False)
            self._log_event("Objetos carregados", profile=profile.name, count=len(objects))
            self._on_profile_opened(result, objects, "")
        except Exception as exc:
            self._log_event("Falha ao ler objetos", profile=profile.name, error=str(exc))
            self._on_profile_opened(result, [], str(exc))

    def _connection_timeout(self):
        if self._open_thread is None:
            return
        self._log_event("Conexão cancelada por timeout", profile=self._opening_profile_name or "")
        self.status.setText("A conexão excedeu 20 segundos. Verifique o servidor, banco e senha.")
        self._open_thread.requestInterruption()
        self._open_thread.terminate()
        self._open_thread.wait(2000)
        self._open_thread = None
        self._open_worker = None

    def _clear_open_worker(self):
        self._open_thread = None
        self._open_worker = None

    def _show_message(self, title: str, message: str, warning: bool = False):
        from .ui_messages import show_message
        show_message(self._window, title, message, warning)

    def _on_profile_opened(self, result, objects, schema_error):
        from PySide6.QtWidgets import QApplication
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        if self._open_timeout_timer is not None:
            self._open_timeout_timer.stop()
            self._open_timeout_timer.deleteLater()
            self._open_timeout_timer = None
        self._log_event("Conexão finalizada", ok=result.ok, objects=len(objects), error=schema_error or result.message)
        if not result.ok:
            if self._opening_profile_name:
                self.connected_profiles.discard(self._opening_profile_name)
                self.refresh_profiles()
                self._update_query_connection_status()
            self.status.setText(result.message)
            self._show_message("Falha ao abrir banco", result.message)
            return
        if self._opening_profile_name:
            self.connected_profiles.add(self._opening_profile_name)
        self._update_query_connection_status()
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
        self._log_event("Catálogo carregado", objects=len(objects), schema_error=schema_error or "")
        self._hide_profile_details()

    def _populate_object_tree(self, objects, profile_index=-1):
        from .tree_utils import populate_profile_children

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
        populate_profile_children(profile_item, objects)
        profile_item.setExpanded(True)
        for index in range(self.sql_tabs.count()):
            self._refresh_sql_completer(self.sql_tabs.widget(index))

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
        self.editor.setProperty("document_title", obj.name)
        self._update_sql_tab_title()

    def _load_preview_object(self, obj):
        """Load missing DDL and table metadata before rendering an object."""
        from PySide6.QtWidgets import QApplication
        from .catalog import load_object_definition

        needs_definition = (
            not obj.columns
            or (obj.kind.upper() == "TABLE" and not getattr(obj, "primary_key", ()))
            or "Use 'Ler estrutura'" in obj.ddl
        )
        if needs_definition:
            try:
                profile = self._profile_from_form()
                self.status.setText(f"Lendo DDL de {obj.kind.lower()} {obj.name}...")
                QApplication.processEvents()
                obj = load_object_definition(profile, self._password_for(profile), obj.kind, obj.name)
                self.selected_object = obj
                self._log_event("DDL de objeto carregado", kind=obj.kind, name=obj.name)
            except Exception as exc:
                self._log_event("Falha ao ler DDL de objeto", kind=obj.kind, name=obj.name, error=str(exc))
                self.status.setText(f"Falha ao ler DDL: {exc}")
                self._show_message("Falha ao ler DDL", str(exc), warning=True)
                return None

        if obj.kind.upper() == "TABLE" and not obj.columns:
            from .catalog import load_table_metadata
            try:
                profile = self._profile_from_form()
                self.status.setText(f"Lendo estrutura da tabela {obj.name}...")
                QApplication.processEvents()
                obj = load_table_metadata(profile, self._password_for(profile), obj.name)
                self.selected_object = obj
                self._log_event("Metadados de tabela carregados", table=obj.name, columns=len(obj.columns))
            except Exception as exc:
                self._log_event("Falha ao ler metadados de tabela", table=obj.name, error=str(exc))
                self.status.setText(f"Falha ao ler estrutura: {exc}")
                self._show_message("Falha ao ler estrutura da tabela", str(exc), warning=True)
                return None
        return obj

    def preview_object(self, item, _column=0, load_data=False):
        """Show metadata/DDL; optionally load the first table data page."""
        from PySide6.QtWidgets import QTableWidgetItem

        obj = item.data(0, 32)
        if obj is None:
            self.selected_object = None
            self._set_table_data_enabled(False)
            return
        self.selected_object = obj
        self._set_table_data_enabled(obj.kind.upper() == "TABLE")
        obj = self._load_preview_object(obj)
        if obj is None:
            return
        self._set_object_breadcrumb(obj)
        if obj.kind.upper() == "TABLE":
            self.table_page = 0
            self.data_filter.clear()
            self.data_page_label.setText("Dados: tabela selecionada; clique em Dados da tabela")
            self.structure_table.clear()
            self.structure_table.setSortingEnabled(False)
            self.structure_table.setColumnCount(5)
            self.structure_table.setHorizontalHeaderLabels(["Campo", "Tipo", "Tamanho", "Escala", "Aceita nulo"])
            self.structure_table.setRowCount(len(obj.columns))
            for row, values in enumerate(obj.columns):
                for column, value in enumerate(values):
                    self.structure_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.structure_table.resizeColumnsToContents()
            self.structure_table.setSortingEnabled(True)
            self.index_table.clear()
            self.index_table.setColumnCount(3)
            self.index_table.setHorizontalHeaderLabels(["Índice", "Único", "Campos"])
            self.index_table.setRowCount(len(getattr(obj, "indexes", ())))
            for row, values in enumerate(getattr(obj, "indexes", ())):
                for column, value in enumerate(values):
                    self.index_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.index_table.resizeColumnsToContents()
            self.constraint_table.clear()
            self.constraint_table.setColumnCount(3)
            self.constraint_table.setHorizontalHeaderLabels(["Restrição", "Tipo", "Índice"])
            self.constraint_table.setRowCount(len(getattr(obj, "constraints", ())))
            for row, values in enumerate(getattr(obj, "constraints", ())):
                for column, value in enumerate(values):
                    self.constraint_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.constraint_table.resizeColumnsToContents()
            self.result_tabs.setCurrentWidget(self.structure_table)
            data_loaded = bool(load_data and self._load_table_page(0))
        else:
            data_loaded = False
            self.data_filter.clear()
            self.index_table.clear(); self.index_table.setRowCount(0)
            self.constraint_table.clear(); self.constraint_table.setRowCount(0)
            self.structure_table.clear()
            self.structure_table.setColumnCount(2)
            self.structure_table.setHorizontalHeaderLabels(["Objeto", "Tipo"])
            self.structure_table.setRowCount(1)
            self.structure_table.setItem(0, 0, QTableWidgetItem(obj.name))
            self.structure_table.setItem(0, 1, QTableWidgetItem(obj.kind))
            self.structure_table.resizeColumnsToContents()
            self.result_tabs.setCurrentWidget(self.structure_table)
        self._show_object_sql(obj, new_tab=False)
        suffix = " DDL e primeira página de dados carregados." if data_loaded else " DDL carregado na janela SQL."
        self.status.setText(f"{obj.kind.title()} selecionado: {obj.name}.{suffix}")

    def open_table_data(self):
        self._load_table_page(self.table_page)

    def _table_context_menu(self, position):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self._window)
        copy_action = menu.addAction("Copiar seleção")
        copy_action.setEnabled(bool(self.result_table.selectedItems()))
        copy_action.triggered.connect(self._copy_table_selection)
        view_action = menu.addAction("Ver valor completo")
        view_action.setEnabled(bool(self.result_table.currentItem()))
        view_action.triggered.connect(self._view_selected_cell)
        menu.addSeparator()
        menu.addAction(self.edit_data_action)
        menu.addAction(self.add_data_row_action)
        menu.addAction(self.generate_update_action)
        menu.addAction(self.generate_insert_action)
        menu.addAction(self.generate_delete_action)
        menu.addAction(self.apply_update_action)
        menu.exec(self.result_table.viewport().mapToGlobal(position))

    def _view_selected_cell(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QTextEdit
        from PySide6.QtCore import Qt

        item = self.result_table.currentItem()
        if item is None:
            self._show_message("Valor da célula", "Selecione uma célula da grade.", warning=True)
            return
        value = item.data(Qt.UserRole)
        if isinstance(value, bytes):
            try:
                text = value.decode("utf-8")
                description = f"BLOB · {len(value)} bytes · UTF-8"
            except UnicodeDecodeError:
                text = value.hex(" ")
                description = f"BLOB binário · {len(value)} bytes · hexadecimal"
        else:
            text = "NULL" if value is None else str(value)
            description = type(value).__name__ if value is not None else "NULL"
        dialog = QDialog(self._window)
        dialog.setWindowTitle("Valor completo da célula")
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(description))
        editor = QTextEdit(); editor.setReadOnly(True); editor.setPlainText(text); layout.addWidget(editor, 1)
        close = QDialogButtonBox(QDialogButtonBox.Close); close.rejected.connect(dialog.reject); close.accepted.connect(dialog.accept); layout.addWidget(close)
        dialog.exec()

    def _toggle_data_edit_mode(self, enabled: bool):
        """Enable local grid editing without opening a write transaction."""
        from PySide6.QtWidgets import QAbstractItemView

        self.edit_data_mode = bool(enabled)
        triggers = (QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed) if enabled else QAbstractItemView.NoEditTriggers
        self.result_table.setEditTriggers(triggers)
        if enabled:
            self.status.setText("Edição local ativada. Revise a linha e use 'Gerar UPDATE' para criar uma prévia.")
        else:
            self.status.setText("Edição local desativada; a grade voltou a ficar protegida.")

    @staticmethod
    def _sql_identifier(value: str) -> str:
        return '"' + str(value).replace('"', '""') + '"'

    @staticmethod
    def _sql_literal(value, original=None) -> str:
        """Render a conservative Firebird literal for a generated preview."""
        import re

        if value is None:
            return "NULL"
        text = str(value)
        if original is None and text == "":
            return "NULL"
        if isinstance(original, bool):
            return "TRUE" if text.strip().casefold() in {"1", "true", "t", "sim", "s"} else "FALSE"
        if isinstance(original, (int, float)) and re.fullmatch(r"-?(?:\d+(?:\.\d*)?|\.\d+)", text.strip()):
            return text.strip()
        return "'" + text.replace("'", "''") + "'"

    def _collect_grid_row(self):
        from PySide6.QtCore import Qt

        selected = self.result_table.selectedItems()
        obj = self.selected_object
        if obj is None or str(getattr(obj, "kind", "")).upper() != "TABLE" or not selected:
            return None
        row_index = selected[0].row()
        columns = [self.result_table.horizontalHeaderItem(column).text() if self.result_table.horizontalHeaderItem(column) else f"COL_{column + 1}" for column in range(self.result_table.columnCount())]
        current, original = [], []
        for column in range(self.result_table.columnCount()):
            item = self.result_table.item(row_index, column)
            current.append(item.text() if item is not None else "")
            raw = item.data(Qt.UserRole) if item is not None else None
            if raw is None and row_index < len(self._table_original_rows) and column < len(self._table_original_rows[row_index]):
                raw = self._table_original_rows[row_index][column]
            original.append(raw)
        return obj, row_index, columns, current, original

    def _row_predicates(self, obj, columns, original):
        primary_key = tuple(getattr(obj, "primary_key", ()) or ())
        key_indexes = [column for column, name in enumerate(columns) if any(name.casefold() == key.casefold() for key in primary_key)]
        predicate_indexes = key_indexes or list(range(len(columns)))
        predicates = []
        for column in predicate_indexes:
            value = original[column]
            identifier = self._sql_identifier(columns[column])
            predicates.append(f"{identifier} IS NULL" if value is None else f"{identifier} = {self._sql_literal(value, value)}")
        return predicates, bool(key_indexes)

    def _add_local_data_row(self):
        if self.selected_object is None or str(getattr(self.selected_object, "kind", "")).upper() != "TABLE":
            return
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        if not self.edit_data_mode:
            self.edit_data_action.setChecked(True)
        self.result_table.setSortingEnabled(False)
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)
        for column in range(self.result_table.columnCount()):
            item = QTableWidgetItem("")
            item.setData(Qt.UserRole, None)
            self.result_table.setItem(row, column, item)
        self.result_table.setSortingEnabled(True)
        self._table_original_rows.append(tuple(None for _ in range(self.result_table.columnCount())))
        self.result_table.selectRow(row)
        self.status.setText("Linha local adicionada. Preencha os campos e gere um INSERT antes de aplicar.")

    def _generate_insert_preview(self):
        values = self._collect_grid_row()
        if values is None:
            self._show_message("Gerar INSERT", "Selecione uma linha de uma tabela.", warning=True)
            return
        obj, row_index, columns, current, original = values
        assignments = ", ".join(self._sql_identifier(column) for column in columns)
        literals = ", ".join(self._sql_literal(value, original[index]) for index, value in enumerate(current))
        sql = (
            "-- Prévia segura: nenhuma alteração foi aplicada.\n"
            "-- Revise os valores e confirme a transação antes de aplicar.\n"
            f"INSERT INTO {self._sql_identifier(obj.name)} ({assignments})\n"
            f"VALUES ({literals});"
        )
        self.editor.setPlainText(sql)
        self.sql_tabs.setCurrentWidget(self.editor)
        self.apply_update_action.setEnabled(True)
        self.status.setText("Prévia INSERT gerada. Revise o SQL antes de aplicar.")
        self._log_event("Prévia INSERT gerada", table=obj.name, row=row_index)

    def _generate_delete_preview(self):
        values = self._collect_grid_row()
        if values is None:
            self._show_message("Gerar DELETE", "Selecione uma linha de uma tabela.", warning=True)
            return
        obj, row_index, columns, _current, original = values
        if all(value is None for value in original):
            self._show_message("Gerar DELETE", "A linha é local e ainda não existe no banco.", warning=True)
            return
        predicates, used_primary_key = self._row_predicates(obj, columns, original)
        where_note = "-- A chave primária foi usada na cláusula WHERE.\n" if used_primary_key else "-- Esta tabela não informou chave primária; todos os valores originais foram usados na cláusula WHERE.\n"
        sql = (
            "-- Prévia segura: nenhuma alteração foi aplicada.\n"
            + where_note
            + f"DELETE FROM {self._sql_identifier(obj.name)}\n"
            + f"WHERE {' AND '.join(predicates)};"
        )
        self.editor.setPlainText(sql)
        self.sql_tabs.setCurrentWidget(self.editor)
        self.apply_update_action.setEnabled(True)
        self.status.setText("Prévia DELETE gerada. Revise o SQL antes de aplicar.")
        self._log_event("Prévia DELETE gerada", table=obj.name, row=row_index)

    def _generate_row_update_preview(self):
        """Put a safe, non-executing UPDATE preview in the SQL editor."""
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtCore import Qt

        obj = self.selected_object
        selected = self.result_table.selectedItems()
        if obj is None or str(getattr(obj, "kind", "")).upper() != "TABLE":
            self._show_message("Gerar UPDATE", "Selecione uma tabela.", warning=True)
            return
        if not selected:
            self._show_message("Gerar UPDATE", "Selecione uma linha da grade.", warning=True)
            return
        row_index = selected[0].row()
        columns = [self.result_table.horizontalHeaderItem(column).text() if self.result_table.horizontalHeaderItem(column) else f"COL_{column + 1}" for column in range(self.result_table.columnCount())]
        current = []
        original = []
        for column in range(self.result_table.columnCount()):
            item = self.result_table.item(row_index, column)
            current.append(item.text() if item is not None else "")
            raw = item.data(Qt.UserRole) if item is not None else None
            if raw is None and row_index < len(self._table_original_rows) and column < len(self._table_original_rows[row_index]):
                raw = self._table_original_rows[row_index][column]
            original.append(raw)
        changes = [(column, current[column], original[column]) for column in range(len(columns)) if current[column] != ("" if original[column] is None else str(original[column]))]
        if not changes:
            self.status.setText("Nenhuma alteração local foi encontrada na linha selecionada.")
            return
        assignments = ",\n    ".join(f"{self._sql_identifier(columns[column])} = {self._sql_literal(value, original[column])}" for column, value, _old in changes)
        primary_key = tuple(getattr(obj, "primary_key", ()) or ())
        key_indexes = [column for column, name in enumerate(columns) if any(name.casefold() == key.casefold() for key in primary_key)]
        predicate_indexes = key_indexes or list(range(len(columns)))
        predicates = []
        for column in predicate_indexes:
            value = original[column]
            identifier = self._sql_identifier(columns[column])
            predicates.append(f"{identifier} IS NULL" if value is None else f"{identifier} = {self._sql_literal(value, value)}")
        where_note = (
            "-- A chave primária foi usada na cláusula WHERE.\n"
            if key_indexes else
            "-- Esta tabela não informou chave primária; todos os valores originais foram usados na cláusula WHERE.\n"
        )
        sql = (
            "-- Prévia segura: nenhuma alteração foi aplicada.\n"
            + where_note
            + f"UPDATE {self._sql_identifier(obj.name)}\n"
            + f"SET {assignments}\n"
            + f"WHERE {' AND '.join(predicates)};"
        )
        if self.editor is not None:
            self.editor.setPlainText(sql)
            self.sql_tabs.setCurrentWidget(self.editor)
        self.status.setText("Prévia UPDATE gerada. Revise o SQL antes de executar; nada foi gravado.")
        self._log_event("Prévia UPDATE gerada", table=obj.name, row=row_index, changes=len(changes))
        if hasattr(self, "apply_update_action"):
            self.apply_update_action.setEnabled(True)

    def _apply_update_preview(self):
        """Execute the reviewed UPDATE only after an explicit confirmation."""
        from PySide6.QtWidgets import QMessageBox
        from .sql import execute_sql

        sql_text = self.editor.toPlainText().strip() if self.editor is not None else ""
        if not sql_text or not any(token in sql_text.upper() for token in ("UPDATE", "INSERT", "DELETE")):
            self._show_message("Aplicar alteração", "Gere ou revise uma prévia de INSERT, UPDATE ou DELETE antes de aplicar.", warning=True)
            return
        answer = QMessageBox.question(
            self._window,
            "Confirmar alteração no banco",
            "A instrução de alteração será executada e confirmada no banco. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.status.setText("UPDATE cancelado; nenhuma alteração foi aplicada.")
            return
        profile = self._query_profile()
        result = execute_sql(profile, sql_text, self._password_for(profile), commit=True)
        self._log_event("Alteração de grade aplicada", profile=profile.name, ok=result.ok, detail=result.message)
        if result.ok:
            self.status.setText("Alteração aplicada e confirmada. Recarregue os dados para conferir a linha.")
            self.apply_update_action.setEnabled(False)
        else:
            self.status.setText(f"Falha ao aplicar alteração: {result.message}")
            self._show_message("Falha ao aplicar alteração", result.message, warning=True)

    def _copy_table_selection(self):
        items = self.result_table.selectedItems()
        if not items:
            return
        rows = {}
        for item in items:
            rows.setdefault(item.row(), {})[item.column()] = item.text()
        text = "\n".join("\t".join(values.get(column, "") for column in range(self.result_table.columnCount())) for _, values in sorted(rows.items()))
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.status.setText(f"{len(rows)} linha(s) copiada(s).")

    def _filter_data_rows(self, text: str):
        query = (text or "").strip().casefold()
        for row in range(self.result_table.rowCount()):
            values = [self.result_table.item(row, column).text() if self.result_table.item(row, column) else "" for column in range(self.result_table.columnCount())]
            self.result_table.setRowHidden(row, bool(query) and query not in " ".join(values).casefold())

    def _page_size_changed(self, value: str):
        try:
            size = max(1, int(value))
        except (TypeError, ValueError):
            return
        self._settings.setValue("data_page_size", size)
        self._settings.sync()
        self._update_pagination_labels(size)
        if self.selected_object is not None and self.selected_object.kind.upper() == "TABLE":
            self._load_table_page(self.table_page)

    def _update_pagination_labels(self, page_size=None):
        """Keep pagination actions aligned with the selected page size."""
        if not hasattr(self, "next_data_button"):
            return
        if page_size is None:
            try:
                page_size = int(self.data_page_size.currentText())
            except (AttributeError, TypeError, ValueError):
                page_size = 200
        self.next_data_button.setText(f"Próximas {max(1, int(page_size))}")

    def _result_header_context_menu(self, table, position):
        from PySide6.QtWidgets import QInputDialog, QMenu

        column = table.horizontalHeader().logicalIndexAt(position)
        if column < 0 or column >= table.columnCount():
            return
        header = table.horizontalHeaderItem(column)
        title = header.text() if header else f"Coluna {column + 1}"
        menu = QMenu(self._window)
        filter_action = menu.addAction(f"Filtrar coluna {title}")
        clear_action = menu.addAction("Limpar filtros da grade")
        chosen = menu.exec(table.horizontalHeader().viewport().mapToGlobal(position))
        if chosen is filter_action:
            value, accepted = QInputDialog.getText(self._window, "Filtrar coluna", f"Valor em {title}:")
            if accepted:
                needle = value.casefold().strip()
                for row in range(table.rowCount()):
                    item = table.item(row, column)
                    table.setRowHidden(row, bool(needle) and needle not in (item.text() if item else "").casefold())
                self.status.setText(f"Filtro aplicado na coluna {title}.")
        elif chosen is clear_action:
            for row in range(table.rowCount()):
                table.setRowHidden(row, False)
            self._filter_data_rows(self.data_filter.text())
            self.status.setText("Filtros da grade removidos.")

    def _load_table_page(self, page: int):
        from .sql import execute_sql
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        obj = self.selected_object
        if obj is None or obj.kind.upper() != "TABLE":
            self._show_message("Abrir dados", "Selecione uma tabela na árvore de objetos.", warning=True)
            return False
        page = max(0, page)
        profile = self._profile_from_form()
        table_name = obj.name.replace('"', '""')
        page_size = max(1, int(self.data_page_size.currentText()))
        start = page * page_size + 1
        end = start + page_size - 1
        self.status.setText(f"Carregando linhas {start} a {end} de {obj.name}...")
        result = execute_sql(profile, f'SELECT * FROM "{table_name}" ROWS {start} TO {end}', self._password_for(profile))
        if not result.ok:
            self.status.setText(result.message)
            self._show_message("Falha ao abrir dados", result.message)
            return False
        self._table_original_rows = [tuple(row) for row in result.rows]
        self._show_sql_result()
        from .result_views import fill_table
        fill_table(self.result_table, result.columns, result.rows, preserve_values=True)
        self._filter_data_rows(self.data_filter.text())
        self.table_page = page
        self.previous_data_button.setEnabled(page > 0)
        self.next_data_button.setText(f"Próximas {page_size}")
        self.next_data_button.setEnabled(len(result.rows) == page_size)
        self.data_page_label.setText(f"Página {page + 1} · linhas {start}-{start + max(0, len(result.rows) - 1)}")
        self.result_summary.setText(f"Dados: {len(result.rows)} linha(s) · página {page + 1} · {profile.name} · {profile.host}:{profile.port}")
        self.status.setText(f"Dados carregados: {len(result.rows)} linha(s).")
        return True

    def open_object(self, item, _column=0):
        obj = item.data(0, 32)
        if obj is None:
            return
        if self.selected_object is not None and self.selected_object.key == obj.key:
            obj = self.selected_object
        self._show_object_sql(obj, new_tab=True)
        self._set_object_breadcrumb(obj)
        self.status.setText(f"Nova janela SQL aberta para {obj.kind.lower()} {obj.name}.")

    def refresh_profiles(self):
        self.profile_list.clear()
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QColor
        from .tree_utils import make_database_icon, populate_profile_children
        dark_theme = str(self._settings.value("theme", "light")) == "dark"
        for index, profile in enumerate(self.profiles):
            connected = profile.name in self.connected_profiles
            marker = "★ " if profile.favorite else ""
            item = QTreeWidgetItem([f"{marker}{profile.name} · FB {profile.version}"])
            item.setIcon(0, make_database_icon(connected))
            item.setForeground(0, QColor(("#98d89c" if dark_theme else "#188038") if connected else ("#b6c2d2" if dark_theme else "#5f6368")))
            item.setData(0, 33, index)
            self.profile_list.addTopLevelItem(item)
            objects = self.profile_objects.get(profile.name, [])
            populate_profile_children(item, objects)
            item.setExpanded(self._tree_expansion(profile.name, bool(objects)))
        connected_count = sum(profile.name in self.connected_profiles for profile in self.profiles)
        self.sidebar_status.setText(f"{connected_count} banco(s) conectado(s) · {len(self.profiles)} cadastrado(s)")
        self.target_profile.clear()
        self.target_profile.addItems([p.name for p in self.profiles])
        for combo in self._query_profile_combos:
            editor = combo.property("sql_editor")
            current_query_name = editor.property("query_profile") if editor is not None else ""
            combo.blockSignals(True)
            combo.clear()
            combo.addItems([p.name for p in self.profiles])
            if current_query_name:
                index = combo.findText(current_query_name)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self._filter_tree(self.tree_filter.text())

    def _tree_connected_filter_changed(self, checked: bool):
        self._settings.setValue("tree_connected_only", bool(checked))
        self._settings.sync()
        self._filter_tree(self.tree_filter.text())

    def _tree_state_key(self, profile_name: str) -> str:
        return f"tree_expanded/{profile_name}"

    def _tree_expansion(self, profile_name: str, default: bool = False) -> bool:
        key = self._tree_state_key(profile_name)
        if not self._settings.contains(key):
            return default
        return bool(self._settings.value(key, default, type=bool))

    def _save_tree_expansion(self, item, expanded: bool):
        if item is None or item.parent() is not None:
            return
        index = item.data(0, 33)
        if index is None or not (0 <= int(index) < len(self.profiles)):
            return
        self._settings.setValue(self._tree_state_key(self.profiles[int(index)].name), bool(expanded))
        self._settings.sync()

    def _filter_tree(self, text):
        query = (text or "").strip().casefold()
        for index in range(self.profile_list.topLevelItemCount()):
            root = self.profile_list.topLevelItem(index)
            visible = not query or query in root.text(0).casefold()
            profile_index = root.data(0, 33)
            connected_visible = (
                not self.tree_connected_only.isChecked()
                or (profile_index is not None and int(profile_index) < len(self.profiles)
                    and self.profiles[int(profile_index)].name in self.connected_profiles)
            )
            for child_index in range(root.childCount()):
                child = root.child(child_index)
                child_visible = not query or query in child.text(0).casefold()
                for object_index in range(child.childCount()):
                    object_item = child.child(object_index)
                    object_item.setHidden(bool(query) and not (child_visible or query in object_item.text(0).casefold()))
                child.setHidden(bool(query) and not (child_visible or any(not child.child(i).isHidden() for i in range(child.childCount()))))
            root.setHidden((bool(query) and not (visible or any(not root.child(i).isHidden() for i in range(root.childCount())))) or not connected_visible)

    def _tree_context_menu(self, position):
        """Offer expansion controls without triggering selection or connection."""
        from PySide6.QtWidgets import QMenu

        item = self.profile_list.itemAt(position)
        if item is None:
            return
        menu = QMenu(self._window)
        profile_index = self._profile_index_for_item(item)
        if item.parent() is None and 0 <= profile_index < len(self.profiles):
            profile = self.profiles[profile_index]
            show_details = menu.addAction("Alterar cadastro...")
            show_details.triggered.connect(lambda _checked=False, selected=profile_index: self._show_profile_dialog(selected))
            copy_name = menu.addAction("Copiar nome do banco")
            copy_name.triggered.connect(lambda _checked=False, value=profile.name: self._copy_tree_value(value, "Nome do banco"))
            copy_database = menu.addAction("Copiar caminho ou alias")
            copy_database.triggered.connect(lambda _checked=False, value=profile.database: self._copy_tree_value(value, "Caminho ou alias"))
            menu.addSeparator()
            if profile.name in self.connected_profiles:
                disconnect = menu.addAction("Desconectar banco")
                disconnect.triggered.connect(self.disconnect_selected)
                menu.addSeparator()
        if item.childCount():
            if item.isExpanded():
                action = menu.addAction("Recolher objetos")
                action.triggered.connect(lambda _checked=False, target=item: target.setExpanded(False))
            else:
                action = menu.addAction("Expandir objetos")
                action.triggered.connect(lambda _checked=False, target=item: target.setExpanded(True))
        collapse_all = menu.addAction("Recolher todos os bancos")
        collapse_all.triggered.connect(self._collapse_all_profiles)
        menu.exec(self.profile_list.viewport().mapToGlobal(position))

    def _copy_tree_value(self, value: str, label: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(value)
        self.status.setText(f"{label} copiado para a área de transferência.")

    def disconnect_selected(self):
        index = self._profile_index_for_item()
        if index < 0 or index >= len(self.profiles):
            self._show_message("Desconectar banco", "Selecione um banco conectado na árvore.", warning=True)
            return
        profile = self.profiles[index]
        self.connected_profiles.discard(profile.name)
        self.profile_objects.pop(profile.name, None)
        self.selected_object = None
        self._set_table_data_enabled(False)
        self.refresh_profiles()
        self._update_query_connection_status()
        self._log_event("Banco desconectado", profile=profile.name)
        self.status.setText(f"Banco '{profile.name}' desconectado. O cadastro e o arquivo foram mantidos.")

    def _collapse_all_profiles(self):
        for index in range(self.profile_list.topLevelItemCount()):
            self.profile_list.topLevelItem(index).setExpanded(False)
        self.status.setText("Objetos dos bancos recolhidos.")

    def new_profile(self):
        self._show_profile_dialog()
        if hasattr(self, "welcome_banner"):
            self.welcome_banner.setVisible(False)

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
        self._log_event("Cadastro excluído", profile=profile.name, remaining=len(self.profiles), profile_store=str(self.store.path))
        from .credentials import CredentialStore
        try:
            CredentialStore().delete(profile.name)
        except Exception:
            pass
        self.profile_objects.pop(profile.name, None)
        self.refresh_profiles()
        self._update_query_connection_status()
        self.name.clear(); self.database.clear(); self.role.clear(); self.password.clear(); self.save_password.setChecked(False); self.favorite.setChecked(False)
        self.status.setText("Cadastro excluído. O arquivo do banco foi mantido.")

    def select_profile(self, index: int):
        if index < 0 or index >= len(self.profiles): return
        p = self.profiles[index]
        for widget, value in ((self.name, p.name), (self.host, p.host), (self.database, p.database), (self.user, p.user), (self.role, p.role), (self.charset, p.charset), (self.isql_path, p.isql_path), (self.gbak_path, p.gbak_path)):
            widget.setText(value)
        stored_password = self._stored_password(p.name)
        self.password.setText(stored_password or "")
        self.save_password.setChecked(bool(stored_password))
        self.favorite.setChecked(bool(p.favorite))
        self.port.setValue(p.port); self.version.setCurrentText(p.version)
        self._update_query_connection_status()

    def _profile_from_form(self):
        return ConnectionProfile(self.name.text(), self.host.text(), self.port.value(), self.database.text(), self.version.currentText(), self.user.text(), role=self.role.text(), charset=self.charset.text(), favorite=self.favorite.isChecked(), isql_path=self.isql_path.text(), gbak_path=self.gbak_path.text())

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
        self._log_event("Perfil salvo", profile=profile.name, count=len(self.profiles), profile_store=str(self.store.path))
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

    def _show_connection_result(self, profile, result, details: str = ""):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QPlainTextEdit, QVBoxLayout

        dialog = QDialog(self._window)
        dialog.setWindowTitle(f"Dados da conexão — {profile.name}")
        dialog.setModal(True)
        dialog.resize(650, 360)
        form = QFormLayout()
        status = QLabel("Conectado" if result.ok else "Falha na conexão")
        status.setStyleSheet("color: #188038; font-weight: bold;" if result.ok else "color: #c5221f; font-weight: bold;")
        form.addRow("Status", status)
        form.addRow("Perfil", QLabel(profile.name))
        form.addRow("Servidor", QLabel(f"{profile.host}:{profile.port}"))
        form.addRow("Banco", QLabel(profile.database))
        form.addRow("Firebird", QLabel(profile.version))
        if result.server_version:
            form.addRow("Versão detectada", QLabel(str(result.server_version)))
        output = QPlainTextEdit(); output.setReadOnly(True); output.setPlainText(result.message + (f"\n\n{details}" if details else ""))
        buttons = QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(dialog.reject); buttons.accepted.connect(dialog.accept)
        layout = QVBoxLayout(dialog); layout.addLayout(form); layout.addWidget(output, 1); layout.addWidget(buttons)
        dialog.exec()

    def test_selected(self):
        from .connection import test_connection

        profile = self._profile_from_form()
        result = test_connection(profile, self._password_for(profile))
        self._log_event("Teste de conexão", profile=profile.name, ok=result.ok, detail=result.message)
        self.status.setText(result.message)
        if not result.ok:
            self._show_connection_result(profile, result)
            return
        if result.ok:
            details = ""
            try:
                from .catalog import load_schema
                objects = load_schema(profile, self._password_for(profile))
                self._populate_object_tree(objects)
                details = f"Objetos carregados: {len(objects)}."
                self.status.setText(f"{result.message} Objetos carregados: {len(objects)}.")
            except Exception as exc:
                message = f"{result.message}\n\nConectado, mas não foi possível ler os objetos:\n{exc}"
                details = f"Conectado, mas não foi possível ler os objetos:\n{exc}"
                self.status.setText(message.replace("\n", " "))
            self._show_connection_result(profile, result, details)
            self._hide_profile_details()

    def execute_selected(self):
        if self.editor is None:
            return
        self._execute_sql_text(self.editor.toPlainText())

    def _execute_sql_text(self, sql_text: str):
        from PySide6.QtWidgets import QTableWidgetItem
        from .sql import execute_sql, is_mutating_statement

        statement = sql_text.lstrip().upper()
        changes_data = is_mutating_statement(sql_text)
        commit = bool(self.commit_changes.isChecked())
        if changes_data and self.read_only_mode.isChecked():
            self.status.setText("Modo somente leitura: a instrução foi bloqueada.")
            self._log_event("SQL bloqueado por somente leitura", statement=statement.split(None, 1)[0] if statement else "")
            return
        profile = self._query_profile()
        explicit_transaction = self._transaction_session is not None and self._transaction_session.active
        if explicit_transaction and self._transaction_profile_name != profile.name:
            self.status.setText(f"A transação aberta pertence ao perfil '{self._transaction_profile_name}'. Faça Commit/Rollback antes de trocar de banco.")
            return
        if changes_data and commit and not explicit_transaction:
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
        result = self._transaction_session.execute(sql_text) if explicit_transaction else execute_sql(profile, sql_text, self._password_for(profile), commit=commit)
        self._log_event("SQL executado", profile=profile.name, statement=statement.split(None, 1)[0] if statement else "", commit=commit, ok=result.ok, rows=len(result.rows), elapsed_ms=f"{result.elapsed_ms:.1f}", detail=result.message)
        self._add_query_history(sql_text)
        suffix = " Transação aberta; escolha Commit ou Rollback." if explicit_transaction and result.ok else (" Alterações confirmadas." if changes_data and commit and result.ok else (" Alterações desfeitas (modo seguro)." if changes_data and result.ok else ""))
        self.status.setText(f"{result.message} ({result.elapsed_ms:.1f} ms)." + suffix)
        profile_state = f"{profile.name} · {profile.host}:{profile.port}"
        self.result_summary.setText(f"Resultado: {'OK' if result.ok else 'falha'} · {len(result.rows)} linha(s) · {result.elapsed_ms:.1f} ms · {profile_state}")
        self._show_sql_result()
        self._table_original_rows = []
        if hasattr(self, "edit_data_action"):
            self.edit_data_action.setChecked(False)
            self.edit_data_action.setEnabled(False)
        if hasattr(self, "generate_update_action"):
            self.generate_update_action.setEnabled(False)
        for action_name in ("add_data_row_action", "generate_insert_action", "generate_delete_action"):
            action = getattr(self, action_name, None)
            if action is not None:
                action.setEnabled(False)
        if hasattr(self, "apply_update_action"):
            self.apply_update_action.setEnabled(False)
        from .result_views import fill_table
        fill_table(self.result_table, result.columns, result.rows)

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

    def export_result_json(self):
        from PySide6.QtWidgets import QFileDialog
        import json
        filename, _ = QFileDialog.getSaveFileName(self._window, "Exportar resultado JSON", "", "JSON (*.json);;Todos (*.*)")
        if not filename:
            return
        columns = [self.result_table.horizontalHeaderItem(column).text() if self.result_table.horizontalHeaderItem(column) else "" for column in range(self.result_table.columnCount())]
        rows = [{columns[column]: (self.result_table.item(row, column).text() if self.result_table.item(row, column) else None) for column in range(self.result_table.columnCount())} for row in range(self.result_table.rowCount())]
        try:
            Path(filename).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.setText(f"JSON exportado: {filename}")
        except OSError as exc:
            self.status.setText(f"Falha ao exportar JSON: {exc}")
            self._show_message("Falha ao exportar JSON", str(exc))

    def save_sql_file(self):
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(self._window, "Salvar script SQL", "", "SQL (*.sql);;Todos (*.*)")
        if not filename:
            return
        try:
            Path(filename).write_text(self.editor.toPlainText(), encoding="utf-8")
            self.status.setText(f"Script SQL salvo: {filename}")
        except OSError as exc:
            self.status.setText(f"Falha ao salvar SQL: {exc}")
            self._show_message("Falha ao salvar SQL", str(exc))

    def _start_background_operation(self, name, operation, on_finished):
        from PySide6.QtCore import QThread, QTimer, Qt

        if self._operation_thread is not None and self._operation_thread.isRunning():
            self.status.setText(f"A operação '{self._operation_name}' ainda está em execução.")
            return False
        if OperationWorker is None:
            self.status.setText("Não foi possível iniciar o executor em segundo plano.")
            return False
        thread = QThread(self._window)
        worker = OperationWorker(operation)
        worker.moveToThread(thread)
        self._operation_name = name
        self._operation_started_at = time.monotonic()
        self._operation_thread = thread
        self._operation_worker = worker
        thread.started.connect(worker.run)
        def finish_safely(result):
            try:
                on_finished(result)
            except Exception as exc:
                self._log_event("Falha ao finalizar operação", operation=name, error=str(exc))
                self.status.setText(f"{name} terminou com erro na interface: {exc}")
                self._show_message(f"Falha em {name}", str(exc), warning=True)

        # A plain Python callback does not reliably carry a Qt receiver
        # context. Queue the UI callback explicitly on the main window so a
        # worker never touches widgets from its own thread.
        def queue_finished(result):
            QTimer.singleShot(0, self._window, lambda: finish_safely(result))

        worker.finished.connect(queue_finished, Qt.DirectConnection)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_background_operation)
        self.status.setText(f"{name} em execução...")
        self.operation_progress.setVisible(True)
        self._log_event("Operação iniciada", operation=name)
        thread.start()
        return True

    def _clear_background_operation(self):
        elapsed = time.monotonic() - self._operation_started_at if self._operation_started_at else 0.0
        if elapsed:
            self.status.setText(f"{self.status.text()} · duração {elapsed:.1f}s")
        self._operation_thread = None
        self._operation_worker = None
        self._operation_name = ""
        self._operation_started_at = 0.0
        if hasattr(self, "operation_progress"):
            self.operation_progress.setVisible(False)

    def _operation_result_text(self, result):
        if isinstance(result, Exception):
            return "", str(result)
        return getattr(result, "output", "") or "", getattr(result, "error", "") or ""

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
        password = self._password_for(profile)
        isql_path = Path(profile.isql_path)
        self._start_background_operation(
            "Script SQL",
            lambda: run_script(profile, Path(filename), password, isql_path),
            lambda result: self._finish_script_operation(result, profile, filename),
        )

    def _finish_script_operation(self, result, profile, filename):
        output, error = self._operation_result_text(result)
        ok = bool(getattr(result, "ok", False)) if not isinstance(result, Exception) else False
        self._log_event("Script executado", profile=profile.name, file=str(filename), ok=ok, error=error)
        self.editor.setPlainText(output + ("\n" + error if error else ""))
        self.status.setText(("Script concluído. " if ok else "Script falhou. ") + error)

    def execute_backup(self):
        from .backup import run_gbak
        from PySide6.QtWidgets import QFileDialog
        from datetime import datetime

        self.status.setText("Selecionando arquivo para salvar o backup...")
        source = Path(self.database.text())
        stem = Path(self.database.text().strip().strip('"')).stem or self.name.text().strip() or "firebird_backup"
        suggested = f"{stem}_{datetime.now():%Y%m%d_%H%M%S}.fbk"
        filename, _ = QFileDialog.getSaveFileName(self._window, "Salvar backup Firebird", suggested, "Backup Firebird (*.fbk);;Todos (*.*)")
        if not filename:
            return
        profile = self._profile_from_form()
        password = self._password_for(profile)
        gbak_path = Path(self.gbak_path.text())
        self._start_background_operation(
            "Backup",
            lambda: run_gbak(profile, "backup", source, Path(filename), password, gbak_path),
            lambda result: self._finish_backup_operation(result, profile, filename),
        )

    def manage_users(self):
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QInputDialog, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout
        from .users import PRIVILEGES, change_user_password, create_role, create_user, delete_user, grant_privilege, grant_role, list_users, revoke_privilege, revoke_role

        profile = self._profile_from_form()
        admin_password = self._password_for(profile)
        dialog = QDialog(self._window)
        dialog.setWindowTitle(f"Usuários · {profile.name}")
        dialog.resize(640, 420)
        layout = QVBoxLayout(dialog)
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
                self._show_message("Gestão de usuários", str(exc), warning=True)
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
                self._show_message("Criar role", "Informe o nome da role.", warning=True); return
            try:
                create_role(profile, admin_password, target)
                self._log_event("Role criada", profile=profile.name, role=target)
                self.status.setText(f"Role {target} criada.")
            except Exception as exc:
                self._show_message("Criar role", str(exc), warning=True)

        def change_role_action(revoke: bool):
            target_user = selected_user(); target_role = role_value()
            if not target_user or not target_role:
                self._show_message("Permissão de role", "Selecione um usuário e informe a role.", warning=True); return
            try:
                (revoke_role if revoke else grant_role)(profile, admin_password, target_role, target_user)
                action = "removida" if revoke else "concedida"
                self._log_event("Role alterada", profile=profile.name, role=target_role, user=target_user, action=action)
                self.status.setText(f"Role {target_role} {action} para {target_user}.")
            except Exception as exc:
                self._show_message("Permissão de role", str(exc), warning=True)

        def change_privilege_action(revoke: bool):
            target_user = selected_user(); target_object = object_name.text().strip(); privilege = privilege_combo.currentText()
            if not target_user or not target_object:
                self._show_message("Privilégio", "Selecione um usuário e informe o objeto.", warning=True); return
            if revoke:
                answer = QMessageBox.question(dialog, "Remover privilégio", f"Remover {privilege} de {target_user} no objeto {target_object}?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return
            try:
                (revoke_privilege if revoke else grant_privilege)(profile, admin_password, privilege, target_object, target_user)
                action = "removido" if revoke else "concedido"
                self._log_event("Privilégio alterado", profile=profile.name, privilege=privilege, object=target_object, user=target_user, action=action)
                self.status.setText(f"Privilégio {privilege} {action} para {target_user}.")
            except Exception as exc:
                self._show_message("Privilégio", str(exc), warning=True)

        def create_user_action():
            username, accepted = QInputDialog.getText(dialog, "Criar usuário", "Nome do usuário:")
            if not accepted or not username.strip():
                return
            secrets = ask_secret("Criar usuário")
            if secrets is None:
                return
            try:
                create_user(profile, admin_password, username, secrets[0], secrets[1])
                self._log_event("Usuário criado", profile=profile.name, user=username.strip())
                reload_users()
            except Exception as exc:
                self._show_message("Criar usuário", str(exc), warning=True)

        def change_user_action(username: str | None = None):
            target = username or selected_user()
            if not target:
                self._show_message("Alterar senha", "Selecione um usuário.", warning=True); return
            secrets = ask_secret(f"Alterar senha · {target}")
            if secrets is None:
                return
            try:
                change_user_password(profile, admin_password, target, secrets[0], secrets[1])
                self._log_event("Senha de usuário alterada", profile=profile.name, user=target)
                reload_users()
            except Exception as exc:
                self._show_message("Alterar senha", str(exc), warning=True)

        def change_sysdba_action():
            answer = QMessageBox.question(dialog, "Alterar senha SYSDBA", "Essa operação altera a senha administrativa do banco. Continuar?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer == QMessageBox.Yes:
                change_user_action("SYSDBA")

        def delete_user_action():
            target = selected_user()
            if not target:
                self._show_message("Excluir usuário", "Selecione um usuário.", warning=True); return
            answer = QMessageBox.question(dialog, "Excluir usuário", f"Excluir o usuário {target}?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            try:
                delete_user(profile, admin_password, target)
                self._log_event("Usuário excluído", profile=profile.name, user=target)
                reload_users()
            except Exception as exc:
                self._show_message("Excluir usuário", str(exc), warning=True)

        refresh.clicked.connect(reload_users); create.clicked.connect(create_user_action); change.clicked.connect(lambda: change_user_action()); sysdba.clicked.connect(change_sysdba_action); remove.clicked.connect(delete_user_action)
        create_role_button.clicked.connect(create_role_action); grant_role_button.clicked.connect(lambda: change_role_action(False)); revoke_role_button.clicked.connect(lambda: change_role_action(True))
        grant_privilege_button.clicked.connect(lambda: change_privilege_action(False)); revoke_privilege_button.clicked.connect(lambda: change_privilege_action(True))
        reload_users()
        dialog.exec()

    def _finish_backup_operation(self, result, profile, filename):
        output, error = self._operation_result_text(result)
        ok = bool(getattr(result, "ok", False)) if not isinstance(result, Exception) else False
        self._record_backup_history("Backup", profile, str(self.database.text()), str(filename), ok, error or output[-300:])
        self._log_event("Backup concluído" if ok else "Backup falhou", profile=profile.name, target=str(filename), ok=ok, error=error)
        self.editor.setPlainText(output + ("\n" + error if error else ""))
        if ok:
            self.status.setText("Backup concluído.")
        else:
            message = error or output or "O gbak retornou uma falha sem detalhes."
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
        password = self._password_for(profile)
        gbak_path = Path(self.gbak_path.text())
        self._start_background_operation(
            "Restore",
            lambda: run_gbak(profile, "restore", Path(source), Path(target), password, gbak_path),
            lambda result: self._finish_restore_operation(result, profile, source, target, password),
        )

    def export_database_sql(self):
        from PySide6.QtWidgets import QFileDialog, QInputDialog
        from datetime import datetime
        from .export_sql import export_database_sql

        labels = ["Somente dados", "Somente metadados", "Dados e metadados"]
        label, accepted = QInputDialog.getItem(self._window, "Exportar banco para SQL", "Conteúdo:", labels, 2, False)
        if not accepted:
            return
        modes = {labels[0]: "data", labels[1]: "metadata", labels[2]: "both"}
        stem = Path(self.database.text().strip().strip('"')).stem or self.name.text().strip() or "firebird_export"
        filename, _ = QFileDialog.getSaveFileName(self._window, "Salvar exportação SQL", f"{stem}_{datetime.now():%Y%m%d_%H%M%S}.sql", "SQL (*.sql);;Todos (*.*)")
        if not filename:
            return
        profile = self._profile_from_form()
        password = self._password_for(profile)
        self._start_background_operation(
            "Exportação SQL",
            lambda: export_database_sql(profile, password, Path(filename), modes[label]),
            lambda result: self._finish_sql_export(result, profile),
        )

    def _finish_sql_export(self, result, profile):
        if isinstance(result, Exception):
            self._show_message("Falha na exportação SQL", str(result))
            return
        if result.ok:
            self.editor.setPlainText(f"-- Exportação SQL concluída\n-- Arquivo: {result.filename}\n-- Tabelas: {result.tables}\n-- Linhas: {result.rows}\n")
            self._log_event("Exportação SQL concluída", profile=profile.name, filename=result.filename, tables=result.tables, rows=result.rows)
            self.status.setText(f"Exportação SQL concluída: {result.filename}")
        else:
            self._log_event("Exportação SQL falhou", profile=profile.name, filename=result.filename, error=result.error)
            self.status.setText(f"Exportação SQL falhou: {result.error}")
            self._show_message("Falha na exportação SQL", result.error)

    def _finish_restore_operation(self, result, profile, source, target, password):
        output, error = self._operation_result_text(result)
        ok = bool(getattr(result, "ok", False)) if not isinstance(result, Exception) else False
        self._record_backup_history("Restore", profile, str(source), str(target), ok, error or output[-300:])
        self._log_event("Restore concluído" if ok else "Restore falhou", profile=profile.name, source=str(source), target=str(target), ok=ok, error=error)
        self.editor.setPlainText(output + ("\n" + error if error else ""))
        if not ok:
            message = error or output or "O gbak retornou uma falha sem detalhes."
            self.status.setText(f"Restore falhou: {message}")
            self._show_message("Falha no restore", message)
            return
        from dataclasses import replace
        from .connection import test_connection
        restored_profile = replace(profile, database=str(target), host="localhost", port=3050)
        validation = test_connection(restored_profile, password)
        if validation.ok:
            self.status.setText("Restore concluído e banco restaurado validado.")
            self._log_event("Restore validado", target=str(target))
        else:
            message = f"Restore concluído, mas a validação falhou: {validation.message}"
            self.status.setText(message)
            self._show_message("Restore com aviso", message, warning=True)
            self._log_event("Restore com falha na validação", target=str(target), error=validation.message)

    def inspect_schema(self):
        from .catalog import load_schema
        profile = self._profile_from_form()
        password = self._password_for(profile)
        self._start_background_operation("Leitura da estrutura", lambda: load_schema(profile, password), lambda result: self._finish_schema_operation(result, profile))

    def _finish_schema_operation(self, objects, profile):
        if isinstance(objects, Exception):
            self._log_event("Falha ao ler estrutura", profile=profile.name, error=str(objects))
            self.status.setText(f"Falha ao ler estrutura: {objects}")
            self._show_message("Falha ao ler estrutura", str(objects))
            return
        self.editor.setPlainText("\n".join(f"{obj.kind}: {obj.name}\n{obj.ddl}" for obj in objects))
        self._populate_object_tree(objects)
        self._log_event("Estrutura lida", profile=profile.name, objects=len(objects))
        self.status.setText(f"Estrutura lida: {len(objects)} objeto(s).")

    def inspect_plan(self):
        from .plan import explain_query

        profile = self._query_profile()
        if not profile.isql_path:
            self.status.setText("Configure o caminho do isql no perfil antes de analisar o plano.")
            self._show_message("Ver plano", "Configure o caminho do isql.exe no perfil antes de analisar o plano.", warning=True)
            return
        password = self._password_for(profile)
        query = self.editor.toPlainText()
        isql_path = Path(profile.isql_path)
        self._start_background_operation("Análise do plano", lambda: explain_query(profile, query, password, isql_path), lambda result: self._finish_plan_operation(result, profile))

    def _finish_plan_operation(self, result, profile):
        if isinstance(result, Exception):
            self._log_event("Falha ao analisar plano", profile=profile.name, error=str(result))
            self.status.setText(f"Falha ao analisar plano: {result}")
            self._show_message("Falha ao obter plano", str(result))
            return
        self._log_event("Plano analisado", profile=profile.name, ok=result.ok, suggestions=len(result.suggestions), error=result.error)
        if not result.ok:
            self.status.setText(result.error)
            self._show_message("Falha ao obter plano", result.error)
            return
        from .diagnostic_views import render_plan
        render_plan(self.plan_tree, self.plan_output, result)
        self.result_tabs.setCurrentWidget(self.plan_panel)
        self.status.setText("Plano analisado sem executar a consulta.")

    def inspect_health(self):
        from .health import inspect_health
        profile = self._profile_from_form()
        password = self._password_for(profile)
        self._start_background_operation("Saúde", lambda: inspect_health(profile, password), lambda result: self._finish_health_operation(result, profile))

    def _finish_health_operation(self, report, profile):
        if isinstance(report, Exception):
            self._log_event("Falha ao analisar saúde", profile=profile.name, error=str(report))
            self.status.setText(f"Falha ao ler saúde: {report}")
            self._show_message("Falha ao analisar saúde", str(report))
            return
        lines = ["INDICADORES", ""] + [f"{key}: {value}" for key, value in report.metrics.items()]
        lines.extend(["", "RECOMENDAÇÕES", ""])
        for finding in report.findings:
            lines.extend([f"[{finding.severity.upper()}] {finding.title}", f"Evidência: {finding.evidence}", f"Ação sugerida: {finding.recommendation}", ""])
        self.last_health_report = "\n".join(lines)
        self.editor.setPlainText(self.last_health_report)
        self._log_event("Saúde analisada", profile=profile.name, findings=len(report.findings))
        self.status.setText(f"Saúde analisada: {len(report.findings)} recomendação(ões).")

    def inspect_activity(self):
        from .health import inspect_health, list_statements

        profile = self._profile_from_form()
        password = self._password_for(profile)
        self._start_background_operation(
            "Painel do banco",
            lambda: (inspect_health(profile, password), list_statements(profile, password)),
            lambda result: self._finish_activity_operation(result, profile),
        )

    def _toggle_activity_auto_refresh(self, enabled: bool):
        if enabled:
            self.activity_refresh_timer.start()
            self.inspect_activity()
            self.status.setText("Atualização automática do painel ativada.")
        else:
            self.activity_refresh_timer.stop()
            self.status.setText("Atualização automática do painel desativada.")

    def _finish_activity_operation(self, result, profile):
        if isinstance(result, Exception):
            self._log_event("Falha ao ler atividade", profile=profile.name, error=str(result))
            self.status.setText(f"Falha ao ler informações do banco: {result}")
            self._show_message("Falha ao ler atividade", str(result))
            return
        report, statements = result
        self.activity_profile_name = profile.name
        metrics = report.metrics
        size = metrics.get("estimated_size_mb")
        lines = [
            f"Banco: {profile.name}",
            f"Tamanho estimado: {size:.1f} MB" if isinstance(size, (int, float)) else "Tamanho estimado: indisponível",
            f"Página: {metrics.get('page_size') or 'N/D'} bytes · páginas: {metrics.get('pages') or 'N/D'}",
            f"ODS: {metrics.get('ods_major') or 'N/D'}.{metrics.get('ods_minor') or 'N/D'} · conexões: {metrics.get('attachments') or 0}",
            f"Transações: oldest={metrics.get('oldest_transaction') or 'N/D'} · active={metrics.get('oldest_active') or 'N/D'} · next={metrics.get('next_transaction') or 'N/D'}",
            f"Consultas em execução: {len(statements)}",
        ]
        self.activity_metrics.setPlainText("\n".join(lines))
        headers = ["ID", "Conexão", "Usuário", "Endereço", "Início", "Duração", "SQL"]
        self.activity_table.setSortingEnabled(False)
        self.activity_table.clear()
        self.activity_table.setColumnCount(len(headers)); self.activity_table.setRowCount(len(statements)); self.activity_table.setHorizontalHeaderLabels(headers)
        for row, statement in enumerate(statements):
            started = statement.get("started")
            started_text = started.strftime("%Y-%m-%d %H:%M:%S") if hasattr(started, "strftime") else "N/D"
            elapsed = statement.get("elapsed_seconds")
            duration_text = f"{elapsed:.1f} s" if isinstance(elapsed, (int, float)) else "N/D"
            values = [statement.get("id"), statement.get("attachment_id"), statement.get("user"), statement.get("address"), started_text, duration_text, statement.get("sql", "")]
            for column, value in enumerate(values):
                from PySide6.QtWidgets import QTableWidgetItem
                self.activity_table.setItem(row, column, QTableWidgetItem("" if value is None else str(value)))
        self.activity_table.resizeColumnsToContents()
        self.activity_table.setSortingEnabled(True)
        self._filter_activity_rows(self.activity_filter.text())
        self.result_tabs.setCurrentWidget(self.activity_panel)
        self._log_event("Atividade lida", profile=profile.name, statements=len(statements), estimated_size_mb=size or "")
        self.status.setText(f"Painel atualizado: {len(statements)} consulta(s) em execução.")

    def _filter_activity_rows(self, text: str):
        needle = text.strip().casefold()
        for row in range(self.activity_table.rowCount()):
            values = []
            for column in range(self.activity_table.columnCount()):
                item = self.activity_table.item(row, column)
                values.append(item.text() if item else "")
            self.activity_table.setRowHidden(row, bool(needle) and needle not in " ".join(values).casefold())

    def _open_activity_sql_at(self, row: int, _column: int):
        self.activity_table.selectRow(row)
        self.open_activity_sql()

    def open_activity_sql(self):
        row = self.activity_table.currentRow()
        if row < 0:
            self._show_message("Abrir SQL", "Selecione uma consulta em execução.", warning=True)
            return
        sql_column = self.activity_table.columnCount() - 1
        item = self.activity_table.item(row, sql_column)
        sql = item.text().strip() if item else ""
        if not sql:
            self._show_message("Abrir SQL", "A consulta selecionada não possui SQL disponível.", warning=True)
            return
        self._new_sql_tab()
        self.editor.setPlainText(sql)
        profile_name = getattr(self, "activity_profile_name", "")
        if profile_name:
            self.editor.setProperty("query_profile", profile_name)
            self._sync_editor(self.sql_tabs.currentIndex())
        self.status.setText("Consulta aberta em uma nova janela SQL.")

    def export_activity_csv(self):
        """Export the currently displayed activity snapshot without credentials."""
        from PySide6.QtWidgets import QFileDialog
        import csv

        if self.activity_table.rowCount() == 0:
            self._show_message("Exportar atividade", "Atualize o painel antes de exportar.", warning=True)
            return
        filename, _ = QFileDialog.getSaveFileName(
            self._window,
            "Exportar atividade",
            "atividade_firebird.csv",
            "CSV (*.csv);;Todos (*.*)",
        )
        if not filename:
            return
        try:
            headers = [self.activity_table.horizontalHeaderItem(column).text() for column in range(self.activity_table.columnCount())]
            with open(filename, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(headers)
                for row in range(self.activity_table.rowCount()):
                    writer.writerow([
                        self.activity_table.item(row, column).text() if self.activity_table.item(row, column) else ""
                        for column in range(self.activity_table.columnCount())
                    ])
            self._log_event("Atividade exportada", filename=filename, rows=self.activity_table.rowCount())
            self.status.setText(f"Atividade exportada: {filename}")
        except Exception as exc:
            self._log_event("Falha ao exportar atividade", filename=filename, error=str(exc))
            self._show_message("Falha ao exportar atividade", str(exc))

    def save_health_report(self):
        """Save the most recent health report without exposing credentials."""
        from PySide6.QtWidgets import QFileDialog

        report = self.last_health_report.strip() or self.editor.toPlainText().strip()
        if not report:
            self._show_message("Salvar saúde", "Analise a saúde de um banco antes de salvar o relatório.", warning=True)
            return
        filename, _ = QFileDialog.getSaveFileName(
            self._window,
            "Salvar relatório de saúde",
            "saude_firebird.txt",
            "Relatório de texto (*.txt);;Todos (*.*)",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(report + "\n", encoding="utf-8")
        except Exception as exc:
            self._log_event("Falha ao salvar saúde", target=str(filename), error=str(exc))
            self._show_message("Falha ao salvar saúde", str(exc))
            return
        self._log_event("Relatório de saúde salvo", target=str(filename), bytes=len(report.encode("utf-8")))
        self.status.setText(f"Relatório de saúde salvo: {filename}")

    def save_health_html(self):
        """Save a shareable HTML health report without credentials or database data."""
        from PySide6.QtWidgets import QFileDialog
        from html import escape

        report = self.last_health_report.strip() or self.editor.toPlainText().strip()
        if not report:
            self._show_message("Salvar saúde em HTML", "Analise a saúde de um banco antes de salvar o relatório.", warning=True)
            return
        filename, _ = QFileDialog.getSaveFileName(
            self._window,
            "Salvar relatório de saúde em HTML",
            "saude_firebird.html",
            "HTML (*.html);;Todos (*.*)",
        )
        if not filename:
            return
        title = escape(self.name.text().strip() or "Banco Firebird")
        document = f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Saúde - {title}</title><style>body{{font-family:Segoe UI,Arial,sans-serif;margin:2rem;color:#202124}}pre{{white-space:pre-wrap;background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:1rem}}h1{{font-size:1.4rem}}</style></head><body><h1>Relatório de saúde: {title}</h1><pre>{escape(report)}</pre></body></html>"
        try:
            Path(filename).write_text(document, encoding="utf-8")
        except Exception as exc:
            self._log_event("Falha ao salvar saúde HTML", target=str(filename), error=str(exc))
            self._show_message("Falha ao salvar saúde HTML", str(exc))
            return
        self._log_event("Relatório de saúde HTML salvo", target=str(filename), bytes=len(document.encode("utf-8")))
        self.status.setText(f"Relatório HTML salvo: {filename}")

    def create_support_package(self):
        from PySide6.QtWidgets import QFileDialog
        from .diagnostics import create_support_package

        profile = self._profile_from_form()
        filename, _ = QFileDialog.getSaveFileName(
            self._window,
            "Criar pacote de suporte",
            "firebird-suporte.zip",
            "Pacote ZIP (*.zip);;Todos (*.*)",
        )
        if not filename:
            return
        try:
            create_support_package(
                Path(filename),
                profile,
                self.last_health_report,
                self.last_compare_report,
                self._event_log_path,
            )
            self._log_event("Pacote de suporte criado", target=filename, profile=profile.name)
            self.status.setText(f"Pacote de suporte criado: {filename}")
        except Exception as exc:
            self._log_event("Falha ao criar pacote de suporte", target=filename, error=str(exc))
            self._show_message("Pacote de suporte", str(exc), warning=True)

    def inspect_sessions(self):
        from .health import list_sessions
        profile = self._profile_from_form()
        password = self._password_for(profile)
        self._start_background_operation("Sessões", lambda: list_sessions(profile, password), lambda result: self._finish_sessions_operation(result, profile))

    def terminate_selected_session(self):
        from PySide6.QtWidgets import QMessageBox
        row = self.sessions_table.currentRow()
        if row < 0:
            self._show_message("Desconectar sessão", "Selecione uma sessão primeiro.", warning=True)
            return
        item = self.sessions_table.item(row, 0)
        if item is None:
            return
        attachment_id = item.text().strip()
        profile = self._profile_from_form()
        answer = QMessageBox.question(
            self._window,
            "Confirmar desconexão",
            f"Desconectar a sessão {attachment_id} do banco '{profile.name}'?\nA operação pode interromper o trabalho do usuário.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        password = self._password_for(profile)
        from .health import terminate_session
        self._start_background_operation(
            "Desconectar sessão",
            lambda: terminate_session(profile, password, int(attachment_id)),
            lambda result: self._finish_terminate_session(result, profile, attachment_id),
        )

    def _finish_terminate_session(self, result, profile, attachment_id):
        if isinstance(result, Exception):
            self._log_event("Falha ao desconectar sessão", profile=profile.name, attachment_id=attachment_id, error=str(result))
            self._show_message("Falha ao desconectar sessão", str(result))
            return
        self._log_event("Sessão desconectada", profile=profile.name, attachment_id=attachment_id)
        self.status.setText(f"Sessão {attachment_id} desconectada.")
        self.inspect_sessions()

    def _finish_sessions_operation(self, sessions, profile):
        from PySide6.QtWidgets import QTableWidgetItem

        if isinstance(sessions, Exception):
            self._log_event("Falha ao ler sessões", profile=profile.name, error=str(sessions))
            self.status.setText(f"Falha ao ler sessões: {sessions}")
            self._show_message("Falha ao ler sessões", str(sessions))
            return
        headers = ["ID", "Usuário", "Endereço", "Processo", "Estado"]
        self.sessions_table.setSortingEnabled(False)
        self.sessions_table.clear()
        self.sessions_table.setColumnCount(len(headers)); self.sessions_table.setRowCount(len(sessions)); self.sessions_table.setHorizontalHeaderLabels(headers)
        for row, session in enumerate(sessions):
            values = [session.get("id"), session.get("user"), session.get("address"), session.get("process"), session.get("state") or "N/D"]
            for column, value in enumerate(values):
                self.sessions_table.setItem(row, column, QTableWidgetItem("" if value is None else str(value)))
        self.sessions_table.resizeColumnsToContents()
        self.sessions_table.setSortingEnabled(True)
        self._filter_session_rows(self.sessions_filter.text())
        self.result_tabs.setCurrentWidget(self.sessions_panel)
        self._log_event("Sessões lidas", profile=profile.name, sessions=len(sessions))
        self.status.setText(f"Sessões lidas: {len(sessions)}.")

    def _filter_session_rows(self, text: str):
        needle = text.strip().casefold()
        for row in range(self.sessions_table.rowCount()):
            values = []
            for column in range(self.sessions_table.columnCount()):
                item = self.sessions_table.item(row, column)
                values.append(item.text() if item else "")
            self.sessions_table.setRowHidden(row, bool(needle) and needle not in " ".join(values).casefold())

    def validate_database(self):
        from .maintenance import validate_database
        profile = self._profile_from_form()
        password = self._password_for(profile)
        gfix_path = Path(self.gbak_path.text()).with_name("gfix.exe")
        self._start_background_operation("Validação gfix", lambda: validate_database(profile, password, gfix_path), lambda result: self._finish_validation_operation(result, profile))

    def _finish_validation_operation(self, result, profile):
        if isinstance(result, Exception):
            self.status.setText(f"Falha ao validar banco: {result}")
            self._show_message("Falha ao validar banco", str(result))
            return
        self.editor.setPlainText(result.output + ("\n" + result.error if result.error else ""))
        self._log_event("Validação gfix concluída", ok=result.ok, error=result.error)
        if result.ok:
            self.status.setText("Validação concluída. Nenhum erro foi reportado pelo gfix.")
        else:
            self.status.setText("Validação encontrou problemas ou não pôde ser executada.")
            self._show_message("Resultado da validação", result.error or result.output or "gfix retornou falha.", warning=True)

    def compare_selected(self):
        from .catalog import load_schema
        from .schema import compare_schema, generate_migration

        target_name = self.target_profile.currentText()
        source = self._profile_from_form()
        target = next((profile for profile in self.profiles if profile.name == target_name), None)
        if target is None or target.name == source.name:
            self.status.setText("Cadastre e selecione um perfil de destino diferente da origem.")
            return
        password = self._password_for(source)
        target_password = self._stored_password(target.name) or password
        self._start_background_operation(
            "Comparação de estruturas",
            lambda: self._compare_profiles(source, target, password, target_password),
            lambda result: self._finish_compare_operation(result, source, target),
        )

    @staticmethod
    def _compare_profiles(source, target, password, target_password):
        from .catalog import load_schema
        from .schema import compare_schema

        source_objects = load_schema(source, password)
        target_objects = load_schema(target, target_password)
        return compare_schema(source_objects, target_objects)

    def _finish_compare_operation(self, changes, source, target):
        from .schema import generate_migration
        from PySide6.QtWidgets import QTableWidgetItem

        if isinstance(changes, Exception):
            self._log_event("Falha ao comparar estruturas", source=source.name, target=target.name, error=str(changes))
            self.status.setText(f"Falha ao comparar estruturas: {changes}")
            self._show_message("Falha ao comparar estruturas", str(changes))
            return
        lines = [f"ORIGEM: {source.name}", f"DESTINO: {target.name}", "", f"Diferenças: {len(changes)}", ""]
        for change in changes:
            marker = "REVISAR" if change.destructive else change.action
            lines.append(f"[{marker}] {change.object.kind} {change.object.name}")
        lines.extend(["", "PRÉVIA DE MIGRAÇÃO", "", generate_migration(changes)])
        self.last_compare_report = "\n".join(lines)
        self.compare_changes = list(changes)
        headers = ["Ação", "Tipo", "Nome", "Destrutiva", "DDL de origem"]
        self.compare_table.setSortingEnabled(False); self.compare_table.clear(); self.compare_table.setColumnCount(len(headers)); self.compare_table.setRowCount(len(changes)); self.compare_table.setHorizontalHeaderLabels(headers)
        for row, change in enumerate(changes):
            values = [change.action, change.object.kind, change.object.name, "SIM" if change.destructive else "NÃO", change.object.ddl]
            for column, value in enumerate(values):
                self.compare_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.compare_table.resizeColumnsToContents(); self.compare_table.setSortingEnabled(True); self._filter_compare_rows(self.compare_filter.text())
        self.result_tabs.setCurrentWidget(self.compare_panel)
        self.editor.setPlainText(self.last_compare_report)
        self._log_event("Comparação concluída", source=source.name, target=target.name, changes=len(changes))
        self.status.setText(f"Comparação concluída: {len(changes)} diferença(s). Nenhuma alteração foi aplicada.")

    def _filter_compare_rows(self, text: str = ""):
        needle = (text or self.compare_filter.text()).strip().casefold()
        action = self.compare_action_filter.currentText()
        for row in range(self.compare_table.rowCount()):
            values = [self.compare_table.item(row, col).text() if self.compare_table.item(row, col) else "" for col in range(self.compare_table.columnCount())]
            matches_text = not needle or needle in " ".join(values).casefold()
            matches_action = action == "Todas as ações" or values[0] == action
            self.compare_table.setRowHidden(row, not (matches_text and matches_action))

    def save_compare_report(self):
        """Save the most recent comparison report without applying any change."""
        from PySide6.QtWidgets import QFileDialog

        report = self.last_compare_report.strip() or self.editor.toPlainText().strip()
        if not report:
            self._show_message("Salvar comparação", "Execute uma comparação antes de salvar o relatório.", warning=True)
            return
        filename, _ = QFileDialog.getSaveFileName(
            self._window,
            "Salvar relatório de comparação",
            "comparacao_firebird.txt",
            "Relatório de texto (*.txt);;Script SQL (*.sql);;Todos (*.*)",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(report + "\n", encoding="utf-8")
        except Exception as exc:
            self._log_event("Falha ao salvar comparação", target=str(filename), error=str(exc))
            self._show_message("Falha ao salvar comparação", str(exc))
            return
        self._log_event("Comparação salva", target=str(filename), bytes=len(report.encode("utf-8")))
        self.status.setText(f"Relatório de comparação salvo: {filename}")

    def save_compare_html(self):
        from PySide6.QtWidgets import QFileDialog
        from html import escape

        report = self.last_compare_report.strip() or self.editor.toPlainText().strip()
        if not report:
            self._show_message("Salvar comparação em HTML", "Execute uma comparação antes de salvar o relatório.", warning=True)
            return
        filename, _ = QFileDialog.getSaveFileName(
            self._window,
            "Salvar comparação em HTML",
            "comparacao_firebird.html",
            "HTML (*.html);;Todos (*.*)",
        )
        if not filename:
            return
        document = "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Comparação Firebird</title><style>body{font-family:Segoe UI,Arial,sans-serif;margin:2rem;color:#202124}pre{white-space:pre-wrap;background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:1rem} .add{color:#137333}.remove{color:#b3261e}</style></head><body><h1>Comparação de estruturas Firebird</h1><pre>" + escape(report) + "</pre></body></html>"
        try:
            Path(filename).write_text(document, encoding="utf-8")
        except Exception as exc:
            self._log_event("Falha ao salvar comparação HTML", target=str(filename), error=str(exc))
            self._show_message("Falha ao salvar comparação HTML", str(exc))
            return
        self._log_event("Comparação HTML salva", target=str(filename), bytes=len(document.encode("utf-8")))
        self.status.setText(f"Comparação HTML salva: {filename}")
