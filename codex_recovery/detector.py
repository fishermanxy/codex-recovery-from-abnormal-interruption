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
    """Find a Continue associated with a current retry-limit failure."""

    dialog_match = _find_latest_action(
        root,
        error_matcher=_is_retry_limit_error_text,
        button_matcher=_is_continue_button,
        action="continue",
        fallback_key=RETRY_LIMIT_ERROR_TEXTS[0],
        container_matcher=lambda node: node.role.casefold() == "dialog",
    )
    if dialog_match is not None:
        return dialog_match

    for conversation, _ in _walk(root):
        if (
            conversation.role.casefold() != "group"
            or conversation.name.casefold() not in {"对话", "conversation"}
        ):
            continue
        match = _find_composer_continue(conversation)
        if match is not None:
            return match
    return None


def _find_composer_continue(conversation: AccessibleNode) -> RetryMatch | None:
    children = [child for child in conversation.children if child.visible]
    if len(children) < 2:
        return None
    composer = list(_walk(children[-1]))
    buttons = [node for node, _ in composer if _is_continue_button(node)]
    edits = [node for node, _ in composer if node.role.casefold() == "edit"]
    if len(buttons) != 1 or len(edits) != 1:
        return None
    edit = edits[0]
    edit_text = [node.name.strip() for node, _ in _walk(edit) if node.role.casefold() == "text"]
    if not edit_text or any(text and text != edit.name.strip() for text in edit_text):
        return None

    # Only idle UI markers may separate the terminal error card and composer.
    preceding = children[:-1]
    while preceding and (
        (preceding[-1].role.casefold() == "statusbar" and not preceding[-1].name)
        or (
            preceding[-1].role.casefold() == "text"
            and preceding[-1].name.strip().casefold() in {"最新一条回复", "latest response"}
        )
    ):
        preceding.pop()
    if not preceding or preceding[-1].role.casefold() != "group":
        return None
    card = preceding[-1]
    card_nodes = [node for node, _ in _walk(card)]
    texts = [node for node in card_nodes if node.role.casefold() == "text" and node.name.strip()]
    if (
        len(texts) != 1
        or not texts[0].name.casefold().startswith("exceeded retry limit")
        or not any(node.role.casefold() == "image" for node in card_nodes)
        or any(node.role.casefold() in {"button", "edit"} for node in card_nodes)
    ):
        return None
    return RetryMatch(
        card_key=card.identifier or texts[0].identifier or texts[0].name,
        button=buttons[0],
        action="continue",
    )
