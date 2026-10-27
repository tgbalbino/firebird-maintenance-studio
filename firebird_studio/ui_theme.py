from __future__ import annotations

COMPACT_STYLE = "QToolButton, QPushButton { min-height: 26px; padding: 5px 10px; } QLineEdit, QComboBox, QSpinBox { min-height: 24px; padding: 2px 6px; } QTabBar::tab { min-height: 26px; padding: 6px 12px; } QHeaderView::section { padding: 5px 7px; font-weight: 600; } QTableWidget::item { padding: 4px 6px; } QMenuBar#mainMenuBar::item:hover, QMenuBar#mainMenuBar::item:selected { border-radius: 4px; } QLabel#workspaceConnection { padding: 3px 8px; border-radius: 4px; font-weight: 600; } QLabel#sectionTitle { font-size: 11px; font-weight: 700; letter-spacing: 1px; } QLabel#sectionHint { font-size: 11px; } QLabel#sidebarStatus { font-size: 11px; padding: 3px 6px; border-radius: 4px; font-weight: 600; } QFrame#appHeader { border-radius: 8px; } QLabel#appTitle { font-size: 18px; font-weight: 700; } QLabel#appSubtitle { font-size: 12px; } QLabel#headerState { font-size: 12px; font-weight: 600; } QLabel#objectBreadcrumb { color: #526173; font-size: 11px; padding: 3px 8px; } QLabel#workspaceStatus, QLabel#cursorStatus { color: #526173; font-size: 11px; padding: 3px 8px; } QLabel#welcomeTitle { font-size: 15px; font-weight: 700; } QFrame#welcomeBanner { border-radius: 8px; padding: 4px; } QLabel#resultSummary { color: #526173; font-size: 11px; padding: 3px 8px; } QLabel#workspaceStatusMessage { min-height: 24px; } QPushButton#aboutLink { color: #1558b0; border: none; background: transparent; font-weight: 600; } QPushButton#aboutLink:hover { color: #0b3c7d; text-decoration: underline; }"
LIGHT_STYLE = COMPACT_STYLE + " QWidget { background: #f7f9fc; color: #1f2937; } QMainWindow, QGroupBox, QMdiArea { background: #f7f9fc; color: #1f2937; } QFrame#appHeader { background: #153e75; color: #ffffff; border: 1px solid #0f2f5d; } QLabel#appSubtitle, QLabel#headerState { color: #dbeafe; } QLabel#sectionHint { color: #64748b; } QLabel#sidebarStatus { background: #eaf2ff; color: #315b91; } QFrame#welcomeBanner { background: #eaf2ff; border: 1px solid #9bbcf0; } QGroupBox { border: 1px solid #b8c2d1; border-radius: 5px; margin-top: 8px; padding-top: 8px; font-weight: 600; } QLineEdit, QTextEdit, QTableWidget, QTreeWidget, QComboBox, QSpinBox { background: #ffffff; color: #111827; border: 1px solid #7b8798; selection-background-color: #1d4ed8; selection-color: #ffffff; } QPushButton, QToolButton { background: #e8eef7; color: #172033; border: 1px solid #718096; border-radius: 4px; } QPushButton:hover, QToolButton:hover { background: #d5e2f5; border-color: #1d4ed8; } QPushButton:pressed, QToolButton:pressed { background: #b9cbea; } QPushButton:disabled, QToolButton:disabled { background: #edf0f4; color: #8a94a3; border-color: #c7ced8; } QTabBar::tab { background: #e3eaf4; color: #26364d; border: 1px solid #aab7c8; padding: 6px 12px; } QTabBar::tab:selected { background: #1d4ed8; color: #ffffff; border-color: #173ea5; } QHeaderView::section { background: #dbe5f2; color: #172033; border: 1px solid #9eacbe; } QTreeWidget::item:selected, QTableWidget::item:selected { background: #1d4ed8; color: #ffffff; } QMenu { background: #ffffff; color: #111827; border: 1px solid #7b8798; } QMenu::item:selected { background: #dbeafe; color: #111827; } QToolTip { background: #111827; color: #ffffff; border: 1px solid #4b5563; } QStatusBar { background: #e5eaf2; color: #172033; } QScrollBar:vertical, QScrollBar:horizontal { background: #e9eef5; } QProgressBar { background: #ffffff; color: #111827; border: 1px solid #7b8798; text-align: center; } QProgressBar::chunk { background: #1d4ed8; }"
DARK_STYLE = COMPACT_STYLE + " QWidget { background: #171a21; color: #f3f4f6; } QMainWindow, QGroupBox, QMdiArea { background: #171a21; color: #f3f4f6; } QFrame#appHeader { background: #243b64; color: #ffffff; border: 1px solid #5f86c6; } QLabel#appSubtitle, QLabel#headerState { color: #dbeafe; } QLabel#sectionHint { color: #b6c2d2; } QLabel#sidebarStatus { background: #263a58; color: #c7dcfa; } QLabel#objectBreadcrumb, QLabel#workspaceStatus, QLabel#cursorStatus { color: #b6c2d2; } QFrame#welcomeBanner { background: #263a58; border: 1px solid #5f86c6; } QPushButton#aboutLink { color: #8fc1ff; background: transparent; border: none; } QPushButton#aboutLink:hover { color: #c3e0ff; } QGroupBox { border: 1px solid #667085; border-radius: 5px; margin-top: 8px; padding-top: 8px; font-weight: 600; } QLineEdit, QTextEdit, QTableWidget, QTreeWidget, QComboBox, QSpinBox { background: #232833; color: #f9fafb; border: 1px solid #8490a3; selection-background-color: #2563eb; selection-color: #ffffff; } QPushButton, QToolButton { background: #2d3748; color: #f9fafb; border: 1px solid #8b98ab; border-radius: 4px; } QPushButton:hover, QToolButton:hover { background: #3b4a62; border-color: #60a5fa; } QPushButton:pressed, QToolButton:pressed { background: #465a78; } QPushButton:disabled, QToolButton:disabled { background: #252b35; color: #7f8a9b; border-color: #4b5563; } QTabBar::tab { background: #2d3748; color: #e5e7eb; border: 1px solid #667085; padding: 6px 12px; } QTabBar::tab:selected { background: #2563eb; color: #ffffff; border-color: #60a5fa; } QHeaderView::section { background: #303b4e; color: #f9fafb; border: 1px solid #6b778b; } QTreeWidget::item:selected, QTableWidget::item:selected { background: #2563eb; color: #ffffff; } QMenu { background: #202631; color: #f9fafb; border: 1px solid #8490a3; } QMenu::item:selected { background: #334e7a; color: #ffffff; } QToolTip { background: #f9fafb; color: #111827; border: 1px solid #9ca3af; } QStatusBar { background: #252c38; color: #f3f4f6; } QScrollBar:vertical, QScrollBar:horizontal { background: #232833; } QProgressBar { background: #232833; color: #f9fafb; border: 1px solid #8490a3; text-align: center; } QProgressBar::chunk { background: #2563eb; }"


