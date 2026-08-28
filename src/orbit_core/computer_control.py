"""Guarded local Windows UI automation for Orbit's computer mode."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any, Callable
from uuid import uuid4


class ComputerControlError(RuntimeError):
    """Raised when a computer-mode action cannot be carried out safely."""


@dataclass(frozen=True)
class _Target:
    identifier: str
    window_handle: int
    window_title: str
    control: Any


class ComputerController:
    """Allow short, visible automation sessions in the last external window."""

    _ACTIONABLE_TYPES = {"Button", "CheckBox", "Hyperlink", "ListItem", "MenuItem", "TabItem"}
    _TEXT_TYPES = {"Document", "Edit"}

    def __init__(
        self,
        *,
        session_seconds: int = 600,
        desktop_factory: Callable[..., Any] | None = None,
        foreground_window: Callable[[], tuple[int, str]] | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if session_seconds < 30:
            raise ValueError("Computer session must last at least 30 seconds.")

        self.session_seconds = session_seconds
        self._desktop_factory = desktop_factory
        self._foreground_window = foreground_window or self._read_foreground_window
        self._clock = clock
        self._lock = Lock()
        self._session_id: str | None = None
        self._expires_at = 0.0
        self._last_external_window: tuple[int, str] | None = None
        self._targets: dict[str, _Target] = {}
        self._stop_monitor = Event()
        self._monitor: Thread | None = None

    def start(self) -> dict[str, object]:
        with self._lock:
            self._session_id = uuid4().hex
            self._expires_at = self._clock() + self.session_seconds
            self._targets.clear()
            self._stop_monitor.clear()
            if self._monitor is None or not self._monitor.is_alive():
                self._monitor = Thread(target=self._monitor_foreground, daemon=True)
                self._monitor.start()
        return self.status()

    def stop(self) -> dict[str, object]:
        with self._lock:
            self._session_id = None
            self._expires_at = 0.0
            self._targets.clear()
            self._last_external_window = None
            self._stop_monitor.set()
        return self.status()

    def status(self) -> dict[str, object]:
        self._expire_if_needed()
        with self._lock:
            remaining = max(0, round(self._expires_at - self._clock()))
            target_title = self._last_external_window[1] if self._last_external_window else None
            return {
                "active": self._session_id is not None,
                "remainingSeconds": remaining,
                "targetWindow": target_title,
            }

    def inspect(self) -> dict[str, object]:
        self._require_active_session()
        self._remember_foreground()
        with self._lock:
            target_window = self._last_external_window

        if target_window is None:
            raise ComputerControlError(
                "Vaxla till appen du vill att ORBIT ska hjalpa med i ett ogonblick."
            )

        handle, expected_title = target_window
        try:
            window = self._desktop().window(handle=handle).wrapper_object()
            title = window.window_text().strip()
            if not title or title != expected_title:
                raise ComputerControlError("Malfonstret har andrats. Uppdatera datorlaget.")
            controls = self._collect_controls(window, handle, title)
        except ComputerControlError:
            raise
        except Exception as exc:
            raise ComputerControlError("Kunde inte lasa malfonstrets kontroller.") from exc

        return {"windowTitle": title, "controls": controls}

    def click(self, identifier: str) -> dict[str, object]:
        target = self._target(identifier, self._ACTIONABLE_TYPES)
        try:
            target.control.click_input()
        except Exception as exc:
            raise ComputerControlError("Klicket kunde inte goras. Uppdatera datorlaget.") from exc
        return {"action": "click", "control": identifier, "windowTitle": target.window_title}

    def type_text(self, identifier: str, text: str) -> dict[str, object]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text must be a non-empty string.")
        if len(text) > 4_000:
            raise ValueError("Text must not exceed 4000 characters.")

        target = self._target(identifier, self._TEXT_TYPES)
        try:
            target.control.set_focus()
            target.control.type_keys(text, with_spaces=True, with_newlines=True)
        except Exception as exc:
            raise ComputerControlError("Texten kunde inte skrivas. Uppdatera datorlaget.") from exc
        return {"action": "type", "control": identifier, "windowTitle": target.window_title}

    def _target(self, identifier: str, allowed_types: set[str]) -> _Target:
        self._require_active_session()
        with self._lock:
            target = self._targets.get(identifier)
            active_target = self._last_external_window

        if target is None or active_target is None:
            raise ComputerControlError("Uppdatera datorlaget innan ORBIT gor en atgard.")
        if target.window_handle != active_target[0] or target.window_title != active_target[1]:
            raise ComputerControlError("Malfonstret har andrats. Uppdatera datorlaget.")
        if target.control.element_info.control_type not in allowed_types:
            raise ComputerControlError("Den har kontrollen ar inte tillaten for denna atgard.")
        return target

    def _collect_controls(self, window: Any, handle: int, title: str) -> list[dict[str, str]]:
        controls: list[dict[str, str]] = []
        targets: dict[str, _Target] = {}
        for control in window.descendants():
            if len(controls) >= 60:
                break
            try:
                info = control.element_info
                name = (info.name or "").strip()
                control_type = info.control_type
                if not name or control_type not in self._ACTIONABLE_TYPES | self._TEXT_TYPES:
                    continue
                if not control.is_visible() or not control.is_enabled():
                    continue
            except Exception:
                continue

            identifier = f"control-{len(controls) + 1}"
            controls.append({"id": identifier, "name": name, "type": control_type})
            targets[identifier] = _Target(identifier, handle, title, control)

        with self._lock:
            self._targets = targets
        return controls

    def _desktop(self) -> Any:
        if self._desktop_factory is not None:
            return self._desktop_factory(backend="uia")
        try:
            from pywinauto import Desktop
        except ImportError as exc:
            raise ComputerControlError("Windows-automation ar inte installerad.") from exc
        return Desktop(backend="uia")

    def _require_active_session(self) -> None:
        self._expire_if_needed()
        with self._lock:
            if self._session_id is None:
                raise ComputerControlError("Datorlaget ar av. Starta det forst.")

    def _expire_if_needed(self) -> None:
        with self._lock:
            if self._session_id is not None and self._clock() >= self._expires_at:
                self._session_id = None
                self._expires_at = 0.0
                self._targets.clear()
                self._last_external_window = None
                self._stop_monitor.set()

    def _monitor_foreground(self) -> None:
        while not self._stop_monitor.wait(0.25):
            self._expire_if_needed()
            with self._lock:
                if self._session_id is None:
                    return
            self._remember_foreground()

    def _remember_foreground(self) -> None:
        try:
            handle, title = self._foreground_window()
        except Exception:
            return
        if not handle or not title or title.strip().upper() == "ORBIT":
            return
        with self._lock:
            self._last_external_window = (handle, title.strip())

    @staticmethod
    def _read_foreground_window() -> tuple[int, str]:
        try:
            import win32gui
        except ImportError as exc:
            raise ComputerControlError("Windows-automation ar inte installerad.") from exc

        handle = win32gui.GetForegroundWindow()
        return handle, win32gui.GetWindowText(handle)
