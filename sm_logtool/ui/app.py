"""Wizard-style Textual UI for sm-logtool."""

from __future__ import annotations

import inspect
from datetime import date
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, ListItem, ListView, Static

from ..logfiles import (
    LogFileInfo,
    parse_log_filename,
    summarize_logs,
)
from ..search import search_smtp_conversations
from ..staging import DEFAULT_STAGING_ROOT, stage_log

try:
    from textual.widgets import TextLog as _BaseLog
except ImportError:  # pragma: no cover - textual>=6 renames widgets
    try:
        from textual.widgets import Log as _BaseLog  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover - final fallback
        _BaseLog = None


if _BaseLog is not None:

    class OutputLog(_BaseLog):
        """Text log widget that adapts to Textual version differences."""

        def __init__(self, *, id: str | None = None) -> None:
            kwargs = {}
            init_sig = inspect.signature(_BaseLog.__init__)
            if "highlight" in init_sig.parameters:
                kwargs["highlight"] = False
            if "wrap" in init_sig.parameters:
                kwargs["wrap"] = True
            if "id" in init_sig.parameters:
                kwargs["id"] = id
            super().__init__(**kwargs)  # type: ignore[arg-type]

else:

    class OutputLog(Static):  # type: ignore[no-redef]
        """Fallback when neither TextLog nor Log widgets are available."""

        def __init__(self, *, id: str | None = None) -> None:
            super().__init__("", id=id)
            self._lines: list[str] = []

        def write(self, text: str) -> None:  # type: ignore[override]
            self._lines.append(text)
            self.update("\n".join(self._lines))

        def clear(self) -> None:  # type: ignore[override]
            self._lines.clear()
            self.update("")


class WizardStep(Enum):
    KIND = auto()
    DATE = auto()
    SEARCH = auto()
    RESULTS = auto()


class KindListItem(ListItem):
    def __init__(self, kind: str) -> None:
        self.label_widget = Static(kind, classes="label")
        super().__init__(self.label_widget)
        self.kind = kind

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")


class KindListView(ListView):
    """Simple list view for selecting a single log kind."""

    pass


class DateListItem(ListItem):
    def __init__(self, info: LogFileInfo) -> None:
        label = info.stamp.strftime("%Y.%m.%d") if info.stamp else info.path.name
        suffix = " (zip)" if info.is_zipped else ""
        self.label_widget = Static(f"{label}{suffix}", classes="label")
        super().__init__(self.label_widget)
        self.info = info
        self.selected = False

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    def on_mouse_down(self, event: events.MouseDown) -> None:  # pragma: no cover - UI behaviour
        parent = self.parent
        if isinstance(parent, DateListView):
            parent.handle_mouse_selection(self, event)
            event.stop()


class DateSelectionChanged(Message):
    def __init__(self, sender: "DateListView", infos: list[LogFileInfo]) -> None:
        super().__init__()
        self.sender = sender
        self.infos = infos


