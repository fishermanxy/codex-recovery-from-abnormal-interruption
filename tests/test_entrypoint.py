import runpy
import sys
import types
from pathlib import Path

import pytest


def test_packaged_entrypoint_imports_tray_app_as_a_top_level_script(monkeypatch):
    entrypoint = Path(__file__).parents[1] / "codex_recovery" / "__main__.py"
    calls: list[str] = []

    package = types.ModuleType("codex_recovery")
    package.__path__ = [str(entrypoint.parent)]
    instance = types.ModuleType("codex_recovery.instance")
    tray_app = types.ModuleType("codex_recovery.tray_app")

    class FakeGuard:
        already_running = False

        def close(self):
            calls.append("close")

    instance.SingleInstanceGuard = FakeGuard
    tray_app.run_application = lambda: calls.append("run") or 0

    monkeypatch.setitem(sys.modules, "codex_recovery", package)
    monkeypatch.setitem(sys.modules, "codex_recovery.instance", instance)
    monkeypatch.setitem(sys.modules, "codex_recovery.tray_app", tray_app)

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(entrypoint), run_name="__main__")

    assert exit_info.value.code == 0
    assert calls == ["run", "close"]
