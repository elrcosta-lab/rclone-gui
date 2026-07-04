from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal, QProcess, QByteArray
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout


class RcloneProcess(QObject):
    finished = Signal(int, str)  # exit_code, output
    progress = Signal(str)       # stdout line
    error_occurred = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._output = ""

    def run(self, args: list[str]):
        self._output = ""
        self._process = QProcess(self)
        self._process.setProgram("rclone")
        self._process.setArguments(args)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.start()

    def _on_stdout(self):
        data = self._process.readAllStandardOutput().data().decode()
        self._output += data
        self.progress.emit(data)

    def _on_stderr(self):
        data = self._process.readAllStandardError().data().decode()
        self._output += data
        self.error_occurred.emit(data)

    def _on_finished(self, exit_code: int):
        self.finished.emit(exit_code, self._output)

    def cancel(self):
        if self._process and self._process.state() == QProcess.Running:
            self._process.terminate()
            if not self._process.waitForFinished(5000):
                self._process.kill()


class ProgressWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self._info_label = QLabel("")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.hide()

        btn_layout = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.hide()
        btn_layout.addStretch()
        btn_layout.addWidget(self._cancel_btn)

        layout.addWidget(self._info_label)
        layout.addWidget(self._progress_bar)
        layout.addLayout(btn_layout)

    def show_progress(self, info: str = "Processando...", indeterminate: bool = True):
        self._info_label.setText(info)
        if indeterminate:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, 100)
        self._progress_bar.show()
        self._cancel_btn.show()

    def hide_progress(self):
        self._progress_bar.hide()
        self._cancel_btn.hide()
        self._info_label.setText("")

    def cancel_requested(self, slot):
        self._cancel_btn.clicked.connect(slot)
