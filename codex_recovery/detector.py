"""Pure selection logic for the Codex capacity-error retry control."""

from __future__ import annotations

from dataclasses import dataclass

ERROR_TEXT = "Selected model is at capacity. Please try a different model."
RETRY_NAMES = frozenset({"retry", "重试"})


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
    """A retry button and the stable identity of its containing error card."""

    card_key: str
    button: AccessibleNode


def _walk(node: AccessibleNode, depth: int = 0):
    if not node.visible:
        return

    yield node, depth
    for child in node.children:
        yield from _walk(child, depth + 1)


def _is_error_text(node: AccessibleNode) -> bool:
    return ERROR_TEXT in node.name


def _is_retry_button(node: AccessibleNode) -> bool:
    return node.role.casefold() == "button" and node.name.strip().casefold() in RETRY_NAMES


def find_latest_retry(root: AccessibleNode) -> RetryMatch | None:
    """Find the latest visible retry button inside a capacity-error card.

    The deepest matching group is preferred so a page-level container that
    contains several historical cards does not win over an individual card.
    Document order breaks ties between multiple cards at the same depth.
    """

    entries = list(_walk(root))
    candidates: list[tuple[int, int, AccessibleNode, AccessibleNode]] = []

    for order, (candidate, depth) in enumerate(entries):
        subtree = list(_walk(candidate))
        error_count = sum(_is_error_text(node) for node, _ in subtree)
        retry_buttons = [
            node for node, _ in subtree if _is_retry_button(node)
        ]

        if error_count == 1 and retry_buttons:
            candidates.append((depth, order, candidate, retry_buttons[-1]))

    if not candidates:
        return None

    _, _, card, button = max(candidates, key=lambda item: (item[0], item[1]))
    card_key = card.identifier or button.identifier or f"{ERROR_TEXT}|{button.name}"
    return RetryMatch(card_key=card_key, button=button)
