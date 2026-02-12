"""Wizard-style Textual UI for sm-logtool."""

from __future__ import annotations

import inspect
from collections import defaultdict
from datetime import date, datetime
from enum import Enum, auto
from itertools import groupby
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.geometry import Offset
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.selection import Selection
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    Static,
    TextArea,
)
from textual.widgets._footer import FooterKey, FooterLabel, KeyGroup
from textual._text_area_theme import TextAreaTheme
from rich.text import Text

from ..highlighting import TOKEN_STYLES
from ..log_kinds import KIND_SMTP, normalize_kind
from ..logfiles import (
    LogFileInfo,
    parse_log_filename,
    summarize_logs,
)
from ..result_rendering import render_search_results
from ..search_modes import (
    MODE_LITERAL,
    MODE_WILDCARD,
    SEARCH_MODE_DESCRIPTIONS,
    SEARCH_MODE_LABELS,
)
from ..search import get_search_function
from ..syntax import spans_for_line
from ..staging import stage_log

try:  # Prefer selection-capable logs when available.
    from textual.widgets import TextLog as _BaseLog
except ImportError:  # pragma: no cover - textual>=6 renames widgets
    try:
        from textual.widgets import Log  # type: ignore[attr-defined]
        _BaseLog = Log
    except ImportError:  # pragma: no cover - older Textual
        try:
            from textual.widgets import (  # type: ignore[attr-defined]
                RichLog as _BaseLog,
            )
        except ImportError:  # pragma: no cover - final fallback
            _BaseLog = None


