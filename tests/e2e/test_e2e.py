"""Testes End-to-End — fluxos completos da aplicação com Qt offscreen + subprocess mockado."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

# For Qt tests, we need QApplication running
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QListWidget, QLabel


# Fixture scoped to session for QApplication
@pytest.fixture(scope="session")
def qapp():
    """QApplication única para toda a sessão de testes Qt."""
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def use_offscreen():
    """Garante que qualquer teste Qt use offscreen."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def e2e_db():
    """Database conectada + isolada para cada teste E2E."""
    from rclone_gui.db.database import Database
    Database._instance = None
    db = Database.get_instance()
    tmp = tempfile.mkdtemp()
    db.db_path = os.path.join(tmp, "test.db")
    db.connect()
    yield
    db.close()


# ==============================================================================
# 5.1 — Inicialização do App
# ==============================================================================

class TestAppStartup:
    """A aplicação deve inicializar sem crash mesmo sem rclone instalado."""

    def test_main_window_creates(self, qapp, mocker: MockerFixture):
        """A MainWindow é criada sem exceções."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        assert window.windowTitle() == "Rclone GUI"
        assert window.isVisible() is False
        window.close()

    def test_window_has_sidebar_buttons(self, qapp, mocker: MockerFixture):
        """Sidebar contém os botões de navegação esperados."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()

        buttons = window.findChildren(QPushButton)
        button_texts = [b.text() for b in buttons]
        for expected in ["Remotos", "Explorador", "Jobs", "Histórico",
                          "Montagens", "Verificação", "Transferir", "Preferências"]:
            assert expected in button_texts, f"Botão '{expected}' não encontrado"

        window.close()

    def test_window_has_status_bar(self, qapp, mocker: MockerFixture):
        """Status bar é criada e exibe mensagem."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        assert window.statusBar() is not None
        window.close()

    def test_stack_starts_at_page_0(self, qapp, mocker: MockerFixture):
        """Stacked widget começa na página de Remotos (índice 0)."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        assert window._stack.currentIndex() == 0
        window.close()


# ==============================================================================
# 5.2 — Fluxo de Remotos (Wizard + Listagem)
# ==============================================================================

class TestRemoteListFlow:
    """Gerenciamento de remotos — listagem, adição, exclusão."""

    def test_remote_list_shows_empty_state(self, qapp, mocker: MockerFixture):
        """Lista vazia exibe '0 remoto(s) configurado(s)'."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        # Pressiona "Remotos" (já está na página 0)
        remote_page = window._pages[0]
        assert "0" in remote_page._status_bar.currentMessage()
        window.close()

    def test_remote_list_shows_remotes(self, qapp, mocker: MockerFixture):
        """Lista populada exibe nomes dos remotos."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value="rclone v1.68.0")
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=["gdrive", "dropbox", "s3"])

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        # Wait for refresh
        remote_page = window._pages[0]
        assert remote_page._list.count() == 3
        assert "gdrive" in remote_page._list.item(0).text()
        window.close()

    def test_remote_add_button_opens_wizard(self, qapp, mocker: MockerFixture):
        """Botão 'Adicionar Remoto' abre o wizard."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value="rclone v1.68.0")

        from rclone_gui.gui.main_window import MainWindow
        from rclone_gui.gui.remote.config_wizard import ConfigWizard

        window = MainWindow()
        window.show()
        remote_page = window._pages[0]

        # Mock exec para não abrir o wizard real
        original_exec = ConfigWizard.exec
        wizard_opened = False

        def mock_exec(self):
            nonlocal wizard_opened
            wizard_opened = True
            return 0  # Reject

        mocker.patch.object(ConfigWizard, "exec", mock_exec)
        remote_page._add_btn.click()
        assert wizard_opened, "Wizard não foi aberto"
        window.close()

    def test_remote_delete_confirmation(self, qapp, mocker: MockerFixture):
        """Excluir remoto pede confirmação."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=["gdrive"])
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value="rclone v1.68.0")
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.config_delete",
                     return_value=(True, ""))

        from rclone_gui.gui.main_window import MainWindow
        from PySide6.QtWidgets import QMessageBox

        window = MainWindow()
        window.show()
        remote_page = window._pages[0]
        remote_page._list.setCurrentRow(0)
        remote_page._on_item_clicked(remote_page._list.item(0))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes) as mock_q:
            remote_page._del_btn.click()
            mock_q.assert_called_once()
        window.close()


# ==============================================================================
# 5.3 — Fluxo do Explorador (Two-Panel)
# ==============================================================================

