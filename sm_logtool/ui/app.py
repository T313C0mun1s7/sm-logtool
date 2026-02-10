"""Wizard-style Textual UI for sm-logtool."""

from __future__ import annotations

import inspect
from datetime import date
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    Static,
)

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
        from textual.widgets import Log  # type: ignore[attr-defined]
        _BaseLog = Log
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

    def set_active(self, active: bool) -> None:
        if active:
            self.add_class("active")
        else:
            self.remove_class("active")


class KindListView(ListView):
    """Simple list view for selecting a single log kind."""

    def set_selection(self, kind: str) -> None:
        for child in self.children:
            if isinstance(child, KindListItem):
                child.set_selected(child.kind == kind)
                child.set_active(child.kind == kind)


class DateListItem(ListItem):
    def __init__(
        self,
        info: LogFileInfo,
    ) -> None:
        label = (
            info.stamp.strftime("%Y.%m.%d")
            if info.stamp
            else info.path.name
        )
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

    def set_active(self, active: bool) -> None:
        if active:
            self.add_class("active")
        else:
            self.remove_class("active")

    def on_mouse_down(
        self,
        event: events.MouseDown,
    ) -> None:  # pragma: no cover - UI behaviour
        parent = self.parent
        if isinstance(parent, DateListView):
            parent.handle_mouse_selection(self, event)
            event.stop()


class DateSelectionChanged(Message):
    def __init__(
        self,
        sender: "DateListView",
        infos: list[LogFileInfo],
    ) -> None:
        super().__init__()
        self.sender = sender
        self.infos = infos