# Keep the menu visually aligned with the selected application theme.
LIGHT_STYLE += " QMenuBar#mainMenuBar { background: #f7f9fc; color: #1f2937; } QMenuBar#mainMenuBar::item:hover, QMenuBar#mainMenuBar::item:selected { background: #dbeafe; color: #111827; } QMenu::item:disabled { color: #9aa3af; }"
DARK_STYLE += " QMenuBar#mainMenuBar { background: #171a21; color: #f3f4f6; } QMenuBar#mainMenuBar::item:hover, QMenuBar#mainMenuBar::item:selected { background: #334e7a; color: #ffffff; } QMenu::item:disabled { color: #6f7b8d; }"
LIGHT_STYLE += " QWidget#sidebarPanel { background: #eef3f9; border: 1px solid #c5d0df; border-radius: 6px; } QWidget#workspacePanel { background: #f7f9fc; } QMdiArea, QMdiArea::viewport, QMdiArea > QWidget { background: #f7f9fc; } QMdiSubWindow { background: #f7f9fc; } QTreeWidget { alternate-background-color: #f3f6fa; }"
DARK_STYLE += " QWidget#sidebarPanel { background: #202631; border: 1px solid #4f5d72; border-radius: 6px; } QWidget#workspacePanel { background: #171a21; } QMdiArea, QMdiArea::viewport, QMdiArea > QWidget { background: #171a21; } QMdiSubWindow { background: #171a21; } QTreeWidget { alternate-background-color: #272d39; }"
LIGHT_STYLE += " QToolButton#workspaceAction, QToolButton#profileMenuButton { background: #e8eef7; border: 1px solid #718096; border-radius: 5px; padding: 6px 12px; font-weight: 600; } QToolButton#workspaceAction:hover, QToolButton#profileMenuButton:hover { background: #d5e2f5; border-color: #1d4ed8; } QToolButton#workspaceAction:pressed, QToolButton#profileMenuButton:pressed { background: #b9cbea; } QLabel#workspaceStatusMessage { padding: 5px 8px; border-top: 1px solid #c5d0df; color: #526173; }"
DARK_STYLE += " QToolButton#workspaceAction, QToolButton#profileMenuButton { background: #2d3748; border: 1px solid #8b98ab; border-radius: 5px; padding: 6px 12px; font-weight: 600; } QToolButton#workspaceAction:hover, QToolButton#profileMenuButton:hover { background: #3b4a62; border-color: #60a5fa; } QToolButton#workspaceAction:pressed, QToolButton#profileMenuButton:pressed { background: #465a78; } QLabel#workspaceStatusMessage { padding: 5px 8px; border-top: 1px solid #4f5d72; color: #b6c2d2; }"
LIGHT_STYLE += " QTreeWidget::item { padding: 3px 4px; } QTreeWidget::item:hover { background: #e1ebf8; }"
DARK_STYLE += " QTreeWidget::item { padding: 3px 4px; } QTreeWidget::item:hover { background: #303b4e; }"
LIGHT_STYLE += " QTableWidget { alternate-background-color: #f3f6fa; } QTableWidget::item:hover { background: #e1ebf8; }"
DARK_STYLE += " QTableWidget { alternate-background-color: #272d39; } QTableWidget::item:hover { background: #303b4e; }"
LIGHT_STYLE += " QTabWidget::pane { border: 1px solid #b8c2d1; border-radius: 4px; top: -1px; }"
DARK_STYLE += " QTabWidget::pane { border: 1px solid #667085; border-radius: 4px; top: -1px; }"
LIGHT_STYLE += " QPushButton#primaryAction { background: #1d4ed8; color: #ffffff; border-color: #173ea5; font-weight: 700; } QPushButton#primaryAction:hover { background: #1e40af; } QPushButton#secondaryAction { background: #ffffff; } QProgressBar#operationProgress { border: none; border-radius: 4px; background: #dbe5f2; } QProgressBar#operationProgress::chunk { border-radius: 4px; background: #1d4ed8; }"
DARK_STYLE += " QPushButton#primaryAction { background: #2563eb; color: #ffffff; border-color: #60a5fa; font-weight: 700; } QPushButton#primaryAction:hover { background: #1d4ed8; } QPushButton#secondaryAction { background: #2d3748; } QProgressBar#operationProgress { border: none; border-radius: 4px; background: #303b4e; } QProgressBar#operationProgress::chunk { border-radius: 4px; background: #60a5fa; }"
LIGHT_STYLE += " QSplitter#mainSplitter::handle:horizontal { background: #d8e1ed; width: 8px; } QSplitter#mainSplitter::handle:horizontal:hover { background: #9bbcf0; }"
DARK_STYLE += " QSplitter#mainSplitter::handle:horizontal { background: #303b4e; width: 8px; } QSplitter#mainSplitter::handle:horizontal:hover { background: #5f86c6; }"
LIGHT_STYLE += " QLabel#connectionStatus { color: #526173; } QLabel#connectionBadge { background: #eaf2ff; border: 1px solid #9bbcf0; border-radius: 9px; padding: 3px 8px; }"
DARK_STYLE += " QLabel#connectionStatus { color: #b6c2d2; } QLabel#connectionBadge { background: #263a58; border: 1px solid #5f86c6; border-radius: 9px; padding: 3px 8px; }"
LIGHT_STYLE += " QLabel#connectionBadge[connectionState=\"connected\"] { color: #166534; background: #ecfdf3; border-color: #86efac; font-weight: 600; } QLabel#connectionBadge[connectionState=\"disconnected\"] { color: #64748b; background: #f1f5f9; border-color: #cbd5e1; font-weight: 600; }"
DARK_STYLE += " QLabel#connectionBadge[connectionState=\"connected\"] { color: #a7f3d0; background: #153b30; border-color: #3f8f72; font-weight: 600; } QLabel#connectionBadge[connectionState=\"disconnected\"] { color: #a8b3c2; background: #28313d; border-color: #566477; font-weight: 600; }"
LIGHT_STYLE += " QCheckBox#toolbarOption { background: #eef3f9; border: 1px solid #c5d0df; border-radius: 4px; padding: 5px 8px; } QFrame#toolbarSeparator, QFrame#actionGroupSeparator { color: #b8c2d1; background: #b8c2d1; min-width: 1px; max-width: 1px; margin: 3px 2px; } QPushButton#paginationButton { background: #eef3f9; border-color: #aab7c8; padding: 5px 10px; } QPushButton#paginationButton:hover { background: #dbeafe; border-color: #1d4ed8; }"
DARK_STYLE += " QCheckBox#toolbarOption { background: #202631; border: 1px solid #4f5d72; border-radius: 4px; padding: 5px 8px; } QFrame#toolbarSeparator, QFrame#actionGroupSeparator { color: #667085; background: #667085; min-width: 1px; max-width: 1px; margin: 3px 2px; } QPushButton#paginationButton { background: #252d3a; border-color: #667085; padding: 5px 10px; } QPushButton#paginationButton:hover { background: #334e7a; border-color: #60a5fa; }"
LIGHT_STYLE += " QTabWidget#sqlDocumentTabs::pane { border-color: #9eacbe; } QTabWidget#sqlDocumentTabs QTabBar::tab { min-width: 76px; } QTabWidget#sqlDocumentTabs QTabBar::tab:selected { font-weight: 700; }"
DARK_STYLE += " QTabWidget#sqlDocumentTabs::pane { border-color: #8490a3; } QTabWidget#sqlDocumentTabs QTabBar::tab { min-width: 76px; } QTabWidget#sqlDocumentTabs QTabBar::tab:selected { font-weight: 700; }"
LIGHT_STYLE += " QListWidget#sqlHistoryList { padding: 6px; } QListWidget#sqlHistoryList::item { padding: 7px 8px; border-bottom: 1px solid #dbe2ec; } QListWidget#sqlHistoryList::item:hover { background: #e1ebf8; }"
DARK_STYLE += " QListWidget#sqlHistoryList { padding: 6px; } QListWidget#sqlHistoryList::item { padding: 7px 8px; border-bottom: 1px solid #3b4658; } QListWidget#sqlHistoryList::item:hover { background: #303b4e; }"

