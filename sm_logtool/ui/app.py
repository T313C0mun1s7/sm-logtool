"""Minimal Textual app scaffold for sm-logtool.

This provides a left-hand file list and a right-hand placeholder view. It reads
available log files from the provided logs directory and lists them for future
interaction (search, preview, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, ListItem, ListView, Static


def list_log_files(logs_dir: Path) -> list[Path]:
    """Return a sorted list of non-hidden files in ``logs_dir``.

    Designed to mirror the CLI's development workflow with ``sample_logs``.
    """

    if not logs_dir.exists() or not logs_dir.is_dir():
        return []
    return sorted(p for p in logs_dir.iterdir() if p.is_file() and not p.name.startswith("."))


class LogBrowser(App):
    """Textual application for exploring SmarterMail logs."""

    CSS = ""
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "search", "Search"),
        ("r", "refresh", "Refresh"),
    ]

    logs_dir: reactive[Path] = reactive(Path.cwd() / "sample_logs")

    def __init__(self, logs_dir: Path) -> None:
        super().__init__()
        self.logs_dir = logs_dir

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=False)
        with Horizontal():
            self.file_list = ListView(id="files")
            self.output = Static("Select a log file to begin.", id="output")
            yield self.file_list
            yield self.output
        yield Footer()

    def on_mount(self) -> None:
        self._populate_files()

    def _populate_files(self) -> None:
        self.file_list.clear()
        files = list_log_files(self.logs_dir)
        if not files:
            self.file_list.append(ListItem(Static(f"No files in {self.logs_dir}")))
            return
        for path in files:
            self.file_list.append(ListItem(Static(path.name, id=f"file-{path.name}")))

    def action_search(self) -> None:
        # Placeholder: later, open an input widget and run a search against the selected file
        self.output.update("Search not implemented yet. Press 'r' to refresh.")

    def action_refresh(self) -> None:
        self._populate_files()


def run(logs_dir: Path) -> int:
    """Run the Textual app. Returns an exit code."""

    app = LogBrowser(logs_dir=logs_dir)
    app.run()
    return 0

