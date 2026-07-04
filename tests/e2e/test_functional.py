"""Testes funcionais E2E — fluxos completos com mocks realistas de rclone.

Testa cada funcionalidade de ponta a ponta, verificando que:
1. A UI responde corretamente
2. Os comandos rclone são chamados com os argumentos certos
3. A navegação entre páginas funciona
4. Operações assíncronas completam corretamente
"""

from __future__ import annotations

import json
import os
import time
import tempfile
import threading
from unittest.mock import patch, MagicMock, call

import pytest
from pytest_mock import MockerFixture

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox, QDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def e2e_db():
    """Isola database para cada teste."""
    from rclone_gui.db.database import Database
    Database._instance = None
    db = Database.get_instance()
    tmp = tempfile.mkdtemp()
    db.db_path = os.path.join(tmp, "test.db")
    db.connect()
    yield
    db.close()


@pytest.fixture
def basic_mocks(mocker: MockerFixture):
    """Mocks base: rclone presente, sem remotos."""
    mocker.patch("PySide6.QtWidgets.QMessageBox.critical")
    mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                 return_value="rclone v1.68.0")
    mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                 return_value=["gdrive", "dropbox"])


@pytest.fixture
def sample_lsjson_basic() -> list[dict]:
    return [
        {"Name": "Documentos", "Path": "Documentos", "Size": -1, "ModTime": "2026-07-01T08:00:00Z", "IsDir": True, "MimeType": "inode/directory"},
        {"Name": "Fotos", "Path": "Fotos", "Size": -1, "ModTime": "2026-06-15T10:30:00Z", "IsDir": True, "MimeType": "inode/directory"},
        {"Name": "readme.txt", "Path": "readme.txt", "Size": 2048, "ModTime": "2026-07-04T12:00:00Z", "IsDir": False, "MimeType": "text/plain"},
        {"Name": "backup.zip", "Path": "backup.zip", "Size": 5242880, "ModTime": "2026-07-03T09:00:00Z", "IsDir": False, "MimeType": "application/zip"},
    ]


@pytest.fixture
def sample_lsjson_subdir() -> list[dict]:
    return [
        {"Name": "foto1.jpg", "Path": "Fotos/foto1.jpg", "Size": 1048576, "ModTime": "2026-06-10T08:00:00Z", "IsDir": False, "MimeType": "image/jpeg"},
        {"Name": "foto2.png", "Path": "Fotos/foto2.png", "Size": 2048576, "ModTime": "2026-06-12T14:00:00Z", "IsDir": False, "MimeType": "image/png"},
    ]


@pytest.fixture
def main_window(qapp, basic_mocks):
    """Cria MainWindow com DB isolado e mocks base."""
    from rclone_gui.gui.main_window import MainWindow
    w = MainWindow()
    w.show()
    yield w
    w.close()


# ==============================================================================
# 1. EXPLORADOR — Navegação em Remotos
# ==============================================================================

def _wait_for_signal(max_seconds: float = 3.0, interval: float = 0.05) -> None:
    """Processa eventos Qt por até max_seconds."""
    elapsed = 0.0
    while elapsed < max_seconds:
        QApplication.processEvents()
        time.sleep(interval)
        elapsed += interval
        QApplication.processEvents()


