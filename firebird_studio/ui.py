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
            QTabBar,
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
        self.showMaximized = self._window.showMaximized
        self._window.setWindowTitle(f"Firebird Maintenance Studio v{__version__}")
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
        self.tree_filter.setPlaceholderText("Filtrar...")
        self.tree_filter.setToolTip("Filtrar bancos e objetos pelo nome")
        self.tree_filter.textChanged.connect(self._filter_tree)
        # A stale filter can make a restored profile look missing.  Start a
        # session with the complete catalog; the user can filter again as
        # needed without losing any saved profile.
        self.tree_filter.setText("")
        self._settings.setValue("tree_filter", "")
        self.tree_filter.textChanged.connect(lambda value: self._settings.setValue("tree_filter", value))
        self.tree_connected_only = QCheckBox("Ativos")
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
        self.database_browse = QPushButton("...")
        self.database_browse.setFixedWidth(34)
        self.database_browse.setToolTip("Selecionar arquivo de banco Firebird")
        self.database_browse.clicked.connect(self._browse_database_file)
        database_row = QWidget()
        database_layout = QHBoxLayout(database_row)
        database_layout.setContentsMargins(0, 0, 0, 0)
        database_layout.setSpacing(6)
        database_layout.addWidget(self.database, 1)
        database_layout.addWidget(self.database_browse)
        self.version = QComboBox(); self.version.addItems(SUPPORTED_VERSIONS)
        self.target_profile = QComboBox()
        self.user = QLineEdit("SYSDBA")
        self.role = QLineEdit()
        self.role.setPlaceholderText("Opcional, por exemplo RDB$ADMIN")
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password); self.password.setPlaceholderText("Senha temporária; não é salva no cadastro")
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
        self.sql_window_bar = QTabBar()
        self.sql_window_bar.setObjectName("sqlWindowBar")
        self.sql_window_bar.setMovable(False)
        self.sql_window_bar.setTabsClosable(True)
        self.sql_window_bar.setExpanding(False)
        self.sql_window_bar.setDocumentMode(True)
        self.sql_window_bar.setToolTip("Consultas SQL abertas; clique para alternar entre elas")
        self.sql_window_bar.currentChanged.connect(self._activate_sql_window_from_bar)
        self.sql_window_bar.tabCloseRequested.connect(self.close_sql_tab)
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
        self._history_lists = []
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
        self._toast = None
        self._restore_query_history()
        self.editor = None
        # Start with a clean workspace.  SQL documents are created on demand
        # from the menu or when a database is opened.
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
            self.activity_refresh_interval,
        ) = create_activity_panel(self.inspect_activity, self.export_activity_csv, self.open_activity_sql, self._filter_activity_rows, self._toggle_activity_auto_refresh, self._open_activity_sql_at, self._set_activity_refresh_interval)
        # Keep a local reference while wiring the shortcut.  This avoids any
        # callback or binding lookup seeing a partially initialized window.
        self.activity_panel = activity_panel
        self.activity_refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), activity_panel)
        self.activity_refresh_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.activity_refresh_shortcut.activated.connect(self.inspect_activity)
        self.activity_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.activity_table.customContextMenuRequested.connect(self._activity_context_menu)
        saved_activity_interval = int(self._settings.value("activity_refresh_interval", 5000))
        interval_index = self.activity_refresh_interval.findData(saved_activity_interval)
        self.activity_refresh_interval.setCurrentIndex(interval_index if interval_index >= 0 else 0)
        self.activity_refresh_timer = QTimer(self._window); self.activity_refresh_timer.setInterval(saved_activity_interval if interval_index >= 0 else 5000); self.activity_refresh_timer.timeout.connect(self.inspect_activity)
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
        self.result_tabs = QTabWidget(); self.result_tabs.setDocumentMode(True); self.result_tabs.setUsesScrollButtons(True); self.result_tabs.addTab(self.structure_table, "Estrutura"); self.result_tabs.addTab(self.index_table, "Índices"); self.result_tabs.addTab(self.constraint_table, "Restrições"); self.result_tabs.addTab(plan_panel, "Plano"); self.result_tabs.addTab(activity_panel, "Atividade"); self.result_tabs.addTab(sessions_panel, "Sessões"); self.result_tabs.addTab(backup_history_panel, "Backups"); self.result_tabs.addTab(compare_panel, "Comparar")
        for index, tooltip in enumerate((
            "Estrutura e DDL dos objetos",
            "Índices e campos indexados",
            "Restrições e chaves",
            "Plano de execução e sugestões",
            "Atividade e tamanho do banco",
            "Sessões e conexões ativas",
            "Histórico de backup e restore",
            "Comparação de estruturas",
        )):
            self.result_tabs.setTabToolTip(index, tooltip)
        self.result_mdi_window = self.sql_tabs.add_panel(self.result_tabs, "Resultados e diagnóstico", width=860, height=330)
        self.result_tabs.currentChanged.connect(lambda _index: self._show_result_window())
        self.result_mdi_window.hide()
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
        profile_button = QToolButton(); profile_button.setText("Conexão"); profile_button.setObjectName("profileMenuButton"); profile_button.setToolTip("Criar, salvar, abrir ou excluir o cadastro selecionado")
        profile_menu = QMenu(profile_button)
        profile_menu.setMinimumWidth(220)
        profile_menu.setStyleSheet("QMenu::item { padding: 6px 24px 6px 12px; }")
        for label, callback in (("Nova conexão", self.new_profile), ("Salvar conexão", self.save_profile), ("Abrir banco", self.open_profile), ("Desconectar banco", self.disconnect_selected), ("Excluir cadastro", self.delete_profile)):
            profile_action = profile_menu.addAction(label)
            profile_action.triggered.connect(callback)
        # QToolButton's native popup always opens below the button and can be
        # clipped when the sidebar reaches the bottom edge of the window.
        # Position it ourselves so it opens above when there is not enough room.
        profile_button.clicked.connect(lambda: self._show_profile_menu(profile_button, profile_menu))
        left_layout.addWidget(profile_button)
        left_layout.addStretch()

        # Connection fields are kept as state for the existing operation
        # handlers. Their form lives only in the modal connection dialog.
        right = QWidget(); right.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding); right.setObjectName("workspacePanel")
        # Fill the complete workspace explicitly.  This prevents the native
        # palette from showing through in empty areas beside/below MDI forms.
        right.setAutoFillBackground(True)
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
        welcome_profile = QPushButton("Criar primeira conexão")
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
        right_layout.addWidget(self.sql_window_bar)
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
            # Keep a separate arrow area while routing the main button click
            # through the bounded popup helper. Native InstantPopup always
            # opens downward and may be clipped at the bottom edge.
            button.setPopupMode(QToolButton.MenuButtonPopup)
            menu = QMenu(button)
            menu.setMinimumWidth(340)
            menu.setStyleSheet("QMenu::item { padding: 6px 48px 6px 12px; }")
            for text, callback in entries:
                action = menu.addAction(text)
                action.triggered.connect(callback)
            button.setMenu(menu)
            button.clicked.connect(lambda: self._show_profile_menu(button, menu))
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
        # The first theme pass runs before the MDI is created.  Apply it once
        # more after the central widget exists so its viewport receives the
        # explicit themed background instead of Qt's native gray brush.
        self._apply_theme(str(self._settings.value("theme", "light")))
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
        # Check once after the UI is ready so startup never waits for the
        # network.  Failures remain silent; the manual menu command still
        # reports them to the user.
        QTimer.singleShot(1800, self._check_updates_on_startup)

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
        # Top-level windows are not QObject children of QApplication, so the
        # generic theme helper cannot discover this MDI area reliably. Apply
        # the background directly whenever the application theme changes.
        if getattr(self, "sql_tabs", None) is not None:
            from PySide6.QtGui import QColor, QBrush, QPalette
            background = QColor({"dark": "#171a21", "blue": "#101d31", "gray": "#e7e9ed"}.get(theme, "#f7f9fc"))
            palette = self.sql_tabs.palette()
            palette.setColor(QPalette.Window, background)
            palette.setColor(QPalette.Base, background)
            self.sql_tabs.setPalette(palette)
            self.sql_tabs.setBackground(QBrush(background))
            self.sql_tabs.viewport().setPalette(palette)
            self.sql_tabs.viewport().setBackgroundRole(QPalette.Base)
            self.sql_tabs.viewport().setAutoFillBackground(True)
            # Keep an explicit rule on the viewport as a final guard against
            # the native style restoring its gray workspace brush.
            self.sql_tabs.viewport().setStyleSheet(
                f"background-color: {background.name()}; border: 0px;"
            )

    def _set_theme(self, theme: str):
        self._settings.setValue("theme", theme)
        self._settings.sync()
        self._apply_theme(theme)
        for index in range(self.sql_tabs.count()):
            highlighter = self.sql_tabs.widget(index).property("sql_highlighter")
            if highlighter is not None and hasattr(highlighter, "set_theme"):
                highlighter.set_theme(theme in {"dark", "blue"})
        labels = {"light": "Tema claro", "dark": "Tema escuro", "gray": "Tema cinza", "blue": "Tema azul escuro"}
        self.status.setText(f"{labels.get(theme, 'Tema aplicado') } aplicado.")

    def _setup_main_menu(self):
        """Create the compact application menu for global commands."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeySequence, QShortcut

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
        execute_action = sql_menu.addAction("Executar SQL", self.execute_selected)
        execute_action.setToolTip("Executar a consulta da janela SQL ativa (F5)")
        # QAction shortcuts can stop reaching the handler when another child
        # widget owns the focus. Keep explicit application shortcuts on the
        # main window so execution remains available from every SQL subview.
        self.execute_sql_shortcut = QShortcut(QKeySequence("F5"), self._window)
        self.execute_sql_shortcut.setContext(Qt.ApplicationShortcut)
        self.execute_sql_shortcut.activated.connect(self.execute_selected)
        selection_menu_action = sql_menu.addAction("Executar seleção", self.execute_selection)
        self.execute_selection_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F5"), self._window)
        self.execute_selection_shortcut.setContext(Qt.ApplicationShortcut)
        self.execute_selection_shortcut.activated.connect(self.execute_selection)
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
        close_all_action = window_menu.addAction("Fechar todas as consultas", self._close_all_sql_tabs)
        close_all_action.setToolTip("Fechar todas as janelas SQL (Ctrl+Shift+W)")
        self.close_all_sql_shortcut = QShortcut(QKeySequence("Ctrl+Shift+W"), self._window)
        self.close_all_sql_shortcut.setContext(Qt.ApplicationShortcut)
        self.close_all_sql_shortcut.activated.connect(self._close_all_sql_tabs)
        window_menu.addSeparator()
        window_menu.addAction(self.menu_always_top_action)

        database_menu = menu_bar.addMenu("Banco")
        database_menu.addAction("Nova conexão", self.new_profile)
        database_menu.addAction("Salvar conexão", self.save_profile)
        database_menu.addAction("Abrir banco", self.open_profile)
        database_menu.addAction("Desconectar banco", self.disconnect_selected)
        database_menu.addSeparator()
        database_menu.addAction("Backup", self.execute_backup)
        database_menu.addAction("Restore", self.execute_restore)

        analysis_menu = menu_bar.addMenu("Análise")
        activity_action = analysis_menu.addAction("Monitorar consultas", self.inspect_activity)
        activity_action.setToolTip("Abrir o monitor de consultas em execução (Ctrl+Shift+A)")
        self.activity_open_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self._window)
        self.activity_open_shortcut.setContext(Qt.ApplicationShortcut)
        self.activity_open_shortcut.activated.connect(self.inspect_activity)

        help_menu = menu_bar.addMenu("Ajuda")
        help_menu.addAction("Sobre", self.show_about)
        help_menu.addAction("Verificar atualizações...", self.check_for_updates)
        for menu in (app_menu, sql_menu, window_menu, database_menu, analysis_menu, help_menu):
            menu.setMinimumWidth(240)

    def _choose_history_query(self):
        if not self.query_history:
            self._show_message("Histórico SQL", "Ainda não há consultas no histórico.", warning=True)
            return
        editor = self.editor
        document_tabs = editor.property("document_tabs") if editor is not None else None
        history_panel = editor.property("history_panel") if editor is not None else None
        history_list = editor.property("history_list") if editor is not None else None
        if document_tabs is not None and history_panel is not None:
            document_tabs.setCurrentWidget(history_panel)
        if history_list is not None:
            history_list.setFocus()

    def show_app_settings(self):
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QCheckBox, QVBoxLayout

        dialog = QDialog(self._window)
        dialog.setWindowTitle("Configurações da aplicação")
        dialog.resize(460, 230)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Preferências do Studio aplicadas ao usuário atual."))
        form = QFormLayout()
        theme = QComboBox(); theme.addItem("Claro", "light"); theme.addItem("Escuro", "dark"); theme.addItem("Cinza", "gray"); theme.addItem("Azul escuro", "blue")
        saved_theme = str(self._settings.value("theme", "light"))
        theme.setCurrentIndex(max(0, theme.findData(saved_theme)))
        page_size = QComboBox(); page_size.addItems(["50", "200", "500", "1000"])
        page_size.setCurrentText(str(self._settings.value("data_page_size", "200")))
        always_top = QCheckBox("Manter a janela sempre no topo")
        always_top.setChecked(bool(self._settings.value("always_on_top", False, type=bool)))
        auto_updates = QCheckBox("Verificar atualizações ao iniciar")
        auto_updates.setChecked(bool(self._settings.value("auto_update_check", True, type=bool)))
        form.addRow("Tema", theme); form.addRow("Linhas por página", page_size); form.addRow("Janela", always_top); form.addRow("Atualizações", auto_updates)
        layout.addLayout(form)
        layout.addWidget(QLabel("As preferências de tamanho, posição, árvore e filtro são salvas automaticamente."))
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject); buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        theme.currentIndexChanged.connect(lambda index: self._set_theme(theme.itemData(index)))
        page_size.currentTextChanged.connect(self._page_size_changed)
        always_top.toggled.connect(self._set_always_on_top)
        auto_updates.toggled.connect(lambda enabled: self._settings.setValue("auto_update_check", bool(enabled)))
        dialog.exec()

    def show_about(self):
        from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QPushButton
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtGui import QDesktopServices

        dialog = QDialog(self._window)
        dialog.setWindowTitle(f"Sobre o Firebird Maintenance Studio v{__version__}")
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
        self.status.setText("Verificando atualizações...")
        self._start_update_check(silent=False)

    def _check_updates_on_startup(self):
        if not bool(self._settings.value("auto_update_check", True, type=bool)):
            return
        self._start_update_check(silent=True)

    def _start_update_check(self, silent=False):
        self._start_background_operation(
            "Verificação de atualizações",
            lambda: __import__("firebird_studio.updates", fromlist=["check_latest"]).check_latest(__version__),
            lambda result: self._finish_update_check(result, silent=silent),
        )

    def _finish_update_check(self, result, silent=False):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QMessageBox
        if isinstance(result, Exception):
            self._log_event("Falha ao verificar atualização", error=str(result))
            self.status.setText("Não foi possível verificar atualizações.")
            if not silent:
                self._show_message("Atualizações", f"Não foi possível consultar o GitHub.\n\nVersão instalada: {__version__}\n\n{result}", warning=True)
            return
        current, latest = result["current"], result["latest"]
        if not result["is_newer"]:
            self.status.setText(f"Aplicação atualizada: versão {current}.")
            if not silent:
                self._show_message("Atualizações", f"Você já está usando a versão mais recente ({current}).")
            return
        self.status.setText(f"Atualização disponível: versão {latest}.")
        answer = QMessageBox.question(self._window, "Atualização disponível", f"Versão instalada: {current}\nNova versão: {latest} ({result['source']})\n\nAbrir a página de download?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(result["url"]))

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
        # Connection details are edited in the modal connection dialog.
        # Keep this handler for compatibility with older actions that may still
        # call it, but do not recreate the removed main-window form.
        return

    def _hide_profile_details(self):
        return

    def _show_profile_details(self):
        return

    def _show_profile_dialog(self, index: int | None = None):
        """Create or edit a profile in a modal configuration window."""
        if index is not None and (index < 0 or index >= len(self.profiles)):
            return
        from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QFileDialog, QWidget

        profile = self.profiles[index] if index is not None else ConnectionProfile(name="", version="5")
        dialog = QDialog(self._window)
        dialog.setWindowTitle(f"{'Nova conexão' if index is None else 'Dados do cadastro — ' + profile.name}")
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
        password = QLineEdit(self._stored_password(profile.name) or ""); password.setEchoMode(QLineEdit.Password)
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

        database_browse.clicked.connect(browse_dialog_database)

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

        candidate = ConnectionProfile(
            name=name.text(), host=host.text(), port=port.value(), database=database.text(),
            version=version.currentText(), user=user.text(), role=role.text(),
            charset=charset.text(), favorite=favorite.isChecked(),
            isql_path=isql_path.text(), gbak_path=gbak_path.text(),
        )
        self._save_profile_record(candidate, password.text(), save_password.isChecked(), index)

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
        self._sync_sql_window_bar(index)
        self.editor = self.sql_tabs.widget(index) if index >= 0 else None
        if self.editor is not None:
            self._set_active_editor_widgets(self.editor)
            self.result_table = getattr(self.editor, "_result_table", None) or self.editor.property("result_table") or self.result_table
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
            # These controls belong to the editor that was just destroyed.
            # Drop the aliases so later actions cannot call deleted Qt
            # objects while the workspace is empty.
            self.query_profile_combo = None
            self.query_connection_status = None
            self.connection_badge = None
            self.query_cursor_status = None
            self.history_combo = None
            self.object_breadcrumb = None
            self.workspace_status = None
            self.commit_changes = None
            self.read_only_mode = None

    def _sync_sql_window_bar(self, active_index: int | None = None):
        """Keep the local SQL document bar aligned with the MDI windows."""
        bar = getattr(self, "sql_window_bar", None)
        if bar is None:
            return
        count = self.sql_tabs.count()
        bar.setVisible(count > 0)
        bar.blockSignals(True)
        try:
            while bar.count() > count:
                bar.removeTab(bar.count() - 1)
            while bar.count() < count:
                bar.addTab(self.sql_tabs.tabText(bar.count()))
            for index in range(count):
                title = self.sql_tabs.tabText(index) or f"SQL {index + 1}"
                bar.setTabText(index, title)
                editor = self.sql_tabs.widget(index)
                profile_name = editor.property("query_profile") if editor is not None else ""
                bar.setTabToolTip(index, f"{title}\nConexão: {profile_name or 'não definida'}")
            if active_index is None:
                active_index = self.sql_tabs.currentIndex()
            bar.setCurrentIndex(active_index if 0 <= active_index < count else -1)
        finally:
            bar.blockSignals(False)

    def _activate_sql_window_from_bar(self, index: int):
        if 0 <= index < self.sql_tabs.count():
            self.sql_tabs.setCurrentIndex(index)

    def _show_result_window(self):
        """Bring the shared result/diagnostic form back to the front."""
        if self.result_mdi_window is None:
            return
        self.result_mdi_window.show()
        self.result_mdi_window.showMaximized()
        self.result_mdi_window.setGeometry(self.sql_tabs.viewport().rect())
        self.result_mdi_window.raise_()

    def _show_sql_result(self):
        if self.editor is None:
            return
        document_tabs = getattr(self.editor, "_document_tabs", None) or self.editor.property("document_tabs")
        result_table = getattr(self.editor, "_result_table", None) or self.editor.property("result_table")
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
        try:
            editor = self.editor
            name = editor.property("query_profile") if editor is not None else ""
        except RuntimeError:
            name = ""
        for profile in self.profiles:
            if profile.name == name:
                return profile
        return self._profile_from_form()

    def _configure_sql_editor(self, editor):
        from PySide6.QtWidgets import QCompleter
        from PySide6.QtCore import QEvent, QObject, QStringListModel, Qt
        from PySide6.QtGui import QKeySequence, QShortcut
        editor.setFont(QFont("Consolas", 10))
        editor.setPlaceholderText("Execute uma instrução SQL...")
        highlighter = SqlHighlighter(editor.document())
        highlighter.set_theme(str(self._settings.value("theme", "light")) == "dark")
        editor.setProperty("sql_highlighter", highlighter)
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), editor)
        shortcut.activated.connect(self.execute_selected)
        editor.setProperty("execute_shortcut", shortcut)
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), editor)
        save_shortcut.activated.connect(lambda target=editor: (self.sql_tabs.setCurrentWidget(target), self.save_sql_file()))
        editor.setProperty("save_shortcut", save_shortcut)
        close_shortcut = QShortcut(QKeySequence("Ctrl+W"), editor)
        close_shortcut.activated.connect(lambda target=editor: self.close_sql_tab(self.sql_tabs.indexOf(target)))
        editor.setProperty("close_shortcut", close_shortcut)
        history_shortcut = QShortcut(QKeySequence("Ctrl+Shift+H"), editor)
        history_shortcut.activated.connect(lambda target=editor: (self.sql_tabs.setCurrentWidget(target), self._choose_history_query()))
        editor.setProperty("history_shortcut", history_shortcut)
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
        completer.activated[str].connect(lambda text, target=editor: self._insert_completion(target, text))
        class CompletionKeyFilter(QObject):
            def eventFilter(filter_self, watched, event):
                # Match the editor behavior users expect from SSMS: Tab or
                # Enter accepts the highlighted completion.  Only consume
                # the key while the popup is visible; otherwise Tab keeps its
                # normal editor behavior (indent/focus navigation).
                if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                    popup = completer.popup()
                    if popup.isVisible():
                        index = popup.currentIndex()
                        if not index.isValid() and completer.completionCount() > 0:
                            index = completer.completionModel().index(0, completer.completionColumn())
                        text = index.data(Qt.DisplayRole) if index.isValid() else ""
                        if text:
                            self._insert_completion(editor, str(text))
                            popup.hide()
                            return True
                return super().eventFilter(watched, event)
        completion_filter = CompletionKeyFilter(editor)
        editor.installEventFilter(completion_filter)
        completer.popup().installEventFilter(completion_filter)
        editor.setProperty("completion_key_filter", completion_filter)
        editor.textChanged.connect(lambda target=editor: self._auto_complete_sql(target))
        completion_shortcut = QShortcut(QKeySequence("Ctrl+Space"), editor)
        completion_shortcut.activated.connect(lambda target=editor: self._show_sql_completions(target))
        editor.setProperty("completion_model", completion_model)
        editor.setProperty("completion", completer)
        editor.setProperty("completion_shortcut", completion_shortcut)

    def _create_sql_document_tabs(self, editor):
        from PySide6.QtWidgets import QListWidget, QComboBox, QHBoxLayout, QLabel, QTableWidget, QTabWidget, QVBoxLayout, QWidget, QPushButton
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction, QKeySequence
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
        document_tabs.setObjectName("sqlDocumentTabs")
        document_tabs.setDocumentMode(True)
        document_tabs.setUsesScrollButtons(True)
        document_tabs.addTab(editor, "Editor")
        document_tabs.addTab(result_table, "Resultado")
        history_list = QListWidget()
        history_list.setObjectName("sqlHistoryList")
        history_list.setAlternatingRowColors(True)
        history_list.setToolTip("Duplo clique em uma consulta para restaurá-la no editor SQL")
        history_list.itemDoubleClicked.connect(lambda item, target=editor: self._restore_history_item(item, target))
        history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        history_list.customContextMenuRequested.connect(
            lambda position, listing=history_list, target=editor: self._history_context_menu(listing, position, target)
        )
        remove_history = QAction("Remover consulta selecionada", history_list)
        remove_history.setShortcut(QKeySequence.Delete)
        remove_history.setShortcutContext(Qt.WidgetShortcut)
        remove_history.triggered.connect(lambda _checked=False, listing=history_list: self._remove_selected_history_item(listing))
        history_list.addAction(remove_history)
        history_panel = QWidget()
        history_layout = QVBoxLayout(history_panel)
        history_layout.setContentsMargins(6, 6, 6, 6)
        history_hint = QLabel("Duplo clique restaura a consulta no editor. Use os botões para gerenciar o histórico.")
        history_hint.setObjectName("sectionHint")
        history_hint.setWordWrap(True)
        history_actions = QHBoxLayout()
        restore_history = QPushButton("Restaurar")
        restore_history.setToolTip("Restaurar a consulta selecionada no editor")
        restore_history.setObjectName("secondaryAction")
        restore_history.clicked.connect(lambda _checked=False, target=editor, listing=history_list: self._restore_selected_history_item(listing, target))
        copy_history = QPushButton("Copiar")
        copy_history.setToolTip("Copiar a consulta selecionada para a área de transferência")
        copy_history.setObjectName("secondaryAction")
        copy_history.clicked.connect(lambda _checked=False, listing=history_list: self._copy_selected_history_item(listing))
        clear_history = QPushButton("Limpar")
        clear_history.setToolTip("Limpar todo o histórico SQL")
        clear_history.setObjectName("secondaryAction")
        clear_history.clicked.connect(self._clear_query_history)
        history_actions.addWidget(restore_history)
        history_actions.addWidget(copy_history)
        history_actions.addWidget(clear_history)
        history_actions.addStretch()
        history_layout.addWidget(history_hint)
        history_layout.addLayout(history_actions)
        history_layout.addWidget(history_list, 1)
        document_tabs.addTab(history_panel, "Histórico SQL")
        history_list.setProperty("history_document_tabs", document_tabs)
        history_list.setProperty("history_panel", history_panel)
        document_tabs.setCurrentWidget(editor)
        document_tabs.setProperty("sql_editor", editor)
        editor.setProperty("document_tabs", document_tabs)
        editor.setProperty("result_table", result_table)

        # Per-document context stays inside the MDI child so multiple SQL
        # windows never appear to share one connection or cursor status.
        profile_combo = QComboBox()
        profile_combo.setMinimumWidth(200)
        profile_combo.setPlaceholderText("Selecionar conexão")
        profile_combo.setToolTip("Conexão usada por esta janela SQL")
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
        connection_row.addWidget(profile_combo)
        connection_row.addWidget(connection_status)
        # The tree and selected database already show the connection state.
        # Keep the compatibility label but avoid repeating a large status
        # pill in every SQL editor.
        connection_badge.setVisible(False)
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.addLayout(connection_row)
        shell_layout.addWidget(document_tabs, 1)
        editor_footer = QHBoxLayout()
        editor_footer.addStretch()
        editor_footer.addWidget(cursor_status)
        shell_layout.addLayout(editor_footer)
        shell.setProperty("sql_editor", editor)
        # Keep Python references to Qt widgets.  Dynamic Qt properties may
        # round-trip a QLabel/QComboBox as the base QWidget in packaged
        # PySide builds, which loses methods such as setText().
        editor._document_tabs = document_tabs
        editor._result_table = result_table
        editor._profile_combo = profile_combo
        editor._connection_status = connection_status
        editor._connection_badge = connection_badge
        editor._cursor_status = cursor_status
        editor._history_combo = history_combo
        editor._history_list = history_list
        editor._history_panel = history_panel
        editor._object_breadcrumb = breadcrumb
        editor._workspace_status = workspace_status
        editor.setProperty("profile_combo", profile_combo)
        editor.setProperty("connection_status", connection_status)
        editor.setProperty("connection_badge", connection_badge)
        editor.setProperty("cursor_status", cursor_status)
        editor.setProperty("history_combo", history_combo)
        editor.setProperty("history_list", history_list)
        editor.setProperty("history_panel", history_panel)
        editor.setProperty("object_breadcrumb", breadcrumb)
        editor.setProperty("workspace_status", workspace_status)
        self._query_profile_combos.append(profile_combo)
        self._history_combos.append(history_combo)
        self._history_lists.append(history_list)
        self._refresh_history_list(history_list)
        self._set_active_editor_widgets(editor)
        return shell, result_table

    def _set_active_editor_widgets(self, editor):
        """Point compatibility aliases at the currently active SQL form."""
        if editor is None:
            return
        ref = lambda name, prop: getattr(editor, name, None) or editor.property(prop)
        self.query_profile_combo = ref("_profile_combo", "profile_combo")
        self.query_connection_status = ref("_connection_status", "connection_status")
        self.connection_badge = ref("_connection_badge", "connection_badge")
        self.query_cursor_status = ref("_cursor_status", "cursor_status")
        self.history_combo = ref("_history_combo", "history_combo")
        self.object_breadcrumb = ref("_object_breadcrumb", "object_breadcrumb")
        self.workspace_status = ref("_workspace_status", "workspace_status")
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
        more_button = QToolButton()
        more_button.setText("Mais")
        more_button.setObjectName("workspaceAction")
        more_button.setToolTip("Ações adicionais desta consulta")
        more_button.setPopupMode(QToolButton.InstantPopup)
        more_menu = QMenu(more_button)
        more_menu.setMinimumWidth(340)
        more_menu.setStyleSheet("QMenu::item { padding: 6px 48px 6px 12px; }")
        execute_action = more_menu.addAction("Executar SQL")
        execute_action.triggered.connect(lambda: self._execute_editor(editor))
        selection_action = more_menu.addAction("Executar seleção")
        selection_action.setShortcut("Ctrl+Shift+F5")
        selection_action.triggered.connect(lambda: self._execute_selection_editor(editor))
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
        for button in (more_button,):
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
        if getattr(self, "result_mdi_window", None) is not None:
            self.result_mdi_window.hide()
        try:
            selected_name = self.query_profile_combo.currentText() if self.query_profile_combo is not None else ""
        except RuntimeError:
            # The previous editor owns this combo; closing the last SQL
            # document also destroys it.  Recreate the binding for the new
            # editor instead of calling a deleted Qt object.
            self.query_profile_combo = None
            selected_name = ""
        if not selected_name and self.profiles:
            selected_name = self.profiles[0].name
        editor = QTextEdit()
        self._configure_sql_editor(editor)
        document_tabs, result_table = self._create_sql_document_tabs(editor)
        editor.setProperty("query_profile", selected_name)
        if self.query_profile_combo is not None:
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
        self._sync_sql_window_bar(index)

    def _close_all_sql_tabs(self):
        self.sql_documents.close_all(self._new_sql_tab)
        self.editor = None
        # Keep the auxiliary document bar and workspace state synchronized
        # after the last MDI child is removed.
        self._sync_sql_window_bar(-1)
        if self.result_mdi_window is not None:
            self.result_mdi_window.hide()
        if self.workspace_status is not None:
            self.workspace_status.setText("Nenhuma consulta SQL aberta")
        self.status.setText("Todas as janelas SQL foram fechadas.")

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
        try:
            typed_password = self.password.text()
        except RuntimeError:
            # The profile form is modal/legacy and may have been destroyed
            # after the last SQL document was closed.
            typed_password = ""
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
            self.status.setText(f"Conexão '{self.profiles[index].name}' selecionada. Duplo clique para conectar.")
            if getattr(self, "object_breadcrumb", None) is not None:
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
        try:
            entered = self.password.text()
        except RuntimeError:
            entered = ""
        return entered or self._stored_password(profile_name) or ""

    def close_sql_tab(self, index: int):
        self.sql_documents.close(index, self._new_sql_tab)
        if self.sql_tabs.count() == 0 and self.result_mdi_window is not None:
            self.result_mdi_window.hide()
        if self.sql_tabs.count() == 0:
            self.editor = None
            self._sync_sql_window_bar(-1)
            if self.workspace_status is not None:
                self.workspace_status.setText("Nenhuma consulta SQL aberta")

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

        live_combos = []
        for combo in self._history_combos:
            try:
                combo.blockSignals(True)
                combo.clear()
                for item in self.query_history:
                    label = " ".join(item.split())
                    combo.addItem(label[:120], item)
                combo.blockSignals(False)
                live_combos.append(combo)
            except RuntimeError:
                continue
        self._history_combos = live_combos
        live_lists = []
        for history_list in self._history_lists:
            try:
                self._refresh_history_list(history_list)
                live_lists.append(history_list)
            except RuntimeError:
                continue
        self._history_lists = live_lists
        self._settings.setValue("query_history", json.dumps(self.query_history, ensure_ascii=False))
        self._settings.sync()

    def _refresh_history_list(self, history_list):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem

        if history_list is None:
            return
        history_list.clear()
        for query in self.query_history:
            label = " ".join(query.split()) or "(consulta vazia)"
            item = QListWidgetItem(label[:160])
            item.setData(Qt.UserRole, query)
            item.setToolTip(query)
            history_list.addItem(item)
        document_tabs = history_list.property("history_document_tabs")
        history_panel = history_list.property("history_panel")
        if document_tabs is not None and history_panel is not None:
            index = document_tabs.indexOf(history_panel)
            if index >= 0:
                count = history_list.count()
                document_tabs.setTabText(index, f"Histórico SQL ({count})" if count else "Histórico SQL")

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

        headers = ["Data", "Operação", "Conexão", "Origem", "Destino", "Resultado", "Detalhe"]
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

    def _restore_history_item(self, item, editor=None):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox

        editor = editor or self.editor
        query = item.data(Qt.UserRole) if item is not None else None
        if not query or editor is None:
            return
        current = editor.toPlainText().strip()
        if current and current != str(query).strip():
            answer = QMessageBox.question(
                self._window,
                "Restaurar consulta do histórico",
                "O editor SQL já contém texto. Deseja sobrescrever a consulta atual?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        editor.setPlainText(str(query))
        document_tabs = editor.property("document_tabs")
        if document_tabs is not None:
            document_tabs.setCurrentWidget(editor)
        self.status.setText("Consulta restaurada do histórico.")

    def _restore_selected_history_item(self, history_list, editor=None):
        item = history_list.currentItem() if history_list is not None else None
        if item is None:
            self.status.setText("Selecione uma consulta no histórico para restaurar.")
            return
        self._restore_history_item(item, editor)

    def _copy_selected_history_item(self, history_list):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        item = history_list.currentItem() if history_list is not None else None
        query = item.data(Qt.UserRole) if item is not None else None
        if not query:
            self.status.setText("Selecione uma consulta no histórico para copiar.")
            return
        QApplication.clipboard().setText(str(query))
        self.status.setText("Consulta do histórico copiada para a área de transferência.")

    def _history_context_menu(self, history_list, position, editor=None):
        from PySide6.QtWidgets import QMenu

        item = history_list.itemAt(position) if history_list is not None else None
        if item is not None:
            history_list.setCurrentItem(item)
        menu = QMenu(history_list)
        restore = menu.addAction("Restaurar no editor")
        copy = menu.addAction("Copiar SQL")
        remove = menu.addAction("Remover do histórico")
        chosen = menu.exec(history_list.viewport().mapToGlobal(position))
        if chosen is restore:
            self._restore_selected_history_item(history_list, editor)
        elif chosen is copy:
            self._copy_selected_history_item(history_list)
        elif chosen is remove:
            self._remove_selected_history_item(history_list)

    def _remove_selected_history_item(self, history_list):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox

        item = history_list.currentItem() if history_list is not None else None
        query = item.data(Qt.UserRole) if item is not None else None
        if not query:
            self.status.setText("Selecione uma consulta no histórico para remover.")
            return
        answer = QMessageBox.question(
            self._window,
            "Remover consulta do histórico",
            "Remover a consulta selecionada do histórico?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.query_history = [entry for entry in self.query_history if entry != str(query)]
        self._refresh_query_history()
        self.status.setText("Consulta removida do histórico.")

    def _clear_query_history(self):
        from PySide6.QtWidgets import QMessageBox

        if not self.query_history:
            self.status.setText("O histórico SQL já está vazio.")
            return
        answer = QMessageBox.question(
            self._window,
            "Limpar histórico SQL",
            "Deseja remover todas as consultas salvas no histórico?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.query_history = []
        self._refresh_query_history()
        self.status.setText("Histórico SQL limpo.")

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

    def _execute_selection_editor(self, editor):
        if editor is None:
            self.execute_selection()
            return
        index = self.sql_tabs.indexOf(editor)
        if index < 0:
            self.status.setText("A janela SQL selecionada não está disponível.")
            return
        self.sql_tabs.setCurrentIndex(index)
        self._sync_editor(index)
        self._set_active_editor_widgets(editor)
        self.execute_selection()

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
        self._log_event("Conexão identificada para abrir", selected=selected, profiles=len(self.profiles))
        # When activation comes from the list, use the saved object directly.
        # This avoids relying on the form repaint completing before the worker
        # starts, which was the reason the button appeared to have no effect.
        profile = self.profiles[selected] if 0 <= selected < len(self.profiles) else self._profile_from_form()
        # The tree click already selected this profile. Calling select_profile
        # again here can block on Windows Credential Manager before the worker
        # even starts; the Testar conexão button does not repeat that lookup.
        errors = profile.validate()
        self._log_event("Conexão validada para abrir", profile=profile.name, errors=len(errors))
        if errors:
            message = " ".join(errors)
            self._log_event("Conexão inválida ao abrir", errors=message)
            return None, message
        # Selecting a tree profile already loads its stored password into the
        # form. Avoid querying Windows Credential Manager a second time here:
        # that lookup can block in packaged Windows builds before the worker
        # starts. Only use the credential fallback when no profile item was
        # selected (for example when opening directly from the form).
        password = self._stored_password(profile.name) if 0 <= selected < len(self.profiles) else self._password_for(profile)
        self._log_event("Senha preparada para abrir", profile=profile.name, password_present=bool(password), selected=selected)
        return (profile, password), ""

    def open_profile(self, selected_index: int | None = None):
        """Open the selected database, like opening a connection in IBExpert."""
        # A connection can be opened even when the user closed every SQL
        # document.  Recreate the working document before resolving the
        # connection so all of the editor aliases and connection controls are
        # available to the normal open flow.
        if self.sql_tabs.count() == 0:
            self._log_event("Nenhuma janela SQL aberta; criando janela para conexão")
            self._new_sql_tab()
        current_item = self.profile_list.currentItem()
        self._log_event("open_profile chamado", current_item=current_item.text(0) if current_item else "", form_name=current_item.text(0) if current_item else "", form_database="")
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
        if self.sql_tabs.count() == 0:
            self._new_sql_tab()
        if self.editor is not None and self._opening_profile_name:
            self.editor.setProperty("query_profile", self._opening_profile_name)
            self._sync_editor(self.sql_tabs.currentIndex())
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
        # A database object can be opened directly after all SQL windows were
        # closed.  Ensure there is a live editor before writing the DDL.
        try:
            current_editor = self.editor
        except RuntimeError:
            current_editor = None
            self.editor = None
        if new_tab or current_editor is None:
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
        self.result_summary.setText(f"Dados: {len(result.rows)} linha(s) · página {page + 1}")
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
        self.sidebar_status.setText(f"Ativos: {connected_count} · Cadastros: {len(self.profiles)}")
        self.sidebar_status.setToolTip(f"Bancos conectados: {connected_count}. Cadastros disponíveis: {len(self.profiles)}.")
        self.target_profile.clear()
        self.target_profile.addItems([p.name for p in self.profiles])
        live_combos = []
        for combo in self._query_profile_combos:
            try:
                editor = combo.property("sql_editor")
            except RuntimeError:
                continue
            current_query_name = editor.property("query_profile") if editor is not None else ""
            combo.blockSignals(True)
            combo.clear()
            combo.addItems([p.name for p in self.profiles])
            if current_query_name:
                index = combo.findText(current_query_name)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
            live_combos.append(combo)
        self._query_profile_combos = live_combos
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
        menu.setMinimumWidth(260)
        menu.setStyleSheet("QMenu::item { padding: 6px 18px 6px 12px; }")
        profile_index = self._profile_index_for_item(item)
        if item.parent() is None and 0 <= profile_index < len(self.profiles):
            profile = self.profiles[profile_index]
            show_details = menu.addAction("Alterar cadastro...")
            show_details.triggered.connect(lambda _checked=False, selected=profile_index: self._show_profile_dialog(selected))
            copy_name = menu.addAction("Copiar nome do banco")
            copy_name.triggered.connect(lambda _checked=False, value=profile.name: self._copy_tree_value(value, "Nome do banco"))
            copy_database = menu.addAction("Copiar caminho ou alias")
            copy_database.triggered.connect(lambda _checked=False, value=profile.database: self._copy_tree_value(value, "Caminho ou alias"))
            monitor = menu.addAction("Monitorar consultas")
            monitor.setToolTip("Abrir atividade e consultas em execução deste banco")
            monitor.triggered.connect(lambda _checked=False, selected=profile_index: self._open_activity_for_profile(selected))
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
        origin = self.profile_list.viewport().mapToGlobal(position)
        self._popup_menu_fitting(menu, origin, self.profile_list)

    def _show_profile_menu(self, button, menu):
        """Show the connection menu inside the available screen geometry."""
        from PySide6.QtCore import QPoint

        origin = button.mapToGlobal(QPoint(0, button.height()))
        self._popup_menu_fitting(menu, origin, button)

    def _popup_menu_fitting(self, menu, origin, reference_widget=None):
        """Open a menu without allowing it to extend beyond the active screen."""
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QGuiApplication

        menu.ensurePolished()
        menu_size = menu.sizeHint()
        # Recalculate after all actions are added so long labels never get
        # clipped by a narrow platform default width.
        menu.setMinimumWidth(max(menu.minimumWidth(), menu_size.width() + 12))
        menu.adjustSize()
        menu_size = menu.sizeHint()
        screen = QGuiApplication.screenAt(origin)
        if screen is None and reference_widget is not None:
            screen = reference_widget.screen()
        available = screen.availableGeometry() if screen is not None else None
        x, y = origin.x(), origin.y()
        if available is not None:
            if y + menu_size.height() > available.bottom():
                if reference_widget is not None:
                    y = reference_widget.mapToGlobal(QPoint(0, 0)).y() - menu_size.height()
                else:
                    y = available.bottom() - menu_size.height()
            x = max(available.left(), min(x, available.right() - menu_size.width()))
            y = max(available.top(), min(y, available.bottom() - menu_size.height()))
        menu.popup(QPoint(x, y))

    def _copy_tree_value(self, value: str, label: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(value)
        self.status.setText(f"{label} copiado para a área de transferência.")

    def disconnect_selected(self):
        from PySide6.QtWidgets import QMessageBox

        index = self._profile_index_for_item()
        if index < 0 or index >= len(self.profiles):
            self._show_message("Desconectar banco", "Selecione um banco conectado na árvore.", warning=True)
            return
        profile = self.profiles[index]
        open_queries = []
        for query_index in range(self.sql_tabs.count()):
            editor = self.sql_tabs.widget(query_index)
            try:
                if editor is not None and editor.property("query_profile") == profile.name:
                    open_queries.append(query_index)
            except RuntimeError:
                continue
        if open_queries:
            answer = QMessageBox.question(
                self._window,
                "Desconectar banco",
                f"Há {len(open_queries)} janela(s) SQL usando '{profile.name}'.\n\n"
                "Deseja fechar todas as janelas SQL e desconectar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                self.status.setText("Desconexão cancelada; as janelas SQL foram mantidas.")
                return
            self._close_all_sql_tabs()
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

    def _browse_database_file(self):
        from PySide6.QtWidgets import QFileDialog

        start_dir = self.database.text().strip()
        if start_dir and not Path(start_dir).is_dir():
            start_dir = str(Path(start_dir).parent)
        filename, _ = QFileDialog.getOpenFileName(
            self._window,
            "Selecionar arquivo do banco Firebird",
            start_dir or str(Path.home()),
            "Bancos Firebird (*.fdb *.FDB *.gdb *.GDB);;Todos os arquivos (*.*)",
        )
        if filename:
            self.database.setText(filename)
            self.status.setText(f"Arquivo selecionado: {filename}")

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
        open_queries = []
        for query_index in range(self.sql_tabs.count()):
            editor = self.sql_tabs.widget(query_index)
            try:
                if editor is not None and editor.property("query_profile") == profile.name:
                    open_queries.append(query_index)
            except RuntimeError:
                continue
        confirmation = QMessageBox(self._window)
        confirmation.setWindowTitle("Confirmar exclusão do cadastro")
        confirmation.setText(f"Excluir o cadastro '{profile.name}'?")
        details = ["Somente o cadastro da conexão será removido. O arquivo do banco não será excluído."]
        if profile.name in self.connected_profiles:
            details.append("O banco está conectado e será desconectado.")
        if open_queries:
            details.append(f"Há {len(open_queries)} janela(s) SQL aberta(s); elas serão fechadas.")
        confirmation.setInformativeText("\n".join(details))
        confirmation.setIcon(QMessageBox.Warning)
        confirmation.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        confirmation.setDefaultButton(QMessageBox.No)
        if confirmation.exec() != QMessageBox.Yes:
            return
        if open_queries:
            self._close_all_sql_tabs()
        self.connected_profiles.discard(profile.name)
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
        for widget, action in (
            (getattr(self, "name", None), "clear"), (getattr(self, "database", None), "clear"),
            (getattr(self, "role", None), "clear"), (getattr(self, "password", None), "clear"),
        ):
            try:
                if widget is not None:
                    getattr(widget, action)()
            except RuntimeError:
                pass
        for widget in (getattr(self, "save_password", None), getattr(self, "favorite", None)):
            try:
                if widget is not None:
                    widget.setChecked(False)
            except RuntimeError:
                pass
        self.status.setText("Cadastro excluído. O arquivo do banco foi mantido.")

    def select_profile(self, index: int):
        if index < 0 or index >= len(self.profiles): return
        p = self.profiles[index]
        self._selected_profile_index = index
        # These legacy fields are no longer displayed on the main window and
        # may have been destroyed with an old SQL form.  Selecting a tree item
        # must still work; the saved profile object is the source of truth.
        fields = ((getattr(self, "name", None), p.name), (getattr(self, "host", None), p.host), (getattr(self, "database", None), p.database), (getattr(self, "user", None), p.user), (getattr(self, "role", None), p.role), (getattr(self, "charset", None), p.charset), (getattr(self, "isql_path", None), p.isql_path), (getattr(self, "gbak_path", None), p.gbak_path))
        for widget, value in fields:
            try:
                if widget is not None:
                    widget.setText(value)
            except RuntimeError:
                pass
        stored_password = self._stored_password(p.name)
        for action in (lambda: self.password.setText(stored_password or ""), lambda: self.save_password.setChecked(bool(stored_password)), lambda: self.favorite.setChecked(bool(p.favorite)), lambda: self.port.setValue(p.port), lambda: self.version.setCurrentText(p.version)):
            try:
                action()
            except RuntimeError:
                pass
        self._update_query_connection_status()

    def _profile_from_form(self):
        try:
            return ConnectionProfile(self.name.text(), self.host.text(), self.port.value(), self.database.text(), self.version.currentText(), self.user.text(), role=self.role.text(), charset=self.charset.text(), favorite=self.favorite.isChecked(), isql_path=self.isql_path.text(), gbak_path=self.gbak_path.text())
        except RuntimeError:
            # The connection form is modal and its widgets may have already
            # been deleted.  The selected tree profile remains authoritative
            # for object preview, DDL loading and database operations.
            selected = getattr(self, "_selected_profile_index", -1)
            if 0 <= selected < len(self.profiles):
                return self.profiles[selected]
            raise

    def save_profile(self):
        self._save_profile_record(self._profile_from_form(), self._password_for(), self.save_password.isChecked(), self._profile_index_for_item())

    def _save_profile_record(self, profile, password, save_password, selected):
        errors = profile.validate()
        if errors:
            message = " ".join(errors)
            self.status.setText(message)
            self._show_message("Conexão inválida", message, warning=True)
            return
        duplicate = next((item for index, item in enumerate(self.profiles) if index != selected and item.name.casefold() == profile.name.casefold()), None)
        if duplicate is not None:
            message = f"Já existe um banco configurado com o nome '{duplicate.name}'. Escolha outro nome."
            self.status.setText(message)
            self._show_message("Nome duplicado", message, warning=True)
            return
        previous_name = self.profiles[selected].name if 0 <= selected < len(self.profiles) else None
        if 0 <= selected < len(self.profiles): self.profiles[selected] = profile
        else: self.profiles.append(profile)
        if previous_name and previous_name != profile.name:
            if previous_name in self.connected_profiles:
                self.connected_profiles.discard(previous_name)
                self.connected_profiles.add(profile.name)
            if previous_name in self.profile_objects:
                self.profile_objects[profile.name] = self.profile_objects.pop(previous_name)
            for combo in tuple(self._query_profile_combos):
                try:
                    editor = combo.property("sql_editor")
                    if editor is not None and editor.property("query_profile") == previous_name:
                        editor.setProperty("query_profile", profile.name)
                except RuntimeError:
                    continue
        self.store.save(self.profiles)
        self._log_event("Conexão salva", profile=profile.name, count=len(self.profiles), profile_store=str(self.store.path))
        from .credentials import CredentialStore
        try:
            credentials = CredentialStore()
            if save_password and password:
                credentials.set(profile.name, password)
                message = "Conexão e senha criptografada salvas."
            else:
                credentials.delete(profile.name)
                message = "Conexão salva sem senha."
            if previous_name and previous_name != profile.name:
                credentials.delete(previous_name)
        except Exception as exc:
            message = f"Conexão salva, mas não foi possível proteger a senha: {exc}"
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
        form.addRow("Conexão", QLabel(profile.name))
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
        active_editor = self.sql_tabs.currentWidget() if self.sql_tabs.count() else None
        if active_editor is not None and active_editor.property("document_tabs") is None:
            active_editor = None
        if active_editor is not None and active_editor is not self.editor:
            self._sync_editor(self.sql_tabs.currentIndex())
        editor = active_editor or self.editor
        if editor is None:
            self.status.setText("Abra uma janela SQL antes de executar.")
            self._log_event("Execução SQL ignorada", reason="nenhuma janela SQL ativa")
            return
        self._set_active_editor_widgets(editor)
        self._execute_sql_text(editor.toPlainText())

    def _execute_editor(self, editor):
        """Activate an editor and execute it through the single SQL path."""
        if editor is None:
            self.execute_selected()
            return
        index = self.sql_tabs.indexOf(editor)
        if index < 0:
            self.status.setText("A janela SQL selecionada não está disponível.")
            return
        self.sql_tabs.setCurrentIndex(index)
        self._sync_editor(index)
        self._set_active_editor_widgets(editor)
        self._execute_sql_text(editor.toPlainText())

    def _execute_sql_text(self, sql_text: str):
        from PySide6.QtWidgets import QTableWidgetItem
        from .sql import execute_sql, is_mutating_statement

        if not sql_text or not sql_text.strip():
            self.status.setText("Digite uma instrução SQL antes de executar.")
            if self.editor is not None:
                self.editor.setFocus()
            return
        statement = sql_text.lstrip().upper()
        changes_data = is_mutating_statement(sql_text)
        commit_control = self.commit_changes
        read_only_control = self.read_only_mode
        if commit_control is None and self.editor is not None:
            controls = self.editor.property("execution_controls") or ()
            commit_control = controls[0] if len(controls) > 0 else None
            read_only_control = controls[1] if len(controls) > 1 else None
        commit = bool(commit_control.isChecked()) if commit_control is not None else False
        if changes_data and read_only_control is not None and read_only_control.isChecked():
            self.status.setText("Modo somente leitura: a instrução foi bloqueada.")
            self._log_event("SQL bloqueado por somente leitura", statement=statement.split(None, 1)[0] if statement else "")
            return
        profile = self._query_profile()
        if not profile.name or not profile.database:
            message = "Selecione uma conexão válida antes de executar a SQL."
            self.status.setText(message)
            self._show_message("Conexão SQL", message, warning=True)
            return
        explicit_transaction = self._transaction_session is not None and self._transaction_session.active
        if explicit_transaction and self._transaction_profile_name != profile.name:
            self.status.setText(f"A transação aberta pertence à conexão '{self._transaction_profile_name}'. Faça Commit/Rollback antes de trocar de banco.")
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
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        self.status.setText("Executando SQL...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            result = self._transaction_session.execute(sql_text) if explicit_transaction else execute_sql(profile, sql_text, self._password_for(profile), commit=commit)
        except Exception as exc:
            detail = str(exc)
            self._log_event("Falha inesperada na execução SQL", profile=profile.name, statement=statement.split(None, 1)[0] if statement else "", error=detail)
            self.status.setText(f"Falha ao executar SQL: {detail}")
            self.result_summary.setText("Resultado: falha na execução")
            self._show_message("Falha ao executar SQL", detail, warning=True)
            return
        finally:
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        self._log_event("SQL executado", profile=profile.name, statement=statement.split(None, 1)[0] if statement else "", commit=commit, ok=result.ok, rows=len(result.rows), elapsed_ms=f"{result.elapsed_ms:.1f}", detail=result.message)
        self._add_query_history(sql_text)
        if not result.ok:
            self._show_message("Falha ao executar SQL", result.message, warning=True)
        suffix = " Transação aberta; escolha Commit ou Rollback." if explicit_transaction and result.ok else (" Alterações confirmadas." if changes_data and commit and result.ok else (" Alterações desfeitas (modo seguro)." if changes_data and result.ok else ""))
        self.status.setText(f"{result.message} ({result.elapsed_ms:.1f} ms)." + suffix)
        self.result_summary.setText(f"Resultado: {'OK' if result.ok else 'falha'} · {len(result.rows)} linha(s) · {result.elapsed_ms:.1f} ms")
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
        from PySide6.QtWidgets import QApplication

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
        QApplication.setOverrideCursor(Qt.WaitCursor)
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
        from PySide6.QtWidgets import QApplication
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

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
            self.status.setText("Configure o caminho do isql na conexão antes de executar um arquivo.")
            self._show_message("Executar script", "Configure o caminho do isql.exe na conexão antes de executar um arquivo.", warning=True)
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

        selected_index = self._profile_index_for_item()
        profile_name = ""
        if 0 <= selected_index < len(self.profiles):
            profile_name = self.profiles[selected_index].name
        elif self.editor is not None:
            profile_name = self.editor.property("query_profile") or ""
        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None and self.profiles:
            profile = self.profiles[0]
        if profile is None:
            self._show_message("Gestão de usuários", "Cadastre uma conexão de banco antes de abrir esta tela.", warning=True)
            return
        admin_password = self._password_for(profile)
        dialog = QDialog(self._window)
        dialog.setWindowTitle(f"Usuários · {profile.name}")
        dialog.resize(640, 420)
        layout = QVBoxLayout(dialog)
        connection_row = QHBoxLayout()
        connection_row.addWidget(QLabel("Conexão"))
        connection_combo = QComboBox()
        connection_combo.addItems([item.name for item in self.profiles])
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
            selected = next((item for item in self.profiles if item.name == name), None)
            if selected is None:
                return
            profile = selected
            admin_password = self._password_for(profile)
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

        connection_combo.currentTextChanged.connect(select_connection)
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
            self._show_toast("Backup concluído com sucesso.")
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

    def restore_backup_file(self, source):
        """Open a .fbk/.gbk received from Windows and prepare its restore."""
        from .backup import run_gbak
        from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QSpinBox, QVBoxLayout, QLabel, QWidget, QPushButton

        source = Path(source).expanduser()
        if not source.exists():
            self._show_message("Restaurar backup", f"Arquivo não encontrado:\n{source}", warning=True)
            return
        dialog = QDialog(self._window)
        dialog.setWindowTitle(f"Restaurar backup — {source.name}")
        dialog.setModal(True)
        dialog.resize(620, 430)
        form = QFormLayout()
        profile_choice = QComboBox()
        profile_choice.addItem("Nova conexão")
        profile_choice.addItems([item.name for item in self.profiles])
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
        target_button.clicked.connect(lambda: self._choose_restore_target(dialog, target))
        def load_restore_profile(profile_name):
            selected = next((item for item in self.profiles if item.name == profile_name), None)
            if selected is None:
                return
            name.setText(f"{selected.name} restaurado")
            host.setText(selected.host); port.setValue(selected.port); version.setCurrentText(selected.version)
            user.setText(selected.user); gbak_path.setText(selected.gbak_path)
            password.setText(self._stored_password(selected.name) or "")
        profile_choice.currentTextChanged.connect(load_restore_profile)
        layout = QVBoxLayout(dialog); layout.addWidget(hint); layout.addLayout(form); layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        candidate = ConnectionProfile(name=name.text(), host=host.text(), port=port.value(), database=target.text(), version=version.currentText(), user=user.text(), isql_path="", gbak_path=gbak_path.text())
        errors = candidate.validate()
        if errors:
            self._show_message("Restaurar backup", " ".join(errors), warning=True)
            return
        target_path = Path(target.text()).expanduser()
        entered_password = password.text()
        register_profile = save_profile.isChecked()
        store_password = save_password.isChecked()
        self._start_background_operation(
            "Restore",
            lambda: run_gbak(candidate, "restore", source, target_path, entered_password, Path(gbak_path.text())),
            lambda result: self._finish_restore_operation(result, candidate, str(source), str(target_path), entered_password, register_profile, store_password),
        )

    @staticmethod
    def _choose_restore_target(parent, target):
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(parent, "Salvar banco restaurado", target.text(), "Banco Firebird (*.fdb *.gdb);;Todos (*.*)")
        if filename:
            target.setText(filename)

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
            self._show_toast("Exportação SQL concluída com sucesso.")
        else:
            self._log_event("Exportação SQL falhou", profile=profile.name, filename=result.filename, error=result.error)
            self.status.setText(f"Exportação SQL falhou: {result.error}")
            self._show_message("Falha na exportação SQL", result.error)

    def _finish_restore_operation(self, result, profile, source, target, password, register_profile=False, save_password=False):
        output, error = self._operation_result_text(result)
        ok = bool(getattr(result, "ok", False)) if not isinstance(result, Exception) else False
        self._record_backup_history("Restore", profile, str(source), str(target), ok, error or output[-300:])
        self._log_event("Restore concluído" if ok else "Restore falhou", profile=profile.name, source=str(source), target=str(target), ok=ok, error=error)
        if self.editor is not None:
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
            if register_profile:
                selected = next((index for index, item in enumerate(self.profiles) if item.name.casefold() == profile.name.casefold()), -1)
                self._save_profile_record(profile, password, save_password, selected)
            self.status.setText("Restore concluído e banco restaurado validado.")
            self._show_toast("Restore concluído com sucesso.")
            self._log_event("Restore validado", target=str(target))
        else:
            message = f"Restore concluído, mas a validação falhou: {validation.message}"
            self.status.setText(message)
            self._show_message("Restore com aviso", message, warning=True)
            self._log_event("Restore com falha na validação", target=str(target), error=validation.message)

    def _show_toast(self, message: str, duration: int = 3500):
        """Show a transient non-blocking confirmation near the status bar."""
        from PySide6.QtCore import QTimer, Qt
        from PySide6.QtWidgets import QLabel

        if self._toast is not None:
            self._toast.deleteLater()
        toast = QLabel(message, self._window)
        toast.setObjectName("toastMessage")
        toast.setAlignment(Qt.AlignCenter)
        toast.setStyleSheet(
            "QLabel#toastMessage { background: #1f7a45; color: #ffffff; "
            "border: 1px solid #8bd3a8; border-radius: 6px; padding: 8px 14px; font-weight: 600; }"
        )
        toast.adjustSize()
        margin = 18
        toast.move(max(margin, self._window.width() - toast.width() - margin), self._window.height() - toast.height() - 48)
        toast.show()
        toast.raise_()
        self._toast = toast
        def clear_toast():
            if self._toast is toast:
                self._toast = None
            toast.deleteLater()
        QTimer.singleShot(duration, clear_toast)

    def inspect_schema(self):
        from .catalog import load_schema
        profile = self._query_profile()
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
            self.status.setText("Configure o caminho do isql na conexão antes de analisar o plano.")
            self._show_message("Ver plano", "Configure o caminho do isql.exe na conexão antes de analisar o plano.", warning=True)
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
        profile = self._query_profile()
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

        # Reopen the shared result form immediately.  After the user closes
        # the MDI child, the activity tab is still selected and no tab-change
        # signal is emitted on the next request; waiting for the worker would
        # leave the click apparently without effect.
        try:
            self.result_tabs.setCurrentWidget(self.activity_panel)
            self._show_result_window()
            self._log_event("Painel de atividade reaberto")
        except RuntimeError:
            # The normal window remains usable even if a closing event is
            # currently being processed by Qt.
            pass

        # The main profile form is hidden during normal SQL work. Prefer the
        # connection assigned to the active SQL document so the monitor never
        # refreshes a different or stale database profile.
        profile = None
        try:
            profile = self._query_profile() if self.editor is not None else None
        except RuntimeError:
            profile = None
        if profile is None:
            selected = getattr(self, "_selected_profile_index", -1)
            if 0 <= selected < len(self.profiles):
                profile = self.profiles[selected]
            else:
                profile = self._profile_from_form()
        password = self._password_for(profile)
        self._start_background_operation(
            "Painel do banco",
            lambda: (inspect_health(profile, password), list_statements(profile, password)),
            lambda result: self._finish_activity_operation(result, profile),
        )

    def _open_activity_for_profile(self, profile_index: int):
        """Open the activity monitor for the profile chosen in the tree."""
        if 0 <= profile_index < len(self.profiles):
            self.select_profile(profile_index)
        self.inspect_activity()

    def _toggle_activity_auto_refresh(self, enabled: bool):
        if enabled:
            self.activity_refresh_timer.start()
            self.inspect_activity()
            self.status.setText("Atualização automática do painel ativada.")
        else:
            self.activity_refresh_timer.stop()
            self.status.setText("Atualização automática do painel desativada.")

    def _set_activity_refresh_interval(self, interval_ms):
        try:
            interval = max(1000, int(interval_ms))
        except (TypeError, ValueError):
            return
        self._settings.setValue("activity_refresh_interval", interval)
        self._settings.sync()
        seconds = interval // 1000
        self.activity_auto_refresh.setText(f"Auto {seconds} s")
        self.activity_auto_refresh.setToolTip(f"Atualizar automaticamente a cada {seconds} segundos")
        timer = getattr(self, "activity_refresh_timer", None)
        if timer is not None:
            timer.setInterval(interval)
            if self.activity_auto_refresh.isChecked():
                timer.start()

    def _finish_activity_operation(self, result, profile):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QTableWidgetItem
        from datetime import datetime

        class DurationItem(QTableWidgetItem):
            def __lt__(self, other):
                left = self.data(Qt.UserRole)
                right = other.data(Qt.UserRole) if other is not None else None
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return float(left) < float(right)
                return super().__lt__(other)

        if isinstance(result, Exception):
            self._log_event("Falha ao ler atividade", profile=profile.name, error=str(result))
            self.status.setText(f"Falha ao ler informações do banco: {result}")
            self._show_message("Falha ao ler atividade", str(result))
            return
        report, statements = result
        self.activity_profile_name = profile.name
        selected_item = self.activity_table.item(self.activity_table.currentRow(), 0)
        selected_statement_id = selected_item.text() if selected_item is not None else ""
        metrics = report.metrics
        size = metrics.get("estimated_size_mb")
        lines = [
            f"Banco: {profile.name}",
            f"Tamanho estimado: {size:.1f} MB" if isinstance(size, (int, float)) else "Tamanho estimado: indisponível",
            f"Página: {metrics.get('page_size') or 'N/D'} bytes · páginas: {metrics.get('pages') or 'N/D'}",
            f"ODS: {metrics.get('ods_major') or 'N/D'}.{metrics.get('ods_minor') or 'N/D'} · conexões: {metrics.get('attachments') or 0}",
            f"Transações: oldest={metrics.get('oldest_transaction') or 'N/D'} · active={metrics.get('oldest_active') or 'N/D'} · next={metrics.get('next_transaction') or 'N/D'}",
            f"Consultas em execução: {len(statements)}",
            "Estado: nenhuma consulta em execução neste instante" if not statements else "Estado: consultas em execução encontradas",
            f"Última atualização: {datetime.now():%d/%m/%Y %H:%M:%S}",
            "Senha: não exposta pelo monitoramento",
        ]
        self.activity_metrics.setPlainText("\n".join(lines))
        headers = ["ID", "Conexão", "Usuário", "Terminal", "Aplicação", "Início", "Duração", "SQL"]
        self.activity_table.setSortingEnabled(False)
        self.activity_table.clear()
        self.activity_table.setColumnCount(len(headers)); self.activity_table.setRowCount(len(statements)); self.activity_table.setHorizontalHeaderLabels(headers)
        for row, statement in enumerate(statements):
            started = statement.get("started")
            started_text = started.strftime("%Y-%m-%d %H:%M:%S") if hasattr(started, "strftime") else "N/D"
            elapsed = statement.get("elapsed_seconds")
            duration_text = f"{elapsed:.1f} s" if isinstance(elapsed, (int, float)) else "N/D"
            values = [statement.get("id"), statement.get("attachment_id"), statement.get("user"), statement.get("address"), statement.get("application"), started_text, duration_text, statement.get("sql", "")]
            for column, value in enumerate(values):
                cell = DurationItem("" if value is None else str(value)) if column == 6 else QTableWidgetItem("" if value is None else str(value))
                if column == 6 and isinstance(elapsed, (int, float)):
                    cell.setData(Qt.UserRole, float(elapsed))
                self.activity_table.setItem(row, column, cell)
        self.activity_table.resizeColumnsToContents()
        self.activity_table.setSortingEnabled(True)
        # Put the longest running statement first so the expensive query is
        # visible immediately, while keeping the column sortable by the user.
        self.activity_table.sortItems(6, Qt.DescendingOrder)
        self._filter_activity_rows(self.activity_filter.text())
        if selected_statement_id:
            for row in range(self.activity_table.rowCount()):
                item = self.activity_table.item(row, 0)
                if item is not None and item.text() == selected_statement_id and not self.activity_table.isRowHidden(row):
                    self.activity_table.selectRow(row)
                    self.activity_table.scrollToItem(item)
                    break
        self.result_tabs.setCurrentWidget(self.activity_panel)
        # The activity tab may already be selected after the MDI result
        # window was closed. In that case currentChanged is not emitted, so
        # explicitly show the auxiliary window on every completed refresh.
        self._show_result_window()
        if self.result_mdi_window.isVisible():
            self.activity_table.setFocus(Qt.OtherFocusReason)
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

    def _activity_context_menu(self, position):
        from PySide6.QtWidgets import QMenu

        item = self.activity_table.itemAt(position)
        if item is not None:
            self.activity_table.selectRow(item.row())
        menu = QMenu(self._window)
        open_action = menu.addAction("Abrir consulta SQL")
        copy_action = menu.addAction("Copiar SQL")
        copy_details_action = menu.addAction("Copiar detalhes")
        slow_action = menu.addAction("Ver consulta mais demorada")
        plan_action = menu.addAction("Analisar plano e sugerir índices")
        cancel_action = menu.addAction("Interromper consulta")
        has_row = self.activity_table.currentRow() >= 0
        open_action.setEnabled(has_row)
        copy_action.setEnabled(has_row)
        copy_details_action.setEnabled(has_row)
        plan_action.setEnabled(has_row)
        cancel_action.setEnabled(has_row)
        slow_action.setEnabled(self.activity_table.rowCount() > 0)
        open_action.triggered.connect(self.open_activity_sql)
        copy_action.triggered.connect(self.copy_activity_sql)
        copy_details_action.triggered.connect(self.copy_activity_details)
        slow_action.triggered.connect(self._select_slowest_activity)
        plan_action.triggered.connect(self._analyze_activity_plan)
        cancel_action.triggered.connect(self._cancel_activity_statement)
        menu.exec(self.activity_table.viewport().mapToGlobal(position))

    def copy_activity_sql(self):
        from PySide6.QtWidgets import QApplication

        row = self.activity_table.currentRow()
        if row < 0:
            self._show_message("Copiar SQL", "Selecione uma consulta em execução.", warning=True)
            return
        item = self.activity_table.item(row, self.activity_table.columnCount() - 1)
        sql = item.text().strip() if item is not None else ""
        if not sql:
            self._show_message("Copiar SQL", "A consulta selecionada não possui SQL disponível.", warning=True)
            return
        QApplication.clipboard().setText(sql)
        self._log_event("SQL da atividade copiado", statement_id=self.activity_table.item(row, 0).text() if self.activity_table.item(row, 0) else "")
        self._show_toast("SQL copiado para a área de transferência.")
        self.status.setText("SQL copiado para a área de transferência.")

    def copy_activity_details(self):
        from PySide6.QtWidgets import QApplication

        row = self.activity_table.currentRow()
        if row < 0:
            self._show_message("Copiar detalhes", "Selecione uma consulta em execução.", warning=True)
            return
        headers = [self.activity_table.horizontalHeaderItem(column).text() for column in range(self.activity_table.columnCount())]
        values = [self.activity_table.item(row, column).text() if self.activity_table.item(row, column) else "" for column in range(self.activity_table.columnCount())]
        details = "\n".join(f"{header}: {value}" for header, value in zip(headers, values))
        if not details.strip():
            self._show_message("Copiar detalhes", "Não há informações disponíveis para esta consulta.", warning=True)
            return
        QApplication.clipboard().setText(details)
        self._log_event("Detalhes da atividade copiados", statement_id=values[0] if values else "")
        self._show_toast("Detalhes copiados para a área de transferência.")
        self.status.setText("Detalhes da consulta copiados para a área de transferência.")

    def _select_slowest_activity(self):
        from PySide6.QtCore import Qt
        if self.activity_table.rowCount() == 0:
            return
        slowest_row, slowest_value = -1, -1.0
        for row in range(self.activity_table.rowCount()):
            if self.activity_table.isRowHidden(row):
                continue
            item = self.activity_table.item(row, 6)
            value = item.data(Qt.UserRole) if item is not None else None
            if isinstance(value, (int, float)) and float(value) > slowest_value:
                slowest_row, slowest_value = row, float(value)
        if slowest_row < 0:
            self.status.setText("Nenhuma consulta visível corresponde ao filtro atual.")
            return
        self.activity_table.selectRow(slowest_row)
        self.activity_table.scrollToItem(self.activity_table.item(slowest_row, 0))
        self.status.setText("Consulta mais demorada selecionada.")

    def _analyze_activity_plan(self):
        row = self.activity_table.currentRow()
        if row < 0:
            self._show_message("Analisar consulta", "Selecione uma consulta em execução.", warning=True)
            return
        sql_item = self.activity_table.item(row, self.activity_table.columnCount() - 1)
        sql = sql_item.text().strip() if sql_item else ""
        if not sql:
            self._show_message("Analisar consulta", "A consulta selecionada não possui SQL disponível.", warning=True)
            return
        profile = next((item for item in self.profiles if item.name == getattr(self, "activity_profile_name", "")), None)
        if profile is None:
            self._show_message("Analisar consulta", "Não foi possível localizar o cadastro da conexão.", warning=True)
            return
        self._new_sql_tab()
        self.editor.setPlainText(sql)
        self.editor.setProperty("query_profile", profile.name)
        self._sync_editor(self.sql_tabs.currentIndex())
        self.inspect_plan()

    def _cancel_activity_statement(self):
        """Cancel the selected monitored statement while keeping its attachment connected."""
        from PySide6.QtWidgets import QMessageBox

        row = self.activity_table.currentRow()
        if row < 0:
            self._show_message("Interromper consulta", "Selecione uma consulta em execução.", warning=True)
            return
        statement_item = self.activity_table.item(row, 0)
        try:
            statement_id = int(statement_item.text().strip()) if statement_item is not None else 0
        except (TypeError, ValueError):
            statement_id = 0
        if statement_id <= 0:
            self._show_message("Interromper consulta", "O identificador da consulta não está disponível.", warning=True)
            return
        profile_name = getattr(self, "activity_profile_name", "")
        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None:
            self._show_message("Interromper consulta", "Não foi possível localizar o cadastro da conexão.", warning=True)
            return
        answer = QMessageBox.question(
            self._window,
            "Confirmar interrupção",
            f"Interromper a consulta {statement_id}?\nA conexão permanecerá ativa.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        password = self._stored_password(profile.name)
        from .health import terminate_statement
        self._start_background_operation(
            "Interrupção de consulta",
            lambda: terminate_statement(profile, password, statement_id),
            lambda result: self._finish_cancel_statement(result, profile, statement_id),
        )

    def _finish_cancel_statement(self, result, profile, statement_id):
        if isinstance(result, Exception):
            self._log_event("Falha ao interromper consulta", profile=profile.name, statement_id=statement_id, error=str(result))
            self._show_message("Falha ao interromper consulta", str(result))
            return
        self._log_event("Consulta interrompida", profile=profile.name, statement_id=statement_id)
        self._show_toast("Consulta interrompida; conexão mantida.")
        self.status.setText(f"Consulta {statement_id} interrompida.")
        self.inspect_activity()

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
        profile = self._query_profile()
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
        profile = self._query_profile()
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
            self.status.setText("Cadastre e selecione uma conexão de destino diferente da origem.")
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