# When focus moves to the SQL editor Qt uses the inactive selection palette
# for the tree. Set that state explicitly so focused object names remain dark
# and readable on the pale blue selection background.
LIGHT_STYLE += " QTreeWidget::item:selected:!active { color: #1f2937; background: #dbeafe; } QTreeWidget::item:focus { color: #111827; }"
LIGHT_STYLE += " QAbstractScrollArea { background: #f7f9fc; }"
DARK_STYLE += " QAbstractScrollArea { background: #171a21; }"
LIGHT_STYLE += " QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPushButton:focus, QToolButton:focus { border: 1px solid #1d4ed8; outline: none; } QTableWidget, QTreeWidget { outline: none; }"
DARK_STYLE += " QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPushButton:focus, QToolButton:focus { border: 1px solid #60a5fa; outline: none; } QTableWidget, QTreeWidget { outline: none; }"

# Additional palettes keep the same layout and controls while offering
# neutral gray and navy blue alternatives. Explicit tree item colors avoid
# the low-contrast platform focus color seen in the light palette.
GRAY_STYLE = LIGHT_STYLE + " QWidget { background: #e7e9ed; color: #20242b; } QMainWindow, QGroupBox, QMdiArea { background: #e7e9ed; color: #20242b; } QWidget#sidebarPanel { background: #dfe3e8; border-color: #aeb7c4; } QWidget#workspacePanel, QMdiArea, QMdiArea::viewport, QMdiArea > QWidget, QMdiSubWindow { background: #e7e9ed; } QLineEdit, QTextEdit, QTableWidget, QTreeWidget, QComboBox, QSpinBox { background: #f7f8fa; color: #20242b; border-color: #7b8491; } QTreeWidget::item:selected, QTableWidget::item:selected { background: #687585; color: #ffffff; } QTreeWidget::item:hover { background: #d2d8e0; color: #20242b; } QMenuBar#mainMenuBar { background: #e7e9ed; color: #20242b; } QStatusBar { background: #d9dde3; color: #20242b; } QMenu::item:disabled { color: #8b949e; }"
BLUE_STYLE = DARK_STYLE + " QWidget { background: #101d31; color: #edf4ff; } QMainWindow, QGroupBox, QMdiArea { background: #101d31; color: #edf4ff; } QWidget#sidebarPanel { background: #142844; border-color: #41648e; } QWidget#workspacePanel, QMdiArea, QMdiArea::viewport, QMdiArea > QWidget, QMdiSubWindow { background: #101d31; } QLineEdit, QTextEdit, QTableWidget, QTreeWidget, QComboBox, QSpinBox { background: #182f50; color: #edf4ff; border-color: #6f91bb; } QPushButton, QToolButton { background: #244a78; color: #edf4ff; border-color: #7fa7d8; } QTreeWidget::item:selected, QTableWidget::item:selected { background: #2f6fbd; color: #ffffff; } QTreeWidget::item:hover { background: #254b78; color: #ffffff; } QMenuBar#mainMenuBar { background: #101d31; color: #edf4ff; } QStatusBar { background: #142844; color: #edf4ff; } QMenu::item:disabled { color: #7184a0; }"
GRAY_STYLE += " QAbstractScrollArea { background: #e7e9ed; }"
BLUE_STYLE += " QAbstractScrollArea { background: #101d31; }"

