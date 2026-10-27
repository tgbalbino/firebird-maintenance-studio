"""Landing page shown while no SQL window is open."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MAX_RECENT_CONNECTIONS = 5
_TEXT_NO_PROFILES = "Cadastre um banco Firebird para conectar, abrir objetos e iniciar consultas SQL."
_TEXT_WITH_PROFILES = "Dê duplo clique em um banco na lista para conectar, ou abra uma consulta SQL."


class WelcomePage(QWidget):
    """Centered card with the next step and one-click saved connections."""

    def __init__(self, on_new_profile, on_new_sql, on_open_log, on_connect):
        super().__init__()
        self._on_new_profile = on_new_profile
        self._on_new_sql = on_new_sql
        self._on_connect = on_connect
        self._has_profiles = False

        self.banner = QFrame()
        self.banner.setObjectName("welcomeBanner")
        self.banner.setMinimumWidth(560)
        self.banner.setMaximumWidth(720)
        layout = QVBoxLayout(self.banner)

        icon = QLabel()
        icon.setPixmap(QApplication.instance().windowIcon().pixmap(40, 40))
        icon.setFixedSize(40, 40)
        title = QLabel("Comece por aqui")
        title.setObjectName("welcomeTitle")
        heading = QHBoxLayout()
        heading.addWidget(icon)
        heading.addWidget(title)
        heading.addStretch()

        self.text = QLabel(_TEXT_NO_PROFILES)
        self.text.setWordWrap(True)

        self.primary = QPushButton("Criar primeira conexão")
        self.primary.setObjectName("primaryAction")
        self.primary.clicked.connect(self._primary_clicked)
        new_sql = QPushButton("Nova janela SQL")
        new_sql.setObjectName("secondaryAction")
        new_sql.clicked.connect(on_new_sql)
        open_log = QPushButton("Abrir log")
        open_log.setObjectName("secondaryAction")
        open_log.clicked.connect(on_open_log)
        actions = QHBoxLayout()
        actions.addWidget(self.primary)
        actions.addWidget(new_sql)
        actions.addWidget(open_log)
        actions.addStretch()

        self.recent_title = QLabel("Conexões salvas")
        self.recent_title.setObjectName("sectionTitle")
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(4)

        layout.addLayout(heading)
        layout.addWidget(self.text)
        layout.addLayout(actions)
        layout.addWidget(self.recent_title)
        layout.addLayout(self.recent_layout)

        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        page.addStretch(2)
        page.addWidget(self.banner, 0, Qt.AlignHCenter)
        page.addStretch(3)

    def _primary_clicked(self):
        (self._on_new_sql if self._has_profiles else self._on_new_profile)()

    def set_profiles(self, profiles):
        """Refresh text, primary action and the list (favorites first)."""
        self._has_profiles = bool(profiles)
        self.text.setText(_TEXT_WITH_PROFILES if profiles else _TEXT_NO_PROFILES)
        self.primary.setText("Nova consulta SQL" if profiles else "Criar primeira conexão")

        while self.recent_layout.count():
            widget = self.recent_layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        ordered = sorted(enumerate(profiles), key=lambda pair: (not pair[1].favorite, pair[1].name.lower()))
        ordered = ordered[:MAX_RECENT_CONNECTIONS]
        self.recent_title.setVisible(bool(ordered))
        for index, profile in ordered:
            row = QWidget(self.banner)
            row.setObjectName("welcomeRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(f"{'★ ' if profile.favorite else ''}{profile.name}  ·  FB {profile.version}  ·  {profile.host}:{profile.port}")
            label.setToolTip(profile.database)
            connect = QPushButton("Conectar")
            connect.setObjectName("secondaryAction")
            connect.setToolTip(f"Conectar a {profile.name}")
            connect.clicked.connect(lambda _checked=False, i=index: self._on_connect(i))
            row_layout.addWidget(label, 1)
            row_layout.addWidget(connect)
            self.recent_layout.addWidget(row)
