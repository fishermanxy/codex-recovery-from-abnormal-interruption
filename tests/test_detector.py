from codex_recovery.detector import (
    ERROR_TEXT,
    AccessibleNode,
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
