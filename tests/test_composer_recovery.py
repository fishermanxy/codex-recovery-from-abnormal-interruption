import json
from dataclasses import replace
from pathlib import Path

import pytest

from codex_recovery.detector import AccessibleNode, find_latest_continue
from codex_recovery.watcher import RetryWatcher


def live_conversation():
    def decode(data):
        children = tuple(decode(child) for child in data['children'])
        return AccessibleNode(**{**data, 'children': children})

    fixture = Path(__file__).parent / 'fixtures/429-composer.json'
    return decode(json.loads(fixture.read_text(encoding='utf-8')))


def test_recovers_observed_429_composer_once():
    root = live_conversation()
    clicks = []
    watcher = RetryWatcher(lambda: root, clicks.append)
    assert watcher.poll_once().status == 'clicked'
    assert watcher.poll_once().status == 'already_processed'
    assert len(clicks) == 1
    assert clicks[0].name == '继续'


@pytest.mark.parametrize('name', ['代理已停止', '用户说', 'ChatGPT 说', 'A later message'])
def test_old_error_followed_by_activity_is_ignored(name):
    root = live_conversation()
    later_message = AccessibleNode(role='Text', name=name)
    root = replace(
        root,
        children=(*root.children[:-1], later_message, root.children[-1]),
    )
    assert find_latest_continue(root) is None


def test_manual_pause_without_error_is_ignored():
    root = live_conversation()
    assert find_latest_continue(replace(root, children=root.children[1:])) is None


def test_quoted_error_text_is_ignored():
    root = live_conversation()
    quote = AccessibleNode(role='Text', name='exceeded retry limit, last status: 429 Too Many Requests')
    assert find_latest_continue(replace(root, children=(quote, *root.children[1:]))) is None


def test_draft_text_is_ignored():
    root = live_conversation()
    composer = root.children[-1]
    edit = composer.children[0]
    edit = replace(edit, children=(AccessibleNode(role='Text', name='my draft'),))
    composer = replace(composer, children=(edit, *composer.children[1:]))
    assert find_latest_continue(replace(root, children=(*root.children[:-1], composer))) is None
