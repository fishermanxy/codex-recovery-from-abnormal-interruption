import uuid

from codex_recovery.instance import SingleInstanceGuard


def test_only_one_instance_owns_the_mutex():
    mutex_name = f"Local\\CodexRecoveryTest-{uuid.uuid4()}"
    first = SingleInstanceGuard(mutex_name)
    second = SingleInstanceGuard(mutex_name)

    try:
        assert first.is_owner
        assert not first.already_running
        assert not second.is_owner
        assert second.already_running
    finally:
        second.close()
        first.close()
