"""Launch the registered Codex app and track its owning process."""

from __future__ import annotations

import ctypes
import time
from ctypes import POINTER
from ctypes.wintypes import DWORD, HANDLE, LONG, LPCWSTR, LPWSTR

import comtypes
import win32api
import win32con
import win32event
import win32gui
import win32process

CODEX_APP_ID = "OpenAI.Codex_2p2nqsd0c76g0!App"
CODEX_PACKAGE_FAMILY = CODEX_APP_ID.split("!", 1)[0]
ACTIVATION_MANAGER_CLSID = "{45BA127D-10A8-46EA-8AB7-56EA9078943C}"


class _ApplicationActivationManager(comtypes.IUnknown):
    _iid_ = comtypes.GUID("{2E941141-7F97-4756-BA1D-9DECDE894A3D}")
    _methods_ = [
        comtypes.COMMETHOD(
            [],
            comtypes.HRESULT,
            "ActivateApplication",
            (["in"], LPCWSTR, "app_user_model_id"),
            (["in"], LPCWSTR, "arguments"),
            (["in"], DWORD, "options"),
            (["out"], POINTER(DWORD), "process_id"),
        ),
    ]


class CodexSession:
    """Hold a process handle so window visibility never determines lifetime."""

    def __init__(self, process_id: int) -> None:
        self.process_id = process_id
        self._handle = win32api.OpenProcess(win32con.SYNCHRONIZE, False, process_id)

    @classmethod
    def start(cls, window_title: str = "ChatGPT") -> "CodexSession":
        comtypes.CoInitialize()
        manager = None
        try:
            manager = comtypes.CoCreateInstance(
                comtypes.GUID(ACTIVATION_MANAGER_CLSID),
                interface=_ApplicationActivationManager,
                clsctx=comtypes.CLSCTX_LOCAL_SERVER,
            )
            manager.ActivateApplication(CODEX_APP_ID, "", 0)
        finally:
            manager = None
            comtypes.CoUninitialize()

        # A single-instance app can return a short-lived activation proxy.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            session = _find_codex_session(window_title)
            if session is not None:
                return session
            time.sleep(0.2)
        raise TimeoutError("Codex did not expose its desktop window within 30 seconds.")

    @property
    def running(self) -> bool:
        return self._handle is not None and (
            win32event.WaitForSingleObject(self._handle, 0) == win32event.WAIT_TIMEOUT
        )

    def close(self) -> None:
        if self._handle is not None:
            self._handle.Close()
            self._handle = None


def _package_family(handle) -> str | None:
    get_family = ctypes.WinDLL("kernel32").GetPackageFamilyName
    get_family.argtypes = [HANDLE, POINTER(DWORD), LPWSTR]
    get_family.restype = LONG
    length = DWORD()
    if get_family(int(handle), ctypes.byref(length), None) != 122:
        return None
    family = ctypes.create_unicode_buffer(length.value)
    if get_family(int(handle), ctypes.byref(length), family) != 0:
        return None
    return family.value


def _find_codex_session(window_title: str) -> CodexSession | None:
    sessions: list[CodexSession] = []

    def inspect_window(hwnd, extra):
        if sessions:
            return
        try:
            if win32gui.GetWindowText(hwnd) != window_title:
                return
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(0x1000, False, process_id)
            try:
                if _package_family(handle) == CODEX_PACKAGE_FAMILY:
                    sessions.append(CodexSession(process_id))
            finally:
                handle.Close()
        except win32api.error:
            # Windows may disappear while startup is still in progress.
            return

    win32gui.EnumWindows(inspect_window, None)
    return sessions[0] if sessions else None
