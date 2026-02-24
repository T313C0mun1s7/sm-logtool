"""Clipboard helpers for the Textual UI."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import os
from pathlib import Path
import shutil
import subprocess

ClipboardCommand = tuple[str, ...]
CLIPBOARD_COMMAND_TIMEOUT_SECONDS = 0.2


def copy_text_to_system_clipboard(
    text: str,
    *,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Copy text with native clipboard tools.

    Returns the backend command name when a copy command succeeds.
    """
    active_env = dict(os.environ if env is None else env)
    command = _preferred_clipboard_command(active_env)
    if command is None:
        return None
    if _run_clipboard_command(command, text, active_env):
        return Path(command[0]).name
    return None


def _clipboard_commands(env: Mapping[str, str]) -> Iterable[ClipboardCommand]:
    if env.get("WAYLAND_DISPLAY"):
        yield ("wl-copy",)
        return
    if env.get("DISPLAY"):
        yield ("xsel", "--clipboard", "--input")
        yield ("xclip", "-selection", "clipboard", "-in")
        return

    if os.name == "nt":
        yield ("clip.exe",)
        return
    yield ("pbcopy",)


def _preferred_clipboard_command(
    env: Mapping[str, str],
) -> ClipboardCommand | None:
    for command in _clipboard_commands(env):
        if shutil.which(command[0]) is not None:
            return command
    return None


def _run_clipboard_command(
    command: ClipboardCommand,
    text: str,
    env: Mapping[str, str],
) -> bool:
    try:
        completed = subprocess.run(
            command,
            input=text,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            env=dict(env),
            timeout=CLIPBOARD_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
