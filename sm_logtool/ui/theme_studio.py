"""Visual theme conversion utility for sm-logtool."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rich.console import Group
from rich.text import Text
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

from ..syntax import spans_for_line
from .theme_importer import (
    default_theme_source_dir,
    discover_theme_files,
    map_terminal_palette,
    parse_terminal_palette,
    save_converted_theme,
)
from .theme_importer import SUPPORTED_THEME_MAPPING_PROFILES
from .themes import CYBERDARK_THEME
from .themes import FIRST_PARTY_APP_THEMES
from .themes import build_results_theme

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
    }

    #title {
        padding: 1 1;
        text-style: bold;
    }

    #layout {
        height: 1fr;
    }

    #sources {
        width: 36;
        margin: 0 1 1 1;
        border: round $accent;
        padding: 1;
    }

    #preview {
        margin: 0 1 1 0;
        border: round $accent;
        padding: 1;
    }

    #source-list {
        height: 1fr;
        margin-top: 1;
    }

    #controls {
        margin-bottom: 1;
        height: auto;
    }

    #save-name {
        width: 28;
        margin-right: 1;
    }

    .profile-button {
        min-width: 12;
        margin-right: 1;
    }

    .preview-box {
        border: round $primary;
        padding: 1;
        margin-top: 1;
        height: auto;
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
        min-width: 18;
        padding: 0 1;
        border: round $panel;
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
                    yield Button(ansi_label, id="toggle-ansi")
                    yield Input(
                        "",
                        id="save-name",
                        placeholder="Theme name",
                    )
                    yield Button("Save", id="save-theme")
                    yield Button("Quit", id="quit-studio")

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
                yield Static("", id="syntax-preview", classes="preview-box")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = CYBERDARK_THEME.name
        self._update_profile_button_states()
        self._load_sources()

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
        self._set_status(f"Saved converted theme: {path}")

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
            else:
                button.variant = "default"

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
            preview_name = "Theme Studio Preview"
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
            name_input.value = palette.name

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

    def _set_syntax_preview(self, preview_theme) -> None:
        syntax_theme = build_results_theme(preview_theme)
        styles = syntax_theme.syntax_styles
        lines: list[Text] = []
        for line in _SAMPLE_LINES:
            rendered = Text(line)
            limit = len(line)
            for span in spans_for_line(_SAMPLE_KIND, line):
                style = styles.get(span.token)
                if style is None:
                    continue
                start = max(0, min(limit, span.start))
                end = max(0, min(limit, span.end))
                if start >= end:
                    continue
                rendered.stylize(style, start, end)
            lines.append(rendered)
        preview = self.query_one("#syntax-preview", Static)
        preview.update(Group(*lines))

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
        primary_fg = (
            preview_theme.variables.get("selection-active-foreground")
            or preview_theme.foreground
        )
        accent_fg = (
            preview_theme.variables.get("selection-selected-foreground")
            or preview_theme.foreground
        )

        top = self.query_one("#swatch-top-action", Static)
        top.styles.background = top_action
        top.styles.color = top_action_fg
        top.update(f"Top Action {top_action}")

        primary = self.query_one("#swatch-primary", Static)
        primary.styles.background = preview_theme.primary
        primary.styles.color = primary_fg
        primary.update(f"Primary {preview_theme.primary}")

        accent = self.query_one("#swatch-accent", Static)
        accent.styles.background = preview_theme.accent
        accent.styles.color = accent_fg
        accent.update(f"Accent {preview_theme.accent}")

    def _selected_theme_name(self) -> str:
        name_input = self.query_one("#save-name", Input)
        value = name_input.value.strip()
        if value:
            return value
        if self.current_source_theme_name:
            return self.current_source_theme_name
        return "Imported Theme"


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
