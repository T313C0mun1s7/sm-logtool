"""Visual theme conversion utility for sm-logtool."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rich.color import Color
from rich.color_triplet import ColorTriplet
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
        margin-top: 1;
        border: round $selection-selected-background;
        background: $background;
    }

    #status {
        color: $warning;
        margin-top: 1;
    }

    #meta {
        margin-top: 1;
    }

    #preview-buttons {
        margin-top: 1;
        height: auto;
    }

    .sample-swatch {
        margin-right: 1;
        width: 1fr;
        min-width: 12;
        padding: 0 1;
        border: round $foreground 20%;
        content-align: center middle;
    }

    #swatch-values {
        margin-top: 1;
        color: $foreground;
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
        margin: 1 1;
        height: 1fr;
    }

    .instruction {
        padding: 1 0;
    }

    .button-row {
        width: 1fr;
        height: auto;
        margin-top: 1;
    }

    .button-row Button {
        margin-right: 1;
    }

    .action-button {
        min-width: 0;
        height: 1;
        min-height: 1;
        padding: 0;
        text-style: bold;
    }

    .action-button.-style-default {
        border: none;
        border-top: none;
        border-bottom: none;
        background: $action-button-background;
        color: $action-button-foreground;
        tint: transparent;
    }

    .action-button.-style-default:hover {
        background: $action-button-hover-background;
        border-top: none;
        border-bottom: none;
    }

    .action-button.-style-default:focus {
        background: $action-button-focus-background;
        color: $action-button-foreground;
        background-tint: transparent;
        border-top: none;
        border-bottom: none;
        text-style: bold;
    }

    .action-button.-style-default.-active {
        background: $action-button-hover-background;
        border: none;
        border-top: none;
        border-bottom: none;
        tint: transparent;
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

    .search-term-input {
        margin-bottom: 1;
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
        margin-bottom: 1;
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
                                    classes="label",
                                )
                            with Horizontal(
                                classes="selection-preview-row active"
                            ):
                                yield Static(
                                    "Active date row",
                                    classes="label",
                                )
                            with Horizontal(
                                classes="selection-preview-row selected active"
                            ):
                                yield Static(
                                    "Selected + active row",
                                    classes="label",
                                )
                        yield Input(
                            "search term example",
                            id="sample-query",
                            classes="search-term-input",
                            placeholder="Search term",
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
                            classes="results-header",
                        )
                        yield ResultsArea(
                            log_kind=_SAMPLE_KIND,
                            id="syntax-preview",
                            classes="result-log",
                        )
                yield Static("", id="status")
                yield Static("", id="meta")
                with Horizontal(id="preview-buttons"):
                    yield Static(
                        "",
                        id="swatch-top-action",
                        classes="sample-swatch",
                    )
                    yield Static(
                        "",
                        id="swatch-primary",
                        classes="sample-swatch",
                    )
                    yield Static(
                        "",
                        id="swatch-accent",
                        classes="sample-swatch",
                    )
                yield Static("", id="swatch-values")
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
            self._update_swatches(loaded_theme)
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
            self._set_meta(
                f"Store dir: {self.store_dir} | Profile: {self.profile} | "
                f"{self._ansi_label()}"
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
        try:
            palette = parse_terminal_palette(self.current_source)
            self.current_source_theme_name = palette.name
            preview_name = self._next_preview_theme_name()
            preview_theme = map_terminal_palette(
                name=preview_name,
                palette=palette,
                profile=self.profile,
                overrides=None,
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
        self._set_meta(
            f"Source: {self.current_source} | Profile: {self.profile} | "
            f"{self._ansi_label()} | Save dir: {self.store_dir} | "
            f"primary={preview_theme.primary} accent={preview_theme.accent}"
        )
        self._update_swatches(preview_theme)
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

    def _set_meta(self, message: str) -> None:
        meta = self.query_one("#meta", Static)
        meta.update(message)

    def _ansi_label(self) -> str:
        if self.quantize_ansi256:
            return "ANSI-256: On"
        return "ANSI-256: Off"

    def _update_swatches(self, preview_theme: Theme) -> None:
        top_action = (
            preview_theme.variables.get("top-action-background")
            or preview_theme.panel
        )
        top_action_fg = (
            preview_theme.variables.get("top-action-mnemonic-foreground")
            or preview_theme.foreground
        )

        top = self.query_one("#swatch-top-action", Static)
        top.styles.background = top_action
        top.styles.color = top_action_fg
        top.update(f"Top Action {top_action}")

        primary = self.query_one("#swatch-primary", Static)
        primary.styles.background = preview_theme.primary
        primary.styles.color = _best_text_color(preview_theme.primary)
        primary.update("Primary")

        accent = self.query_one("#swatch-accent", Static)
        accent.styles.background = preview_theme.accent
        accent.styles.color = _best_text_color(preview_theme.accent)
        accent.update("Accent")

        values = self.query_one("#swatch-values", Static)
        values.update(
            " | ".join(
                (
                    f"Top Action: {top_action}",
                    f"Primary: {preview_theme.primary}",
                    f"Accent: {preview_theme.accent}",
                )
            )
        )

    def _selected_theme_name(self) -> str:
        name_input = self.query_one("#save-name", Input)
        value = name_input.value.strip()
        if value:
            return value
        if self.current_source_theme_name:
            return self._default_save_name(self.current_source_theme_name)
        return "Converted Theme"

    def _default_save_name(self, source_theme_name: str) -> str:
        normalized = source_theme_name.strip()
        if not normalized:
            return "Converted Theme"
        if normalized.lower().startswith("converted "):
            return normalized
        return f"Converted {normalized}"


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


def _best_text_color(background: str) -> str:
    try:
        triplet = Color.parse(background).get_truecolor()
    except Exception:
        return "#ffffff"
    if _relative_luminance(triplet) > 0.5:
        return "#000000"
    return "#ffffff"


def _relative_luminance(color: ColorTriplet) -> float:
    return (
        (0.2126 * _linear_channel(color.red))
        + (0.7152 * _linear_channel(color.green))
        + (0.0722 * _linear_channel(color.blue))
    )


def _linear_channel(channel: int) -> float:
    scaled = channel / 255
    if scaled <= 0.03928:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


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
