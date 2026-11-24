"""Windows UI Automation adapter for the Codex desktop window."""

from __future__ import annotations

from typing import Any

from .detector import AccessibleNode


class UiaSnapshotError(RuntimeError):
    """Raised when the live UI tree cannot be read or acted on."""


class UiaWindowSource:
    """Read a Codex window through pywinauto's UIA backend."""

    def __init__(self, window: Any) -> None:
        self._window = window
        self._controls: dict[str, Any] = {}

    @classmethod
    def connect(cls, title: str = "ChatGPT", timeout: float = 5.0) -> "UiaWindowSource":
        try:
            from pywinauto import Desktop
        except ImportError as error:
            raise UiaSnapshotError(
                "pywinauto is required. Use the native-ui Python environment."
            ) from error

        win32_window = Desktop(backend="win32").window(title=title)
        win32_window.wait("exists", timeout=timeout)

        window = Desktop(backend="uia").window(handle=win32_window.handle)
        window.wait("exists", timeout=timeout)
        return cls(window)

    def snapshot(self) -> AccessibleNode:
        self._controls = {}
        return self._build_node(self._window)

    def click(self, node: AccessibleNode) -> None:
        control = self._controls.get(node.identifier)
        if control is None:
            raise UiaSnapshotError("The control snapshot is stale. Read the window again.")
        if not node.enabled:
            raise UiaSnapshotError("The retry control is disabled.")

        invoke = getattr(control, "invoke", None)
        if invoke is None:
            raise UiaSnapshotError("The retry control does not expose UIA Invoke.")
        invoke()

    def _build_node(self, control: Any) -> AccessibleNode:
        identifier = self._identifier(control)
        self._controls[identifier] = control

        children = tuple(self._build_node(child) for child in control.children())
        return AccessibleNode(
            role=self._control_type(control),
            name=self._name(control),
            enabled=control.is_enabled(),
            visible=control.is_visible(),
            identifier=identifier,
            children=children,
        )

    @staticmethod
    def _control_type(control: Any) -> str:
        return str(getattr(control.element_info, "control_type", "") or "")

    @staticmethod
    def _name(control: Any) -> str:
        element_name = getattr(control.element_info, "name", None)
        if element_name:
            return str(element_name)
        return str(control.window_text() or "")

    @staticmethod
    def _identifier(control: Any) -> str:
        element_info = control.element_info
        runtime_id = getattr(element_info, "runtime_id", None)
        if runtime_id:
            return f"runtime:{runtime_id!r}"

        automation_id = getattr(element_info, "automation_id", None)
        if automation_id:
            return f"automation:{automation_id}"

        return f"control:{id(control)}"
