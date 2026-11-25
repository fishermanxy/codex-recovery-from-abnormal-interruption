"""Stateful retry policy built on top of the pure accessibility detector."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .detector import AccessibleNode, find_latest_continue, find_latest_retry


@dataclass(frozen=True)
class PollResult:
    """Outcome of one watcher poll."""

    status: str
    card_key: str | None = None
    action: str | None = None


class RetryWatcher:
    """Click each supported recovery control once per visible error occurrence."""

    def __init__(
        self,
        snapshot: Callable[[], AccessibleNode],
        click: Callable[[AccessibleNode], None],
    ) -> None:
        self._snapshot = snapshot
        self._click = click
        self._processed_card_key: str | None = None

    def poll_once(self) -> PollResult:
        root = self._snapshot()
        match = find_latest_retry(root) or find_latest_continue(root)
        if match is None:
            self._processed_card_key = None
            return PollResult(status="no_match")

        if not match.button.enabled:
            return PollResult(
                status="disabled",
                card_key=match.card_key,
                action=match.action,
            )

        if match.card_key == self._processed_card_key:
            return PollResult(
                status="already_processed",
                card_key=match.card_key,
                action=match.action,
            )

        self._click(match.button)
        self._processed_card_key = match.card_key
        return PollResult(
            status="clicked",
            card_key=match.card_key,
            action=match.action,
        )
