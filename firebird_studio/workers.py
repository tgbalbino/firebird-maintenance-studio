from __future__ import annotations

try:
    from PySide6.QtCore import QObject, Signal, Slot

    class OperationWorker(QObject):
        finished = Signal(object)

        def __init__(self, operation):
            super().__init__()
            self.operation = operation

        @Slot()
        def run(self):
            try:
                self.finished.emit(self.operation())
            except Exception as exc:
                self.finished.emit(exc)

    class OpenConnectionWorker(QObject):
        finished = Signal(object, object, str)
        progress = Signal(str)

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
                self.progress.emit(f"Falha ao conectar: {result.message}")
                self.finished.emit(result, [], "")
                return
            self.progress.emit("Conexão realizada. Lendo objetos do banco...")
            try:
                objects = load_schema(self.profile, self.password, detailed=False)
                self.finished.emit(result, objects, "")
            except Exception as exc:
                self.progress.emit(f"Falha ao ler objetos: {exc}")
                self.finished.emit(result, [], str(exc))
except ImportError:  # pragma: no cover - allows headless model tests
    OperationWorker = None
    OpenConnectionWorker = None
