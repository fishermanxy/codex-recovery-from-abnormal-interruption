import subprocess
import sys
from types import SimpleNamespace

import pytest
import win32con

from codex_recovery import tray_app
from codex_recovery.config import AppConfig, load_config, save_config


@pytest.mark.parametrize("paused", [False, True])
def test_process_exit_ends_tray_even_when_listening_is_paused(monkeypatch, paused):
    app = tray_app.TrayApplication.__new__(tray_app.TrayApplication)
    app._session = SimpleNamespace(running=False)
    app._exiting = False
    app._settings_root = None
    app._hwnd = 123
    calls = []
    app._worker = SimpleNamespace(enabled=not paused, stop=lambda: calls.append("stop"))
    monkeypatch.setattr(tray_app.win32gui, "Shell_NotifyIcon", lambda *args: calls.append("icon"))
    monkeypatch.setattr(tray_app.win32gui, "DestroyWindow", lambda hwnd: calls.append("destroy"))
    monkeypatch.setattr(tray_app.win32gui, "PostQuitMessage", lambda code: calls.append("quit"))

    app._window_proc(123, win32con.WM_TIMER, tray_app.LIFECYCLE_TIMER, 0)

    assert calls == ["stop", "icon", "destroy", "quit"]
    assert app._exiting


def test_running_owner_keeps_tray_alive_without_a_visible_window():
    app = tray_app.TrayApplication.__new__(tray_app.TrayApplication)
    app._session = SimpleNamespace(running=True)
    app._exiting = False

    assert app._window_proc(123, win32con.WM_TIMER, tray_app.LIFECYCLE_TIMER, 0) == 0
    assert not app._exiting


def test_exit_closes_open_settings_and_is_idempotent(monkeypatch):
    calls = []
    app = tray_app.TrayApplication.__new__(tray_app.TrayApplication)
    app._exiting = False
    app._settings_root = SimpleNamespace(destroy=lambda: calls.append("settings"))
    app._worker = SimpleNamespace(stop=lambda: calls.append("worker"))
    app._hwnd = 123
    monkeypatch.setattr(tray_app.win32gui, "Shell_NotifyIcon", lambda *args: calls.append("icon"))
    monkeypatch.setattr(tray_app.win32gui, "DestroyWindow", lambda hwnd: calls.append("window"))

    app._exit()
    app._exit()

    assert calls == ["settings", "worker", "icon", "window"]


def test_legacy_startup_migrates_and_session_is_closed(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    save_config(AppConfig(autostart=True), config_path)
    calls = []
    session = SimpleNamespace(process_id=123, close=lambda: calls.append("close"))
    monkeypatch.setattr(sys, "argv", ["recovery", "--config-path", str(config_path)])
    monkeypatch.setattr(tray_app, "is_autostart_enabled", lambda: True)
    monkeypatch.setattr(tray_app, "set_autostart", lambda enabled: calls.append(("autostart", enabled)))
    monkeypatch.setattr(tray_app.CodexSession, "start", lambda **kwargs: session)
    monkeypatch.setattr(
        tray_app,
        "TrayApplication",
        lambda *args, **kwargs: SimpleNamespace(run=lambda: calls.append("run")),
    )

    assert tray_app.run_application() == 0
    assert calls == [("autostart", False), "run", "close"]
    assert not load_config(config_path).autostart


def test_native_message_pump_exits_when_process_finishes():
    # Exercise the real WM_TIMER/message loop in an isolated process.
    script = """
import subprocess
import sys
from codex_recovery.config import AppConfig
from codex_recovery.lifecycle import CodexSession
from codex_recovery.tray_app import TrayApplication

process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1)'])
session = CodexSession(process.pid)
try:
    app = TrayApplication(AppConfig(listening_enabled=False), session=session)
    app.run()
    assert app._exiting
finally:
    session.close()
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=5)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