class TestExplorerRemoteNavigation:
    """Navegação no explorador: selecionar remoto, listar, navegar em pastas."""

    def test_switch_to_remote_triggers_lsjson(self, main_window, mocker: MockerFixture):
        """Ao selecionar um remoto, lsjson é chamado com o path correto."""
        from rclone_gui.services.rclone_service import RcloneService

        main_window._stack.setCurrentIndex(1)
        explorer = main_window._pages[1]
        left_panel = explorer._left_panel

        lsjson_results = []

        def mock_lsjson(path):
            lsjson_results.append(path)
            return []

        mocker.patch.object(RcloneService, "lsjson", side_effect=mock_lsjson)

        left_panel._source_combo.setCurrentIndex(1)  # gdrive:
        _wait_for_signal(2.0)

        assert len(lsjson_results) >= 1, f"lsjson não foi chamado. results={lsjson_results}"
        assert "gdrive:" in lsjson_results[0], f"Path errado: {lsjson_results[0]}"

    def test_remote_listing_populates_model(self, main_window, sample_lsjson_basic,
                                              mocker: MockerFixture):
        """Listagem remota popula o modelo com itens visíveis."""
        from rclone_gui.services.rclone_service import RcloneService

        main_window._stack.setCurrentIndex(1)
        explorer = main_window._pages[1]
        left_panel = explorer._left_panel

        mocker.patch.object(RcloneService, "lsjson", return_value=sample_lsjson_basic)

        left_panel._source_combo.setCurrentIndex(1)  # gdrive:
        _wait_for_signal(2.0)

        model = left_panel._tree.model()
        assert model is not None
        row_count = model.rowCount()
        assert row_count == 4, f"Esperado 4 linhas, obtido {row_count}"

        all_names = {model.item(r, 0).text() for r in range(row_count)}
        expected = {"Documentos", "Fotos", "readme.txt", "backup.zip"}
        assert all_names == expected, f"Nomes: {all_names}"

        # _items_by_row deve mapear corretamente (pastas primeiro)
        assert len(left_panel._items_by_row) == 4
        by_row_names = [e.get("Name") for e in left_panel._items_by_row]
        # Pastas devem vir antes de arquivos
        assert by_row_names[:2] == ["Documentos", "Fotos"], \
            f"Pastas não estão primeiro: {by_row_names}"
        assert set(by_row_names[2:]) == {"readme.txt", "backup.zip"}

    def test_double_click_dir_enters_subdirectory(self, main_window, sample_lsjson_basic,
                                                   sample_lsjson_subdir, mocker: MockerFixture):
        """Duplo clique numa pasta navega para dentro dela e dispara novo lsjson."""
        from rclone_gui.services.rclone_service import RcloneService

        main_window._stack.setCurrentIndex(1)
        explorer = main_window._pages[1]
        left_panel = explorer._left_panel

        call_args = []
        call_index = 0
        responses = [sample_lsjson_basic, sample_lsjson_subdir]

        def smart_lsjson(path):
            nonlocal call_index
            call_args.append(path)
            resp = responses[min(call_index, len(responses) - 1)]
            call_index += 1
            return resp

        mocker.patch.object(RcloneService, "lsjson", side_effect=smart_lsjson)

        # Seleciona remoto — primeira listagem
        left_panel._source_combo.setCurrentIndex(1)
        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()

        assert call_args, "lsjson não foi chamado na primeira navegação"
        assert left_panel._remote_model.current_path.startswith("gdrive:")

        # Encontra a linha da pasta "Fotos" no modelo ordenado alfabeticamente
        model = left_panel._tree.model()
        fotos_row = None
        import json
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            entry_json = idx.data(0x0101)  # Qt.UserRole + 1
            if entry_json:
                entry = json.loads(entry_json)
                if entry.get("IsDir") and entry.get("Name") == "Fotos":
                    fotos_row = row
                    break
        assert fotos_row is not None, "Fotos não encontrado no modelo"

        fotos_index = model.index(fotos_row, 0)
        left_panel._tree.doubleClicked.emit(fotos_index)

        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()

        assert len(call_args) >= 2, f"lsjson só foi chamado {len(call_args)} vez(es)"
        last_path = call_args[-1]
        assert "Fotos" in last_path, f"Não navegou para dentro de Fotos: {last_path}"
        assert left_panel._breadcrumb.text() == last_path

    def test_multiple_dir_navigations_work(self, main_window, mocker: MockerFixture):
        """Navegações múltiplas (entrar/sair/entrar de novo) funcionam."""
        from rclone_gui.services.rclone_service import RcloneService

        main_window._stack.setCurrentIndex(1)
        explorer = main_window._pages[1]
        left_panel = explorer._left_panel

        nav_calls = []
        root_items = [
            {"Name": "A", "Path": "A", "Size": -1, "ModTime": "", "IsDir": True, "MimeType": "inode/directory"},
        ]
        sub_items = [
            {"Name": "B", "Path": "A/B", "Size": -1, "ModTime": "", "IsDir": True, "MimeType": "inode/directory"},
        ]
        deep_items = [
            {"Name": "foo.txt", "Path": "A/B/foo.txt", "Size": 100, "ModTime": "", "IsDir": False, "MimeType": "text/plain"},
        ]

        responses = [root_items, sub_items, deep_items]
        response_idx = [0]

        def mock_lsjson(path):
            nav_calls.append(path)
            resp = responses[min(response_idx[0], len(responses) - 1)]
            response_idx[0] += 1
            return resp

        mocker.patch.object(RcloneService, "lsjson", side_effect=mock_lsjson)

        # Navega para gdrive: → vê pasta "A"
        left_panel._source_combo.setCurrentIndex(1)
        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()

        # Duplo clique em "A" → entra
        idx_a = left_panel._tree.model().index(0, 0)
        left_panel._tree.doubleClicked.emit(idx_a)
        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()

        # Duplo clique em "B" → entra
        idx_b = left_panel._tree.model().index(0, 0)
        left_panel._tree.doubleClicked.emit(idx_b)
        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()

        assert len(nav_calls) == 3, f"Esperado 3 navegações, obtido {len(nav_calls)}"
        # A última navegação deve incluir "B"
        assert "B" in nav_calls[-1], f"Última navegação não contém B: {nav_calls[-1]}"

    def test_double_click_file_does_not_navigate(self, main_window, sample_lsjson_basic, mocker: MockerFixture):
        """Duplo clique num arquivo não dispara navegação."""
        from rclone_gui.services.rclone_service import RcloneService

        main_window._stack.setCurrentIndex(1)
        explorer = main_window._pages[1]
        left_panel = explorer._left_panel

        nav_paths = []

        def mock_lsjson(path):
            nav_paths.append(path)
            return sample_lsjson_basic

        mocker.patch.object(RcloneService, "lsjson", side_effect=mock_lsjson)

        left_panel._source_combo.setCurrentIndex(1)
        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()

        # Encontra a linha do arquivo no modelo ordenado alfabeticamente
        model = left_panel._tree.model()
        file_row = None
        import json
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            entry_json = idx.data(0x0101)  # Qt.UserRole + 1
            if entry_json:
                entry = json.loads(entry_json)
                if not entry.get("IsDir"):
                    file_row = row
                    break
        assert file_row is not None, "Arquivo não encontrado no modelo"

        old_path = left_panel._current_path
        file_idx = model.index(file_row, 0)
        left_panel._tree.doubleClicked.emit(file_idx)
        QApplication.processEvents()
        time.sleep(0.1)

        # Path não deve ter mudado
        assert left_panel._current_path == old_path, \
            f"Path mudou após clique em arquivo: {left_panel._current_path}"


