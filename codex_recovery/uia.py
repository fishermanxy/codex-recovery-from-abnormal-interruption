"""Windows UI Automation adapter for the Codex desktop window."""

from __future__ import annotations

import logging
from typing import Any

from .detector import CONTINUE_NAMES, RECOVERY_ACTION_NAMES, AccessibleNode, find_latest_continue

LOGGER = logging.getLogger("codex_recovery.uia")


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
        return self._build_node(self._window, is_root=True)

    def click(self, node: AccessibleNode) -> None:
        if node.name.strip().casefold() in CONTINUE_NAMES:
            match = find_latest_continue(self.snapshot())
            if match is None or match.button.identifier != node.identifier:
                raise UiaSnapshotError("The error recovery context has changed.")
        control = self._controls.get(node.identifier)
        if control is None:
            raise UiaSnapshotError("The control snapshot is stale. Read the window again.")
        if not node.enabled:
            raise UiaSnapshotError("The recovery control is disabled.")

        if self._control_type(control).casefold() != "button":
            raise UiaSnapshotError("The target control is no longer a button.")
        current_name = self._name(control).strip().casefold()
        if (
            current_name not in RECOVERY_ACTION_NAMES
            or current_name != node.name.strip().casefold()
        ):
            raise UiaSnapshotError(
                "The target control is no longer a supported recovery action."
            )
        try:
            enabled = bool(control.is_enabled())
            visible = bool(control.is_visible())
        except Exception as error:
            raise UiaSnapshotError(
                "The retry control could not be safely revalidated."
            ) from error
        if not enabled or not visible:
            raise UiaSnapshotError("The retry control is no longer available.")

        invoke = getattr(control, "invoke", None)
        if not callable(invoke):
            raise UiaSnapshotError("The retry control does not expose UIA Invoke.")
        invoke()

    def _build_node(self, control: Any, *, is_root: bool = False) -> AccessibleNode:
        identifier = self._identifier(control)
        self._controls[identifier] = control

        children: list[AccessibleNode] = []
        try:
            child_controls = control.children()
            for child in child_controls:
                try:
                    children.append(self._build_node(child))
                except Exception:
                    LOGGER.debug("Skipping inaccessible UIA child", exc_info=True)
        except Exception as error:
            if is_root:
                raise UiaSnapshotError(
                    "The Codex UI Automation tree could not be read."
                ) from error
            LOGGER.debug("Skipping inaccessible UIA subtree", exc_info=True)

        role = self._control_type(control)
        return AccessibleNode(
            role=role,
            name=self._name(control),
            enabled=self._is_enabled(control) if role.casefold() == "button" else True,
            visible=self._is_visible(control),
            identifier=identifier,
            children=tuple(children),
        )

    @staticmethod
    def _control_type(control: Any) -> str:
        try:
            return str(getattr(control.element_info, "control_type", "") or "")
        except Exception:
            return ""

    @staticmethod
    def _name(control: Any) -> str:
        try:
            element_name = getattr(control.element_info, "name", None)
            if element_name:
                return str(element_name)
            return str(control.window_text() or "")
        except Exception:
            return ""

    @staticmethod
    def _is_enabled(control: Any) -> bool:
        try:
            return bool(control.is_enabled())
        except Exception:
            return False

    @staticmethod
    def _is_visible(control: Any) -> bool:
        try:
            return bool(control.is_visible())
        except Exception:
            return True

    @staticmethod
    def _identifier(control: Any) -> str:
        try:
            element_info = control.element_info
            runtime_id = getattr(element_info, "runtime_id", None)
            if runtime_id:
                return f"runtime:{runtime_id!r}"

            automation_id = getattr(element_info, "automation_id", None)
            if automation_id:
                return f"automation:{automation_id}"
        except Exception:
            pass

        return f"control:{id(control)}"
