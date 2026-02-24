from sm_logtool.ui import clipboard as clipboard_module


def test_copy_text_to_system_clipboard_prefers_wayland(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def _fake_run(command: tuple[str, ...], *_args) -> bool:
        calls.append(command)
        return command[0] == "wl-copy"

    monkeypatch.setattr(
        clipboard_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name == "wl-copy" else None,
    )
    monkeypatch.setattr(clipboard_module, "_run_clipboard_command", _fake_run)
    backend = clipboard_module.copy_text_to_system_clipboard(
        "demo",
        env={"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"},
    )
    assert backend == "wl-copy"
    assert calls == [("wl-copy",)]


def test_copy_text_to_system_clipboard_uses_xsel_on_x11(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def _fake_run(command: tuple[str, ...], *_args) -> bool:
        calls.append(command)
        return command[0] == "xsel"

    monkeypatch.setattr(
        clipboard_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"xsel", "xclip"} else None,
    )
    monkeypatch.setattr(clipboard_module, "_run_clipboard_command", _fake_run)
    backend = clipboard_module.copy_text_to_system_clipboard(
        "demo",
        env={"DISPLAY": ":0"},
    )
    assert backend == "xsel"
    assert calls == [("xsel", "--clipboard", "--input")]


def test_copy_text_to_system_clipboard_uses_xclip_when_xsel_missing(
    monkeypatch,
):
    calls: list[tuple[str, ...]] = []

    def _fake_run(command: tuple[str, ...], *_args) -> bool:
        calls.append(command)
        return command[0] == "xclip"

    monkeypatch.setattr(
        clipboard_module.shutil,
        "which",
        lambda name: "/usr/bin/xclip" if name == "xclip" else None,
    )
    monkeypatch.setattr(clipboard_module, "_run_clipboard_command", _fake_run)
    backend = clipboard_module.copy_text_to_system_clipboard(
        "demo",
        env={"DISPLAY": ":0"},
    )
    assert backend == "xclip"
    assert calls == [("xclip", "-selection", "clipboard", "-in")]


def test_copy_text_to_system_clipboard_returns_none_without_backend(
    monkeypatch,
):
    monkeypatch.setattr(
        clipboard_module.shutil,
        "which",
        lambda _name: None,
    )

    def _fake_run(*_args) -> bool:
        return False

    monkeypatch.setattr(clipboard_module, "_run_clipboard_command", _fake_run)
    backend = clipboard_module.copy_text_to_system_clipboard(
        "demo",
        env={},
    )
    assert backend is None


def test_run_clipboard_command_returns_false_on_timeout(monkeypatch):
    monkeypatch.setattr(
        clipboard_module.shutil,
        "which",
        lambda _name: "/usr/bin/wl-copy",
    )

    def _timeout_run(*_args, **_kwargs):
        raise clipboard_module.subprocess.TimeoutExpired(
            cmd=("wl-copy",),
            timeout=clipboard_module.CLIPBOARD_COMMAND_TIMEOUT_SECONDS,
        )

    monkeypatch.setattr(
        clipboard_module.subprocess,
        "run",
        _timeout_run,
    )
    ok = clipboard_module._run_clipboard_command(
        ("wl-copy",),
        "demo",
        {},
    )
    assert ok is False