class DateListView(ListView):
    """ListView that supports multi-selection with ctrl/shift modifiers."""

    def __init__(self) -> None:
        super().__init__(id="date-list")
        self.selected_indices: set[int] = set()
        self.anchor_index: Optional[int] = None

    # Keyboard handling -----------------------------------------------------------------
    def on_key(self, event: events.Key) -> None:  # pragma: no cover - UI behaviour
        mods_raw = getattr(event, 'modifiers', set())
        if isinstance(mods_raw, (list, tuple, set, frozenset)):
            mods_iter = mods_raw
        elif mods_raw:
            mods_iter = (mods_raw,)
        else:
            mods_iter = ()
        mods: set[str] = set()
        for mod in mods_iter:
            text = str(mod).lower()
            if '.' in text:
                text = text.split('.')[-1]
            mods.add(text)
        key_value = event.key if hasattr(event, 'key') and event.key else ''
        key_lower = key_value.lower()
        shift = 'shift' in mods or bool(getattr(event, 'shift', False)) or 'shift+' in key_lower or key_lower.endswith('+shift')
        ctrl = bool(mods.intersection({'ctrl', 'control', 'primary', 'meta', 'command'})) or bool(getattr(event, 'ctrl', False)) or 'ctrl+' in key_lower or key_lower.endswith('+ctrl') or 'control+' in key_lower

        key = event.key
        index = self.index if self.index is not None else 0
        if key == 'space':
            if shift and self.anchor_index is not None:
                self._select_range(self.anchor_index, index, additive=ctrl)
            else:
                self._toggle_index(index, exclusive=not ctrl)
                self.anchor_index = index
            self._update_visual_state()
            self.post_message(DateSelectionChanged(self, self.selected_infos))
            event.stop()
            return
        if key == 'enter':
            selected_infos = self.selected_infos
            self.post_message(DateSelectionChanged(self, selected_infos))
            app = getattr(self, 'app', None)
            if selected_infos and hasattr(app, '_show_step_search') and hasattr(app, '_update_next_button_state'):
                try:
                    app.selected_logs = selected_infos  # type: ignore[attr-defined]
                    app._update_next_button_state()  # type: ignore[attr-defined]
                    app._show_step_search()  # type: ignore[attr-defined]
                except Exception:
                    pass
            event.stop()
            return

        movement_handled = False
        new_index = index
        if key in {'down', 'shift+down'}:
            self.action_cursor_down()
            new_index = self.index if self.index is not None else index
            movement_handled = True
        elif key in {'up', 'shift+up'}:
            self.action_cursor_up()
            new_index = self.index if self.index is not None else index
            movement_handled = True
        elif key in {'pageup', 'shift+pageup'}:
            self.action_cursor_page_up()
            new_index = self.index if self.index is not None else index
            movement_handled = True
        elif key in {'pagedown', 'shift+pagedown'}:
            self.action_cursor_page_down()
            new_index = self.index if self.index is not None else index
            movement_handled = True
        elif key in {'home', 'shift+home'}:
            self.action_cursor_home()
            new_index = self.index if self.index is not None else index
            movement_handled = True
        elif key in {'end', 'shift+end'}:
            self.action_cursor_end()
            new_index = self.index if self.index is not None else index
            movement_handled = True

        if movement_handled:
            if shift:
                if self.anchor_index is None:
                    self.anchor_index = index
                anchor = self.anchor_index if self.anchor_index is not None else index
                self._select_range(anchor, new_index, additive=ctrl)
            else:
                self.anchor_index = new_index
                if not ctrl:
                    self.selected_indices = {new_index}
            self._update_visual_state()
            self.post_message(DateSelectionChanged(self, self.selected_infos))
            event.stop()
            return
        # Remaining keys fall back to default behaviours

    # Mouse handling --------------------------------------------------------------------
    def handle_mouse_selection(self, item: DateListItem, event: events.MouseDown) -> None:
        children = list(self.children)
        try:
            index = children.index(item)
        except ValueError:  # pragma: no cover - defensive
            return

        mods_raw = getattr(event, 'modifiers', set())
        if isinstance(mods_raw, (list, tuple, set, frozenset)):
            mods_iter = mods_raw
        elif mods_raw:
            mods_iter = (mods_raw,)
        else:
            mods_iter = ()
        mods: set[str] = set()
        for mod in mods_iter:
            text = str(mod).lower()
            if '.' in text:
                text = text.split('.')[-1]
            mods.add(text)
        shift = 'shift' in mods or bool(getattr(event, 'shift', False))
        ctrl = bool(mods.intersection({'ctrl', 'control', 'primary', 'meta', 'command'})) or bool(getattr(event, 'ctrl', False))

        if shift:
            if self.anchor_index is None:
                self.anchor_index = index
            anchor = self.anchor_index if self.anchor_index is not None else index
            self._select_range(anchor, index, additive=ctrl)
        elif ctrl:
            self._toggle_index(index, exclusive=False)
            self.anchor_index = index
        else:
            self._toggle_index(index, exclusive=True)
            self.anchor_index = index

        self.index = index
        self._update_visual_state()
        self.post_message(DateSelectionChanged(self, self.selected_infos))

    # Helpers ---------------------------------------------------------------------------
    def populate(self, infos: list[LogFileInfo], default_indices: Iterable[int]) -> None:
        for child in list(self.children):
            child.remove()
        for info in infos:
            self.append(DateListItem(info))
        self.selected_indices = set(default_indices)
        if self.selected_indices:
            first = min(self.selected_indices)
            self.index = first
            self.anchor_index = first
        self._update_visual_state()

    def _toggle_index(self, index: int, *, exclusive: bool) -> None:
        if exclusive:
            self.selected_indices = {index}
        elif index in self.selected_indices:
            self.selected_indices.remove(index)
        else:
            self.selected_indices.add(index)

    def _select_range(self, start: int, end: int, *, additive: bool) -> None:
        if not additive:
            self.selected_indices.clear()
        if start <= end:
            rng = range(start, end + 1)
        else:
            rng = range(end, start + 1)
        self.selected_indices.update(rng)

    def _update_visual_state(self) -> None:
        for idx, child in enumerate(self.children):
            if isinstance(child, DateListItem):
                child.set_selected(idx in self.selected_indices)

    @property
    def selected_infos(self) -> list[LogFileInfo]:
        infos: list[LogFileInfo] = []
        for idx, child in enumerate(self.children):
            if isinstance(child, DateListItem) and idx in self.selected_indices:
                infos.append(child.info)
        return infos