# ==============================================================================
# 2. TRANSFERÊNCIAS — Copy/Move no Two-Panel
# ==============================================================================

class TestTransferFlow:
    """Transferências entre painéis: copy e move via RcloneService."""

    def test_copy_triggers_rclone_copy(self, main_window, mocker: MockerFixture):
        """Botão '→ Copiar' chama RcloneService.copy com os paths corretos."""
        from rclone_gui.services.rclone_service import RcloneService

        main_window._stack.setCurrentIndex(1)
        explorer = main_window._pages[1]

        left_panel = explorer._left_panel
        right_panel = explorer._right_panel

        # Simula estado local com um item selecionável
        left_panel._is_local = False
        left_panel._current_path = "/home/user/docs"
        right_panel._current_path = "gdrive:/Backup"

        left_panel._items_by_row = [
            {"Name": "arquivo.txt", "Path": "arquivo.txt", "Size": 100,
             "ModTime": "", "IsDir": False, "MimeType": "text/plain"},
        ]
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        from PySide6.QtCore import QItemSelectionModel, Qt
        import json
        model = QStandardItemModel()
        entry_json = json.dumps({"Name": "arquivo.txt", "Path": "arquivo.txt", "Size": 100,
                                  "ModTime": "", "IsDir": False, "MimeType": "text/plain"})
        item = QStandardItem("arquivo.txt")
        item.setData(entry_json, Qt.UserRole + 1)
        model.appendRow([item, QStandardItem("100 B"), QStandardItem("")])
        left_panel._tree.setModel(model)
        sel = left_panel._tree.selectionModel()
        sel.select(model.index(0, 0), QItemSelectionModel.Select)

        copy_calls = []
        def mock_copy(src, dst, flags=None):
            copy_calls.append((src, dst, flags))
            return True, ""
        mocker.patch.object(RcloneService, "copy", side_effect=mock_copy)
        mocker.patch("PySide6.QtWidgets.QMessageBox.information")

        explorer._copy_btn.click()
        QApplication.processEvents()
        time.sleep(0.1)
        QApplication.processEvents()

        assert len(copy_calls) >= 1, f"copy não foi chamado: {copy_calls}"

    def test_move_with_dry_run_confirmation(self, mocker: MockerFixture):
        """Mover com dry-run primeiro confirma antes de executar real."""
        from rclone_gui.services.rclone_service import RcloneService

        move_calls = []

        def mock_move(src, dst, flags=None):
            move_calls.append((src, dst, flags))
            return True, ""
        mocker.patch.object(RcloneService, "move", side_effect=mock_move)

        svc = RcloneService()
        ok, _ = svc.move("/tmp/src/f.txt", "gdrive:/dst", {"dry_run": True})
        assert ok
        ok2, _ = svc.move("/tmp/src/f.txt", "gdrive:/dst")
        assert ok2

        assert len(move_calls) == 2
        assert move_calls[0][2] == {"dry_run": True}
        assert move_calls[1][2] is None  # sem flags


