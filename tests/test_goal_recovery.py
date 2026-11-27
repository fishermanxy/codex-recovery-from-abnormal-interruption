import json
from dataclasses import replace
from pathlib import Path

import pytest

from codex_recovery.detector import AccessibleNode, find_latest_continue
from codex_recovery.watcher import RetryWatcher


def live_goal_conversation():
    def decode(data):
        return AccessibleNode(**{**data, 'children': tuple(decode(c) for c in data['children'])})

    fixture = Path(__file__).parent / 'fixtures/429-goal.json'
    return decode(json.loads(fixture.read_text(encoding='utf-8')))


def test_recovers_observed_429_stalled_goal_once():
    root = live_goal_conversation()
    clicks = []
    watcher = RetryWatcher(lambda: root, clicks.append)

    result = watcher.poll_once()

    assert result.status == 'clicked'
    assert result.action == 'resume_goal'
    assert watcher.poll_once().status == 'already_processed'
    assert len(clicks) == 1
    assert clicks[0].name == '恢复目标'


def test_goal_without_change_summary_can_recover():
    root = live_goal_conversation()
    root = replace(root, children=(root.children[0], root.children[-1]))

    match = find_latest_continue(root)

    assert match is not None
    assert match.action == 'resume_goal'


def single_file_goal_conversation():
    root = live_goal_conversation()
    summary = list(root.children[1:8])
    summary[2] = replace(summary[2], name='已编辑 visual-audit-progress.md')
    summary[3] = replace(summary[3], name='+3')
    summary[4] = replace(summary[4], name='-2')
    group = AccessibleNode(role='Group', children=tuple(summary))
    return replace(root, children=(root.children[0], group, *root.children[-3:]))


def test_recovers_stalled_goal_with_single_file_summary():
    clicks = []
    watcher = RetryWatcher(single_file_goal_conversation, clicks.append)

    assert watcher.poll_once().action == 'resume_goal'
    assert len(clicks) == 1


def test_single_file_summary_with_extra_content_blocks_recovery():
    root = single_file_goal_conversation()
    summary = root.children[1]
    summary = replace(summary, children=(*summary.children, AccessibleNode(role='Text', name='later message')))
    root = replace(root, children=(root.children[0], summary, *root.children[2:]))

    assert find_latest_continue(root) is None


def test_single_file_summary_followed_by_message_blocks_recovery():
    root = single_file_goal_conversation()
    activity = AccessibleNode(role='Text', name='A later message')
    root = replace(root, children=(*root.children[:2], activity, *root.children[2:]))

    assert find_latest_continue(root) is None


def test_single_file_summary_with_paused_goal_blocks_recovery():
    root = single_file_goal_conversation()
    composer = root.children[-1]
    status = replace(composer.children[0], name='目标已暂停 Example goal')
    composer = replace(composer, children=(status, *composer.children[1:]))

    assert find_latest_continue(replace(root, children=(*root.children[:-1], composer))) is None


def test_latest_goal_error_can_recover_after_an_older_change_summary():
    root = live_goal_conversation()
    old_error = replace(root.children[0], identifier='old-error')
    latest_error = replace(root.children[0], identifier='latest-error')
    root = replace(root, children=(
        old_error, *root.children[1:-1], latest_error, *root.children[1:],
    ))

    match = find_latest_continue(root)

    assert match is not None
    assert match.card_key == 'latest-error'


@pytest.mark.parametrize('state', ['目标已暂停 Example goal', '目标进行中 Example goal', '目标已完成 Example goal'])
def test_does_not_resume_a_goal_that_is_not_stalled(state):
    root = live_goal_conversation()
    composer = root.children[-1]
    status = replace(composer.children[0], name=state)
    composer = replace(composer, children=(status, *composer.children[1:]))
    root = replace(root, children=(*root.children[:-1], composer))

    assert find_latest_continue(root) is None


def test_stalled_goal_without_error_does_not_resume():
    root = live_goal_conversation()

    assert find_latest_continue(replace(root, children=root.children[1:])) is None


@pytest.mark.parametrize('name', ['代理已停止', '用户说', 'ChatGPT 说', 'A later message'])
@pytest.mark.parametrize('before_summary', [False, True])
def test_historical_error_followed_by_activity_does_not_resume_goal(name, before_summary):
    root = live_goal_conversation()
    index = 1 if before_summary else len(root.children)-1
    activity = AccessibleNode(role='Text', name=name)
    root = replace(root, children=(*root.children[:index], activity, *root.children[index:]))

    assert find_latest_continue(root) is None


def test_goal_with_draft_does_not_resume():
    root = live_goal_conversation()
    composer = root.children[-1]
    edit_index = next(i for i, n in enumerate(composer.children) if n.role == 'Edit')
    edit = replace(composer.children[edit_index], children=(AccessibleNode(role='Text', name='my draft'),))
    children = list(composer.children)
    children[edit_index] = edit
    root = replace(root, children=(*root.children[:-1], replace(composer, children=tuple(children))))

    assert find_latest_continue(root) is None


def test_incomplete_goal_snapshot_does_not_resume():
    assert find_latest_continue(replace(live_goal_conversation(), complete=False)) is None


def test_unknown_change_summary_content_blocks_goal_recovery():
    root = live_goal_conversation()
    children = list(root.children)
    children[3] = replace(children[3], name='A new message after the error')

    assert find_latest_continue(replace(root, children=tuple(children))) is None
