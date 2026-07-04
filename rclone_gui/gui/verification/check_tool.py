from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QStatusBar, QFileDialog,
)

from ...services.rclone_service import RcloneService


class CheckToolWidget(QWidget):
    def __init__(self, rclone: RcloneService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rclone = rclone
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Verificação de Integridade")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        form = QHBoxLayout()
        self._source_input = QLineEdit()
        self._source_input.setPlaceholderText("Origem (ex: /home/user/docs)")
        form.addWidget(QLabel("Origem:"))
        form.addWidget(self._source_input)

        self._dest_input = QLineEdit()
        self._dest_input.setPlaceholderText("Destino (ex: gdrive:Backup)")
        form.addWidget(QLabel("Destino:"))
        form.addWidget(self._dest_input)
        layout.addLayout(form)

        opts = QHBoxLayout()
        self._checksum_cb = QCheckBox("Usar checksum (mais preciso)")
        opts.addWidget(self._checksum_cb)
        self._one_way_cb = QCheckBox("One-way (verificar apenas se origem está no destino)")
        opts.addWidget(self._one_way_cb)
        self._check_btn = QPushButton("Verificar")
        self._check_btn.clicked.connect(self._check)
        opts.addWidget(self._check_btn)
        layout.addLayout(opts)

        self._results_table = QTableWidget()
        self._results_table.setColumnCount(4)
        self._results_table.setHorizontalHeaderLabels(["Path", "Tipo Diferença", "Origem", "Destino"])
        self._results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._results_table)

        btn_layout = QHBoxLayout()
        self._export_btn = QPushButton("Exportar CSV")
        self._export_btn.clicked.connect(self._export)
        self._export_btn.setEnabled(False)
        btn_layout.addWidget(self._export_btn)
        self._clear_btn = QPushButton("Limpar")
        self._clear_btn.clicked.connect(self._clear)
        btn_layout.addWidget(self._clear_btn)
        layout.addLayout(btn_layout)

        self._status = QStatusBar()
        layout.addWidget(self._status)

        self._differences: list[dict] = []

    def _check(self):
        src = self._source_input.text().strip()
        dst = self._dest_input.text().strip()
        if not src or not dst:
            QMessageBox.warning(self, "Erro", "Preencha origem e destino.")
            return
        import subprocess
        args = ["rclone", "check", src, dst, "--progress"]
        if self._checksum_cb.isChecked():
            args.append("--checksum")
        if self._one_way_cb.isChecked():
            args.append("--one-way")

        self._check_btn.setEnabled(False)
        self._status.showMessage("Verificando...")

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=300)
            output = result.stdout + result.stderr
            lines = output.split("\n")
            diffs = [l for l in lines if "ERROR" in l.upper() or "missing" in l.lower()]
            self._differences = [{"path": d, "type": "erro", "src": "", "dst": ""} for d in diffs]
            self._populate_results()
            if not diffs:
                QMessageBox.information(self, "Resultado", "Origem e destino são idênticos!")
            else:
                self._status.showMessage(f"{len(diffs)} diferença(s) encontrada(s)")
            self._export_btn.setEnabled(bool(diffs))
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Erro", "Verificação excedeu o tempo limite.")
        finally:
            self._check_btn.setEnabled(True)

    def _populate_results(self):
        self._results_table.setRowCount(len(self._differences))
        for i, d in enumerate(self._differences):
            self._results_table.setItem(i, 0, QTableWidgetItem(d.get("path", "")))
            self._results_table.setItem(i, 1, QTableWidgetItem(d.get("type", "")))
            self._results_table.setItem(i, 2, QTableWidgetItem(d.get("src", "")))
            self._results_table.setItem(i, 3, QTableWidgetItem(d.get("dst", "")))

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "verificacao.csv",
                                               "CSV (*.csv)")
        if path:
            import csv
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Path", "Tipo Diferença", "Origem", "Destino"])
                for d in self._differences:
                    w.writerow([d.get("path"), d.get("type"), d.get("src"), d.get("dst")])
            QMessageBox.information(self, "Exportado", f"Relatório salvo em:\n{path}")

    def _clear(self):
        self._differences.clear()
        self._results_table.setRowCount(0)
        self._status.clearMessage()
        self._export_btn.setEnabled(False)
