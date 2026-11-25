from codex_recovery.detector import (
    ERROR_TEXT,
    AccessibleNode,
    find_latest_continue,
    find_latest_retry,
)


def error_card(identifier: str, *, enabled: bool = True) -> AccessibleNode:
    return AccessibleNode(
        role="group",
        identifier=identifier,
        children=(
            AccessibleNode(
                role="group",
                children=(
                    AccessibleNode(role="text", name=ERROR_TEXT),
                    AccessibleNode(
                        role="button",
                        name="重试",
                        enabled=enabled,
                        identifier=f"{identifier}:retry",
                    ),
                ),
            ),
        ),
    )


def retry_limit_dialog(identifier: str = "dialog") -> AccessibleNode:
    return AccessibleNode(
        role="dialog",
        identifier=identifier,
        children=(
            AccessibleNode(
                role="text",
                name="exceeded retry limit, last status: 429 Too Many Requests",
            ),
            AccessibleNode(
                role="button",
                name="继续",
                identifier=f"{identifier}:continue",
            ),
        ),
    )


def test_selects_latest_error_card() -> None:
    root = AccessibleNode(
        role="window",
        children=(error_card("old"), error_card("new")),
    )

    match = find_latest_retry(root)

    assert match is not None
    assert match.card_key == "new:retry"
    assert match.button.name == "重试"


def test_ignores_other_errors() -> None:
    root = AccessibleNode(
        role="window",
        children=(
            AccessibleNode(
                role="group",
                children=(
                    AccessibleNode(role="text", name="正在重新连接"),
                    AccessibleNode(role="button", name="重试"),
                ),
            ),
        ),
    )

    assert find_latest_retry(root) is None


def test_returns_disabled_retry_for_policy_to_skip() -> None:
    match = find_latest_retry(error_card("card", enabled=False))

    assert match is not None
    assert match.button.enabled is False


def test_matches_continue_only_inside_retry_limit_dialog() -> None:
    root = AccessibleNode(
        role="window",
        children=(retry_limit_dialog("dialog"),),
    )

    match = find_latest_continue(root)

    assert match is not None
    assert match.card_key == "dialog"
    assert match.action == "continue"


def test_ignores_continue_button_for_manual_pause() -> None:
    root = AccessibleNode(
        role="window",
        children=(
            AccessibleNode(
                role="dialog",
                children=(AccessibleNode(role="button", name="继续"),),
            ),
        ),
    )

    assert find_latest_continue(root) is None


def test_ignores_error_text_outside_the_continue_dialog() -> None:
    root = AccessibleNode(
        role="window",
        children=(
            AccessibleNode(
                role="text",
                name="exceeded retry limit, last status: 429 Too Many Requests",
            ),
            AccessibleNode(
                role="dialog",
                children=(AccessibleNode(role="button", name="继续"),),
            ),
        ),
    )

    assert find_latest_continue(root) is None
