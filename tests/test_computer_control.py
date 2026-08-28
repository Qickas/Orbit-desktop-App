import pytest

from orbit_core.computer_control import ComputerControlError, ComputerController


class FakeInfo:
    def __init__(self, name: str, control_type: str) -> None:
        self.name = name
        self.control_type = control_type


class FakeControl:
    def __init__(self, name: str, control_type: str) -> None:
        self.element_info = FakeInfo(name, control_type)
        self.clicked = False
        self.typed = ""

    def is_visible(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def click_input(self) -> None:
        self.clicked = True

    def set_focus(self) -> None:
        return None

    def type_keys(self, text: str, **_kwargs: object) -> None:
        self.typed += text


class FakeWindow:
    def __init__(self, title: str, controls: list[FakeControl]) -> None:
        self.title = title
        self.controls = controls

    def wrapper_object(self) -> "FakeWindow":
        return self

    def window_text(self) -> str:
        return self.title

    def descendants(self) -> list[FakeControl]:
        return self.controls


class FakeDesktop:
    def __init__(self, window: FakeWindow) -> None:
        self.window_value = window

    def window(self, *, handle: int) -> FakeWindow:
        assert handle == 42
        return self.window_value


def test_computer_mode_inspects_clicks_and_types_in_its_saved_window() -> None:
    click = FakeControl("Spara", "Button")
    edit = FakeControl("Dokument", "Edit")
    window = FakeWindow("Exempel", [click, edit])
    controller = ComputerController(
        desktop_factory=lambda **_kwargs: FakeDesktop(window),
        foreground_window=lambda: (42, "Exempel"),
    )

    started = controller.start()
    context = controller.inspect()
    controller.click("control-1")
    controller.type_text("control-2", "Hej ORBIT")
    stopped = controller.stop()

    assert started["active"] is True
    assert context == {
        "windowTitle": "Exempel",
        "controls": [
            {"id": "control-1", "name": "Spara", "type": "Button"},
            {"id": "control-2", "name": "Dokument", "type": "Edit"},
        ],
    }
    assert click.clicked is True
    assert edit.typed == "Hej ORBIT"
    assert stopped["active"] is False


def test_computer_mode_rejects_actions_after_stop() -> None:
    controller = ComputerController(
        desktop_factory=lambda **_kwargs: FakeDesktop(FakeWindow("Exempel", [])),
        foreground_window=lambda: (42, "Exempel"),
    )

    with pytest.raises(ComputerControlError, match="Datorlaget ar av"):
        controller.inspect()
