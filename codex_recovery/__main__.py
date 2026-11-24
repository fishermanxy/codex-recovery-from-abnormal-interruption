from codex_recovery.instance import SingleInstanceGuard


guard = SingleInstanceGuard()
if guard.already_running:
    raise SystemExit(0)

try:
    from codex_recovery.tray_app import run_application

    raise SystemExit(run_application())
finally:
    guard.close()
