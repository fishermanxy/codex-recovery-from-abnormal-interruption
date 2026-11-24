from codex_recovery.uia import UiaWindowSource


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

    @property
    def element_info(self):
        info = FakeElementInfo()
        info.control_type = self._role
        info.name = self._name
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
