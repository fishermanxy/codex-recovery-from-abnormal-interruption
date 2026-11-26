import subprocess
import sys
from types import SimpleNamespace

import pytest

from codex_recovery import lifecycle
from codex_recovery.lifecycle import CODEX_APP_ID, CodexSession


def test_session_tracks_process_lifetime():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    session = CodexSession(process.pid)
    try:
        assert session.running
        process.terminate()
        process.wait(timeout=5)
        assert not session.running
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        session.close()
    assert not session.running
    session.close()


def test_activation_uses_window_owner_instead_of_activation_proxy(monkeypatch):
    activations = []
    com_calls = []

    def activate(app_id, arguments, options):
        activations.append((app_id, arguments, options))
        return 1234

    def create_manager(clsid, **kwargs):
        assert isinstance(clsid, lifecycle.comtypes.GUID)
        return SimpleNamespace(ActivateApplication=activate)

    monkeypatch.setattr(lifecycle.comtypes, "CoInitialize", lambda: com_calls.append("init"))
    monkeypatch.setattr(lifecycle.comtypes, "CoUninitialize", lambda: com_calls.append("uninit"))
    monkeypatch.setattr(
        lifecycle.comtypes,
        "CoCreateInstance",
        create_manager,
    )
    handle = SimpleNamespace(Close=lambda: None)
    opened = []
    monkeypatch.setattr(
        lifecycle.win32api,
        "OpenProcess",
        lambda access, inherit, pid: opened.append(pid) or handle,
    )
    owner = CodexSession(5678)
    monkeypatch.setattr(lifecycle, "_find_codex_session", lambda title: owner)

    session = CodexSession.start()
    assert activations == [(CODEX_APP_ID, "", 0)]
    assert opened == [5678]
    assert session.process_id == 5678
    assert com_calls == ["init", "uninit"]
    session.close()


def test_activation_failure_balances_com_initialization(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        raise OSError("App activation failed")

    monkeypatch.setattr(lifecycle.comtypes, "CoInitialize", lambda: calls.append("init"))
    monkeypatch.setattr(lifecycle.comtypes, "CoUninitialize", lambda: calls.append("uninit"))
    monkeypatch.setattr(lifecycle.comtypes, "CoCreateInstance", fail)

    with pytest.raises(OSError, match="activation failed"):
        CodexSession.start()
    assert calls == ["init", "uninit"]


def test_window_discovery_rejects_another_package_with_the_same_title(monkeypatch):
    closed = []
    monkeypatch.setattr(lifecycle.win32gui, "EnumWindows", lambda callback, extra: callback(1, extra))
    monkeypatch.setattr(lifecycle.win32gui, "GetWindowText", lambda hwnd: "ChatGPT")
    monkeypatch.setattr(lifecycle.win32process, "GetWindowThreadProcessId", lambda hwnd: (1, 123))
    handle = SimpleNamespace(Close=lambda: closed.append(True))
    monkeypatch.setattr(lifecycle.win32api, "OpenProcess", lambda *args: handle)
    monkeypatch.setattr(lifecycle, "_package_family", lambda handle: "Another.Package")

    assert lifecycle._find_codex_session("ChatGPT") is None
    assert closed == [True]
