import pytest

from codex_recovery.detector import ERROR_TEXT
from codex_recovery.uia import UiaWindowSource
from codex_recovery.uia import UiaSnapshotError
from codex_recovery.watcher import RetryWatcher


class FakeElementInfo:
    control_type = "Window"
    name = ""
    runtime_id = (1,)
    automation_id = ""


class FakeControl:
    element_info = FakeElementInfo()

    def __init__(self, *, children=(), role="Window", name="", fail_enabled=False):
        self._children = tuple(children)
        self._role = role
        self._name = name
        self._fail_enabled = fail_enabled
        self.invoked = False

    @property
    def element_info(self):
        info = FakeElementInfo()
        info.control_type = self._role
        info.name = self._name
        info.runtime_id = (id(self),)
        return info

    def children(self):
        return self._children

    def is_enabled(self):
        if self._fail_enabled:
            raise RuntimeError("transient UIA failure")
        return True

    def is_visible(self):
        return True

    def window_text(self):
        return self._name

    def invoke(self):
        self.invoked = True


def test_snapshot_keeps_working_when_an_unrelated_control_is_unavailable():
    broken_control = FakeControl(role="Text", fail_enabled=True)
    root = FakeControl(children=(broken_control,))

    snapshot = UiaWindowSource(root).snapshot()

    assert len(snapshot.children) == 1
    assert snapshot.children[0].enabled is True


def test_snapshot_marks_an_unreadable_button_as_disabled():
    broken_button = FakeControl(
        role="Button",
        name="重试",
        fail_enabled=True,
    )
    root = FakeControl(children=(broken_button,))

    snapshot = UiaWindowSource(root).snapshot()

    assert snapshot.children[0].enabled is False


def test_click_revalidates_the_control_before_invoking_it():
    button = FakeControl(role="Button", name="重试")
    root = FakeControl(children=(button,))
    source = UiaWindowSource(root)
    snapshot = source.snapshot()

    source.click(snapshot.children[0])

    assert button.invoked is True


def test_click_accepts_a_continue_recovery_control():
    button = FakeControl(role="Button", name="继续")
    error = FakeControl(role="Text", name="exceeded retry limit")
    root = FakeControl(role="Dialog", children=(error, button))
    source = UiaWindowSource(root)
    snapshot = source.snapshot()

    source.click(snapshot.children[1])

    assert button.invoked is True


def test_continue_rechecks_error_context_before_invocation():
    button = FakeControl(role="Button", name="继续")
    error = FakeControl(role="Text", name="exceeded retry limit")
    root = FakeControl(role="Dialog", children=(error, button))
    source = UiaWindowSource(root)
    snapshot = source.snapshot()
    root._children = (button,)

    with pytest.raises(UiaSnapshotError):
        source.click(snapshot.children[1])

    assert button.invoked is False


def test_click_rejects_a_control_whose_name_changed():
    button = FakeControl(role="Button", name="重试")
    root = FakeControl(children=(button,))
    source = UiaWindowSource(root)
    snapshot = source.snapshot()
    button._name = "发送"

    with pytest.raises(UiaSnapshotError):
        source.click(snapshot.children[0])

    assert button.invoked is False


def test_click_rejects_retry_changed_to_continue():
    button = FakeControl(role="Button", name="重试")
    source = UiaWindowSource(FakeControl(children=(button,)))
    snapshot = source.snapshot()
    button._name = "继续"

    with pytest.raises(UiaSnapshotError):
        source.click(snapshot.children[0])

    assert button.invoked is False


@pytest.mark.parametrize('failure', ['enabled', 'children'])
def test_partial_post_click_snapshot_does_not_rearm_recovery(failure):
    button = FakeControl(role='Button', name='重试')
    error = FakeControl(role='Text', name=ERROR_TEXT)
    group = FakeControl(role='Group', children=(error, button))
    source = UiaWindowSource(FakeControl(children=(group,)))
    clicks = []
    original_children = group.children

    def unavailable_children():
        raise RuntimeError('UIA refresh after recovery')

    def click(node):
        source.click(node)
        clicks.append(node)
        if failure == 'enabled':
            button._fail_enabled = True
        else:
            group.children = unavailable_children

    watcher = RetryWatcher(source.snapshot, click)

    assert watcher.poll_once().status == 'clicked'
    button._fail_enabled = False
    group.children = original_children
    assert watcher.poll_once().status == 'already_processed'
    assert len(clicks) == 1