if _BaseLog is not None:

    class OutputLog(_BaseLog):
        """Text log widget that adapts to Textual version differences."""

        can_focus = True

        def __init__(
            self,
            *,
            id: str | None = None,
            classes: str | None = None,
        ) -> None:
            kwargs = {}
            init_sig = inspect.signature(_BaseLog.__init__)
            if "highlight" in init_sig.parameters:
                kwargs["highlight"] = False
            self._prefer_markup = False
            if "markup" in init_sig.parameters:
                kwargs["markup"] = True
                self._prefer_markup = True
            if "wrap" in init_sig.parameters:
                kwargs["wrap"] = True
            if "id" in init_sig.parameters:
                kwargs["id"] = id
            if "classes" in init_sig.parameters:
                kwargs["classes"] = classes
            super().__init__(**kwargs)  # type: ignore[arg-type]
            self._selection_anchor: Offset | None = None
            self._selection_cursor: Offset | None = None
            self._cursor_only = False
            self._mouse_selecting = False
            self._mouse_dragged = False
            self._use_custom_selection = not callable(
                getattr(_BaseLog, "on_mouse_down", None),
            )
            if getattr(_BaseLog, "__name__", "") == "RichLog":
                self._use_custom_selection = True
            self._plain_lines: list[str] = []
            if hasattr(self, "markup"):
                try:
                    self.markup = True  # type: ignore[attr-defined]
                    self._prefer_markup = True
                except Exception:
                    self._prefer_markup = bool(
                        getattr(self, "markup", False),
                    )

        def clear_selection(self) -> None:
            try:
                screen = self.screen
            except Exception:
                return
            selections = dict(screen.selections)
            if self in selections:
                del selections[self]
                screen.selections = selections
            self._selection_anchor = None
            self._selection_cursor = None
            self._cursor_only = False

        def clear(self) -> None:  # type: ignore[override]
            try:
                super().clear()  # type: ignore[misc]
            except Exception:
                pass
            self._plain_lines = []

        def write_line(self, line: str | Text) -> None:
            if isinstance(line, Text):
                plain = line.plain
            else:
                plain = str(line)
            if plain.endswith("\n"):
                plain = plain[:-1]
            self._plain_lines.append(plain)

            payload: str | Text = line
            if isinstance(line, Text):
                if self._prefer_markup:
                    to_markup = getattr(line, "to_markup", None)
                    if callable(to_markup):
                        payload = to_markup()
                    else:
                        payload = plain
                else:
                    payload = plain

            needs_newline = getattr(_BaseLog, "__name__", "") in {
                "TextLog",
                "Log",
            }
            if needs_newline and isinstance(payload, str):
                if not payload.endswith("\n"):
                    payload = f"{payload}\n"
            self.write(payload)  # type: ignore[arg-type]

        def cursor_only_selection(self) -> bool:
            return self._cursor_only

        def _set_selection(
            self,
            start: Offset,
            end: Offset,
        ) -> None:
            try:
                screen = self.screen
            except Exception:
                return
            selections = dict(screen.selections)
            selections[self] = Selection.from_offsets(start, end)
            screen.selections = selections

        def _line_text(self, line: object) -> str:
            plain = getattr(line, "plain", None)
            if isinstance(plain, str):
                return plain
            return str(line)

        def _get_lines(self) -> list[object]:
            lines = getattr(self, "lines", None)
            if isinstance(lines, list):
                return lines
            return self._plain_lines

        def _line_count(self) -> int:
            count = getattr(self, "line_count", None)
            if isinstance(count, int):
                return count
            return len(self._plain_lines)

        def _clamp_offset(self, offset: Offset) -> Offset:
            if self._line_count() <= 0:
                return Offset(0, 0)
            max_y = max(self._line_count() - 1, 0)
            y = min(max(offset.y, 0), max_y)
            lines = self._get_lines()
            line = lines[y] if lines else ""
            max_x = len(line)
            x = min(max(offset.x, 0), max_x)
            return Offset(x, y)

        def _offset_from_event(
            self,
            event: events.MouseDown | events.MouseMove | events.MouseUp,
        ) -> Offset:
            scroll_x, scroll_y = self.scroll_offset
            return self._clamp_offset(
                Offset(scroll_x + event.x, scroll_y + event.y),
            )

        def _order_offsets(
            self,
            start: Offset,
            end: Offset,
        ) -> tuple[Offset, Offset]:
            if (start.y, start.x) <= (end.y, end.x):
                return start, end
            return end, start

        def get_selection_text(self) -> str | None:
            if self._line_count() <= 0:
                return None
            if self._selection_anchor is None:
                return None
            if self._selection_cursor is None:
                return None
            start = self._clamp_offset(self._selection_anchor)
            end = self._clamp_offset(self._selection_cursor)
            start, end = self._order_offsets(start, end)
            if (start.y, start.x) == (end.y, end.x):
                return None
            lines = self._get_lines()
            if not lines:
                return None
            if start.y == end.y:
                line = self._line_text(lines[start.y])
                return line[start.x:end.x] or None
            parts: list[str] = []
            first_line = self._line_text(lines[start.y])
            parts.append(first_line[start.x:])
            for line_idx in range(start.y + 1, end.y):
                parts.append(self._line_text(lines[line_idx]))
            last_line = self._line_text(lines[end.y])
            parts.append(last_line[:end.x])
            text = "\n".join(parts)
            return text or None

        def get_all_text(self) -> str | None:
            lines = self._get_lines()
            if not lines:
                return None
            plain_lines = [self._line_text(line) for line in lines]
            text = "\n".join(plain_lines).rstrip("\n")
            return text or None

        def _cursor_span(self) -> tuple[Offset, Offset]:
            cursor = self._selection_cursor
            if cursor is None:
                cursor = Offset(0, 0)
                self._selection_cursor = cursor
            lines = self._get_lines()
            line = lines[cursor.y] if lines else ""
            line_len = len(line)
            if line_len == 0:
                start = cursor
                end = cursor
            elif cursor.x >= line_len:
                start = Offset(max(line_len - 1, 0), cursor.y)
                end = Offset(line_len, cursor.y)
            else:
                start = cursor
                end = Offset(cursor.x + 1, cursor.y)
            return start, end

        def _move_cursor(
            self,
            *,
            dx: int = 0,
            dy: int = 0,
            extend: bool = False,
        ) -> None:
            scroll_x, scroll_y = self.scroll_offset
            if self._selection_cursor is None:
                self._selection_cursor = Offset(scroll_x, scroll_y)
            if extend and self._selection_anchor is None:
                self._selection_anchor = self._selection_cursor
            cursor = self._selection_cursor
            max_y = max(self._line_count() - 1, 0)
            new_y = min(max(cursor.y + dy, 0), max_y)
            lines = self._get_lines()
            line = lines[new_y] if lines else ""
            max_x = len(line)
            new_x = min(max(cursor.x + dx, 0), max_x)
            self._selection_cursor = Offset(new_x, new_y)

            if extend:
                self._cursor_only = False
                assert self._selection_anchor is not None
                self._set_selection(
                    self._selection_anchor,
                    self._selection_cursor,
                )
            else:
                self._cursor_only = True
                self._selection_anchor = self._selection_cursor
                start, end = self._cursor_span()
                self._set_selection(start, end)

            view_height = max(self.size.height, 1)
            view_width = max(self.size.width, 1)
            target_y: int | None = None
            target_x: int | None = None
            if new_y < scroll_y:
                target_y = new_y
            elif new_y >= scroll_y + view_height:
                target_y = new_y - view_height + 1
            if new_x < scroll_x:
                target_x = new_x
            elif new_x >= scroll_x + view_width:
                target_x = new_x - view_width + 1
            if target_x is not None or target_y is not None:
                self.scroll_to(
                    x=target_x,
                    y=target_y,
                    animate=False,
                    immediate=True,
                )

        def show_cursor(self) -> None:
            if self._line_count() <= 0:
                return
            try:
                _ = self.screen
            except Exception:
                return
            self._move_cursor(dx=0, dy=0, extend=False)

        def on_mouse_down(
            self,
            event: events.MouseDown,
        ) -> None:  # pragma: no cover - UI behaviour
            try:
                self.focus()
            except Exception:
                pass
            if getattr(event, "button", None) == 3:
                app = getattr(self, "app", None)
                show_menu = getattr(app, "_show_context_menu", None)
                if show_menu is not None:
                    show_menu(event.screen_x, event.screen_y)
                event.stop()
                return
            offset = self._offset_from_event(event)
            self._selection_cursor = offset
            self._selection_anchor = offset
            self._cursor_only = True
            self._mouse_selecting = True
            self._mouse_dragged = False
            if self._use_custom_selection:
                start, end = self._cursor_span()
                self._set_selection(start, end)
            capture = getattr(self, "capture_mouse", None)
            if capture is not None:
                capture()
            handler = getattr(super(), "on_mouse_down", None)
            if handler is not None:
                handler(event)

        def on_mouse_move(
            self,
            event: events.MouseMove,
        ) -> None:  # pragma: no cover - UI behaviour
            if not self._mouse_selecting:
                handler = getattr(super(), "on_mouse_move", None)
                if handler is not None:
                    handler(event)
                return

            offset = self._offset_from_event(event)
            self._selection_cursor = offset
            if self._selection_anchor is None:
                self._selection_anchor = offset
            if offset != self._selection_anchor:
                self._mouse_dragged = True
            if self._mouse_dragged:
                self._cursor_only = False
                if self._use_custom_selection:
                    self._set_selection(
                        self._selection_anchor,
                        self._selection_cursor,
                    )
            handler = getattr(super(), "on_mouse_move", None)
            if handler is not None:
                handler(event)

        def on_mouse_up(
            self,
            event: events.MouseUp,
        ) -> None:  # pragma: no cover - UI behaviour
            if not self._mouse_selecting:
                handler = getattr(super(), "on_mouse_up", None)
                if handler is not None:
                    handler(event)
                return

            offset = self._offset_from_event(event)
            self._selection_cursor = offset
            if self._selection_anchor is None:
                self._selection_anchor = offset
            if offset != self._selection_anchor:
                self._mouse_dragged = True
            if self._mouse_dragged:
                self._cursor_only = False
                if self._use_custom_selection:
                    self._set_selection(
                        self._selection_anchor,
                        self._selection_cursor,
                    )
            self._mouse_selecting = False
            release = getattr(self, "release_mouse", None)
            if release is not None:
                release()
            handler = getattr(super(), "on_mouse_up", None)
            if handler is not None:
                handler(event)

        def on_key(
            self,
            event: events.Key,
        ) -> None:  # pragma: no cover - UI behaviour
            aliases = set(event.aliases)
            if not aliases.intersection(
                {
                    "shift+up",
                    "shift+down",
                    "shift+left",
                    "shift+right",
                }
            ):
                if aliases.intersection({"up", "down", "left", "right"}):
                    dx, dy = 0, 0
                    if "up" in aliases:
                        dy = -1
                    elif "down" in aliases:
                        dy = 1
                    elif "left" in aliases:
                        dx = -1
                    elif "right" in aliases:
                        dx = 1
                    self._move_cursor(dx=dx, dy=dy, extend=False)
                    event.stop()
                return

            dx, dy = 0, 0
            if "shift+up" in aliases:
                dy = -1
            elif "shift+down" in aliases:
                dy = 1
            elif "shift+left" in aliases:
                dx = -1
            elif "shift+right" in aliases:
                dx = 1
            self._move_cursor(dx=dx, dy=dy, extend=True)
            event.stop()
            return