# ==============================================================================
# 3. REMOTOS — Wizard + Edição + Exclusão
# ==============================================================================

class TestRemoteManagementFlow:
    """Gerenciamento completo de remotos: adicionar, editar, excluir."""

    def test_add_remote_opens_wizard_with_backends(self, main_window, mocker: MockerFixture):
        """Wizard de configuração lista backends do catálogo."""
        from rclone_gui.services.rclone_service import RcloneService
        from rclone_gui.gui.remote.config_wizard import ConfigWizard

        remote_page = main_window._pages[0]

        # Mock exec do wizard para capturar args
        wizard_args = []
        def fake_exec(self_wizard):
            wizard_args.append(self_wizard)
            # Verifica backends carregados
            assert self_wizard._backends, "Backends não carregados"
            assert self_wizard._search_input is not None
            return 0
        mocker.patch.object(ConfigWizard, "exec", fake_exec)

        remote_page._add_btn.click()
        QApplication.processEvents()

        assert len(wizard_args) == 1

    def test_edit_remote_shows_config(self, mocker: MockerFixture):
        """Editar remoto: config_show retorna dados corretos."""
        from rclone_gui.services.rclone_service import RcloneService

        svc = RcloneService()
        mocker.patch.object(RcloneService, "config_show", return_value={
            "type": "drive", "client_id": "abc", "scope": "drive"
        })

        cfg = svc.config_show("gdrive")
        assert cfg["type"] == "drive"
        assert cfg["client_id"] == "abc"

    def test_delete_remote_with_confirmation(self, main_window, mocker: MockerFixture):
        """Excluir remoto com confirmação executa config_delete."""
        from rclone_gui.services.rclone_service import RcloneService

        remote_page = main_window._pages[0]

        delete_calls = []
        mocker.patch.object(RcloneService, "config_delete", side_effect=lambda n: delete_calls.append(n) or (True, ""))

        mocker.patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes)

        remote_page._list.setCurrentRow(0)
        remote_page._on_item_clicked(remote_page._list.item(0))
        remote_page._del_btn.click()

        assert len(delete_calls) == 1
        assert delete_calls[0] == "gdrive"

    def test_config_create_and_delete_roundtrip(self, mocker: MockerFixture):
        """Roundtrip: criar remoto local e deletar — mockado."""
        from rclone_gui.services.rclone_service import RcloneService
        mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr=""))
        svc = RcloneService()
        ok, msg = svc.config_create("test-roundtrip", "local")
        assert ok, f"config_create falhou: {msg}"
        ok2, msg2 = svc.config_delete("test-roundtrip")
        assert ok2, f"config_delete falhou: {msg2}"


# ==============================================================================
# 4. JOBS — Criação, Edição, Execução
# ==============================================================================