class LogBrowser(App):
    """Wizard-style application for exploring SmarterMail logs."""

    CSS = """
    #wizard-body {
        margin: 1 2;
        height: 1fr;
    }

    .instruction {
        padding: 1 0;
    }

    .button-row Button {
        margin-right: 1;
    }

    .selected .label {
        text-style: bold;
    }

    #result-log {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "focus_search", "Focus search"),
        ("r", "refresh", "Refresh"),
    ]

    logs_dir: reactive[Path] = reactive(Path.cwd() / "sample_logs")
    staging_dir: reactive[Optional[Path]] = reactive(None)
    default_kind: reactive[Optional[str]] = reactive("smtpLog")

    def __init__(self, logs_dir: Path, staging_dir: Path | None = None, default_kind: str | None = None) -> None:
        super().__init__()
        self.logs_dir = logs_dir
        self.staging_dir = staging_dir
        self.default_kind = default_kind or "smtpLog"
        self._logs_by_kind: Dict[str, List[LogFileInfo]] = {}
        self.current_kind: Optional[str] = None
        self.selected_logs: list[LogFileInfo] = []
        self.step: WizardStep = WizardStep.KIND
        self.kind_list: KindListView | None = None
        self.date_list: DateListView | None = None
        self.search_input: Input | None = None
        self.output_log: OutputLog | None = None

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=False)
        self.wizard = Vertical(id="wizard-body")
        yield self.wizard
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_logs()
        self._show_step_kind()

    # Step rendering --------------------------------------------------------------------
    def _show_step_kind(self) -> None:
        self.step = WizardStep.KIND
        self._clear_wizard()
        self.wizard.mount(Static("Step 1: Choose a log type", classes="instruction"))
        self.kind_list = KindListView()
        self.wizard.mount(self.kind_list)
        button_row = Horizontal(Button("Next", id="next-kind"), Button("Quit", id="quit-kind"), classes="button-row")
        self.wizard.mount(button_row)

        if not self._logs_by_kind:
            self.kind_list.append(ListItem(Static("No logs discovered")))
        else:
            kinds_sorted = sorted(self._logs_by_kind)
            for kind in kinds_sorted:
                item = KindListItem(kind)
                item.set_selected(False)
                self.kind_list.append(item)
            preferred = self.default_kind if self.default_kind in self._logs_by_kind else None
            if preferred is None and "smtpLog" in self._logs_by_kind:
                preferred = "smtpLog"
            if preferred is None:
                preferred = kinds_sorted[0]
            self.current_kind = preferred
            if hasattr(self.kind_list, "index"):
                if preferred in kinds_sorted:
                    idx = kinds_sorted.index(preferred)
                    self.kind_list.index = idx
            for child in self.kind_list.children:
                if isinstance(child, KindListItem):
                    child.set_selected(child.kind == preferred)
            self.kind_list.focus()
        self._update_next_button_state()

    def _show_step_date(self) -> None:
        self.step = WizardStep.DATE
        self._clear_wizard()
        self.wizard.mount(Static("Step 2: Select one or more log dates", classes="instruction"))
        instructions = Static(
            "Use Arrow keys or the mouse to choose dates. Space toggles selection.\n"
            "Use Shift+Arrow/Click for range selection and Ctrl+Click to add/remove individual dates."
        )
        self.wizard.mount(instructions)

        self.date_list = DateListView()
        self.wizard.mount(self.date_list)

        button_row = Horizontal(
            Button("Back", id="back-date"),
            Button("Next", id="next-date"),
            classes="button-row",
        )
        self.wizard.mount(button_row)

        infos = self._logs_by_kind.get(self.current_kind or "", [])
        default_indices = self._default_date_indices(infos)
        self.selected_logs = [infos[i] for i in default_indices] if infos else []
        self.date_list.populate(infos, default_indices)
        self._update_next_button_state()
        self.date_list.focus()

    def _show_step_search(self) -> None:
        self.step = WizardStep.SEARCH
        self._clear_wizard()
        summary = Static(
            f"Step 3: Enter a search term for {self.current_kind} across {len(self.selected_logs)} log(s)",
            classes="instruction",
        )
        self.wizard.mount(summary)
        self.search_input = Input(placeholder="Enter search term", id="search-term")
        self.wizard.mount(self.search_input)
        button_row = Horizontal(
            Button("Back", id="back-search"),
            Button("Search", id="do-search"),
            classes="button-row",
        )
        self.wizard.mount(button_row)
        self.search_input.focus()

    def _show_step_results(self, rendered: str | None = None) -> None:
        self.step = WizardStep.RESULTS
        self._clear_wizard()
        self.wizard.mount(Static("Search results", classes="instruction"))
        self.output_log = OutputLog(id="result-log")
        self.wizard.mount(self.output_log)
        button_row = Horizontal(
            Button("Back", id="back-results"),
            Button("New Search", id="new-search"),
            classes="button-row",
        )
        self.wizard.mount(button_row)
        if rendered:
            self.output_log.write(rendered)

    # Step helpers ---------------------------------------------------------------------
    def _default_date_indices(self, infos: list[LogFileInfo]) -> list[int]:
        if not infos:
            return []
        today = date.today()
        for idx, info in enumerate(infos):
            if info.stamp == today:
                return [idx]
        return [0]

    def _update_next_button_state(self) -> None:
        try:
            next_button = self.wizard.query_one('Button#next-date')
        except Exception:
            next_button = None
        if isinstance(next_button, Button) and self.step == WizardStep.DATE:
            next_button.disabled = not bool(self.selected_logs)
        try:
            kind_next = self.wizard.query_one('Button#next-kind')
        except Exception:
            kind_next = None
        if isinstance(kind_next, Button) and self.step == WizardStep.KIND:
            kind_next.disabled = not bool(self._logs_by_kind)

    # Events ----------------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        button_id = event.button.id
        if button_id == "quit-kind":
            self.exit()
        elif button_id == "next-kind":
            if self.current_kind:
                self._show_step_date()
        elif button_id == "back-date":
            self._show_step_kind()
        elif button_id == "next-date":
            if self.selected_logs:
                self._show_step_search()
        elif button_id == "back-search":
            self._show_step_date()
        elif button_id == "do-search":
            self._perform_search()
        elif button_id == "back-results":
            self._show_step_search()
        elif button_id == "new-search":
            self._show_step_kind()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:  # type: ignore[override]
        if self.step == WizardStep.KIND and isinstance(event.item, KindListItem):
            self.current_kind = event.item.kind
            if self.kind_list is not None:
                for child in self.kind_list.children:
                    if isinstance(child, KindListItem):
                        child.set_selected(child is event.item)
        elif self.step == WizardStep.DATE and isinstance(event.item, DateListItem):
            if self.date_list is not None and self.date_list.index is not None:
                self.date_list.anchor_index = self.date_list.index

    def on_list_view_selected(self, event: ListView.Selected) -> None:  # type: ignore[override]
        if self.step == WizardStep.KIND and isinstance(event.item, KindListItem):
            self.current_kind = event.item.kind
            self._show_step_date()
        elif self.step == WizardStep.DATE and isinstance(event.item, DateListItem):
            if self.date_list is not None:
                self.selected_logs = self.date_list.selected_infos or [event.item.info]
            self._update_next_button_state()

    def on_date_selection_changed(self, message: DateSelectionChanged) -> None:
        if self.step != WizardStep.DATE:
            return
        self.selected_logs = message.infos
        self._update_next_button_state()

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        if self.step == WizardStep.SEARCH and event.input is self.search_input:
            self._perform_search()

    def action_focus_search(self) -> None:
        if self.step == WizardStep.SEARCH and self.search_input is not None:
            self.search_input.focus()

    def action_refresh(self) -> None:
        self._refresh_logs()
        if self.step == WizardStep.KIND:
            self._show_step_kind()
        elif self.step == WizardStep.DATE:
            self._show_step_date()
        elif self.step == WizardStep.SEARCH:
            self._show_step_search()
        else:
            self._show_step_kind()

    def _clear_wizard(self) -> None:
        if hasattr(self, 'wizard'):
            for child in list(self.wizard.children):
                child.remove()

    # Core behaviour -------------------------------------------------------------------
    def _refresh_logs(self) -> None:
        kinds: Dict[str, List[LogFileInfo]] = {}
        if self.logs_dir.exists():
            for path in self.logs_dir.iterdir():
                info = parse_log_filename(path)
                if not info.kind:
                    continue
                kinds.setdefault(info.kind, []).append(info)
        for kind, infos in list(kinds.items()):
            kinds[kind] = summarize_logs(self.logs_dir, kind)
        self._logs_by_kind = kinds
        if self.current_kind not in self._logs_by_kind:
            self.current_kind = None

    def _perform_search(self) -> None:
        if not self.selected_logs:
            self._notify("Select at least one log date before searching.")
            return
        term = (self.search_input.value if self.search_input else "").strip()
        if not term:
            self._notify("Enter a search term.")
            return

        rendered_lines: list[str] = []
        for info in self.selected_logs:
            try:
                staged = stage_log(info.path, staging_dir=self.staging_dir or DEFAULT_STAGING_ROOT)
            except Exception as exc:  # pragma: no cover - filesystem feedback
                self._notify(f"Failed to stage {info.path.name}: {exc}")
                return
            result = search_smtp_conversations(staged.staged_path, term)
            rendered_lines.append(f"=== {info.path.name} ===")
            rendered_lines.append(
                f"Search term '{result.term}' -> {result.total_conversations} conversation(s)"
            )
            if not result.conversations and not result.orphan_matches:
                rendered_lines.append("No matches found.")
            for conversation in result.conversations:
                rendered_lines.append("")
                rendered_lines.append(
                    f"[{conversation.message_id}] first seen on line {conversation.first_line_number}"
                )
                rendered_lines.extend(conversation.lines)
            if result.orphan_matches:
                rendered_lines.append("")
                rendered_lines.append("Lines without message identifiers that matched:")
                for line_number, line in result.orphan_matches:
                    rendered_lines.append(f"{line_number}: {line}")
            rendered_lines.append("")

        self._show_step_results()
        if self.output_log is not None:
            if hasattr(self.output_log, 'clear'):
                self.output_log.clear()  # type: ignore[call-arg]
            else:  # pragma: no cover - safety for unknown widgets
                self.output_log.update('')
            for line in rendered_lines:
                self.output_log.write(line)
            if hasattr(self.output_log, 'scroll_end'):
                try:
                    self.output_log.scroll_end()
                except Exception:
                    pass
        self._notify("Search complete.")

    def _notify(self, message: str) -> None:
        try:
            status = self.wizard.query_one('Static#status')
        except Exception:
            status = None
        if isinstance(status, Static):
            status.update(message)
        else:
            status = Static(message, id='status')
            self.wizard.mount(status)


def list_log_files(logs_dir: Path) -> list[Path]:
    """Return a sorted list of non-hidden files in ``logs_dir``.

    Retained for compatibility with legacy tests.
    """

    if not logs_dir.exists() or not logs_dir.is_dir():
        return []
    return sorted(p for p in logs_dir.iterdir() if p.is_file() and not p.name.startswith("."))


def run(logs_dir: Path, staging_dir: Path | None = None, default_kind: str | None = None) -> int:
    """Run the Textual app. Returns an exit code."""

    app = LogBrowser(logs_dir=logs_dir, staging_dir=staging_dir, default_kind=default_kind)
    app.run()
    return 0

