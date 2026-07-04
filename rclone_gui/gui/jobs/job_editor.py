from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QCheckBox, QComboBox, QDialog, QTabWidget, QTextEdit,
    QLineEdit, QFormLayout, QGroupBox, QSpinBox, QDialogButtonBox,
)

from ...services.job_service import JobService
from ...models.job import SyncJob, FilterRule


class JobEditor(QDialog):
    def __init__(self, job_service: JobService, job: Optional[SyncJob] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.job_service = job_service
        self._job = job or SyncJob()
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Criar/Editar Job")
        self.setMinimumSize(550, 550)
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        basic = QWidget()
        advanced = QWidget()
        tabs.addTab(basic, "Básico")
        tabs.addTab(advanced, "Avançado")

        # Basic tab
        basic_layout = QFormLayout(basic)
        self._name_input = QLineEdit(self._job.name)
        basic_layout.addRow("Nome:", self._name_input)

        self._type_combo = QComboBox()
        for t in ["sync", "copy", "move", "bisync"]:
            self._type_combo.addItem(t.capitalize(), t)
        self._type_combo.setCurrentIndex(["sync", "copy", "move", "bisync"].index(self._job.job_type))
        basic_layout.addRow("Tipo:", self._type_combo)

        self._source_input = QLineEdit(self._job.source)
        self._source_input.setPlaceholderText("Ex: /home/user/docs ou gdrive:Backup")
        basic_layout.addRow("Origem:", self._source_input)

        self._dest_input = QLineEdit(self._job.destination)
        self._dest_input.setPlaceholderText("Ex: gdrive:Backup")
        basic_layout.addRow("Destino:", self._dest_input)

        self._dry_run_cb = QCheckBox("Executar dry-run primeiro")
        self._dry_run_cb.setChecked(self._job.dry_run_first)
        basic_layout.addRow(self._dry_run_cb)

        # Advanced tab
        adv_layout = QFormLayout(advanced)
        self._checksum_cb = QCheckBox()
        self._checksum_cb.setChecked(self._job.flags.get("checksum", False))
        adv_layout.addRow("Checksum:", self._checksum_cb)

        self._bwlimit_input = QLineEdit(self._job.flags.get("bwlimit", ""))
        self._bwlimit_input.setPlaceholderText("Ex: 10M ou 10M:off")
        adv_layout.addRow("Bwlimit:", self._bwlimit_input)

        self._transfers_spin = QSpinBox()
        self._transfers_spin.setRange(1, 64)
        self._transfers_spin.setValue(self._job.flags.get("transfers", 4))
        adv_layout.addRow("Transfers:", self._transfers_spin)

        self._checkers_spin = QSpinBox()
        self._checkers_spin.setRange(1, 256)
        self._checkers_spin.setValue(self._job.flags.get("checkers", 8))
        adv_layout.addRow("Checkers:", self._checkers_spin)

        self._retries_spin = QSpinBox()
        self._retries_spin.setRange(1, 20)
        self._retries_spin.setValue(self._job.flags.get("retries", 3))
        adv_layout.addRow("Retries:", self._retries_spin)

        # Schedule
        sched_group = QGroupBox("Agendamento")
        sched_layout = QFormLayout(sched_group)
        self._enabled_cb = QCheckBox("Habilitar agendamento")
        self._enabled_cb.setChecked(self._job.schedule_enabled)
        sched_layout.addRow(self._enabled_cb)

        self._schedule_combo = QComboBox()
        for k, v in [("Manual", "manual"), ("A cada N minutos", "minutes"),
                     ("A cada hora", "hourly"), ("Diário", "daily"),
                     ("Semanal", "weekly"), ("Cron customizado", "custom")]:
            self._schedule_combo.addItem(k, v)
        idx = self._schedule_combo.findData(self._job.schedule_type)
        if idx >= 0:
            self._schedule_combo.setCurrentIndex(idx)
        sched_layout.addRow("Frequência:", self._schedule_combo)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 1440)
        self._interval_spin.setValue(self._job.schedule_interval or 30)
        sched_layout.addRow("Intervalo (min):", self._interval_spin)

        self._cron_input = QLineEdit(self._job.schedule_cron or "0 2 * * *")
        self._cron_input.setPlaceholderText("Ex: 0 2 * * *")
        sched_layout.addRow("Cron expr:", self._cron_input)
        adv_layout.addRow(sched_group)

        layout.addWidget(tabs)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        self._job.name = self._name_input.text().strip()
        self._job.job_type = self._type_combo.currentData()
        self._job.source = self._source_input.text().strip()
        self._job.destination = self._dest_input.text().strip()
        self._job.dry_run_first = self._dry_run_cb.isChecked()
        self._job.flags = {
            "checksum": self._checksum_cb.isChecked(),
            "bwlimit": self._bwlimit_input.text().strip(),
            "transfers": self._transfers_spin.value(),
            "checkers": self._checkers_spin.value(),
            "retries": self._retries_spin.value(),
        }
        self._job.schedule_enabled = self._enabled_cb.isChecked()
        self._job.schedule_type = self._schedule_combo.currentData()
        self._job.schedule_interval = self._interval_spin.value()
        self._job.schedule_cron = self._cron_input.text().strip()

        if not self._job.name:
            QMessageBox.warning(self, "Erro", "Nome do job é obrigatório.")
            return
        if not self._job.source or not self._job.destination:
            QMessageBox.warning(self, "Erro", "Origem e destino são obrigatórios.")
            return
        self.job_service.save_job(self._job)
        self.accept()

    def job(self) -> SyncJob:
        return self._job


