"""Testes unitários — SyncFolderWatcher (watchdog inotify + debounce)."""

from __future__ import annotations

import os
import tempfile

from rclone_gui.daemon.sync_folder_watcher import SyncFolderWatcher


class TestSyncFolderWatcher:
    def test_watcher_starts_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = SyncFolderWatcher(tmp, debounce_seconds=0.5)
            watcher.start()
            assert watcher.is_running()
            watcher.stop()
            assert not watcher.is_running()

    def test_file_creation_emits_signal(self, qtbot):
        from PySide6.QtTest import QSignalSpy

        with tempfile.TemporaryDirectory() as tmp:
            watcher = SyncFolderWatcher(tmp, debounce_seconds=0.2)
            spy = QSignalSpy(watcher.changes_detected)
            watcher.start()
            qtbot.wait(100)
            file_path = os.path.join(tmp, "new_file.txt")
            with open(file_path, "w") as f:
                f.write("hello")
            qtbot.wait(600)
            assert spy.count() >= 1, f"Signal n\u00e3o emitido. count={spy.count()}"
            watcher.stop()

    def test_multiple_files_debounced(self, qtbot):
        from PySide6.QtTest import QSignalSpy

        with tempfile.TemporaryDirectory() as tmp:
            watcher = SyncFolderWatcher(tmp, debounce_seconds=0.3)
            spy = QSignalSpy(watcher.changes_detected)
            watcher.start()
            qtbot.wait(100)
            for i in range(5):
                fp = os.path.join(tmp, f"f{i}.txt")
                with open(fp, "w") as f:
                    f.write("data")
                qtbot.wait(50)
            qtbot.wait(800)
            c = spy.count()
            assert c >= 1, f"Signal n\u00e3o emitido. count={c}"
            assert c <= 2, f"Debounce falhou: {c} sinais (esperado 1-2)"
            watcher.stop()

    def test_ignores_hidden_files(self, qtbot):
        from PySide6.QtTest import QSignalSpy

        with tempfile.TemporaryDirectory() as tmp:
            watcher = SyncFolderWatcher(
                tmp, debounce_seconds=0.2, ignore_patterns=[".*"]
            )
            spy = QSignalSpy(watcher.changes_detected)
            watcher.start()
            qtbot.wait(100)
            hidden_path = os.path.join(tmp, ".hidden_file")
            with open(hidden_path, "w") as f:
                f.write("secret")
            qtbot.wait(500)
            assert spy.count() == 0, f"Signal emitido p/ oculto: count={spy.count()}"
            watcher.stop()

    def test_stop_no_crash_if_not_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = SyncFolderWatcher(tmp)
            watcher.stop()

    def test_ignores_lock_files(self, qtbot):
        from PySide6.QtTest import QSignalSpy

        with tempfile.TemporaryDirectory() as tmp:
            watcher = SyncFolderWatcher(tmp, debounce_seconds=0.2)
            spy = QSignalSpy(watcher.changes_detected)
            watcher.start()
            qtbot.wait(100)
            lock_path = os.path.join(tmp, "test.rclonelck")
            with open(lock_path, "w") as f:
                f.write("lock")
            qtbot.wait(500)
            assert spy.count() == 0, f"Signal emitido p/ lock: count={spy.count()}"
            watcher.stop()
