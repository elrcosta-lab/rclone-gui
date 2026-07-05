"""Testes unitários — SyncFolderPoller (QTimer para polling periódico)."""

from __future__ import annotations

from rclone_gui.daemon.sync_folder_poller import SyncFolderPoller


class TestSyncFolderPoller:
    def test_poller_starts_and_stops(self, qtbot):
        poller = SyncFolderPoller(interval_seconds=0.1)
        poller.start()
        assert poller.is_running()
        poller.stop()
        assert not poller.is_running()

    def test_poller_emits_time_to_sync(self, qtbot):
        from PySide6.QtTest import QSignalSpy

        poller = SyncFolderPoller(interval_seconds=0.1)
        spy = QSignalSpy(poller.time_to_sync)
        poller.start()
        qtbot.wait(350)
        c = spy.count()
        assert c >= 2, f"Polling n\u00e3o emitiu sinais suficientes: {c}"
        poller.stop()

    def test_poller_respects_suppressed_state(self, qtbot):
        from PySide6.QtTest import QSignalSpy

        poller = SyncFolderPoller(interval_seconds=0.1)
        spy = QSignalSpy(poller.time_to_sync)
        poller.set_suppressed(True)
        poller.start()
        qtbot.wait(350)
        assert spy.count() == 0, f"Signal emitido mesmo com suppressed=True: count={spy.count()}"
        poller.stop()

    def test_stop_no_crash_if_not_started(self):
        poller = SyncFolderPoller(interval_seconds=0.1)
        poller.stop()