class JobListWidget(QWidget):
    def __init__(self, job_service: JobService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.job_service = job_service
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Jobs de Sincronização")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("Novo Job")
        self._add_btn.clicked.connect(self._add)
        btn_layout.addWidget(self._add_btn)
        self._edit_btn = QPushButton("Editar")
        self._edit_btn.clicked.connect(self._edit)
        self._edit_btn.setEnabled(False)
        btn_layout.addWidget(self._edit_btn)
        self._del_btn = QPushButton("Excluir")
        self._del_btn.clicked.connect(self._delete)
        self._del_btn.setEnabled(False)
        btn_layout.addWidget(self._del_btn)
        self._run_btn = QPushButton("Executar Agora")
        self._run_btn.clicked.connect(self._run)
        self._run_btn.setEnabled(False)
        btn_layout.addWidget(self._run_btn)
        layout.addLayout(btn_layout)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Status", "Nome", "Tipo", "Origem", "Destino", "Agendamento"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.doubleClicked.connect(self._edit)
        layout.addWidget(self._table)

    def refresh(self):
        jobs = self.job_service.get_all_jobs()
        self._table.setRowCount(len(jobs))
        for i, j in enumerate(jobs):
            status = "✓" if j.enabled else "✗"
            schedule = j.schedule_type if j.schedule_enabled else "Manual"
            self._table.setItem(i, 0, QTableWidgetItem(status))
            self._table.setItem(i, 1, QTableWidgetItem(j.name))
            self._table.setItem(i, 2, QTableWidgetItem(j.job_type))
            self._table.setItem(i, 3, QTableWidgetItem(j.source))
            self._table.setItem(i, 4, QTableWidgetItem(j.destination))
            self._table.setItem(i, 5, QTableWidgetItem(schedule))
            item = QTableWidgetItem(str(j.id))
            item.setData(Qt.UserRole, j.id)
            self._table.setItem(i, 0, item)
        self._table.resizeColumnsToContents()

    def _on_selection(self):
        has = len(self._table.selectedItems()) > 0
        self._edit_btn.setEnabled(has)
        self._del_btn.setEnabled(has)
        self._run_btn.setEnabled(has)

    def _selected_id(self) -> Optional[int]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _add(self):
        dialog = JobEditor(self.job_service, None, self)
        if dialog.exec():
            self.refresh()

    def _edit(self):
        job_id = self._selected_id()
        if not job_id:
            return
        job = self.job_service.get_job(job_id)
        if not job:
            return
        dialog = JobEditor(self.job_service, job, self)
        if dialog.exec():
            self.refresh()

    def _delete(self):
        job_id = self._selected_id()
        if not job_id:
            return
        reply = QMessageBox.question(self, "Confirmar",
                                     "Excluir este job permanentemente?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.job_service.delete_job(job_id)
            self.refresh()

    def _run(self):
        job_id = self._selected_id()
        if not job_id:
            return
        from datetime import datetime
        job = self.job_service.get_job(job_id)
        if not job:
            return
        if job.dry_run_first:
            reply = QMessageBox.question(
                self, "Executar Dry-Run",
                "Dry-run está ativado para este job.\nExecutar dry-run primeiro?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                QMessageBox.information(self, "Dry-Run",
                                        "Dry-run em andamento.\n"
                                        "Funcionalidade completa em breve.")
                return
        QMessageBox.information(self, "Executar",
                                f"Executando job '{job.name}'...\nProgresso em breve.")