class DateListView(ListView):
    """List view that supports persistent multi-selection via toggles."""

    def __init__(self) -> None:
        super().__init__(id="date-list")
        self.selected_indices: set[int] = set()
        self.anchor_index: Optional[int] = None

    # Keyboard handling --------------------------------------------------
    def on_key(
        self,
        event: events.Key,
    ) -> None:  # pragma: no cover - UI behaviour
        key = event.key
        index = self.index if self.index is not None else 0

        if key == "space":
            self._toggle_current(index)
            self._post_selection()
            event.stop()
            return

        if key == "enter":
            self._apply_enter(index)
            event.stop()
            return

        if self._handle_navigation_key(key, index):
            event.stop()

    def _toggle_current(self, index: int) -> None:
        self._toggle_index(index)
        self.anchor_index = index
        self._update_visual_state()

    def _apply_enter(self, index: int) -> None:
        if not self.selected_indices:
            self.selected_indices = {index}
            self._update_visual_state()

        self._post_selection()
        self._trigger_search_transition()

    def _handle_navigation_key(self, key: str, fallback_index: int) -> bool:
        action_names = {
            "down": "action_cursor_down",
            "shift+down": "action_cursor_down",
            "up": "action_cursor_up",
            "shift+up": "action_cursor_up",
            "pageup": "action_cursor_page_up",
            "shift+pageup": "action_cursor_page_up",
            "pagedown": "action_cursor_page_down",
            "shift+pagedown": "action_cursor_page_down",
            "home": "action_cursor_home",
            "shift+home": "action_cursor_home",
            "end": "action_cursor_end",
            "shift+end": "action_cursor_end",
        }
        action_name = action_names.get(key)
        if action_name is None:
            return False

        action = getattr(self, action_name, None)
        if action is None:
            return False

        action()
        new_index = self.index if self.index is not None else fallback_index
        self.anchor_index = new_index
        self._update_visual_state()
        self._post_selection()
        return True

    def _post_selection(self) -> None:
        self.post_message(DateSelectionChanged(self, self.selected_infos))

    def _trigger_search_transition(self) -> None:
        infos = self.selected_infos
        if not infos:
            return

        app = getattr(self, "app", None)
        if app is None or not hasattr(app, "_show_step_search"):
            return

        try:
            app.selected_logs = infos  # type: ignore[attr-defined]
            if hasattr(app, "_update_next_button_state"):
                app._update_next_button_state()  # type: ignore[attr-defined]
            app._show_step_search()  # type: ignore[attr-defined]
        except Exception:
            pass

    # Mouse handling -----------------------------------------------------
    def handle_mouse_selection(
        self,
        item: DateListItem,
        event: events.MouseDown,
    ) -> None:
        children = list(self.children)
        try:
            index = children.index(item)
        except ValueError:  # pragma: no cover - defensive
            return

        self._toggle_current(index)
        self.index = index
        self._post_selection()

    # Helpers ------------------------------------------------------------
    def populate(
        self,
        infos: list[LogFileInfo],
        default_indices: Iterable[int],
    ) -> None:
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

    def _toggle_index(self, index: int) -> None:
        if index in self.selected_indices:
            self.selected_indices.remove(index)
        else:
            self.selected_indices.add(index)

    def _update_visual_state(self) -> None:
        current_index = self.index if self.index is not None else -1
        for idx, child in enumerate(self.children):
            if isinstance(child, DateListItem):
                child.set_selected(idx in self.selected_indices)
                child.set_active(idx == current_index)

    @property
    def selected_infos(self) -> list[LogFileInfo]:
        infos: list[LogFileInfo] = []
        for idx, child in enumerate(self.children):
            if not isinstance(child, DateListItem):
                continue
            if idx not in self.selected_indices:
                continue
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
        background: #444444;
        color: yellow;
    }

    .active .label {
        background: #005f87;
        color: white;
    }

    .selected.active .label {
        background: #1b98d3;
        color: black;
    }

    .cursor--true .label {
        background: #005f87;
        color: white;
    }

    .selected.cursor--true .label {
        background: #1b98d3;
        color: black;
    }

    #result-log {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "reset", "Reset Search", show=True),
        Binding("/", "focus_search", "Focus search", show=True),
    ]

    logs_dir: reactive[Path] = reactive(Path.cwd() / "sample_logs")
    staging_dir: reactive[Optional[Path]] = reactive(None)
    default_kind: reactive[Optional[str]] = reactive("smtpLog")

    def __init__(
        self,
        logs_dir: Path,
        staging_dir: Path | None = None,
        default_kind: str | None = None,
    ) -> None:
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
        self.footer: Footer | None = None

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=False)
        self.wizard = Vertical(id="wizard-body")
        yield self.wizard
        self.footer = Footer()
        yield self.footer

    def on_mount(self) -> None:
        self._refresh_logs()
        self._show_step_kind()

    # Step rendering -----------------------------------------------------
    def _show_step_kind(self) -> None:
        self.step = WizardStep.KIND
        self._clear_wizard()
        self.wizard.mount(
            Static("Step 1: Choose a log type", classes="instruction")
        )
        button_row = Horizontal(
            Button("Next", id="next-kind"),
            Button("Quit", id="quit-kind"),
            classes="button-row",
        )

        if not self._logs_by_kind:
            self.kind_list = KindListView(
                ListItem(Static("No logs discovered"))
            )
            self.current_kind = None
            self.wizard.mount(self.kind_list)
            self.kind_list.focus()
        else:
            kinds_sorted = sorted(self._logs_by_kind)
            preferred = self._initial_kind_choice(kinds_sorted)
            items: list[ListItem] = []
            preferred_index = 0
            for idx, kind in enumerate(kinds_sorted):
                item = KindListItem(kind)
                items.append(item)
                if kind == preferred:
                    preferred_index = idx
            initial_index = preferred_index + 1 if preferred is not None else 0
            self.kind_list = KindListView(
                *items,
                initial_index=initial_index,
            )
            self.current_kind = preferred
            self.wizard.mount(self.kind_list)
            if preferred:
                self.call_after_refresh(
                    lambda: self._apply_kind_selection(preferred)
                )
            else:
                self.kind_list.focus()

        self.wizard.mount(button_row)
        self._update_next_button_state()
        self._refresh_footer_bindings()

    def _show_step_date(self) -> None:
        self.step = WizardStep.DATE
        self._clear_wizard()
        step_text = "Step 2: Select one or more log dates"
        self.wizard.mount(Static(step_text, classes="instruction"))
        instructions = Static(
            "Use arrow keys or the mouse to highlight a date. Press Space or "
            "click to toggle it.\nPress Enter (or Next) when you are ready "
            "to continue."
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
        if infos:
            self.selected_logs = [infos[i] for i in default_indices]
        else:
            self.selected_logs = []
        self.date_list.populate(infos, default_indices)
        self._update_next_button_state()
        self.date_list.focus()
        self._refresh_footer_bindings()

    def _show_step_search(self) -> None:
        self.step = WizardStep.SEARCH
        self._clear_wizard()
        summary_text = (
            "Step 3: Enter a search term for "
            f"{self.current_kind} across {len(self.selected_logs)} log(s)"
        )
        summary = Static(summary_text, classes="instruction")
        self.wizard.mount(summary)
        self.search_input = Input(
            placeholder="Enter search term",
            id="search-term",
        )
        self.wizard.mount(self.search_input)
        button_row = Horizontal(
            Button("Back", id="back-search"),
            Button("Search", id="do-search"),
            classes="button-row",
        )
        self.wizard.mount(button_row)
        self.search_input.focus()
        self._refresh_footer_bindings()

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
            self._write_output_lines(rendered.splitlines())
        self._refresh_footer_bindings()

    # Step helpers -------------------------------------------------------
    def _initial_kind_choice(self, kinds_sorted: list[str]) -> str | None:
        if self.default_kind in self._logs_by_kind:
            return self.default_kind
        if "smtpLog" in self._logs_by_kind:
            return "smtpLog"
        return kinds_sorted[0] if kinds_sorted else None

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

    # Events -------------------------------------------------------------
    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:  # type: ignore[override]
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

        self._refresh_footer_bindings()

    def on_list_view_highlighted(
        self,
        event: ListView.Highlighted,
    ) -> None:  # type: ignore[override]
        if self.step == WizardStep.KIND:
            self._highlight_kind_item(event.item)
            return
        if self.step == WizardStep.DATE:
            self._highlight_date_item(event.item)

    def on_list_view_selected(
        self,
        event: ListView.Selected,
    ) -> None:  # type: ignore[override]
        if self.step == WizardStep.KIND:
            self._select_kind_item(event.item)
            return
        if self.step == WizardStep.DATE:
            self._select_date_item(event.item)

    def on_date_selection_changed(self, message: DateSelectionChanged) -> None:
        if self.step != WizardStep.DATE:
            return
        self.selected_logs = message.infos
        self._update_next_button_state()

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:  # type: ignore[override]
        if self.step == WizardStep.SEARCH and event.input is self.search_input:
            self._perform_search()

    def _highlight_kind_item(self, item: ListItem) -> None:
        if not isinstance(item, KindListItem):
            return
        self.current_kind = item.kind
        if isinstance(self.kind_list, KindListView):
            self.kind_list.set_selection(item.kind)

    def _highlight_date_item(self, item: ListItem) -> None:
        if not isinstance(item, DateListItem):
            return
        if self.date_list is None or self.date_list.index is None:
            return
        self.date_list.anchor_index = self.date_list.index
        self.date_list._update_visual_state()

    def _select_kind_item(self, item: ListItem) -> None:
        if not isinstance(item, KindListItem):
            return
        self.current_kind = item.kind
        self._show_step_date()

    def _select_date_item(self, item: ListItem) -> None:
        if self.date_list is None or not isinstance(item, DateListItem):
            return
        index = self._child_index(self.date_list, item)
        if index is None:
            return
        self.date_list._toggle_index(index)
        self.date_list.anchor_index = index
        self.date_list._update_visual_state()
        self.selected_logs = self.date_list.selected_infos
        self.post_message(
            DateSelectionChanged(self.date_list, self.date_list.selected_infos)
        )
        self._update_next_button_state()

    @staticmethod
    def _child_index(container: ListView, item: ListItem) -> int | None:
        children = list(container.children)
        try:
            return children.index(item)
        except ValueError:
            index = container.index
            return index if index is not None else None

    def action_focus_search(self) -> None:
        if self.step == WizardStep.SEARCH and self.search_input is not None:
            self.search_input.focus()

    def action_quit(self) -> None:
        self.exit()

    def action_reset(self) -> None:
        self._refresh_logs()
        self.selected_logs = []
        self.current_kind = None
        self._show_step_kind()
        self._refresh_footer_bindings()

    def _refresh_footer_bindings(self) -> None:
        if self.footer is not None:
            # Reset footer legend so shortcuts display on every step.
            self.footer._key_text = None  # type: ignore[attr-defined]
            self.footer.refresh()

    def _apply_kind_selection(self, kind: str) -> None:
        if not self.kind_list:
            return
        children = list(self.kind_list.children)
        for idx, child in enumerate(children):
            if isinstance(child, KindListItem) and child.kind == kind:
                try:
                    self.kind_list.index = idx
                except Exception:
                    pass
                if isinstance(self.kind_list, KindListView):
                    self.kind_list.set_selection(kind)
                else:
                    child.set_selected(True)
                self.kind_list.focus()
                break

    def _clear_wizard(self) -> None:
        if hasattr(self, 'wizard'):
            for child in list(self.wizard.children):
                child.remove()

    # Core behaviour -----------------------------------------------------
    def _refresh_logs(self) -> None:
        kinds: Dict[str, List[LogFileInfo]] = {}
        if self.logs_dir.exists():
            for path in self.logs_dir.iterdir():
                if not path.is_file():
                    continue
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
                staged = stage_log(
                    info.path,
                    staging_dir=self.staging_dir or DEFAULT_STAGING_ROOT,
                )
            except Exception as exc:  # pragma: no cover - filesystem feedback
                self._notify(f"Failed to stage {info.path.name}: {exc}")
                return
            result = search_smtp_conversations(staged.staged_path, term)
            rendered_lines.append(f"=== {info.path.name} ===")
            summary = (
                f"Search term '{result.term}' -> "
                f"{result.total_conversations} conversation(s)"
            )
            rendered_lines.append(summary)
            if not result.conversations and not result.orphan_matches:
                rendered_lines.append("No matches found.")
            for conversation in result.conversations:
                rendered_lines.append("")
                header = (
                    f"[{conversation.message_id}] first seen on line "
                    f"{conversation.first_line_number}"
                )
                rendered_lines.append(header)
                rendered_lines.extend(conversation.lines)
            if result.orphan_matches:
                rendered_lines.append("")
                rendered_lines.append(
                    "Lines without message identifiers that matched:"
                )
                for line_number, line in result.orphan_matches:
                    rendered_lines.append(f"{line_number}: {line}")
            rendered_lines.append("")

        self._show_step_results()
        self._write_output_lines(rendered_lines)
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

    def _write_output_lines(self, lines: list[str]) -> None:
        if self.output_log is None:
            return
        if hasattr(self.output_log, 'clear'):
            self.output_log.clear()  # type: ignore[call-arg]
        else:  # pragma: no cover - safety for unknown widgets
            self.output_log.update('')
        if hasattr(self.output_log, 'write'):
            for line in lines:
                try:
                    self.output_log.write(f"{line}\n")
                except Exception:
                    self.output_log.write(f"{str(line)}\n")
        else:
            self.output_log.update("\n".join(lines))
        if hasattr(self.output_log, 'scroll_end'):
            try:
                self.output_log.scroll_end()
            except Exception:
                pass


def list_log_files(logs_dir: Path) -> list[Path]:
    """Return a sorted list of non-hidden files in ``logs_dir``.

    Retained for compatibility with legacy tests.
    """

    if not logs_dir.exists() or not logs_dir.is_dir():
        return []
    return sorted(
        p
        for p in logs_dir.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )


def run(
    logs_dir: Path,
    staging_dir: Path | None = None,
    default_kind: str | None = None,
) -> int:
    """Run the Textual app. Returns an exit code."""

    app = LogBrowser(
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind=default_kind,
    )
    app.run()
    return 0
