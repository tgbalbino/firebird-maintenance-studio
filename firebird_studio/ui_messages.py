from __future__ import annotations


def show_message(parent, title: str, message: str, warning: bool = False) -> None:
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Warning if warning else QMessageBox.Critical)
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()