else:

    class OutputLog(Static):  # type: ignore[no-redef]
        """Fallback when neither TextLog nor Log widgets are available."""

        def __init__(
            self,
            *,
            id: str | None = None,
            classes: str | None = None,
        ) -> None:
            super().__init__("", id=id, classes=classes)
            self._lines: list[str] = []

        def write(self, text: str) -> None:  # type: ignore[override]
            self._lines.append(text)
            self.update("\n".join(self._lines))

        def clear(self) -> None:  # type: ignore[override]
            self._lines.clear()
            self.update("")

        def clear_selection(self) -> None:
            return


_SMLOG_THEME = TextAreaTheme(
    name="smlog",
    syntax_styles=dict(TOKEN_STYLES),
)


class ResultsArea(TextArea):
    """Read-only results viewer with log-aware highlights."""

    def __init__(
        self,
        *,
        log_kind: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._log_kind = log_kind or ""
        super().__init__(
            text="",
            language=None,
            theme="css",
            soft_wrap=True,
            tab_behavior="focus",
            read_only=True,
            show_line_numbers=False,
            id=id,
            classes=classes,
        )
        self.register_theme(_SMLOG_THEME)
        self.theme = "smlog"

    def set_log_kind(self, log_kind: str | None) -> None:
        self._log_kind = log_kind or ""
        self._build_highlight_map()
        self.refresh()

    async def _on_mouse_down(
        self,
        event: events.MouseDown,
    ) -> None:  # pragma: no cover - UI behaviour
        if getattr(event, "button", None) == 3:
            selection = self.selected_text or None
            end_selection = getattr(self, "_end_mouse_selection", None)
            if callable(end_selection):
                try:
                    end_selection()
                except Exception:
                    pass
            try:
                self.release_mouse()
            except Exception:
                pass
            region = getattr(self, "region", None)
            if region is not None:
                screen_x = int(region.x + event.x)
                screen_y = int(region.y + event.y)
            else:
                screen_x = int(event.screen_x)
                screen_y = int(event.screen_y)

            def _open_menu() -> None:
                app = getattr(self, "app", None)
                show_menu = getattr(app, "_show_context_menu", None)
                if show_menu is not None:
                    show_menu(
                        screen_x,
                        screen_y,
                        selection=selection,
                    )

            self.call_after_refresh(_open_menu)
            event.stop()
            return
        await super()._on_mouse_down(event)

    def _build_highlight_map(self) -> None:
        highlights = self._highlights
        highlights.clear()
        document = self.document
        kind = getattr(self, "_log_kind", "")
        for row in range(document.line_count):
            line = document.get_line(row)
            spans = spans_for_line(kind, line)
            if not spans:
                continue
            offsets = _byte_offsets(line)
            line_highlights = highlights[row]
            for span in spans:
                start = _clamp_index(span.start, len(line))
                end = _clamp_index(span.end, len(line))
                if start >= end:
                    continue
                line_highlights.append(
                    (offsets[start], offsets[end], span.token),
                )


def _byte_offsets(line: str) -> list[int]:
    offsets = [0]
    total = 0
    for ch in line:
        total += len(ch.encode("utf-8"))
        offsets.append(total)
    return offsets


def _clamp_index(value: int, upper: int) -> int:
    if value < 0:
        return 0
    if value > upper:
        return upper
    return value


class ContextMenuScreen(ModalScreen[str | None]):
    """Modal context menu used for result copy actions."""

    DEFAULT_CSS = """
    ContextMenuScreen {
        background: transparent;
    }

    #context-menu {
        position: absolute;
        layer: overlay;
        background: #1f1f1f;
        border: solid #5f5f5f;
        padding: 0 1;
        height: auto;
        width: auto;
    }

    #context-menu Button {
        width: auto;
        height: auto;
        margin-right: 1;
    }
    """

    def __init__(self, *, x: float, y: float) -> None:
        super().__init__()
        self._origin = Offset(int(x), int(y))

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Button("Copy", id="context-copy"),
            Button("Copy All", id="context-copy-all"),
            id="context-menu",
        )

    def on_mount(self) -> None:
        self.call_after_refresh(self._position_menu)
        try:
            self.query_one("#context-copy").focus()
        except Exception:
            pass

    def on_mouse_down(
        self,
        event: events.MouseDown,
    ) -> None:  # pragma: no cover - UI behaviour
        menu = self.query_one("#context-menu")
        if not menu.region.contains(event.screen_x, event.screen_y):
            self.dismiss(None)

    def on_key(
        self,
        event: events.Key,
    ) -> None:  # pragma: no cover - UI behaviour
        if event.key == "escape":
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "context-copy":
            self.dismiss("copy")
        elif event.button.id == "context-copy-all":
            self.dismiss("copy-all")

    def _position_menu(self) -> None:
        menu = self.query_one("#context-menu")
        width = menu.outer_size.width
        height = menu.outer_size.height
        max_x = max(self.size.width - width, 0)
        max_y = max(self.size.height - height, 0)
        offset = Offset(
            min(self._origin.x, max_x),
            min(self._origin.y, max_y),
        )
        menu.styles.offset = offset


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


