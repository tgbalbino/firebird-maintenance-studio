"""Top-level application menu and the global keyboard shortcuts."""


def build_main_menu(studio):
    """Create the compact application menu for global commands."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence, QShortcut

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app._sql_execution_handler = studio._handle_sql_execution_key

    menu_bar = studio._window.menuBar()
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
    settings_action.setShortcut("Ctrl+,")
    settings_action.triggered.connect(studio.show_app_settings)
    app_menu.addSeparator()
    studio.menu_always_top_action = app_menu.addAction("Sempre no topo")
    studio.menu_always_top_action.setCheckable(True)
    studio.menu_always_top_action.setChecked(bool(studio._settings.value("always_on_top", False, type=bool)))
    studio.menu_always_top_action.toggled.connect(studio._set_always_on_top)
    app_menu.addAction("Abrir log de eventos", studio.open_event_log)
    app_menu.addSeparator()
    app_menu.addAction("Sair", studio._window.close)

    sql_menu = menu_bar.addMenu("SQL")
    new_sql_action = sql_menu.addAction("Nova janela SQL", studio._new_sql_tab)
    new_sql_action.setToolTip("Abrir uma nova janela SQL (Ctrl+N)")
    studio.new_sql_shortcut = QShortcut(QKeySequence("Ctrl+N"), studio._window)
    studio.new_sql_shortcut.setContext(Qt.ApplicationShortcut)
    studio.new_sql_shortcut.activated.connect(studio._new_sql_tab)
    execute_action = sql_menu.addAction("Executar SQL", studio.execute_selected)
    execute_action.setToolTip("Executar a consulta da janela SQL ativa (F5)")
    # QAction shortcuts can stop reaching the handler when another child
    # widget owns the focus. Keep explicit application shortcuts on the
    # main window so execution remains available from every SQL subview.
    studio.execute_sql_shortcut = QShortcut(QKeySequence("F5"), studio._window)
    studio.execute_sql_shortcut.setContext(Qt.ApplicationShortcut)
    studio.execute_sql_shortcut.activated.connect(studio.execute_selected)
    execute_action.setShortcut(QKeySequence("F5"))
    execute_action.setShortcutContext(Qt.ApplicationShortcut)
    selection_menu_action = sql_menu.addAction("Executar seleção", studio.execute_selection)
    studio.execute_selection_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F5"), studio._window)
    studio.execute_selection_shortcut.setContext(Qt.ApplicationShortcut)
    studio.execute_selection_shortcut.activated.connect(studio.execute_selection)
    selection_menu_action.setShortcut(QKeySequence("Ctrl+Shift+F5"))
    selection_menu_action.setShortcutContext(Qt.ApplicationShortcut)
    sql_menu.addAction("Ver plano", studio.inspect_plan)
    sql_menu.addAction("Histórico SQL", studio._choose_history_query)
    sql_menu.addSeparator()
    sql_menu.addAction(studio.begin_transaction_action)
    sql_menu.addAction(studio.commit_transaction_action)
    sql_menu.addAction(studio.rollback_transaction_action)

    window_menu = menu_bar.addMenu("Janelas")
    window_menu.addAction("Selecionar consulta aberta", studio._choose_sql_window)
    window_menu.addAction("Mostrar resultados e diagnóstico", studio._show_result_window)
    window_menu.addAction("Próxima consulta", studio.sql_tabs.activate_next)
    window_menu.addAction("Consulta anterior", studio.sql_tabs.activate_previous)
    window_menu.addAction("Fechar consulta atual", lambda: studio.close_sql_tab(studio.sql_tabs.currentIndex()))
    close_all_action = window_menu.addAction("Fechar todas as consultas", studio._close_all_sql_tabs)
    close_all_action.setToolTip("Fechar todas as janelas SQL (Ctrl+Shift+W)")
    studio.close_all_sql_shortcut = QShortcut(QKeySequence("Ctrl+Shift+W"), studio._window)
    studio.close_all_sql_shortcut.setContext(Qt.ApplicationShortcut)
    studio.close_all_sql_shortcut.activated.connect(studio._close_all_sql_tabs)
    window_menu.addSeparator()
    window_menu.addAction(studio.menu_always_top_action)

    database_menu = menu_bar.addMenu("Banco")
    database_menu.addAction("Nova conexão", studio.new_profile)
    database_menu.addAction("Salvar conexão", studio.save_profile)
    database_menu.addAction("Abrir banco", studio.open_profile)
    database_menu.addAction("Desconectar banco", studio.disconnect_selected)
    database_menu.addSeparator()
    existing = {action.text() for action in database_menu.actions()}
    database_menu.addAction("Backup", studio.execute_backup)
    database_menu.addAction("Restore", studio.execute_restore)
    existing |= {"Backup", "Restore"}
    for action in studio._command_menus["Banco"].menu().actions():
        if action.text() not in existing:
            database_menu.addAction(action)

    data_menu = menu_bar.addMenu("Dados")
    data_menu.addActions(studio._command_menus["Dados"].menu().actions())
    security_menu = menu_bar.addMenu("Segurança")
    security_menu.addActions(studio._command_menus["Segurança"].menu().actions())

    analysis_menu = menu_bar.addMenu("Análise")
    activity_action = analysis_menu.addAction("Monitorar consultas", studio.inspect_activity)
    activity_action.setToolTip("Abrir o monitor de consultas em execução (Ctrl+Shift+A)")
    studio.activity_open_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), studio._window)
    studio.activity_open_shortcut.setContext(Qt.ApplicationShortcut)
    studio.activity_open_shortcut.activated.connect(studio.inspect_activity)
    analysis_menu.addSeparator()
    analysis_menu.addActions(studio._command_menus["Análise"].menu().actions())

    help_menu = menu_bar.addMenu("Ajuda")
    help_menu.addAction("Sobre", studio.show_about)
    help_menu.addAction("Verificar atualizações...", studio.check_for_updates)
    for menu in (app_menu, sql_menu, window_menu, database_menu, data_menu, security_menu, analysis_menu, help_menu):
        menu.setMinimumWidth(240)
