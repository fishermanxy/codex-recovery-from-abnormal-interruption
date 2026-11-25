"""Pure selection logic for the Codex capacity-error retry control."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ERROR_TEXT = "Selected model is at capacity. Please try a different model."
RETRY_LIMIT_ERROR_TEXTS = (
    "exceeded retry limit",
    "429 too many requests",
)
RETRY_NAMES = frozenset({"retry", "重试"})
CONTINUE_NAMES = frozenset({"continue", "继续"})
RECOVERY_ACTION_NAMES = RETRY_NAMES | CONTINUE_NAMES


@dataclass(frozen=True)
class AccessibleNode:
    """Small, testable representation of a Windows Accessibility node."""

    role: str
    name: str = ""
    enabled: bool = True
    visible: bool = True
    identifier: str = ""
    children: tuple["AccessibleNode", ...] = ()


@dataclass(frozen=True)
class RetryMatch:
    """A recovery button and the stable identity of its containing error card."""

    card_key: str
    button: AccessibleNode
    action: str = "retry"


def _walk(node: AccessibleNode, depth: int = 0):
    if not node.visible:
        return

    yield node, depth
    for child in node.children:
        yield from _walk(child, depth + 1)


def _is_error_text(node: AccessibleNode) -> bool:
    return ERROR_TEXT in node.name


def _is_retry_button(node: AccessibleNode) -> bool:
    return _is_named_button(node, RETRY_NAMES)


def _is_continue_button(node: AccessibleNode) -> bool:
    return _is_named_button(node, CONTINUE_NAMES)


def _is_named_button(node: AccessibleNode, names: frozenset[str]) -> bool:
    return node.role.casefold() == "button" and node.name.strip().casefold() in names


def _is_retry_limit_error_text(node: AccessibleNode) -> bool:
    name = node.name.casefold()
    return any(marker in name for marker in RETRY_LIMIT_ERROR_TEXTS)


def _find_latest_action(
    root: AccessibleNode,
    *,
    error_matcher: Callable[[AccessibleNode], bool],
    button_matcher: Callable[[AccessibleNode], bool],
    action: str,
    fallback_key: str,
    container_matcher: Callable[[AccessibleNode], bool] | None = None,
) -> RetryMatch | None:
    entries = list(_walk(root))
    candidates: list[tuple[int, int, AccessibleNode, AccessibleNode]] = []

    for order, (candidate, depth) in enumerate(entries):
        if container_matcher is not None and not container_matcher(candidate):
            continue
        subtree = list(_walk(candidate))
        error_count = sum(error_matcher(node) for node, _ in subtree)
        action_buttons = [
            node for node, _ in subtree if button_matcher(node)
        ]

        if error_count == 1 and action_buttons:
            candidates.append((depth, order, candidate, action_buttons[-1]))

    if not candidates:
        return None

    _, _, card, button = max(candidates, key=lambda item: (item[0], item[1]))
    card_key = card.identifier or button.identifier or f"{fallback_key}|{button.name}"
    return RetryMatch(card_key=card_key, button=button, action=action)


def find_latest_retry(root: AccessibleNode) -> RetryMatch | None:
    """Find the latest visible retry button inside a capacity-error card.

    The deepest matching group is preferred so a page-level container that
    contains several historical cards does not win over an individual card.
    Document order breaks ties between multiple cards at the same depth.
    """

    return _find_latest_action(
        root,
        error_matcher=_is_error_text,
        button_matcher=_is_retry_button,
        action="retry",
        fallback_key=ERROR_TEXT,
    )


def find_latest_continue(root: AccessibleNode) -> RetryMatch | None:
    """Find a continue button only inside a visible retry-limit error dialog.

    A standalone continue button is intentionally ignored so a user-paused
    conversation remains paused.
    """

    return _find_latest_action(
        root,
        error_matcher=_is_retry_limit_error_text,
        button_matcher=_is_continue_button,
        action="continue",
        fallback_key=RETRY_LIMIT_ERROR_TEXTS[0],
        container_matcher=lambda node: node.role.casefold() == "dialog",
    )
