from codex_recovery.detector import ERROR_TEXT, AccessibleNode
from codex_recovery.watcher import RetryWatcher


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


def test_processes_one_card_once() -> None:
    root = AccessibleNode(
        role="window",
        children=(error_card("card"),),
    )
    clicks = []
    watcher = RetryWatcher(lambda: root, clicks.append)

    assert watcher.poll_once().status == "clicked"
    assert watcher.poll_once().status == "already_processed"
    assert len(clicks) == 1


def test_processes_new_card_after_previous_card_disappears() -> None:
    roots = iter(
        (
            AccessibleNode(role="window", children=(error_card("first"),)),
            AccessibleNode(role="window"),
            AccessibleNode(role="window", children=(error_card("second"),)),
        )
    )
    clicks = []
    watcher = RetryWatcher(lambda: next(roots), clicks.append)

    assert watcher.poll_once().status == "clicked"
    assert watcher.poll_once().status == "no_match"
    assert watcher.poll_once().status == "clicked"
    assert len(clicks) == 2


def test_skips_disabled_retry() -> None:
    root = AccessibleNode(
        role="window",
        children=(error_card("card", enabled=False),),
    )
    clicks = []
    watcher = RetryWatcher(lambda: root, clicks.append)

    assert watcher.poll_once().status == "disabled"
    assert clicks == []


def test_does_not_resume_a_manually_paused_conversation() -> None:
    root = AccessibleNode(
        role="window",
        children=(
            AccessibleNode(
                role="dialog",
                children=(AccessibleNode(role="button", name="继续"),),
            ),
        ),
    )
    clicks = []
    watcher = RetryWatcher(lambda: root, clicks.append)

    assert watcher.poll_once().status == "no_match"
    assert clicks == []


def test_resumes_a_retry_limit_dialog_once() -> None:
    root = AccessibleNode(
        role="window",
        children=(retry_limit_dialog(),),
    )
    clicks = []
    watcher = RetryWatcher(lambda: root, clicks.append)

    assert watcher.poll_once().action == "continue"
    assert watcher.poll_once().status == "already_processed"
    assert len(clicks) == 1