class TestExplorerFlow:
    """Navegação no explorador two-panel."""

    def test_explorer_two_panels_exist(self, qapp, mocker: MockerFixture):
        """Explorador tem dois painéis."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        window._stack.setCurrentIndex(1)

        explorer = window._pages[1]
        assert explorer._left_panel is not None
        assert explorer._right_panel is not None
        assert explorer._copy_btn is not None
        assert explorer._move_btn is not None
        window.close()

    def test_explorer_panel_has_source_combo(self, qapp, mocker: MockerFixture):
        """Cada painel tem combo de seleção de fonte."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        window._stack.setCurrentIndex(1)
        explorer = window._pages[1]

        combo = explorer._left_panel._source_combo
        assert combo.count() >= 1
        assert "Sistema Local" in combo.currentText()
        window.close()

    def test_explorer_can_set_remotes(self, qapp, mocker: MockerFixture):
        """set_remotes popula os combos dos dois painéis."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=["gdrive", "dropbox"])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        window._stack.setCurrentIndex(1)

        explorer = window._pages[1]
        explorer.set_remotes(["gdrive", "dropbox"])

        left_combo = explorer._left_panel._source_combo
        assert left_combo.count() == 3  # Sistema Local + gdrive: + dropbox:
        window.close()


# ==============================================================================
# 5.4 — Fluxo de Jobs (Listagem, Criação)
# ==============================================================================

class TestJobsFlow:
    """Gerenciamento de jobs de sincronização."""

    def test_jobs_list_shows_empty_state(self, qapp, mocker: MockerFixture):
        """Lista de jobs vazia não crasha."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        window._stack.setCurrentIndex(2)

        jobs_page = window._pages[2]
        assert jobs_page._table.rowCount() == 0
        window.close()

    def test_jobs_new_button_opens_editor(self, qapp, mocker: MockerFixture):
        """Botão 'Novo Job' abre o editor."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        from rclone_gui.gui.jobs.job_editor import JobEditor

        window = MainWindow()
        window.show()
        window._stack.setCurrentIndex(2)

        jobs_page = window._pages[2]
        editor_opened = False

        def mock_edit_exec(self):
            nonlocal editor_opened
            editor_opened = True
            return 0

        mocker.patch.object(JobEditor, "exec", mock_edit_exec)
        jobs_page._add_btn.click()
        assert editor_opened, "Editor de job não foi aberto"
        window.close()

    def test_job_editor_has_required_fields(self, qapp, mocker: MockerFixture):
        """Editor de job tem todos os campos essenciais."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        from rclone_gui.gui.jobs.job_editor import JobEditor
        window = MainWindow()

        editor = JobEditor(window._pages[2].job_service, parent=window)
        assert editor._name_input is not None
        assert editor._type_combo is not None
        assert editor._source_input is not None
        assert editor._dest_input is not None
        assert editor._dry_run_cb is not None
        assert editor._checksum_cb is not None
        assert editor._bwlimit_input is not None
        assert editor._transfers_spin is not None
        assert editor._checkers_spin is not None
        assert editor._retries_spin is not None
        assert editor._schedule_combo is not None
        editor.close()
        window.close()


# ==============================================================================
# 5.5 — Fluxo de Verificação
# ==============================================================================

class TestVerificationFlow:
    """Ferramenta de verificação de integridade."""

    def test_check_tool_has_required_fields(self, qapp, mocker: MockerFixture):
        """CheckTool tem campos de origem, destino e flags."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        window._stack.setCurrentIndex(5)

        check_page = window._pages[5]
        assert check_page._source_input is not None
        assert check_page._dest_input is not None
        assert check_page._checksum_cb is not None
        assert check_page._one_way_cb is not None
        assert check_page._check_btn is not None
        assert check_page._export_btn is not None
        window.close()


# ==============================================================================
# 5.6 — Navegação entre Páginas
# ==============================================================================

class TestNavigationFlow:
    """Sidebar navega entre todas as páginas corretamente."""

    def test_sidebar_click_changes_page(self, qapp, mocker: MockerFixture):
        """Clicar em cada botão da sidebar navega para a página correta."""
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.check_version",
                     return_value=None)
        mocker.patch("rclone_gui.services.rclone_service.RcloneService.list_remotes",
                     return_value=[])
        mocker.patch("PySide6.QtWidgets.QMessageBox.critical")

        from rclone_gui.gui.main_window import MainWindow
        window = MainWindow()
        window.show()

        # Mapeia texto do botão → página esperada
        pages = {
            "Remotos": 0, "Explorador": 1, "Jobs": 2, "Histórico": 3,
            "Montagens": 4, "Verificação": 5, "Transferir": 6, "Preferências": 7,
        }

        buttons = {b.text(): b for b in window.findChildren(QPushButton) if b.text() in pages}
        for text, expected_idx in pages.items():
            btn = buttons.get(text)
            if btn:
                btn.click()
                assert window._stack.currentIndex() == expected_idx, \
                    f"Botão '{text}' deveria navegar para página {expected_idx}"

        window.close()


class TestDaemonMode:
    """5.7 — Flag --daemon para modo background."""

    def test_daemon_flag_detection(self, mocker: MockerFixture):
        """Flag --daemon no sys.argv é detectada corretamente."""
        import sys
        mocker.patch.object(sys, "argv", ["rclone-gui", "--daemon"])
        mocker.patch("rclone_gui.daemon.daemon_app.main")

        from rclone_gui.__main__ import main
        main()
        from rclone_gui.daemon.daemon_app import main as daemon_main
        daemon_main.assert_called_once()