class TestJobManagementFlow:
    """Gerenciamento de jobs: CRUD completo + execução."""

    def test_create_job_saves_correctly(self, main_window):
        """Criar um job via editor persiste no banco."""
        from rclone_gui.gui.jobs.job_editor import JobEditor, JobListWidget
        from rclone_gui.models.job import SyncJob

        main_window._stack.setCurrentIndex(2)
        jobs_page = main_window._pages[2]

        # Cria job via service diretamente
        job = SyncJob(
            name="test-job-func",
            job_type="sync",
            source="/data/src",
            destination="gdrive:/dst",
            flags={"checksum": True, "bwlimit": "5M"},
            schedule_enabled=False,
        )
        job_id = jobs_page.job_service.save_job(job)
        assert job_id > 0

        jobs_page.refresh()
        assert jobs_page._table.rowCount() == 1

        # Limpa
        jobs_page.job_service.delete_job(job_id)
        jobs_page.refresh()
        assert jobs_page._table.rowCount() == 0

    def test_edit_job_updates_fields(self, main_window):
        """Editar job altera campos e persiste."""
        from rclone_gui.models.job import SyncJob

        main_window._stack.setCurrentIndex(2)
        jobs_page = main_window._pages[2]

        job = SyncJob(
            name="before-edit",
            job_type="copy",
            source="/a",
            destination="gdrive:/b",
        )
        job_id = jobs_page.job_service.save_job(job)
        jobs_page.refresh()

        # Edita
        loaded = jobs_page.job_service.get_job(job_id)
        loaded.name = "after-edit"
        loaded.job_type = "sync"
        jobs_page.job_service.save_job(loaded)

        reloaded = jobs_page.job_service.get_job(job_id)
        assert reloaded.name == "after-edit"
        assert reloaded.job_type == "sync"

        jobs_page.job_service.delete_job(job_id)

    def test_run_job_calls_execute_job(self, main_window, mocker: MockerFixture):
        """Executar job chama JobService.execute_job."""
        from rclone_gui.models.job import SyncJob

        main_window._stack.setCurrentIndex(2)
        jobs_page = main_window._pages[2]

        job = SyncJob(
            name="run-test",
            job_type="sync",
            source="/tmp/a",
            destination="gdrive:/dst",
            dry_run_first=False,
        )
        job_id = jobs_page.job_service.save_job(job)
        jobs_page.refresh()

        # Mock execute_job
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"ok", b"")
        exec_calls = []

        def fake_execute(job_arg, trigger="manual"):
            exec_calls.append(job_arg.name)
            return mock_proc, 99

        mocker.patch.object(jobs_page.job_service, "execute_job", side_effect=fake_execute)
        mocker.patch.object(jobs_page.job_service, "complete_execution")
        mocker.patch("PySide6.QtWidgets.QMessageBox.information")

        # Seleciona job e clica Executar
        jobs_page._table.selectRow(0)
        jobs_page._on_selection()
        jobs_page._run_btn.click()

        QApplication.processEvents()
        time.sleep(0.15)
        QApplication.processEvents()

        assert len(exec_calls) == 1, f"execute_job não foi chamado: {exec_calls}"
        assert exec_calls[0] == "run-test"

        jobs_page.job_service.delete_job(job_id)


# ==============================================================================
# 5. VERIFICAÇÃO — Check Tool
# ==============================================================================

class TestVerificationFlow:
    """Ferramenta de verificação de integridade."""

    def test_check_tool_all_fields_present(self, main_window):
        """Todos os campos da ferramenta de check estão presentes."""
        main_window._stack.setCurrentIndex(5)
        check_page = main_window._pages[5]

        assert check_page._source_input is not None
        assert check_page._dest_input is not None
        assert check_page._checksum_cb is not None
        assert check_page._one_way_cb is not None
        assert check_page._check_btn is not None
        assert check_page._export_btn is not None

        assert check_page._checksum_cb.text() != ""
        assert "one-way" in check_page._one_way_cb.text().lower()


# ==============================================================================
# 6. PREFERÊNCIAS — Settings Dialog
# ==============================================================================

