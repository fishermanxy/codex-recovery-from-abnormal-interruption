"""Single-instance guard for the Windows tray application."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes

ERROR_ALREADY_EXISTS = 183


class SingleInstanceGuard:
    """Keep a named Windows mutex open while this process is running."""

    def __init__(self, name: str = "Local\\CodexRecovery") -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._close_handle = kernel32.CloseHandle
        self._close_handle.argtypes = [wintypes.HANDLE]
        self._close_handle.restype = wintypes.BOOL

        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        create_mutex.restype = wintypes.HANDLE

        ctypes.set_last_error(0)
        handle = create_mutex(None, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())

        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        self.is_owner = not self.already_running
        self._handle = handle if self.is_owner else None
        if self.already_running:
            self._close_handle(handle)

    def close(self) -> None:
        if self._handle is not None:
            self._close_handle(self._handle)
            self._handle = None