class WizardBody(Vertical):
    can_focus = True
    BINDINGS = [
        Binding(
            "ctrl+u",
            "app.menu",
            "Menu",
            show=True,
            key_display="CTRL+U",
            priority=True,
        ),
        Binding(
            "ctrl+q",
            "app.quit",
            "Quit",
            show=True,
            key_display="CTRL+Q",
            priority=True,
        ),
        Binding(
            "ctrl+r",
            "app.reset",
            "Reset Search",
            show=True,
            key_display="CTRL+R",
        ),
        Binding(
            "ctrl+f",
            "app.focus_search",
            "Focus search",
            show=True,
            key_display="CTRL+F",
        ),
        Binding(
            "ctrl+period",
            "app.next_search_mode",
            "Switch mode next",
            show=True,
            key_display="CTRL+>",
        ),
        Binding(
            "ctrl+comma",
            "app.prev_search_mode",
            "Switch mode prev",
            show=True,
            key_display="CTRL+<",
        ),
    ]


class SearchInput(Input, inherit_bindings=False):
    BINDINGS = [
        Binding("left", "cursor_left", show=False),
        Binding("right", "cursor_right", show=False),
        Binding("home", "home", show=False),
        Binding("end", "end", show=False),
        Binding("backspace", "delete_left", show=False),
        Binding("delete", "delete_right", show=False),
        Binding("ctrl+period", "app.next_search_mode", show=False),
        Binding("ctrl+comma", "app.prev_search_mode", show=False),
        Binding("enter", "submit", show=False),
    ]


