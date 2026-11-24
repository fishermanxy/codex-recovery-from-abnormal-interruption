from codex_recovery.connection_notice import ConnectionRecoveryNotice


def test_repeated_connection_errors_only_notify_once_until_recovery():
    notice = ConnectionRecoveryNotice()

    assert notice.on_error()
    assert not notice.on_error()

    notice.on_success()

    assert notice.on_error()
