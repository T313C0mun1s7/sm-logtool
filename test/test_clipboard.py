from sm_logtool.ui import clipboard as clipboard_module


def test_copy_text_to_system_clipboard_prefers_wayland(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def _fake_run(command: tuple[str, ...], *_args) -> bool:
        calls.append(command)
        return command[0] == "wl-copy"

    monkeypatch.setattr(clipboard_module, "_run_clipboard_command", _fake_run)
    backend = clipboard_module.copy_text_to_system_clipboard(
        "demo",
        env={"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"},
    )
    assert backend == "wl-copy"
    assert calls == [("wl-copy",)]


def test_copy_text_to_system_clipboard_uses_xclip_when_available(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def _fake_run(command: tuple[str, ...], *_args) -> bool:
        calls.append(command)
        return command[0] == "xclip"

    monkeypatch.setattr(clipboard_module, "_run_clipboard_command", _fake_run)
    backend = clipboard_module.copy_text_to_system_clipboard(
        "demo",
        env={"DISPLAY": ":0"},
    )
    assert backend == "xclip"
    assert calls[0] == ("xclip", "-selection", "clipboard")


def test_copy_text_to_system_clipboard_returns_none_without_backend(
    monkeypatch,
):
    def _fake_run(*_args) -> bool:
        return False

    monkeypatch.setattr(clipboard_module, "_run_clipboard_command", _fake_run)
    backend = clipboard_module.copy_text_to_system_clipboard(
        "demo",
        env={},
    )
    assert backend is None
