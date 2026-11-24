from pathlib import Path

from codex_recovery.config import (
    DEFAULT_INTERVAL_SECONDS,
    AppConfig,
    load_config,
    save_config,
)


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = AppConfig(
        listening_enabled=False,
        autostart=True,
        notify_on_retry=False,
        window_title="ChatGPT",
        interval_seconds=12.5,
    )

    save_config(config, path)

    assert load_config(path) == config


def test_missing_config_uses_safe_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.json")

    assert config.listening_enabled is True
    assert config.autostart is False
    assert config.notify_on_retry is True
    assert config.interval_seconds == DEFAULT_INTERVAL_SECONDS


def test_config_clamps_interval_to_ten_seconds(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"interval_seconds": 0.2}', encoding="utf-8")

    config = load_config(path)

    assert config.interval_seconds == 10.0


def test_config_clamps_interval_to_twenty_seconds(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"interval_seconds": 30}', encoding="utf-8")

    config = load_config(path)

    assert config.interval_seconds == 20.0
