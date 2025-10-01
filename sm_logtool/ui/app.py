
"""Textual application for exploring SmarterMail logs."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, ListItem, ListView, Static

from ..logfiles import (
    LogFileInfo,
    parse_log_filename,
    summarize_logs,
)
from ..search import search_smtp_conversations
from ..staging import DEFAULT_STAGING_ROOT, stage_log


try:
    from textual.widgets import TextLog as _TextualTextLog
except ImportError:  # pragma: no cover - textual>=6 renames widgets
    _TextualTextLog = None


if _TextualTextLog is not None:

    class OutputLog(_TextualTextLog):
        def __init__(self, *, id: str | None = None) -> None:
            super().__init__(highlight=False, wrap=True, id=id)

else:

    class OutputLog(Static):
        """Fallback output widget for Textual builds without TextLog."""

        def __init__(self, *, id: str | None = None) -> None:
            super().__init__("", id=id)
            self._lines: list[str] = []

        def write(self, text: str) -> None:
            self._lines.append(text)
            self.update("\n".join(self._lines))

        def clear(self) -> None:
            self._lines.clear()
            self.update("")

class KindListItem(ListItem):
    """List item representing a log kind (e.g., smtpLog)."""

    def __init__(self, kind: str) -> None:
        super().__init__(Static(kind, classes="label"))
        self.kind = kind


class LogListItem(ListItem):
    """List item representing a specific log file."""

    def __init__(self, info: LogFileInfo) -> None:
        label = info.stamp.strftime("%Y.%m.%d") if info.stamp else "unknown"
        suffix = " (zip)" if info.is_zipped else ""
        super().__init__(Static(f"{label}{suffix}", classes="label"))
        self.info = info


class LogBrowser(App):
    """Textual application for exploring SmarterMail logs."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "focus_search", "Focus search"),
        ("r", "refresh", "Refresh"),
    ]

    logs_dir: reactive[Path] = reactive(Path.cwd() / "sample_logs")
    current_kind: reactive[Optional[str]] = reactive(None)
    current_log: reactive[Optional[LogFileInfo]] = reactive(None)

    def __init__(self, logs_dir: Path) -> None:
        super().__init__()
        self.logs_dir = logs_dir
        self._logs_by_kind: Dict[str, List[LogFileInfo]] = {}

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=False)
        with Horizontal(id="panels"):
            with Vertical(id="left_panel"):
                yield Static("Log kinds", classes="panel_title")
                self.kind_list = ListView(id="kind-list")
                yield self.kind_list
            with Vertical(id="middle_panel"):
                yield Static("Available logs", classes="panel_title")
                self.log_list = ListView(id="log-list")
                yield self.log_list
            with Vertical(id="right_panel"):
                yield Static("Search term", classes="panel_title")
                self.search_input = Input(placeholder="Enter search term")
                yield self.search_input
                self.output = OutputLog(id="search-output")
                self.output.write("Select a log and enter a search term.")
                yield self.output
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_logs()
        self._populate_kind_list()
        self._select_initial_kind()
        self.search_input.focus()

    def _refresh_logs(self) -> None:
        kinds: Dict[str, List[LogFileInfo]] = {}
        for path in self.logs_dir.iterdir() if self.logs_dir.exists() else []:
            info = parse_log_filename(path)
            if not info.kind:
                continue
            kinds.setdefault(info.kind, []).append(info)
        for kind, infos in kinds.items():
            kinds[kind] = summarize_logs(self.logs_dir, kind)
        self._logs_by_kind = kinds

    def _populate_kind_list(self) -> None:
        self.kind_list.clear()
        for kind in sorted(self._logs_by_kind):
            self.kind_list.append(KindListItem(kind))
        if not self._logs_by_kind:
            self.kind_list.append(ListItem(Static("No logs discovered")))

    def _select_initial_kind(self) -> None:
        if not self._logs_by_kind:
            self.current_kind = None
            self._populate_log_list([])
            return
        initial = "smtpLog" if "smtpLog" in self._logs_by_kind else next(iter(sorted(self._logs_by_kind)))
        self.current_kind = initial
        self._populate_log_list(self._logs_by_kind[initial])

    def _populate_log_list(self, infos: List[LogFileInfo]) -> None:
        self.log_list.clear()
        if not infos:
            self.log_list.append(ListItem(Static("No logs available")))
            self.current_log = None
            return
        for info in infos:
            self.log_list.append(LogListItem(info))
        self.current_log = infos[0]

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:  # type: ignore[override]
        if event.list_view is self.kind_list and isinstance(event.item, KindListItem):
            self.current_kind = event.item.kind
            self._populate_log_list(self._logs_by_kind.get(event.item.kind, []))
            self._notify(f"Selected kind: {event.item.kind}")
        elif event.list_view is self.log_list and isinstance(event.item, LogListItem):
            self.current_log = event.item.info
            self._notify(f"Ready to search {event.item.info.path.name}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        if event.list_view is self.log_list and isinstance(event.item, LogListItem):
            self.current_log = event.item.info
            self._execute_search()

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        if event.input is self.search_input:
            self._execute_search()

    def action_focus_search(self) -> None:
        self.search_input.focus()

    def action_refresh(self) -> None:
        self._refresh_logs()
        self._populate_kind_list()
        if self.current_kind and self.current_kind in self._logs_by_kind:
            self._populate_log_list(self._logs_by_kind[self.current_kind])
        else:
            self._select_initial_kind()
        self._notify("Log lists refreshed")

    def _execute_search(self) -> None:
        info = self.current_log
        if info is None:
            self._notify("Select a log before searching")
            return
        term = self.search_input.value.strip()
        if not term:
            self._notify("Enter a search term")
            return
        if (self.current_kind or info.kind) != "smtpLog":
            self._notify("Search currently supports smtpLog only")
            return
        try:
            staged = stage_log(info.path, staging_dir=DEFAULT_STAGING_ROOT)
        except Exception as exc:  # pragma: no cover - Textual runtime feedback
            self._notify(f"Failed to stage log: {exc}")
            return
        result = search_smtp_conversations(staged.staged_path, term)
        self._render_result(info, result)

    def _render_result(self, info: LogFileInfo, result) -> None:
        self.output.clear()
        self.output.write(
            f"Search term '{result.term}' -> {result.total_conversations} conversation(s) in {info.path.name}"
        )
        if not result.conversations and not result.orphan_matches:
            self.output.write("No matches found.")
            return
        for conversation in result.conversations:
            self.output.write("")
            self.output.write(
                f"[{conversation.message_id}] first seen on line {conversation.first_line_number}"
            )
            for line in conversation.lines:
                self.output.write(line)
        if result.orphan_matches:
            self.output.write("")
            self.output.write("Lines without message identifiers that matched:")
            for line_number, line in result.orphan_matches:
                self.output.write(f"{line_number}: {line}")

    def _notify(self, message: str) -> None:
        self.output.write(message)


def list_log_files(logs_dir: Path) -> list[Path]:
    """Return a sorted list of non-hidden files in ``logs_dir``.

    Retained for compatibility with legacy tests.
    """

    if not logs_dir.exists() or not logs_dir.is_dir():
        return []
    return sorted(p for p in logs_dir.iterdir() if p.is_file() and not p.name.startswith("."))


def run(logs_dir: Path) -> int:
    """Run the Textual app. Returns an exit code."""

    app = LogBrowser(logs_dir=logs_dir)
    app.run()
    return 0