# SQL workspace hierarchy: a clear command bar, compact connection context,
# and a focused editor surface keep the central area useful at every size.
LIGHT_STYLE += " QFrame#sqlCommandBar { background: #eef3f9; border: 1px solid #c5d0df; border-radius: 5px; } QPushButton#secondaryAction { min-height: 28px; } QTextEdit#sqlEditor { background: #ffffff; color: #172033; border: 1px solid #9eacbe; border-radius: 3px; padding: 8px; selection-background-color: #bfdbfe; selection-color: #111827; } QTabBar#sqlWindowBar::tab { margin-right: 3px; } QLabel#connectionBadge { padding: 2px 7px; border-radius: 8px; } QLabel#workspaceStatus { padding-left: 2px; }"
DARK_STYLE += " QFrame#sqlCommandBar { background: #202631; border: 1px solid #4f5d72; border-radius: 5px; } QPushButton#secondaryAction { min-height: 28px; } QTextEdit#sqlEditor { background: #1d2430; color: #f3f4f6; border: 1px solid #8091aa; border-radius: 3px; padding: 8px; selection-background-color: #334e7a; selection-color: #ffffff; } QTextEdit#sqlEditor:focus { border: 2px solid #60a5fa; padding: 7px; } QTabBar#sqlWindowBar::tab { margin-right: 3px; } QLabel#connectionBadge { padding: 2px 7px; border-radius: 8px; } QLabel#workspaceStatus { padding-left: 2px; }"
GRAY_STYLE += " QFrame#sqlCommandBar { background: #dfe3e8; border: 1px solid #aeb7c4; border-radius: 5px; } QTextEdit#sqlEditor { background: #f7f8fa; color: #20242b; border: 1px solid #7b8491; padding: 8px; }"
BLUE_STYLE += " QFrame#sqlCommandBar { background: #142844; border: 1px solid #41648e; border-radius: 5px; } QTextEdit#sqlEditor { background: #142844; color: #edf4ff; border: 1px solid #83a7d3; padding: 8px; } QTextEdit#sqlEditor:focus { border: 2px solid #9bc5ff; padding: 7px; }"
LIGHT_STYLE += " QToolButton#treeToolButton { min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; padding: 0px; font-weight: 700; }"
DARK_STYLE += " QToolButton#treeToolButton { min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; padding: 0px; font-weight: 700; }"
GRAY_STYLE += " QToolButton#treeToolButton { min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; padding: 0px; font-weight: 700; }"
BLUE_STYLE += " QToolButton#treeToolButton { min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; padding: 0px; font-weight: 700; }"
LIGHT_STYLE += " QFrame#sqlEditorShell { background: #eef3f9; border: 1px solid #c5d0df; border-radius: 7px; } QFrame#sqlEditorShell QLabel { color: #526173; font-size: 11px; } QFrame#sqlEditorShell QLabel#connectionBadge { font-size: 11px; } QFrame#sqlEditorShell QLabel#objectBreadcrumb { background: #e5edf7; border-radius: 4px; padding: 3px 7px; }"
DARK_STYLE += " QFrame#sqlEditorShell { background: #202631; border: 1px solid #4f5d72; border-radius: 7px; } QFrame#sqlEditorShell QLabel { color: #b6c2d2; font-size: 11px; } QFrame#sqlEditorShell QLabel#connectionBadge { font-size: 11px; } QFrame#sqlEditorShell QLabel#objectBreadcrumb { background: #2a3444; border-radius: 4px; padding: 3px 7px; }"
GRAY_STYLE += " QFrame#sqlEditorShell { background: #dfe3e8; border: 1px solid #aeb7c4; border-radius: 7px; } QFrame#sqlEditorShell QLabel { color: #596575; font-size: 11px; } QFrame#sqlEditorShell QLabel#connectionBadge { font-size: 11px; } QFrame#sqlEditorShell QLabel#objectBreadcrumb { background: #d3d9e1; border-radius: 4px; padding: 3px 7px; }"
BLUE_STYLE += " QFrame#sqlEditorShell { background: #142844; border: 1px solid #41648e; border-radius: 7px; } QFrame#sqlEditorShell QLabel { color: #bcd0ea; font-size: 11px; } QFrame#sqlEditorShell QLabel#connectionBadge { font-size: 11px; } QFrame#sqlEditorShell QLabel#objectBreadcrumb { background: #1b3658; border-radius: 4px; padding: 3px 7px; }"
LIGHT_STYLE += " QLabel#planSummary { background: #eef3f9; color: #334155; border: 1px solid #c5d0df; border-radius: 4px; padding: 8px; } QTreeWidget#planTree { border: 1px solid #9eacbe; } QTextEdit#planTechnicalOutput { font-family: Consolas; font-size: 9pt; }"
DARK_STYLE += " QLabel#planSummary { background: #202631; color: #dbeafe; border: 1px solid #4f5d72; border-radius: 4px; padding: 8px; } QTreeWidget#planTree { border: 1px solid #667085; } QTextEdit#planTechnicalOutput { font-family: Consolas; font-size: 9pt; }"
GRAY_STYLE += " QLabel#planSummary { background: #dfe3e8; color: #20242b; border: 1px solid #aeb7c4; border-radius: 4px; padding: 8px; } QTreeWidget#planTree { border: 1px solid #7b8491; }"
BLUE_STYLE += " QLabel#planSummary { background: #142844; color: #edf4ff; border: 1px solid #41648e; border-radius: 4px; padding: 8px; } QTreeWidget#planTree { border: 1px solid #6f91bb; }"

