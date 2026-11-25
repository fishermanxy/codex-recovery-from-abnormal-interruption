"""Command-line entry point for the Codex recovery watcher."""

from __future__ import annotations

import argparse
import time

from .detector import AccessibleNode
from .config import DEFAULT_INTERVAL_SECONDS
from .uia import UiaWindowSource
from .watcher import RetryWatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Watch Codex for recoverable errors and act once per error occurrence."
    )
    parser.add_argument("--window-title", default="ChatGPT")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = UiaWindowSource.connect(title=args.window_title)

    def click(node: AccessibleNode) -> None:
        if args.dry_run:
            print(f"dry-run: matched recovery control {node.name!r}")
            return
        source.click(node)
        print(f"clicked recovery control {node.name!r}")

    watcher = RetryWatcher(source.snapshot, click)

    while True:
        result = watcher.poll_once()
        if result.status not in {"no_match", "already_processed"}:
            print(result.status, result.card_key or "")

        if args.once:
            if result.status in {"no_match", "already_processed"}:
                print(result.status, result.card_key or "")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
