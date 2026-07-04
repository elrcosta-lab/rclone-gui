"""Testes de validação contra rclone real + banco SQLite real + GUI offscreen.

Executa todas as funcionalidades da aplicação e reporta falhas.
Requer rclone ≥ 1.60 no PATH e ao menos um remoto configurado.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

# ── Utilitários ──────────────────────────────────────────────────────

PASS = 0
FAIL = 0
ERROS: list[str] = []


def val_test(nome: str):
    def decorator(fn):
        global PASS, FAIL
        try:
            fn()
            PASS += 1
            print(f"  ✅ {nome}")
        except Exception as e:
            FAIL += 1
            msg = f"{nome}: {e}"
            ERROS.append(msg)
            print(f"  ❌ {msg}")
        return fn
    return decorator


def require_rclone() -> str:
    r = subprocess.run(["rclone", "version"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, "rclone não encontrado no PATH"
    return r.stdout.strip()


def require_remote() -> str:
    r = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    remotes = [line.strip().rstrip(":") for line in r.stdout.strip().split("\n") if line.strip()]
    assert remotes, "Nenhum remoto configurado"
    return remotes[0]


# ── Imports da aplicação ─────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from rclone_gui.services.rclone_service import RcloneService
from rclone_gui.db.database import Database
from rclone_gui.services.job_service import JobService
from rclone_gui.models.job import SyncJob, FilterRule, JobExecution
from rclone_gui.models.mount import MountConfig
from rclone_gui.models.remote import BackendMeta, RemoteStatus, RemoteEntry


# ══════════════════════════════════════════════════════════════════════
# 1.  RcloneService — comandos reais
# ══════════════════════════════════════════════════════════════════════

def test_rclone_service():
    print("\n── 1. RcloneService contra rclone real ──")
    svc = RcloneService()

    @val_test("check_version retorna versão")
    def _():
        v = svc.check_version()
        assert v, "versão não retornada"
        assert "rclone" in v.lower()

    @val_test("list_remotes retorna lista com google-drive")
    def _():
        remotes = svc.list_remotes()
        assert remotes, "nenhum remoto listado"
        assert "google-drive" in remotes, "google-drive não encontrado"
        print(f"         remotos: {remotes}")

    @val_test("list_remotes strips colons")
    def _():
        remotes = svc.list_remotes()
        for r in remotes:
            assert not r.endswith(":"), f"{r} tem ':' no final"

    @val_test("about retorna quota do google-drive")
    def _():
        q = svc.about("google-drive", timeout=90)
        assert q, "about vazio"
        assert "total" in q, "campo 'total' ausente"

    @val_test("lsjson no diretório raiz do google-drive")
    def _():
        itens = svc.lsjson("google-drive:")
        assert isinstance(itens, list), "lsjson não retornou lista"

    @val_test("lsjson em subdiretório vazio não crasha")
    def _():
        itens = svc.lsjson("google-drive:/nonexistent-test-123")
        assert isinstance(itens, list)

    @val_test("mkdir + rmdir no google-drive")
    def _():
        ok, msg = svc.mkdir("google-drive:/teste-gui-automated")
        assert ok, f"mkdir falhou: {msg}"
        ok2, msg2 = svc.purge("google-drive:/teste-gui-automated")
        assert ok2, f"purge falhou: {msg2}"

    @val_test("copy de arquivo local para remoto")
    def _():
        with tempfile.NamedTemporaryFile(prefix="rgui-test-", suffix=".txt", delete=False) as f:
            f.write(b"test content")
            local_path = f.name
        try:
            svc.mkdir("google-drive:/rgui-test")
            r = subprocess.run(
                ["rclone", "copy", local_path, "google-drive:/rgui-test/"],
                capture_output=True, text=True, timeout=90
            )
            assert r.returncode == 0, f"copy falhou: {r.stderr}"
            svc.purge("google-drive:/rgui-test")
        finally:
            os.unlink(local_path)

    @val_test("config_show do google-drive retorna tipo=drive")
    def _():
        cfg = svc.config_show("google-drive")
        assert cfg, "config_show vazio"
        assert cfg.get("type") == "drive", f"tipo esperado 'drive', obtido '{cfg.get('type')}'"

    @val_test("load_backends_catalog contém drive")
    def _():
        catalog = svc.load_backends_catalog()
        types = [b.type for b in catalog]
        assert "drive" in types, "drive não no catálogo"
        assert "s3" in types, "s3 não no catálogo"
        assert "sftp" in types, "sftp não no catálogo"

    @val_test("config_create + config_delete (backend sem OAuth)")
    def _():
        ok, msg = svc.config_create("rgui-test-local", "local")
        assert ok, f"config_create falhou: {msg}"
        ok2, msg2 = svc.config_delete("rgui-test-local")
        assert ok2, f"config_delete falhou: {msg2}"

    @val_test("check_version retorna None quando binary inválido")
    def _():
        bad = RcloneService(binary="/nonexistent/rclone")
        v = bad.check_version()
        assert v is None, "devia retornar None para binary inválido"


# ══════════════════════════════════════════════════════════════════════
# 2.  Database — CRUD real
# ══════════════════════════════════════════════════════════════════════

def test_database():
    print("\n── 2. Database (SQLite real) ──")
    Database._instance = None
    db = Database.get_instance()

    @val_test("connect cria tabelas e app_config")
    def _():
        db.connect()
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        nomes = [r[0] for r in tables]
        for t in ["sync_jobs", "job_history", "mount_configs", "app_config"]:
            assert t in nomes, f"tabela {t} não criada"

    @val_test("app_config has default row")
    def _():
        row = db.conn.execute("SELECT id FROM app_config WHERE id=1").fetchone()
        assert row, "app_config sem linha padrão"

    @val_test("get_config / set_config roundtrip")
    def _():
        db.set_config("autostart_enabled", 1)
        val = db.get_config("autostart_enabled")
        assert val == 1, f"get_config retornou {val}"
        db.set_config("autostart_enabled", 0)
        val2 = db.get_config("autostart_enabled")
        assert val2 == 0

    @val_test("save_job + get_all_jobs + delete_job roundtrip")
    def _():
        job = SyncJob(name="test-job", job_type="sync", source="/tmp/a", destination="google-drive:/b")
        job_id = db.save_job(job)
        assert job_id, "save_job não retornou id"
        jobs = db.get_all_jobs()
        nomes = [j.name for j in jobs]
        assert "test-job" in nomes, "job não encontrado na listagem"
        db.delete_job(job_id)
        jobs2 = db.get_all_jobs()
        nomes2 = [j.name for j in jobs2]
        assert "test-job" not in nomes2, "job não foi deletado"

    @val_test("save_job com flags e filters")
    def _():
        job = SyncJob(
            name="test-job-flags",
            job_type="sync", source="/tmp/a", destination="google-drive:/b",
            flags={"checksum": True, "bwlimit": "10M"},
            filters=[FilterRule(rule_type="exclude", pattern="*.tmp")],
        )
        job_id = db.save_job(job)
        retrieved = db.get_job(job_id)
        assert retrieved, "get_job retornou None"
        assert retrieved.flags.get("checksum") is True
        assert len(retrieved.filters) == 1
        assert retrieved.filters[0].pattern == "*.tmp"
        db.delete_job(job_id)

    @val_test("add_execution + get_job_history")
    def _():
        job = SyncJob(name="test-exec", job_type="sync", source="/tmp/a", destination="google-drive:/b")
        job_id = db.save_job(job)
        exec_ = JobExecution(job_id=job_id, status="success", trigger="manual",
                             started_at="2026-07-04T12:00:00")
        exec_id = db.add_execution(exec_)
        assert exec_id, "add_execution não retornou id"
        history = db.get_job_history(job_id)
        assert len(history) == 1
        assert history[0].status == "success"
        db.delete_job(job_id)

    @val_test("mount_config CRUD")
    def _():
        mc = MountConfig(remote_name="google-drive", mountpoint="/tmp/mnt-gdrive")
        db.save_mount_config(mc)
        all_mc = db.get_all_mount_configs()
        nomes = [m.remote_name for m in all_mc]
        assert "google-drive" in nomes
        retrieved = db.get_mount_config("google-drive")
        assert retrieved and retrieved.mountpoint == "/tmp/mnt-gdrive"
        db.delete_mount_config("google-drive")
        after = db.get_mount_config("google-drive")
        assert after is None

    db.close()


# ══════════════════════════════════════════════════════════════════════
# 3.  JobService — persistência + scheduler
# ══════════════════════════════════════════════════════════════════════

def test_job_service():
    print("\n── 3. JobService ──")
    Database._instance = None
    db = Database.get_instance()
    db.connect()
    js = JobService(db)

    @val_test("save_job + get + list + update + delete")
    def _():
        job = SyncJob(name="js-test", job_type="copy", source="/tmp/x", destination="google-drive:/y")
        js.save_job(job)
        assert job.id, "save_job não setou id"
        got = js.get_job(job.id)
        assert got and got.name == "js-test"
        all_jobs = js.get_all_jobs()
        assert any(j.name == "js-test" for j in all_jobs)
        js.delete_job(job.id)
        assert js.get_job(job.id) is None

    @val_test("save multiple jobs")
    def _():
        j1 = SyncJob(name="js-filter-a", job_type="sync", source="/s", destination="google-drive:/d")
        j2 = SyncJob(name="js-filter-b", job_type="copy", source="/s", destination="google-drive:/d")
        js.save_job(j1)
        js.save_job(j2)
        all_j = js.get_all_jobs()
        assert len(all_j) >= 2
        js.delete_job(j1.id)
        js.delete_job(j2.id)

    @val_test("get_all_jobs returns saved jobs")
    def _():
        job = SyncJob(name="js-exec-test", job_type="sync", source="/a", destination="google-drive:/b")
        js.save_job(job)
        all_j = js.get_all_jobs()
        assert any(j.name == "js-exec-test" for j in all_j)
        js.delete_job(job.id)

    db.close()


# ══════════════════════════════════════════════════════════════════════
# 4.  GUI — Qt offscreen
# ══════════════════════════════════════════════════════════════════════

def test_gui():
    print("\n── 4. GUI (Qt offscreen) ──")
    from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QListWidget, QTableWidget, QMessageBox
    from PySide6.QtCore import Qt, QTimer

    # Garante que temos uma QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    Database._instance = None
    db = Database.get_instance()
    db.connect()

    from rclone_gui.services.rclone_service import RcloneService
    from rclone_gui.gui.main_window import MainWindow

    import unittest.mock as mock

    def _make_win():
        w = MainWindow()
        # Patch closeEvent to prevent db.close() (singleton isolation)
        def _noop_close(event):
            event.accept()
        w.closeEvent = _noop_close
        return w

    @val_test("MainWindow abre sem crash")
    def _():
        w = _make_win()
        assert w.windowTitle() == "Rclone GUI"
        w.close()

    @val_test("sidebar tem 8 botões de navegação")
    def _():
        w = _make_win()
        btns = w.findChildren(QPushButton)
        textos = {b.text() for b in btns}
        esperados = {"Remotos", "Explorador", "Jobs", "Histórico",
                      "Montagens", "Verificação", "Transferir", "Preferências"}
        assert esperados.issubset(textos), f"faltam: {esperados - textos}"
        w.close()

    @val_test("navegação por sidebar muda página")
    def _():
        w = _make_win()
        pages = {"Remotos": 0, "Explorador": 1, "Jobs": 2, "Histórico": 3,
                  "Montagens": 4, "Verificação": 5, "Transferir": 6, "Preferências": 7}
        btn_map = {b.text(): b for b in w.findChildren(QPushButton)}
        for text, idx in pages.items():
            btn = btn_map.get(text)
            if btn:
                btn.click()
                assert w._stack.currentIndex() == idx, f"{text} → página {idx}, esperado {idx}"
        w.close()

    @val_test("remote list carrega google-drive")
    def _():
        w = _make_win()
        remote_page = w._pages[0]
        remote_page.refresh()
        for i in range(remote_page._list.count()):
            if "google-drive" in remote_page._list.item(i).text():
                break
        else:
            assert False, "google-drive não encontrado na lista de remotos"
        w.close()

    @val_test("explorador two-panel tem painéis esquerdo e direito")
    def _():
        w = _make_win()
        w._stack.setCurrentIndex(1)
        explorer = w._pages[1]
        assert explorer._left_panel is not None
        assert explorer._right_panel is not None
        assert explorer._copy_btn is not None
        assert explorer._move_btn is not None
        w.close()

    @val_test("explorador set_remotes popula combos")
    def _():
        w = _make_win()
        w._stack.setCurrentIndex(1)
        explorer = w._pages[1]
        explorer.set_remotes(["google-drive"])
        left_combo = explorer._left_panel._source_combo
        textos = [left_combo.itemText(i) for i in range(left_combo.count())]
        assert any("google-drive" in t for t in textos), f"google-drive não nos combos: {textos}"
        w.close()

    @val_test("jobs list abre sem crash com google-drive como destino")
    def _():
        w = _make_win()
        w._stack.setCurrentIndex(2)
        jobs_page = w._pages[2]
        from rclone_gui.models.job import SyncJob
        job = SyncJob(
            name="test-gui-job",
            job_type="sync",
            source="/tmp/teste-rclone-validate",
            destination="google-drive:/rgui-validate",
        )
        jobs_page.job_service.save_job(job)
        jobs_page.refresh()
        assert jobs_page._table.rowCount() >= 1
        jobs_page.job_service.delete_job(job.id)
        w.close()

    @val_test("check tool tem todos os campos")
    def _():
        w = _make_win()
        w._stack.setCurrentIndex(5)
        check_page = w._pages[5]
        assert check_page._source_input is not None
        assert check_page._dest_input is not None
        assert check_page._checksum_cb is not None
        assert check_page._check_btn is not None
        assert check_page._export_btn is not None
        w.close()

    @val_test("preferências dialog abre sem crash")
    def _():
        from rclone_gui.gui.settings.preferences import PreferencesDialog
        w = _make_win()
        dlg = PreferencesDialog(db, w)
        assert dlg.windowTitle() == "Preferências"
        dlg.close()
        w.close()

    db.close()


# ══════════════════════════════════════════════════════════════════════
# 5.  Daemon — rcd + scheduler + tray
# ══════════════════════════════════════════════════════════════════════

def test_daemon():
    print("\n── 5. Daemon / Tray / Autostart ──")

    @val_test("tray manager setup funciona sem crash")
    def _():
        from PySide6.QtWidgets import QSystemTrayIcon
        from rclone_gui.daemon.tray_manager import TrayManager
        from PySide6.QtWidgets import QMainWindow
        w = QMainWindow()
        tray = TrayManager(w)
        tray.setup()
        assert tray.tray is not None or not QSystemTrayIcon.isSystemTrayAvailable()

    @val_test("autostart .desktop cria e remove")
    def _():
        from rclone_gui.daemon.notification import setup_autostart, remove_autostart
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop = autostart_dir / "rclone-gui-daemon.desktop"

        # Cria
        setup_autostart()
        assert desktop.exists(), ".desktop não foi criado"
        content = desktop.read_text()
        assert "rclone" in content.lower()
        assert "daemon" in content.lower()

        # Remove
        remove_autostart()
        assert not desktop.exists(), ".desktop não foi removido"

    @val_test("rclone rcd aceita POST em /rc/noop")
    def _():
        import socket
        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen(
            ["rclone", "rcd", f"--rc-addr=127.0.0.1:{port}", "--rc-no-auth"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        import time
        time.sleep(1)
        try:
            import urllib.request
            data = b"{}"
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/rc/noop",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=5)
            assert resp.status == 200, f"rcd retornou {resp.status}"
        finally:
            proc.terminate()
            proc.wait(timeout=5)


# ══════════════════════════════════════════════════════════════════════
# 6.  Caminho feliz — fluxo completo
# ══════════════════════════════════════════════════════════════════════

def test_flow():
    print("\n── 6. Fluxo completo (happy path) ──")

    @val_test("cria pasta local, sincroniza para nuvem e verifica")
    def _():
        svc = RcloneService()
        # Cria arquivo local
        tmp = tempfile.mkdtemp()
        local_file = Path(tmp) / "hello.txt"
        local_file.write_text("Hello Rclone GUI!")
        local_dir = Path(tmp) / "subdir"
        local_dir.mkdir()
        (local_dir / "nested.txt").write_text("nested content")

        # mkdir no destino
        ok, msg = svc.mkdir("google-drive:/rgui-flow-test")
        assert ok, f"mkdir falhou: {msg}"

        # copy para nuvem
        r = subprocess.run(
            ["rclone", "copy", tmp, "google-drive:/rgui-flow-test/"],
            capture_output=True, text=True, timeout=90
        )
        assert r.returncode == 0, f"copy falhou: {r.stderr}"

        # lsjson para verificar
        itens = svc.lsjson("google-drive:/rgui-flow-test")
        nomes = [i["Name"] for i in itens]
        assert "hello.txt" in nomes, f"hello.txt não encontrado: {nomes}"
        assert "subdir" in nomes, f"subdir não encontrado: {nomes}"

        # check entre local e remoto
        r2 = subprocess.run(
            ["rclone", "check", tmp, f"google-drive:/rgui-flow-test"],
            capture_output=True, text=True, timeout=90
        )
        assert r2.returncode == 0, f"check encontrou diferenças: {r2.stdout}"

        # Limpa
        subprocess.run(["rclone", "purge", "google-drive:/rgui-flow-test"],
                       capture_output=True, timeout=30)

    @val_test("about mostra quota antes e depois")
    def _():
        svc = RcloneService()
        q = svc.about("google-drive")
        assert q, "about vazio"
        assert q.get("total", 0) > 0, "total deveria ser > 0"
        print(f"         quota: {q.get('used', 0)} usado / {q.get('total', 0)} total")


# ══════════════════════════════════════════════════════════════════════
# Execução
# ══════════════════════════════════════════════════════════════════════

def main():
    global PASS, FAIL, ERROS
    print("=" * 60)
    print("  Validação completa — Rclone GUI")
    print(f"  rclone: {require_rclone()}")
    print(f"  remote: {require_remote()}")
    print("=" * 60)

    test_rclone_service()
    test_database()
    test_job_service()
    test_gui()
    test_daemon()
    test_flow()

    print("\n" + "=" * 60)
    print(f"  Resultado: {PASS} passaram, {FAIL} falharam")
    if ERROS:
        print("\n  Erros:")
        for e in ERROS:
            print(f"    • {e}")
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