# Labels and check boxes must not paint the page color over cards, banners and
# tinted panels; the generic QWidget rule above would otherwise give them an
# opaque background (visible as dark/white boxes behind text).
_TRANSPARENT = " QLabel, QCheckBox, QWidget#welcomeRow { background: transparent; }"
# Every popup menu (context menus included) gets the same roomy rows; without
# it, menus created without their own sheet render items cramped and cut off.
_TRANSPARENT += " QPushButton:checked, QPushButton#paginationButton:checked { background: #1d4ed8; color: #ffffff; border-color: #60a5fa; font-weight: 700; }"
_TRANSPARENT += " QMenu { padding: 4px 0; } QMenu::item { padding: 6px 28px 6px 14px; min-height: 18px; } QMenu::separator { height: 1px; margin: 4px 8px; background: #94a3b8; }"
LIGHT_STYLE += _TRANSPARENT + " QPushButton#primaryAction:disabled { background: #94a9d6; color: #ffffff; border-color: #94a9d6; }"
GRAY_STYLE += _TRANSPARENT + " QPushButton#primaryAction:disabled { background: #94a9d6; color: #ffffff; border-color: #94a9d6; }"
DARK_STYLE += _TRANSPARENT + " QPushButton#primaryAction:disabled { background: #2a3a5a; color: #9fb0cc; border-color: #3f5578; }"
BLUE_STYLE += _TRANSPARENT + " QPushButton#primaryAction:disabled { background: #2a3a5a; color: #9fb0cc; border-color: #3f5578; }"


