"""Windows system-tray application for continuous Codex recovery watching."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import logging
import queue
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import comtypes
import pythoncom
import win32api
import win32con
import win32gui

from .config import AppConfig, default_config_path, load_config, save_config
from .connection_notice import ConnectionRecoveryNotice
from .startup import set_autostart
from .uia import UiaWindowSource
from .watcher import RetryWatcher

LOGGER = logging.getLogger("codex_recovery.tray")
WM_TRAY = win32con.WM_USER + 20
WM_WORKER_EVENT = win32con.WM_USER + 21
COMMAND_TOGGLE = 1001
COMMAND_SETTINGS = 1002
COMMAND_EXIT = 1003


class _Guid(ctypes.Structure):
    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", wintypes.BYTE * 8),
    ]


class _NotifyIconData(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeout", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", _Guid),
        ("hBalloonIcon", wintypes.HICON),
    ]


def _load_tray_icon() -> int:
    if getattr(sys, "frozen", False):
        try:
            icon = win32gui.LoadIcon(win32api.GetModuleHandle(None), 1)
            if icon:
                return icon
        except win32gui.error:
            pass
        icon_path = Path(sys.executable)
    else:
        icon_path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "codex-recovery.ico"
        )

    try:
        icon = win32gui.LoadImage(
            0,
            str(icon_path),
            win32con.IMAGE_ICON,
            0,
            0,
            win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
        )
        if icon:
            return icon
    except win32gui.error:
        pass
    return win32gui.LoadIcon(0, win32con.IDI_APPLICATION)


@dataclass(frozen=True)
class WorkerEvent:
    status: str
    card_key: str | None = None
    detail: str = ""


class WatchWorker:
    """Own the UIA connection and watcher state on one COM-enabled thread."""

    def __init__(self, config: AppConfig, on_event: Any) -> None:
        self._config = config
        self._on_event = on_event
        self._stop_event = threading.Event()
        self._enabled_event = threading.Event()
        if config.listening_enabled:
            self._enabled_event.set()
        self._thread = threading.Thread(
            target=self._run,
            name="codex-recovery-watcher",
            daemon=True,
        )
        self._source: UiaWindowSource | None = None
        self._watcher: RetryWatcher | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled_event.is_set()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._enabled_event.set()
        self._thread.join(timeout=3)

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._enabled_event.set()
        else:
            self._enabled_event.clear()
            self._source = None
            self._watcher = None

    def _run(self) -> None:
        pythoncom.CoInitialize()
        comtypes.CoInitialize()
        try:
            self._run_loop()
        finally:
            comtypes.CoUninitialize()
            pythoncom.CoUninitialize()

    def _run_loop(self) -> None:
        paused_reported = False
        while not self._stop_event.is_set():
            if not self._enabled_event.is_set():
                if not paused_reported:
                    self._on_event(WorkerEvent("paused"))
                    paused_reported = True
                self._stop_event.wait(0.5)
                continue

            paused_reported = False
            try:
                if self._watcher is None:
                    self._source = UiaWindowSource.connect(
                        title=self._config.window_title
                    )
                    self._watcher = RetryWatcher(
                        self._source.snapshot,
                        self._source.click,
                    )
                    self._on_event(WorkerEvent("listening"))

                result = self._watcher.poll_once()
                self._on_event(
                    WorkerEvent(
                        status=result.status,
                        card_key=result.card_key,
                    )
                )
                self._stop_event.wait(self._config.interval_seconds)
            except Exception as error:
                LOGGER.exception("Watcher iteration failed")
                self._source = None
                self._watcher = None
                self._on_event(WorkerEvent("error", detail=str(error)))
                self._stop_event.wait(self._config.interval_seconds)


class TrayApplication:
    """Own the tray icon, settings dialog and worker lifecycle."""

    def __init__(self, config: AppConfig, config_path: Path | None = None) -> None:
        self._config = config
        self._config_path = config_path or default_config_path()
        self._events: queue.Queue[WorkerEvent] = queue.Queue()
        self._connection_notice = ConnectionRecoveryNotice()
        self._tooltip = "Codex Recovery"
        self._class_name = "CodexRecoveryTrayWindow"
        self._hwnd = self._create_window()
        self._icon = _load_tray_icon()
        self._install_tray_icon()
        self._worker = WatchWorker(config, self._enqueue_event)
        self._worker.start()

    def run(self) -> None:
        win32gui.PumpMessages()

    def _create_window(self) -> int:
        instance = win32api.GetModuleHandle(None)
        window_class = win32gui.WNDCLASS()
        window_class.hInstance = instance
        window_class.lpszClassName = self._class_name
        window_class.lpfnWndProc = self._window_proc
        try:
            win32gui.RegisterClass(window_class)
        except win32gui.error:
            pass

        return win32gui.CreateWindow(
            self._class_name,
            "Codex Recovery",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            instance,
            None,
        )

    def _install_tray_icon(self) -> None:
        flags = win32gui.NIF_MESSAGE | win32gui.NIF_ICON | win32gui.NIF_TIP
        win32gui.Shell_NotifyIcon(
            win32gui.NIM_ADD,
            (self._hwnd, 0, flags, WM_TRAY, self._icon, self._tooltip),
        )

    def _update_tooltip(self, tooltip: str) -> None:
        self._tooltip = tooltip
        flags = win32gui.NIF_MESSAGE | win32gui.NIF_ICON | win32gui.NIF_TIP
        win32gui.Shell_NotifyIcon(
            win32gui.NIM_MODIFY,
            (self._hwnd, 0, flags, WM_TRAY, self._icon, tooltip),
        )

    def _notify(self, title: str, message: str) -> None:
        data = _NotifyIconData()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = self._hwnd
        data.uID = 0
        data.uFlags = win32gui.NIF_INFO
        data.uCallbackMessage = WM_TRAY
        data.hIcon = self._icon
        data.szInfo = message[:255]
        data.uTimeout = 5000
        data.szInfoTitle = title[:63]
        data.dwInfoFlags = win32gui.NIIF_INFO
        shell32 = ctypes.windll.shell32
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(_NotifyIconData),
        ]
        if not shell32.Shell_NotifyIconW(
            win32gui.NIM_MODIFY,
            ctypes.byref(data),
        ):
            raise ctypes.WinError()

    def _enqueue_event(self, event: WorkerEvent) -> None:
        self._events.put(event)
        win32gui.PostMessage(self._hwnd, WM_WORKER_EVENT, 0, 0)

    def _drain_events(self) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                return

            if event.status == "listening":
                self._connection_notice.on_success()
                self._update_tooltip("Codex Recovery：监听中")
            elif event.status == "paused":
                self._update_tooltip("Codex Recovery：已暂停")
            elif event.status == "clicked":
                self._update_tooltip("Codex Recovery：已重试")
                if self._config.notify_on_retry:
                    self._notify(
                        "Codex Recovery",
                        "检测到模型容量错误，已自动点击重试。",
                    )
            elif event.status == "error":
                self._update_tooltip("Codex Recovery：连接异常")
                if self._connection_notice.on_error():
                    self._notify("Codex Recovery", "监听器连接异常，正在恢复。")

    def _show_menu(self) -> None:
        menu = win32gui.CreatePopupMenu()
        toggle_text = "暂停监听" if self._worker.enabled else "开始监听"
        win32gui.AppendMenu(menu, win32con.MF_STRING, COMMAND_TOGGLE, toggle_text)
        win32gui.AppendMenu(menu, win32con.MF_STRING, COMMAND_SETTINGS, "设置")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, COMMAND_EXIT, "退出")
        win32gui.SetForegroundWindow(self._hwnd)
        x, y = win32gui.GetCursorPos()
        win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON,
            x,
            y,
            0,
            self._hwnd,
            None,
        )
        win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)
        win32gui.DestroyMenu(menu)

    def _toggle_listening(self) -> None:
        self._config.listening_enabled = not self._worker.enabled
        save_config(self._config, self._config_path)
        self._worker.set_enabled(self._config.listening_enabled)

    def _show_settings(self) -> None:
        root = tk.Tk()
        root.title("Codex Recovery 设置")
        root.resizable(False, False)

        listening_var = tk.BooleanVar(value=self._config.listening_enabled)
        autostart_var = tk.BooleanVar(value=self._config.autostart)
        notify_var = tk.BooleanVar(value=self._config.notify_on_retry)

        frame = tk.Frame(root, padx=18, pady=16)
        frame.pack()
        tk.Checkbutton(frame, text="启动监听", variable=listening_var).pack(anchor="w")
        tk.Checkbutton(
            frame,
            text="登录 Windows 后自动启动",
            variable=autostart_var,
        ).pack(anchor="w")
        tk.Checkbutton(
            frame,
            text="自动重试后发送通知",
            variable=notify_var,
        ).pack(anchor="w")

        buttons = tk.Frame(frame, pady=12)
        buttons.pack(anchor="e")

        def save_and_close() -> None:
            self._config.listening_enabled = listening_var.get()
            self._config.autostart = autostart_var.get()
            self._config.notify_on_retry = notify_var.get()
            save_config(self._config, self._config_path)
            set_autostart(self._config.autostart)
            self._worker.set_enabled(self._config.listening_enabled)
            root.destroy()

        tk.Button(buttons, text="保存", command=save_and_close).pack(
            side="right",
            padx=(8, 0),
        )
        tk.Button(buttons, text="取消", command=root.destroy).pack(side="right")
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        root.mainloop()

    def _exit(self) -> None:
        self._worker.stop()
        win32gui.Shell_NotifyIcon(
            win32gui.NIM_DELETE,
            (self._hwnd, 0),
        )
        win32gui.DestroyWindow(self._hwnd)

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == WM_TRAY:
            if lparam == win32con.WM_LBUTTONDBLCLK:
                self._show_settings()
            elif lparam == win32con.WM_RBUTTONUP:
                self._show_menu()
            return 0

        if message == WM_WORKER_EVENT:
            self._drain_events()
            return 0

        if message == win32con.WM_COMMAND:
            command = win32api.LOWORD(wparam)
            if command == COMMAND_TOGGLE:
                self._toggle_listening()
            elif command == COMMAND_SETTINGS:
                self._show_settings()
            elif command == COMMAND_EXIT:
                self._exit()
                win32gui.PostQuitMessage(0)
            return 0

        if message == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)


def run_application() -> int:
    parser = argparse.ArgumentParser(
        description="Run Codex Recovery in the system tray."
    )
    parser.add_argument("--config-path", type=str)
    args = parser.parse_args()

    config_path = Path(args.config_path) if args.config_path else None
    log_path = (config_path or default_config_path()).with_name(
        "codex-recovery.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = load_config(config_path)
    application = TrayApplication(config, config_path)
    application.run()
    return 0


def main() -> int:
    from .instance import SingleInstanceGuard

    instance_guard = SingleInstanceGuard()
    if instance_guard.already_running:
        return 0

    try:
        return run_application()
    finally:
        instance_guard.close()


if __name__ == "__main__":
    raise SystemExit(main())