class MnemonicFooterKey(FooterKey):
    def __init__(
        self,
        *args: object,
        mnemonic_index: int | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._mnemonic_index = mnemonic_index

    def render(self) -> Text:
        key_style = self.get_component_rich_style("footer-key--key")
        description_style = self.get_component_rich_style(
            "footer-key--description"
        )
        key_display = self.key_display
        key_padding = self.get_component_styles("footer-key--key").padding
        description_padding = self.get_component_styles(
            "footer-key--description"
        ).padding

        description = self.description
        if description:
            key_text = Text(
                " " * key_padding.left + key_display + " " * key_padding.right,
                style=key_style,
            )
            desc_text = Text(
                " " * description_padding.left
                + description
                + " " * description_padding.right,
                style=description_style,
            )
            if self._mnemonic_index is not None:
                bold_pos = description_padding.left + self._mnemonic_index
                if 0 <= bold_pos < len(desc_text):
                    desc_text.stylize(
                        "bold",
                        bold_pos,
                        bold_pos + 1,
                    )
            label_text = Text.assemble(key_text, desc_text)
        else:
            label_text = Text.assemble((key_display, key_style))

        label_text.stylize_before(self.rich_style)
        return label_text


class MenuFooter(Footer):
    def _mnemonic_index(self, binding: Binding) -> int | None:
        description = binding.description
        if not description:
            return None
        letters = [char for char in binding.key if char.isalpha()]
        if not letters:
            return None
        target = letters[-1]
        for idx, char in enumerate(description):
            if char.lower() == target.lower():
                return idx
        return None

    def _build_footer_key(
        self,
        binding: Binding,
        enabled: bool,
        tooltip: str,
        *,
        grouped: bool = False,
    ) -> FooterKey:
        key_display = self.app.get_key_display(binding)
        classes = "-grouped" if grouped else ""
        mnemonic_index = self._mnemonic_index(binding)
        if mnemonic_index is not None and binding.description:
            return MnemonicFooterKey(
                binding.key,
                key_display,
                binding.description,
                binding.action,
                disabled=not enabled,
                tooltip=tooltip or binding.description,
                classes=classes,
                mnemonic_index=mnemonic_index,
            ).data_bind(compact=Footer.compact)
        return FooterKey(
            binding.key,
            key_display,
            "" if grouped else binding.description,
            binding.action,
            disabled=not enabled,
            tooltip=tooltip,
            classes=classes,
        ).data_bind(compact=Footer.compact)

    def compose(self) -> ComposeResult:
        if not self._bindings_ready:
            return
        active_bindings = self.screen.active_bindings
        bindings = [
            (binding, enabled, tooltip)
            for (_, binding, enabled, tooltip) in active_bindings.values()
            if binding.show
        ]
        action_to_bindings: defaultdict[str, list[tuple[Binding, bool, str]]]
        action_to_bindings = defaultdict(list)
        for binding, enabled, tooltip in bindings:
            action_to_bindings[binding.action].append(
                (binding, enabled, tooltip)
            )

        self.styles.grid_size_columns = len(action_to_bindings)

        for group, multi_bindings_iterable in groupby(
            action_to_bindings.values(),
            lambda multi_bindings_: multi_bindings_[0][0].group,
        ):
            multi_bindings = list(multi_bindings_iterable)
            if group is not None and len(multi_bindings) > 1:
                with KeyGroup(classes="-compact" if group.compact else ""):
                    for multi_bindings in multi_bindings:
                        binding, enabled, tooltip = multi_bindings[0]
                        yield self._build_footer_key(
                            binding,
                            enabled,
                            tooltip,
                            grouped=True,
                        )
                yield FooterLabel(group.description)
            else:
                for multi_bindings in multi_bindings:
                    binding, enabled, tooltip = multi_bindings[0]
                    yield self._build_footer_key(binding, enabled, tooltip)


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

    .button-row {
        height: auto;
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

    .result-log {
        height: 1fr;
        width: 1fr;
    }

    .results-header {
        height: auto;
    }

    .results-spacer {
        width: 1fr;
    }

    .results-help {
        text-align: right;
    }

    .results-body {
        height: 1fr;
    }

    .button-spacer {
        width: 1fr;
        height: 1;
    }

    .button-row > Horizontal {
        height: auto;
    }

    .right-buttons Button {
        margin-left: 1;
        margin-right: 0;
    }

    .mode-row {
        height: auto;
    }

    .mode-row Button {
        min-width: 18;
        margin-right: 1;
    }

    .mode-description {
        width: 1fr;
    }
    """

    logs_dir: reactive[Path] = reactive(Path.cwd())
    staging_dir: reactive[Optional[Path]] = reactive(None)
    default_kind: reactive[Optional[str]] = reactive(KIND_SMTP)
    _search_mode_cycle = (MODE_LITERAL, MODE_WILDCARD)

    def __init__(
        self,
        logs_dir: Path,
        staging_dir: Path | None = None,
        default_kind: str | None = None,
    ) -> None:
        super().__init__()
        self.logs_dir = logs_dir
        self.staging_dir = staging_dir
        self.default_kind = normalize_kind(default_kind or KIND_SMTP)
        self._logs_by_kind: Dict[str, List[LogFileInfo]] = {}
        self.current_kind: Optional[str] = None
        self.selected_logs: list[LogFileInfo] = []
        self.step: WizardStep = WizardStep.KIND
        self.kind_list: KindListView | None = None
        self.date_list: DateListView | None = None
        self.search_input: Input | None = None
        self.search_mode = MODE_LITERAL
        self.search_mode_status: Static | None = None
        self.search_mode_button: Button | None = None
        self.output_log: ResultsArea | None = None
        self.footer: Footer | None = None
        self.subsearch_path: Path | None = None
        self.subsearch_active = False
        self.subsearch_kind: str | None = None
        self.subsearch_depth = 0
        self.last_rendered_lines: list[str] | None = None
        self.last_rendered_kind: str | None = None
        self.subsearch_terms: list[str] = []
        self.subsearch_paths: list[Path] = []
        self.subsearch_rendered: list[list[str]] = []
        self._result_log_counter = 0
        self._context_menu_open = False

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Header(show_clock=False, icon="Menu")
        self.wizard = WizardBody(id="wizard-body")
        yield self.wizard
        self.footer = MenuFooter(show_command_palette=False)
        yield self.footer

    def on_mount(self) -> None:
        self._refresh_logs()
        self._show_step_kind()

    # Step rendering -----------------------------------------------------
    def _show_step_kind(self) -> None:
        self.step = WizardStep.KIND
        self._clear_wizard()
        self._reset_subsearch()
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
        if self.subsearch_active:
            summary_text = "Step 3: Enter a sub-search term"
        else:
            summary_text = (
                "Step 3: Enter a search term for "
                f"{self.current_kind} across {len(self.selected_logs)} log(s)"
            )
        summary = Static(summary_text, classes="instruction")
        self.wizard.mount(summary)
        self.search_input = SearchInput(
            placeholder="Enter search term",
            id="search-term",
        )
        self.wizard.mount(self.search_input)
        self.search_mode_status = Static(
            self._search_mode_status_text(),
            classes="mode-description",
            id="search-mode-status",
        )
        self.search_mode_button = Button(
            self._search_mode_button_text(),
            id="cycle-search-mode",
        )
        mode_row = Horizontal(
            self.search_mode_button,
            self.search_mode_status,
            classes="mode-row",
        )
        self.wizard.mount(mode_row)
        back_label = "Back"
        back_id = "back-search"
        if self.subsearch_active:
            back_label = "Back to Results"
            back_id = "back-results"
        button_row = Horizontal(
            Button(back_label, id=back_id),
            Button("Search", id="do-search"),
            classes="button-row",
        )
        self.wizard.mount(button_row)
        self.search_input.focus()
        self._refresh_footer_bindings()

    def _show_step_results(self) -> None:
        self.step = WizardStep.RESULTS
        self._clear_wizard()
        title = self._results_title()
        help_text = (
            "Selection: arrows move, Shift+arrows select, "
            "mouse drag works. Right-click for copy."
        )
        header_row = Horizontal(
            Static(title, classes="instruction"),
            Static("", classes="results-spacer"),
            Static(help_text, classes="results-help"),
            classes="results-header",
        )
        self.wizard.mount(header_row)
        self._result_log_counter += 1
        result_id = f"result-log-{self._result_log_counter}"
        self.output_log = ResultsArea(id=result_id, classes="result-log")
        self.output_log.styles.height = "1fr"
        self.output_log.styles.min_height = 5
        show_back = len(self.subsearch_terms) > 1
        left_buttons: list[Static] = [
            Button("New Search", id="new-search"),
            Button("Sub-search", id="sub-search"),
        ]
        if show_back:
            left_buttons.append(Button("Back", id="back-subsearch"))
        left_buttons.append(Button("Quit", id="quit-results"))
        right_buttons = [
            Button("Copy", id="copy-selection"),
            Button("Copy All", id="copy-all"),
        ]
        button_row = Horizontal(
            Horizontal(*left_buttons),
            Static("", classes="button-spacer"),
            Horizontal(*right_buttons, classes="right-buttons"),
            classes="button-row",
            id="results-buttons",
        )
        results_body = Vertical(
            self.output_log,
            button_row,
            classes="results-body",
        )
        self.wizard.mount(results_body)
        self.call_after_refresh(self._focus_results)
        self._refresh_footer_bindings()

    # Step helpers -------------------------------------------------------
    def _initial_kind_choice(self, kinds_sorted: list[str]) -> str | None:
        if self.default_kind in self._logs_by_kind:
            return self.default_kind
        if KIND_SMTP in self._logs_by_kind:
            return KIND_SMTP
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
        elif button_id == "back-results":
            self._show_last_results()
        elif button_id == "cycle-search-mode":
            self._cycle_search_mode()
        elif button_id == "do-search":
            self._perform_search()
        elif button_id == "new-search":
            self._reset_subsearch()
            self._show_step_kind()
        elif button_id == "sub-search":
            self._start_subsearch()
        elif button_id == "back-subsearch":
            self._step_back_subsearch()
        elif button_id == "quit-results":
            self.exit()
        elif button_id == "copy-selection":
            self._copy_results(selection_only=True)
        elif button_id == "copy-all":
            self._copy_results(selection_only=False)

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

    def action_next_search_mode(self) -> None:
        if self.step == WizardStep.SEARCH:
            self._step_search_mode(1)

    def action_prev_search_mode(self) -> None:
        if self.step == WizardStep.SEARCH:
            self._step_search_mode(-1)

    def action_menu(self) -> None:
        self.action_command_palette()

    def action_quit(self) -> None:
        self.exit()

    def check_action(
        self,
        action: str,
        parameters: tuple[object, ...],
    ) -> bool | None:
        if action == "focus_search":
            return self.step == WizardStep.SEARCH
        if action == "next_search_mode":
            return self.step == WizardStep.SEARCH
        if action == "prev_search_mode":
            return self.step == WizardStep.SEARCH
        return True

    def action_reset(self) -> None:
        self._refresh_logs()
        self.selected_logs = []
        self.current_kind = None
        self._reset_subsearch()
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

    def _show_context_menu(
        self,
        x: float,
        y: float,
        *,
        selection: str | None = None,
    ) -> None:
        if self._context_menu_open:
            return
        self._context_menu_open = True

        def handle_choice(result: str | None) -> None:
            self._context_menu_open = False
            if result == "copy":
                self._copy_results(
                    selection_only=True,
                    fallback_text=selection,
                )
            elif result == "copy-all":
                self._copy_results(selection_only=False)

        self.push_screen(
            ContextMenuScreen(x=x, y=y),
            handle_choice,
        )

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
        if self.staging_dir is None:
            self._notify(
                "Staging directory is not configured. Set 'staging_dir' in "
                "config.yaml or pass --staging-dir."
            )
            return

        if self.subsearch_active:
            if self.subsearch_path is None:
                self._notify("No prior results available for sub-search.")
                return
            search_targets = [self.subsearch_path]
        else:
            if not self.selected_logs:
                self._notify("Select at least one log date before searching.")
                return
            search_targets = []
            for info in self.selected_logs:
                try:
                    staged = stage_log(
                        info.path,
                        staging_dir=self.staging_dir,
                    )
                except Exception as exc:
                    # pragma: no cover - filesystem feedback
                    self._notify(f"Failed to stage {info.path.name}: {exc}")
                    return
                search_targets.append(staged.staged_path)
        search_kind = self.subsearch_kind if self.subsearch_active else None
        if search_kind is None:
            search_kind = self.current_kind
        if search_kind is None:
            self._notify("Select a log type before searching.")
            return
        search_fn = get_search_function(search_kind)
        if search_fn is None:
            self._notify(f"No search handler for log kind: {search_kind}")
            return
        term = (self.search_input.value if self.search_input else "").strip()
        if not term:
            self._notify("Enter a search term.")
            return

        try:
            results = [
                search_fn(
                    target,
                    term,
                    mode=self.search_mode,
                )
                for target in search_targets
            ]
        except ValueError as exc:
            self._notify(str(exc))
            return
        rendered_lines = self._render_results(
            results,
            search_targets,
            search_kind,
        )
        self.last_rendered_lines = rendered_lines
        self.last_rendered_kind = search_kind
        self._write_subsearch_snapshot(results, term, rendered_lines)
        self.subsearch_kind = search_kind

        self._display_results(rendered_lines, search_kind)
        self._notify("Search complete.")

    def _cycle_search_mode(self) -> None:
        self._step_search_mode(1)

    def _step_search_mode(self, step: int) -> None:
        current = self.search_mode
        modes = self._search_mode_cycle
        try:
            index = modes.index(current)
        except ValueError:
            index = 0
        self.search_mode = modes[(index + step) % len(modes)]
        self._refresh_search_mode_controls()
        label = SEARCH_MODE_LABELS.get(self.search_mode, self.search_mode)
        self._notify(f"Search mode: {label}")

    def _refresh_search_mode_controls(self) -> None:
        if self.search_mode_status is not None:
            self.search_mode_status.update(self._search_mode_status_text())
        if self.search_mode_button is not None:
            self.search_mode_button.label = self._search_mode_button_text()

    def _search_mode_button_text(self) -> str:
        label = SEARCH_MODE_LABELS.get(self.search_mode, self.search_mode)
        return f"Mode: {label}"

    def _search_mode_status_text(self) -> str:
        description = SEARCH_MODE_DESCRIPTIONS.get(self.search_mode, "")
        return description

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
        if isinstance(self.output_log, ResultsArea):
            self.output_log.text = "\n".join(lines)
            return

        if hasattr(self.output_log, "clear"):
            self.output_log.clear()  # type: ignore[call-arg]
        if hasattr(self.output_log, "update"):
            self.output_log.update("\n".join(lines))

    def _copy_results(
        self,
        *,
        selection_only: bool,
        fallback_text: str | None = None,
    ) -> None:
        if selection_only:
            text = self._get_selected_text()
            if not text and fallback_text:
                text = fallback_text
            if not text:
                self._notify("Select text to copy.")
                return
            self.copy_to_clipboard(text)
            self._notify("Copied selection to clipboard.")
            return
        text = self._get_full_results_text()
        if not text:
            self._notify("No results available to copy.")
            return
        self.copy_to_clipboard(text)
        self._notify("Copied full results to clipboard.")

    def _get_selected_text(self) -> str | None:
        if isinstance(self.output_log, ResultsArea):
            text = self.output_log.selected_text
            return text or None
        if self.screen is None:
            return None
        selected = self.screen.get_selected_text()
        return selected or None

    def _get_full_results_text(self) -> str | None:
        if self.last_rendered_lines:
            return "\n".join(self.last_rendered_lines).rstrip("\n")
        if isinstance(self.output_log, ResultsArea):
            return self.output_log.text
        return None

    def _display_results(
        self,
        lines: list[str],
        kind: str | None,
    ) -> None:
        self._show_step_results()
        if not lines:
            return
        if isinstance(self.output_log, ResultsArea):
            self.output_log.set_log_kind(kind)
        self._write_output_lines(lines)


    def _render_results(
        self,
        results: list,
        targets: list[Path],
        kind: str,
    ) -> list[str]:
        return render_search_results(results, targets, kind)

    def _subsearch_output_path(self) -> Path:
        if self.staging_dir is None:
            raise ValueError(
                "Staging directory is not configured. Set 'staging_dir' in "
                "config.yaml or pass --staging-dir."
            )
        staging_dir = self.staging_dir
        staging_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        depth = self.subsearch_depth + 1
        name = f"subsearch_{depth:02d}_{timestamp}.log"
        return staging_dir / name

    def _write_subsearch_snapshot(
        self,
        results: list,
        term: str,
        rendered_lines: list[str],
    ) -> None:
        if not self.subsearch_active:
            self._reset_subsearch()
        output_path = self._subsearch_output_path()
        lines: list[str] = []
        for result in results:
            for conversation in result.conversations:
                lines.extend(conversation.lines)
            for _line_number, line in result.orphan_matches:
                lines.append(line)
        with output_path.open("w", encoding="utf-8") as handle:
            for line in lines:
                handle.write(f"{line}\n")
        self.subsearch_path = output_path
        self.subsearch_depth += 1
        self.subsearch_terms.append(term)
        self.subsearch_paths.append(output_path)
        self.subsearch_rendered.append(rendered_lines)

    def _start_subsearch(self) -> None:
        if self.subsearch_path is None:
            self._notify("No prior results available for sub-search.")
            return
        self.subsearch_active = True
        self._show_step_search()

    def _show_last_results(self) -> None:
        if not self.last_rendered_lines:
            self._notify("No prior results to display.")
            return
        self._display_results(
            self.last_rendered_lines,
            self.last_rendered_kind,
        )

    def _step_back_subsearch(self) -> None:
        if len(self.subsearch_terms) <= 1:
            return
        self.subsearch_terms.pop()
        self.subsearch_paths.pop()
        self.subsearch_rendered.pop()
        self.subsearch_depth = len(self.subsearch_paths)
        self.subsearch_path = (
            self.subsearch_paths[-1] if self.subsearch_paths else None
        )
        self.last_rendered_lines = (
            self.subsearch_rendered[-1] if self.subsearch_rendered else None
        )
        self.last_rendered_kind = self.subsearch_kind
        if self.last_rendered_lines:
            self._display_results(
                self.last_rendered_lines,
                self.last_rendered_kind,
            )
        else:
            self._show_step_kind()

    def _reset_subsearch(self) -> None:
        self.subsearch_active = False
        self.subsearch_path = None
        self.subsearch_kind = None
        self.subsearch_depth = 0
        self.last_rendered_lines = None
        self.last_rendered_kind = None
        self.subsearch_terms = []
        self.subsearch_paths = []
        self.subsearch_rendered = []

    def _results_title(self) -> str:
        if not self.subsearch_terms:
            return "Search results"
        crumb = " » ".join(self.subsearch_terms)
        return f"Search results: {crumb}"

    def _focus_results(self) -> None:
        if self.output_log is not None:
            try:
                self.output_log.focus()
                return
            except Exception:
                pass
        try:
            self.wizard.focus()
        except Exception:
            return


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
