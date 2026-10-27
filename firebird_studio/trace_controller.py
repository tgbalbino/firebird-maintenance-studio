"""Runs fbtracemgr and shows its events in the activity panel."""
from __future__ import annotations

import csv
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QTableWidgetItem

from .trace_monitor import build_trace_config, find_trace_manager, parse_trace_line

START_LABEL = "Iniciar histórico (Trace)"
STOP_LABEL = "Parar histórico"
MAX_LINES = 200
RENDER_INTERVAL = 0.25


class TraceController:
    """Owns the trace process and its buffered output.

    ``resolve_profile()`` returns the connection to trace (or ``None``) and
    ``password_for(profile)`` its password; messages, logging and the main
    status line are reported through the callbacks.
    """

    def __init__(self, window, table, button, metrics, *, resolve_profile, password_for, set_status, show_message, log_event):
        self._window = window
        self.table = table
        self.button = button
        self.metrics = metrics
        self._resolve_profile = resolve_profile
        self._password_for = password_for
        self._set_status = set_status
        self._show_message = show_message
        self._log_event = log_event
        self.process = None
        self.config_path = None
        self.lines: list[str] = []
        self.status = ""
        self._last_render = 0.0

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def toggle(self):
        if self.running:
            self.stop()
            return
        try:
            profile = self._resolve_profile()
            if profile is None:
                self._show_message("Histórico de consultas", "Selecione um banco conectado para iniciar o Trace.", warning=True)
                return
            executable = find_trace_manager(profile)
            if executable is None:
                self._show_message("Histórico de consultas", "fbtracemgr.exe não foi encontrado na instalação do Firebird.", warning=True)
                return
            config = NamedTemporaryFile("w", encoding="utf-8", suffix=".conf", delete=False)
            config.write(build_trace_config(profile))
            config.close()
            self.config_path = Path(config.name)
            password = self._password_for(profile)
            service = "service_mgr" if profile.host.strip().lower() in {"", "localhost", "127.0.0.1"} else f"{profile.host}:service_mgr"
            process = QProcess(self._window)
            process.setProcessChannelMode(QProcess.MergedChannels)
            process.readyReadStandardOutput.connect(self._read_output)
            process.errorOccurred.connect(self._on_error)
            process.finished.connect(self._on_finished)
            process.started.connect(self._on_started)
            self.process = process
            self.lines = []
            self._last_render = 0.0
            self.status = "Trace ativo · aguardando eventos do banco..."
            # Firebird 2.5 does not preserve spaces in the -NAME value and
            # treats the remaining words as unknown switches. Keep the trace
            # session name as one token for all supported Firebird versions.
            process.start(str(executable), ["-SE", service, "-USER", profile.user, "-PASSWORD", password, "-START", "-NAME", "FirebirdMaintenanceStudio", "-CONFIG", str(self.config_path)])
            self.button.setText(STOP_LABEL)
            self._set_status(self.status)
            self.render()
        except Exception as exc:
            self._show_message("Histórico de consultas", str(exc), warning=True)

    def _on_started(self):
        """Confirm asynchronously that fbtracemgr really started."""
        pid = self.process.processId() if self.process is not None else 0
        self.status = f"Trace ativo · aguardando eventos do banco (PID {pid})"
        self._set_status(self.status)
        self.render()

    def _read_output(self):
        if self.process is None:
            return
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not text:
            return
        self.lines.extend(line for line in text.splitlines() if line.strip())
        self.lines = self.lines[-MAX_LINES:]
        self.update_table()
        self.status = f"Trace ativo · {len(self.lines)} evento(s) recebido(s)"
        self._set_status(self.status)
        # Trace can emit a large burst of lines. Keep collecting immediately,
        # but redraw the Qt text widget a few times per second so the
        # application stays responsive while another tool is querying.
        now = time.monotonic()
        if now - self._last_render < RENDER_INTERVAL:
            return
        self._last_render = now
        self.render()

    def update_table(self):
        """Show raw Trace events in a sortable grid, separate from active SQL."""
        table = self.table
        selected_detail = ""
        selected = table.currentItem()
        if selected is not None:
            detail = table.item(selected.row(), 2)
            selected_detail = detail.text() if detail is not None else ""
        table.setRowCount(0)
        for line in self.lines[-MAX_LINES:]:
            timestamp, event = parse_trace_line(line)
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(timestamp))
            table.setItem(row, 1, QTableWidgetItem(event))
            table.setItem(row, 2, QTableWidgetItem(line))
            if selected_detail and line == selected_detail:
                table.selectRow(row)
        table.resizeColumnsToContents()
        if table.columnCount() >= 3:
            table.horizontalHeader().setStretchLastSection(True)

    def context_menu(self, position):
        table = self.table
        item = table.itemAt(position)
        if item is not None:
            table.selectRow(item.row())
        row = table.currentRow()
        menu = QMenu(self._window)
        copy_action = menu.addAction("Copiar evento")
        copy_sql_action = menu.addAction("Copiar SQL/detalhes")
        copy_action.setEnabled(row >= 0)
        copy_sql_action.setEnabled(row >= 0)
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(" | ".join(
            table.item(row, column).text() if table.item(row, column) is not None else ""
            for column in range(table.columnCount())
        )))
        copy_sql_action.triggered.connect(lambda: QApplication.clipboard().setText(
            table.item(row, 2).text() if table.item(row, 2) is not None else ""
        ))
        menu.exec(table.viewport().mapToGlobal(position))

    def render(self):
        """Render the buffered trace tail without hiding the active summary."""
        marker = "\n\nHISTÓRICO DE CONSULTAS (TRACE)"
        prefix = self.metrics.toPlainText().split(marker, 1)[0].rstrip()
        body = self.status or "Trace aguardando eventos."
        if self.lines:
            body += "\n" + "\n".join(self.lines)
        self.metrics.setPlainText(prefix + marker + "\nO Trace registra consultas concluídas e em execução.\n" + body)

    def _on_finished(self):
        self._read_output()
        if self.lines:
            self.render()
        self.button.setText(START_LABEL)
        self.process = None
        self.status = f"Trace encerrado · {len(self.lines)} evento(s) recebido(s)" if self.lines else "Trace encerrado sem eventos recebidos"
        config_path, self.config_path = self.config_path, None
        if config_path is not None:
            try:
                config_path.unlink(missing_ok=True)
            except OSError:
                pass
        if self.lines:
            self._set_status(self.status)
        else:
            self._set_status("O Trace Service foi encerrado sem registrar eventos. Verifique usuário, senha e permissões de monitoramento.")
        self.update_table()

    def _on_error(self, error):
        self._read_output()
        self.status = f"Falha no Trace Service: {error}"
        self._set_status(self.status)
        self.render()

    def stop(self):
        if self.process is None:
            return
        if self.process.state() != QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(1500):
                self.process.kill()
        self._on_finished()

    def clear(self):
        """Clear displayed Trace events while keeping fbtracemgr running."""
        self.lines = []
        self.table.setRowCount(0)
        self.status = "Trace ativo · aguardando novos eventos..." if self.process is not None else "Histórico Trace limpo"
        self.render()
        self._set_status("Histórico Trace limpo.")

    def export_csv(self):
        """Export captured Trace events independently from active statements."""
        if not self.lines:
            self._show_message("Exportar Trace", "Inicie o histórico e aguarde eventos antes de exportar.", warning=True)
            return
        filename, _ = QFileDialog.getSaveFileName(self._window, "Exportar histórico Trace", "historico_trace.csv", "CSV (*.csv);;Todos (*.*)")
        if not filename:
            return
        table = self.table
        try:
            headers = [table.horizontalHeaderItem(column).text() for column in range(table.columnCount())]
            with open(filename, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(headers)
                for row in range(table.rowCount()):
                    writer.writerow([
                        table.item(row, column).text() if table.item(row, column) else ""
                        for column in range(table.columnCount())
                    ])
            self._log_event("Histórico Trace exportado", filename=filename, rows=table.rowCount())
            self._set_status(f"Histórico Trace exportado: {filename}")
        except Exception as exc:
            self._log_event("Falha ao exportar Trace", filename=filename, error=str(exc))
            self._show_message("Falha ao exportar Trace", str(exc))