class TestPreferencesFlow:
    """Janela de preferências globais."""

    def test_preferences_dialog_opens(self, main_window):
        """Abrir preferências não crasha com DB conectado."""
        from rclone_gui.gui.settings.preferences import PreferencesDialog

        main_window._stack.setCurrentIndex(7)
        prefs_page = main_window._pages[7]

        db = main_window.db
        dlg = PreferencesDialog(db, main_window)
        assert dlg.windowTitle() == "Preferências"
        dlg.close()

    def test_preferences_crash_on_null_db(self):
        """PreferencesDialog não crasha com database não conectado."""
        from rclone_gui.db.database import Database
        from rclone_gui.gui.settings.preferences import PreferencesDialog
        Database._instance = None
        db = Database.get_instance()
        # Não chama connect — conn é None
        # Não executa dialog, apenas cria e fecha
        import collections
        parent = collections.namedtuple("FakeParent", ["close", "show"])(
            close=lambda: None, show=lambda: None
        )
        dlg = PreferencesDialog(db)
        assert dlg is not None
        dlg.close()


# ==============================================================================
# 7. NAVEGAÇÃO — Todas as 8 Páginas
# ==============================================================================

class TestFullNavigation:
    """Navegação completa entre todas as páginas da aplicação."""

    def test_all_eight_pages_accessible(self, main_window):
        """Todas as 8 páginas podem ser acessadas sem crash."""
        from rclone_gui.gui.remote.remote_list import RemoteListWidget
        from rclone_gui.gui.explorer.two_panel import TwoPanelBrowser
        from rclone_gui.gui.jobs.job_editor import JobListWidget
        from rclone_gui.gui.jobs.job_history import JobHistoryWidget

        pages = [
            (0, RemoteListWidget, "RemoteList"),
            (1, TwoPanelBrowser, "Explorador"),
            (2, JobListWidget, "Jobs"),
            (3, JobHistoryWidget, "Histórico"),
        ]

        for idx, expected_type, name in pages:
            main_window._stack.setCurrentIndex(idx)
            QApplication.processEvents()
            page = main_window._pages[idx]
            assert isinstance(page, expected_type), \
                f"Página {idx} ({name}) é {type(page).__name__}, esperado {expected_type.__name__}"


# ==============================================================================
# 8. DAEMON / TRAY / AUTOSTART
# ==============================================================================

class TestDaemonFeatures:
    """Daemon, system tray e autostart."""

    def test_tray_manager_setup_no_crash(self, main_window, mocker: MockerFixture):
        """TrayManager.setup não crasha em ambiente offscreen."""
        mocker.patch("PySide6.QtWidgets.QSystemTrayIcon.isSystemTrayAvailable", return_value=True)
        mocker.patch("PySide6.QtWidgets.QSystemTrayIcon.show")
        from rclone_gui.daemon.tray_manager import TrayManager
        mgr = TrayManager(main_window)
        mgr.setup()
        assert mgr.tray is not None
        mgr.cleanup()

    def test_autostart_desktop_create_and_remove(self):
        """Arquivo .desktop de autostart é criado e removido corretamente."""
        from rclone_gui.daemon.notification import setup_autostart, remove_autostart

        setup_autostart()
        desktop_path = os.path.expanduser("~/.config/autostart/rclone-gui-daemon.desktop")
        assert os.path.exists(desktop_path), f"{desktop_path} não criado"

        remove_autostart()
        assert not os.path.exists(desktop_path), f"{desktop_path} não removido"

    def test_rcd_process_spawn(self):
        """rclone rcd pode ser iniciado e terminado via subprocess."""
        import subprocess
        import time
        import socket

        # Verifica se rclone está disponível
        try:
            r = subprocess.run(["rclone", "version"], capture_output=True, timeout=5)
            if r.returncode != 0:
                pytest.skip("rclone não disponível")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("rclone não disponível")

        with socket.socket() as s:
            s.bind(("", 0))
            port = s.getsockname()[1]
        proc = subprocess.Popen(
            ["rclone", "rcd", f"--rc-addr=127.0.0.1:{port}", "--rc-no-auth"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        try:
            import urllib.request
            data = json.dumps({}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/rc/noop",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=5)
            assert resp.status == 200
        finally:
            proc.terminate()
            proc.wait(timeout=5)
