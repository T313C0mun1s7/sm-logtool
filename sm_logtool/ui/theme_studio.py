"""Visual theme conversion utility for sm-logtool."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Input,
    ListItem,
    ListView,
    Static,
)
from textual.theme import Theme

from .app import ResultsArea
from .app import TopAction
from .theme_importer import (
    default_theme_source_dir,
    discover_theme_files,
    load_saved_themes,
    map_terminal_palette,
    parse_terminal_palette,
    save_converted_theme,
)
from .theme_importer import SUPPORTED_THEME_MAPPING_PROFILES
from .themes import CYBERDARK_THEME
from .themes import FIRST_PARTY_APP_THEMES
from .themes import CYBER_THEME_VARIABLE_DEFAULTS

_SAMPLE_KIND = "smtp"
_SAMPLE_LINES = (
    "00:00:01 [1.1.1.1][123] SMTP cmd: EHLO mail.example.com",
    "00:00:02 [1.1.1.1][123] SMTP rsp: 250 ok",
    "00:00:03 [1.1.1.1][123] Authentication failed for user admin@example.com",
)

_SELECTION_SAMPLE_TARGETS = {
    "sample-row-selected": "selection-selected-background",
    "sample-row-active": "selection-active-background",
    "sample-row-selected-active": "selection-selected-active-background",
}

_OVERRIDE_TARGET_LABELS = {
    "background": "App background",
    "foreground": "App foreground",
    "panel": "Panel background",
    "surface": "Surface background",
    "primary": "Primary color",
    "secondary": "Secondary color",
    "accent": "Accent color",
    "success": "Success color",
    "warning": "Warning color",
    "error": "Error color",
    "top-actions-background": "Top bar background",
    "top-action-background": "Top action background",
    "top-action-hover-background": "Top action hover",
    "top-action-mnemonic-foreground": "Top action mnemonic",
    "selection-selected-background": "Selected row",
    "selection-active-background": "Active row",
    "selection-selected-active-background": "Selected + active row",
    "selection-selected-foreground": "Selected row text",
    "selection-active-foreground": "Active row text",
    "selection-selected-active-foreground": "Selected+active row text",
    "action-button-background": "Action button background",
    "action-button-foreground": "Action button text",
    "action-button-hover-background": "Action button hover",
    "action-button-focus-background": "Action button focus",
    "context-menu-background": "Context menu background",
    "context-menu-border": "Context menu border",
}

_OVERRIDE_TARGETS = tuple(_OVERRIDE_TARGET_LABELS.keys())

_CLICK_TARGETS = {
    **_SELECTION_SAMPLE_TARGETS,
    "browse-preview-shell": "background",
    "top-actions": "top-actions-background",
    "preview-top-menu": "top-action-background",
    "preview-top-quit": "top-action-background",
    "preview-top-reset": "top-action-background",
    "sample-instruction": "primary",
    "sample-query": "panel",
    "sample-mode": "accent",
    "preview-back": "action-button-background",
    "preview-search": "action-button-background",
    "preview-cancel": "action-button-background",
    "sample-results-header": "primary",
    "syntax-preview": "panel",
}

_OVERRIDE_CHOICES = (
    "auto",
    "accent",
    "primary",
    "secondary",
    "warning",
    "error",
    "success",
    "foreground",
    "background",
    "panel",
    "surface",
    "ansi0",
    "ansi1",
    "ansi2",
    "ansi3",
    "ansi4",
    "ansi5",
    "ansi6",
    "ansi7",
    "ansi8",
    "ansi9",
    "ansi10",
    "ansi11",
    "ansi12",
    "ansi13",
    "ansi14",
    "ansi15",
)


class SourceThemeItem(ListItem):
    """List item containing a source theme path."""

    def __init__(self, source_path: Path) -> None:
        super().__init__(Static(source_path.name, classes="source-label"))
        self.source_path = source_path


class ThemeStudio(App):
    """Interactive studio for converting terminal themes."""

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
        color: $foreground;
    }

    #title {
        padding: 1 1;
        text-style: bold;
        background: $top-actions-background;
        color: $foreground;
        border-bottom: solid $top-action-background;
    }

    #layout {
        height: 1fr;
        background: $background;
    }

    #sources {
        width: 36;
        margin: 0 1 1 1;
        border: round $top-action-background;
        background: $panel;
        color: $foreground;
        padding: 1;
    }

    #preview {
        margin: 0 1 1 0;
        border: round $top-action-background;
        background: $panel;
        color: $foreground;
        padding: 1;
    }

    #source-list {
        height: 1fr;
        margin-top: 1;
        border: round $selection-selected-background;
        background: $surface;
        color: $foreground;
    }

    .source-label {
        color: $foreground;
    }

    #controls {
        margin-bottom: 1;
        height: auto;
        background: $surface;
        border: round $selection-selected-background;
        padding: 1;
    }

    #save-name {
        width: 28;
        margin-right: 1;
        background: $surface;
        color: $foreground;
        border: round $accent;
    }

    .profile-button {
        min-width: 12;
        margin-right: 1;
        background: $action-button-background;
        color: $action-button-foreground;
        border: round $action-button-hover-background;
    }

    .profile-button.-active {
        background: $action-button-hover-background;
        color: $action-button-foreground;
    }

    .studio-button {
        background: $action-button-background;
        color: $action-button-foreground;
        border: round $action-button-hover-background;
    }

    #browse-preview-shell {
        height: 1fr;
        margin-top: 0;
        border: round $selection-selected-background;
        background: $background;
    }

    #status {
        color: $accent;
        margin-top: 1;
    }

    #top-actions {
        height: 1;
        padding: 0 1;
        background: $top-actions-background;
    }

    .top-action {
        width: auto;
        height: 1;
        min-height: 1;
        padding: 0 1;
        margin-right: 1;
        background: $top-action-background;
    }

    .top-action:hover {
        background: $top-action-hover-background;
    }

    .top-action:focus {
        text-style: bold;
    }

    #wizard-body {
        margin: 0 1;
        height: 1fr;
    }

    .instruction {
        padding: 0;
        color: $primary;
    }

    .button-row {
        width: 1fr;
        height: auto;
        margin-top: 0;
    }

    .button-row Button {
        margin-right: 1;
    }

    .action-button {
        text-style: bold;
    }

    .action-button.-style-default {
        background: $action-button-background;
        color: $action-button-foreground;
        border: round $action-button-hover-background;
    }

    .action-button.-style-default:hover {
        background: $action-button-hover-background;
        border: round $action-button-hover-background;
    }

    .action-button.-style-default:focus {
        background: $action-button-focus-background;
        color: $action-button-foreground;
        border: round $action-button-focus-background;
        text-style: bold;
    }

    .action-button.-style-default.-active {
        background: $action-button-hover-background;
        border: round $action-button-hover-background;
    }

    .selected .label {
        text-style: bold;
        background: $selection-selected-background;
        color: $selection-selected-foreground;
    }

    .active .label {
        background: $selection-active-background;
        color: $selection-active-foreground;
    }

    .selected.active .label {
        background: $selection-selected-active-background;
        color: $selection-selected-active-foreground;
    }

    .result-log {
        height: 1fr;
        width: 1fr;
        background: $panel;
    }

    .results-header {
        height: auto;
    }

    .mode-description {
        width: 1fr;
        color: $accent;
    }

    .search-term-input {
        margin-bottom: 0;
        background: $panel;
        color: $foreground;
        border: none;
        border-top: none;
        border-bottom: none;
    }

    .search-term-input:focus {
        background: $panel;
        border: none;
        border-top: none;
        border-bottom: none;
    }

    .selection-list {
        margin-bottom: 0;
        background: $panel;
    }

    .selection-preview-row {
        height: auto;
    }

    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("s", "save_theme", "Save Theme"),
        Binding("1", "profile_balanced", "Balanced"),
        Binding("2", "profile_vivid", "Vivid"),
        Binding("3", "profile_soft", "Soft"),
        Binding("a", "toggle_ansi", "Toggle ANSI-256"),
        Binding("[", "override_source_prev", "Source Prev"),
        Binding("]", "override_source_next", "Source Next"),
        Binding("-", "override_target_prev", "Target Prev"),
        Binding("=", "override_target_next", "Target Next"),
        Binding("c", "override_clear", "Clear Override"),
    ]

    def __init__(
        self,
        *,
        source_paths: tuple[Path, ...],
        store_dir: Path,
        profile: str,
        quantize_ansi256: bool,
    ) -> None:
        super().__init__()
        for theme_model in FIRST_PARTY_APP_THEMES:
            self.register_theme(theme_model)
        self.source_paths = source_paths
        self.store_dir = store_dir.expanduser()
        self.profile = profile
        self.quantize_ansi256 = quantize_ansi256
        self.current_source: Path | None = None
        self.current_theme_name: str | None = None
        self.current_source_theme_name: str | None = None
        self._preview_revision = 0
        self._manual_overrides: dict[str, str] = {}
        self._active_override_target = "selection-selected-background"
        self._override_source_path: Path | None = None

    def compose(self) -> ComposeResult:
        yield Static("Theme Studio", id="title")
        with Horizontal(id="layout"):
            with Vertical(id="sources"):
                yield Static("Source Themes")
                self.source_list = ListView(id="source-list")
                yield self.source_list
            with Vertical(id="preview"):
                with Horizontal(id="controls"):
                    yield Button(
                        "Balanced",
                        id="profile-balanced",
                        classes="profile-button",
                    )
                    yield Button(
                        "Vivid",
                        id="profile-vivid",
                        classes="profile-button",
                    )
                    yield Button(
                        "Soft",
                        id="profile-soft",
                        classes="profile-button",
                    )
                    ansi_label = self._ansi_label()
                    yield Button(
                        ansi_label,
                        id="toggle-ansi",
                        classes="studio-button",
                    )
                    yield Input(
                        "",
                        id="save-name",
                        placeholder="Theme name",
                    )
                    yield Button(
                        "Save",
                        id="save-theme",
                        classes="studio-button",
                    )
                    yield Button(
                        "Quit",
                        id="quit-studio",
                        classes="studio-button",
                    )
                with Vertical(id="browse-preview-shell"):
                    with Horizontal(id="top-actions"):
                        yield TopAction(
                            "Menu",
                            "menu",
                            "u",
                            id="preview-top-menu",
                        )
                        yield TopAction(
                            "Quit",
                            "quit",
                            "q",
                            id="preview-top-quit",
                        )
                        yield TopAction(
                            "Reset",
                            "reset",
                            "r",
                            id="preview-top-reset",
                        )
                    with Vertical(id="wizard-body"):
                        yield Static(
                            "Step Preview: Browse UI parity",
                            id="sample-instruction",
                            classes="instruction",
                        )
                        with Vertical(
                            id="preview-selection-list",
                            classes="selection-list",
                        ):
                            with Horizontal(
                                classes="selection-preview-row selected"
                            ):
                                yield Static(
                                    "Selected date row",
                                    id="sample-row-selected",
                                    classes="label",
                                )
                            with Horizontal(
                                classes="selection-preview-row active"
                            ):
                                yield Static(
                                    "Active date row",
                                    id="sample-row-active",
                                    classes="label",
                                )
                            with Horizontal(
                                classes="selection-preview-row selected active"
                            ):
                                yield Static(
                                    "Selected + active row",
                                    id="sample-row-selected-active",
                                    classes="label",
                                )
                        yield Input(
                            "search term example",
                            id="sample-query",
                            classes="search-term-input",
                            placeholder="Search term",
                        )
                        yield Static(
                            "Search mode: Literal "
                            "(Ctrl+Right/Ctrl+Left to cycle)",
                            id="sample-mode",
                            classes="mode-description",
                        )
                        with Horizontal(classes="button-row"):
                            yield Button(
                                "Back",
                                id="preview-back",
                                classes="action-button",
                            )
                            yield Button(
                                "Search",
                                id="preview-search",
                                classes="action-button",
                            )
                            yield Button(
                                "Cancel",
                                id="preview-cancel",
                                classes="action-button",
                            )
                        yield Static(
                            "Results Preview",
                            id="sample-results-header",
                            classes="results-header",
                        )
                        yield ResultsArea(
                            log_kind=_SAMPLE_KIND,
                            id="syntax-preview",
                            classes="result-log",
                        )
                yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = CYBERDARK_THEME.name
        self._update_profile_button_states()
        self._load_sources()

    def get_theme_variable_defaults(self) -> dict[str, str]:
        return dict(CYBER_THEME_VARIABLE_DEFAULTS)

    def on_list_view_highlighted(
        self,
        event: ListView.Highlighted,
    ) -> None:
        item = event.item
        if isinstance(item, SourceThemeItem):
            self.current_source = item.source_path
            self._refresh_preview(reset_name=True)

    def on_list_view_selected(
        self,
        event: ListView.Selected,
    ) -> None:
        item = event.item
        if isinstance(item, SourceThemeItem):
            self.current_source = item.source_path
            self._refresh_preview(reset_name=True)

    def on_input_submitted(
        self,
        event: Input.Submitted,
    ) -> None:
        if event.input.id == "save-name":
            self.action_save_theme()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "quit-studio":
            self.exit()
            return
        if button_id == "save-theme":
            self.action_save_theme()
            return
        if button_id == "toggle-ansi":
            self.action_toggle_ansi()
            return
        if button_id == "profile-balanced":
            self.action_profile_balanced()
            return
        if button_id == "profile-vivid":
            self.action_profile_vivid()
            return
        if button_id == "profile-soft":
            self.action_profile_soft()
            return

    def on_click(
        self,
        event: events.Click,
    ) -> None:  # pragma: no cover - UI behavior
        widget = event.widget
        while widget is not None:
            widget_id = getattr(widget, "id", None)
            target = _CLICK_TARGETS.get(widget_id or "")
            if target is not None:
                self._active_override_target = target
                label = self._override_target_label(
                    self._active_override_target
                )
                self._set_status(
                    "Editing "
                    f"{label}."
                )
                event.stop()
                return
            widget = getattr(widget, "parent", None)

    def action_override_source_prev(self) -> None:
        self._cycle_override_source(-1)

    def action_override_source_next(self) -> None:
        self._cycle_override_source(1)

    def action_override_target_prev(self) -> None:
        self._cycle_override_target(-1)

    def action_override_target_next(self) -> None:
        self._cycle_override_target(1)

    def action_override_clear(self) -> None:
        self._set_current_override("auto")

    def action_save_theme(self) -> None:
        if self.current_source is None or self.current_theme_name is None:
            self._set_status("Select a source theme before saving.")
            return
        theme_model = self.get_theme(self.current_theme_name)
        if theme_model is None:
            self._set_status("Preview theme is not available to save.")
            return
        save_name = self._selected_theme_name()
        if not save_name:
            self._set_status("Theme name cannot be empty.")
            return
        theme_to_save = _theme_with_name(theme_model, save_name)
        path = save_converted_theme(
            theme=theme_to_save,
            store_dir=self.store_dir,
            source_path=self.current_source,
            mapping_profile=self.profile,
            quantize_ansi256=self.quantize_ansi256,
        )
        loaded_themes, warnings = load_saved_themes(store_dir=self.store_dir)
        loaded_by_name = {
            loaded_theme.name: loaded_theme
            for loaded_theme in loaded_themes
        }
        loaded_theme = loaded_by_name.get(save_name)
        if loaded_theme is not None:
            self.register_theme(loaded_theme)
            self.theme = loaded_theme.name
            self.current_theme_name = loaded_theme.name
            self._set_syntax_preview(loaded_theme)
        details = f"profile={self.profile} {self._ansi_label()}"
        if warnings:
            details = f"{details} | warnings={len(warnings)}"
        self._set_status(f"Saved converted theme: {path} ({details})")

    def action_toggle_ansi(self) -> None:
        self.quantize_ansi256 = not self.quantize_ansi256
        toggle = self.query_one("#toggle-ansi", Button)
        toggle.label = self._ansi_label()
        self._refresh_preview(reset_name=False)

    def action_profile_balanced(self) -> None:
        self._set_profile("balanced")

    def action_profile_vivid(self) -> None:
        self._set_profile("vivid")

    def action_profile_soft(self) -> None:
        self._set_profile("soft")

    def _set_profile(self, profile: str) -> None:
        if profile not in SUPPORTED_THEME_MAPPING_PROFILES:
            return
        self.profile = profile
        self._update_profile_button_states()
        self._refresh_preview(reset_name=False)

    def _update_profile_button_states(self) -> None:
        for profile in SUPPORTED_THEME_MAPPING_PROFILES:
            button = self.query_one(f"#profile-{profile}", Button)
            if profile == self.profile:
                button.variant = "primary"
                button.add_class("-active")
            else:
                button.variant = "default"
                button.remove_class("-active")

    def _load_sources(self) -> None:
        source_paths = self.source_paths
        if not source_paths:
            source_paths = (default_theme_source_dir(),)

        files = discover_theme_files(source_paths)
        self.source_list.clear()
        if not files:
            self._set_status(
                "No source themes found. Add files and relaunch with "
                "--source /path/to/themes."
            )
            return

        items = [SourceThemeItem(path) for path in files]
        self.source_list.extend(items)
        self.source_list.index = 0
        first = items[0]
        self.current_source = first.source_path
        self._refresh_preview(reset_name=True)

    def _refresh_preview(self, *, reset_name: bool) -> None:
        if self.current_source is None:
            return
        if reset_name and self.current_source != self._override_source_path:
            self._manual_overrides.clear()
            self._active_override_target = "selection-selected-background"
            self._override_source_path = self.current_source
        try:
            palette = parse_terminal_palette(self.current_source)
            self.current_source_theme_name = palette.name
            preview_name = self._next_preview_theme_name()
            preview_theme = map_terminal_palette(
                name=preview_name,
                palette=palette,
                profile=self.profile,
                overrides=self._resolved_overrides(),
                quantize_ansi256=self.quantize_ansi256,
            )
        except ValueError as exc:
            self._set_status(str(exc))
            return

        if reset_name:
            name_input = self.query_one("#save-name", Input)
            name_input.value = self._default_save_name(palette.name)

        self.register_theme(preview_theme)
        self.theme = preview_theme.name
        self.current_theme_name = preview_theme.name
        self._set_status("Preview updated. Press 's' to save converted theme.")
        self._set_syntax_preview(preview_theme)

    def _next_preview_theme_name(self) -> str:
        self._preview_revision += 1
        return f"Theme Studio Preview {self._preview_revision}"

    def _set_syntax_preview(self, preview_theme: Theme) -> None:
        _ = preview_theme
        preview = self.query_one("#syntax-preview", ResultsArea)
        preview.set_log_kind(_SAMPLE_KIND)
        preview.set_visual_theme()
        preview.text = "\n".join(_SAMPLE_LINES)

    def _set_status(self, message: str) -> None:
        status = self.query_one("#status", Static)
        status.update(message)

    def _ansi_label(self) -> str:
        if self.quantize_ansi256:
            return "ANSI-256: On"
        return "ANSI-256: Off"

    def _selected_theme_name(self) -> str:
        name_input = self.query_one("#save-name", Input)
        value = name_input.value.strip()
        if value:
            return value
        if self.current_source_theme_name:
            return self.current_source_theme_name
        return "Imported Theme"

    def _default_save_name(self, source_theme_name: str) -> str:
        normalized = source_theme_name.strip()
        if not normalized:
            return "Imported Theme"
        return normalized

    def _cycle_override_source(self, delta: int) -> None:
        current = self._manual_overrides.get(
            self._active_override_target,
            "auto",
        )
        try:
            index = _OVERRIDE_CHOICES.index(current)
        except ValueError:
            index = 0
        next_index = (index + delta) % len(_OVERRIDE_CHOICES)
        self._set_current_override(_OVERRIDE_CHOICES[next_index])

    def _set_current_override(self, source: str) -> None:
        target = self._active_override_target
        if source == "auto":
            self._manual_overrides.pop(target, None)
        else:
            self._manual_overrides[target] = source
        self._set_status(
            "Override "
            f"{self._override_target_label(target)} -> {source}."
        )
        self._refresh_preview(reset_name=False)

    def _cycle_override_target(self, delta: int) -> None:
        current = self._active_override_target
        try:
            index = _OVERRIDE_TARGETS.index(current)
        except ValueError:
            index = 0
        next_index = (index + delta) % len(_OVERRIDE_TARGETS)
        self._active_override_target = _OVERRIDE_TARGETS[next_index]
        source = self._manual_overrides.get(
            self._active_override_target,
            "auto",
        )
        self._set_status(
            "Editing "
            f"{self._override_target_label(self._active_override_target)} "
            f"(source {source})."
        )

    def _override_target_label(self, target: str) -> str:
        return _OVERRIDE_TARGET_LABELS.get(target, target)

    def _resolved_overrides(self) -> dict[str, str] | None:
        if not self._manual_overrides:
            return None
        return dict(self._manual_overrides)


def _theme_with_name(theme: Theme, name: str) -> Theme:
    return Theme(
        name=name,
        primary=theme.primary,
        secondary=theme.secondary,
        warning=theme.warning,
        error=theme.error,
        success=theme.success,
        accent=theme.accent,
        foreground=theme.foreground,
        background=theme.background,
        surface=theme.surface,
        panel=theme.panel,
        dark=theme.dark,
        variables=dict(theme.variables or {}),
    )


def run(
    *,
    source_paths: Iterable[Path],
    store_dir: Path,
    profile: str,
    quantize_ansi256: bool,
) -> int:
    """Run the interactive theme studio."""

    app = ThemeStudio(
        source_paths=tuple(source_paths),
        store_dir=store_dir,
        profile=profile,
        quantize_ansi256=quantize_ansi256,
    )
    app.run()
    return 0
