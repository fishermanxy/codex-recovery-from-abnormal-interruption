"""Track whether a connection failure has already been reported."""

from __future__ import annotations


class ConnectionRecoveryNotice:
    """Allow one notification per continuous connection-failure period."""

    def __init__(self) -> None:
        self._failure_active = False

    def on_error(self) -> bool:
        if self._failure_active:
            return False
        self._failure_active = True
        return True

    def on_success(self) -> None:
        self._failure_active = False