def _close_icon_css() -> str:
    """Tab close buttons drawn per state: dark glyph on idle tabs, white on selected."""
    import tempfile
    from pathlib import Path
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    folder = Path(tempfile.gettempdir()) / "firebird-maintenance-studio-icons"
    folder.mkdir(parents=True, exist_ok=True)
    urls = {}
    for name, color in (("idle", "#475569"), ("idle_dark", "#cbd5e1"), ("selected", "#ffffff")):
        path = folder / f"close_{name}.png"
        pixmap = QPixmap(24, 18)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(color), 1.8, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(5, 5, 13, 13)
        painter.drawLine(13, 5, 5, 13)
        painter.end()
        pixmap.save(str(path), "PNG")
        urls[name] = path.as_posix()
    return (
        f" QTabBar::close-button {{ image: url({urls['idle']}); subcontrol-position: right; }}"
        f" QTabBar::close-button:hover {{ background: rgba(148,163,184,0.35); border-radius: 3px; }}"
        f" QTabBar::close-button:selected {{ image: url({urls['selected']}); }}"
    ), (
        f" QTabBar::close-button {{ image: url({urls['idle_dark']}); }}"
        f" QTabBar::close-button:selected {{ image: url({urls['selected']}); }}"
    )


def apply_theme(theme: str) -> None:
    from PySide6.QtGui import QColor, QPalette, QBrush
    from PySide6.QtWidgets import QApplication, QMdiArea

    app = QApplication.instance()
    if app is not None:
        styles = {"light": LIGHT_STYLE, "dark": DARK_STYLE, "gray": GRAY_STYLE, "blue": BLUE_STYLE}
        light_close, dark_close = _close_icon_css()
        extra = dark_close if theme in {"dark", "blue"} else light_close
        app.setStyleSheet(styles.get(theme, LIGHT_STYLE) + extra)
        # Qt can paint an MDI viewport with the platform gray palette even
        # when the stylesheet targets QMdiArea. Set the viewport palette
        # explicitly so the workspace never falls back to gray or brown.
        background = QColor({"dark": "#171a21", "blue": "#101d31", "gray": "#e7e9ed"}.get(theme, "#f7f9fc"))
        for area in app.findChildren(QMdiArea):
            palette = area.palette()
            palette.setColor(QPalette.Window, background)
            palette.setColor(QPalette.Base, background)
            area.setPalette(palette)
            # QMdiArea has a separate viewport and can otherwise retain the
            # platform default gray/brown brush.  Set both the MDI background
            # brush and the viewport palette so empty workspace areas always
            # follow the selected application theme.
            area.setBackground(QBrush(background))
            area.setAutoFillBackground(True)
            area.viewport().setPalette(palette)
            area.viewport().setBackgroundRole(QPalette.Base)
            area.viewport().setAutoFillBackground(True)
            # Some Windows styles keep a native brush on the viewport even
            # after the palette is updated. An explicit local rule prevents
            # the gray/brown fallback from returning when the last MDI child
            # is closed or the main window is maximized.
            # Scoped by name so the rule does not cascade into SQL forms.
            area.viewport().setObjectName("mdiViewport")
            area.viewport().setStyleSheet(
                f"QWidget#mdiViewport {{ background-color: {background.name()}; border: 0px; }}"
            )
