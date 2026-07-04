from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView,
)

from ...services.job_service import JobService


class JobHistoryWidget(QWidget):
    def __init__(self, job_service: JobService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.job_service = job_service
        self._current_job_id: Optional[int] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        header = QLabel("Histórico de Execuções")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Status", "Trigger", "Início", "Fim", "Duração", "Arquivos", "Erros"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self._table)

    def show_job_history(self, job_id: int):
        self._current_job_id = job_id
        executions = self.job_service.get_history(job_id)
        self._table.setRowCount(len(executions))
        for i, e in enumerate(executions):
            items = [
                str(e.id),
                e.status,
                e.trigger,
                (e.started_at or "")[:19],
                (e.finished_at or "em andamento")[:19],
                f"{e.duration_seconds:.1f}s" if e.duration_seconds else "-",
                str(e.files_transferred),
                str(e.errors_count),
            ]
            for j, val in enumerate(items):
                self._table.setItem(i, j, QTableWidgetItem(val))
        self._table.resizeColumnsToContents()
