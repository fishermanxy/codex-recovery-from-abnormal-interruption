"""Persistent settings for the Codex Recovery tray application."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_INTERVAL_SECONDS = 15.0
MIN_INTERVAL_SECONDS = 10.0
MAX_INTERVAL_SECONDS = 20.0


@dataclass
class AppConfig:
    listening_enabled: bool = True
    autostart: bool = False
    notify_on_retry: bool = True
    window_title: str = "ChatGPT"
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS


def default_config_path() -> Path:
    app_data = os.environ.get("APPDATA")
    root = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    return root / "CodexRecovery" / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or default_config_path()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return AppConfig()

    return AppConfig(
        listening_enabled=bool(data.get("listening_enabled", True)),
        autostart=bool(data.get("autostart", False)),
        notify_on_retry=bool(data.get("notify_on_retry", True)),
        window_title=str(data.get("window_title", "ChatGPT")),
        interval_seconds=min(
            MAX_INTERVAL_SECONDS,
            max(
                MIN_INTERVAL_SECONDS,
                float(data.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)),
            ),
        ),
    )


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config_path
