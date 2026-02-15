"""First-party Textual themes used by the TUI."""

from __future__ import annotations

from rich.style import Style
from textual._text_area_theme import TextAreaTheme
from textual.theme import Theme

from ..highlighting import TOKEN_STYLES
from ..syntax import TOKEN_BRACKET
from ..syntax import TOKEN_COMMAND
from ..syntax import TOKEN_EMAIL
from ..syntax import TOKEN_ID
from ..syntax import TOKEN_IP
from ..syntax import TOKEN_LINE_NUMBER
from ..syntax import TOKEN_MESSAGE_ID
from ..syntax import TOKEN_RESPONSE
from ..syntax import TOKEN_STATUS_BAD
from ..syntax import TOKEN_STATUS_GOOD
from ..syntax import TOKEN_TAG
from ..syntax import TOKEN_TERM
from ..syntax import TOKEN_TIMESTAMP

CYBERDARK_THEME_NAME = "Cyberdark"
CYBERNOTDARK_THEME_NAME = "Cybernotdark"

RESULTS_THEME_DARK_NAME = "smlog-cyberdark"
RESULTS_THEME_LIGHT_NAME = "smlog-cybernotdark"
RESULTS_THEME_DEFAULT_NAME = "smlog-default"

CYBER_THEME_VARIABLE_DEFAULTS: dict[str, str] = {
    "top-actions-background": "#1f1f1f",
    "top-action-background": "#333333",
    "top-action-hover-background": "#4a4a4a",
    "top-action-mnemonic-foreground": "#ffd75f",
    "selection-selected-background": "#444444",
    "selection-selected-foreground": "yellow",
    "selection-active-background": "#005f87",
    "selection-active-foreground": "white",
    "selection-selected-active-background": "#1b98d3",
    "selection-selected-active-foreground": "black",
    "context-menu-background": "#1f1f1f",
    "context-menu-border": "#5f5f5f",
}

CYBERDARK_THEME = Theme(
    name=CYBERDARK_THEME_NAME,
    primary="#00a8e8",
    secondary="#ab82ff",
    warning="#f2c14e",
    error="#ff6b81",
    success="#64f9a8",
    accent="#ff7ad9",
    foreground="#e8f2ff",
    background="#0a111f",
    surface="#111b31",
    panel="#15233d",
    dark=True,
    variables={
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": "#101726",
        "top-action-background": "#1a2b47",
        "top-action-hover-background": "#24406a",
        "top-action-mnemonic-foreground": "#ffd166",
        "selection-selected-background": "#24344f",
        "selection-selected-foreground": "#f3f8ff",
        "selection-active-background": "#00639f",
        "selection-active-foreground": "#f6fcff",
        "selection-selected-active-background": "#2ec4ff",
        "selection-selected-active-foreground": "#081423",
        "context-menu-background": "#111a2b",
        "context-menu-border": "#2f4f78",
    },
)

CYBERNOTDARK_THEME = Theme(
    name=CYBERNOTDARK_THEME_NAME,
    primary="#005f87",
    secondary="#7653c1",
    warning="#8a5a00",
    error="#b00020",
    success="#1b7f3b",
    accent="#9c27b0",
    foreground="#10233b",
    background="#f4f8ff",
    surface="#e9effb",
    panel="#dce7f6",
    dark=False,
    variables={
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": "#dce7f6",
        "top-action-background": "#c8d9f2",
        "top-action-hover-background": "#b7cde9",
        "top-action-mnemonic-foreground": "#8a4b00",
        "selection-selected-background": "#ccddf2",
        "selection-selected-foreground": "#12263f",
        "selection-active-background": "#0068a6",
        "selection-active-foreground": "#ffffff",
        "selection-selected-active-background": "#1ea0e6",
        "selection-selected-active-foreground": "#081a2f",
        "context-menu-background": "#eef4ff",
        "context-menu-border": "#89a6cb",
    },
)

FIRST_PARTY_APP_THEMES = (CYBERDARK_THEME, CYBERNOTDARK_THEME)


def _cybernotdark_syntax_styles() -> dict[str, Style]:
    styles = dict(TOKEN_STYLES)
    styles.update(
        {
            TOKEN_TERM: Style(color="#7b1fa2", bold=True),
            TOKEN_TIMESTAMP: Style(color="#006f8e", bold=True),
            TOKEN_BRACKET: Style(color="#546e7a"),
            TOKEN_IP: Style(color="#1565c0"),
            TOKEN_ID: Style(color="#8e24aa"),
            TOKEN_TAG: Style(color="#006f8e"),
            TOKEN_EMAIL: Style(color="#a62f6f"),
            TOKEN_COMMAND: Style(color="#2e7d32"),
            TOKEN_RESPONSE: Style(color="#8a5a00"),
            TOKEN_LINE_NUMBER: Style(color="#546e7a"),
            TOKEN_MESSAGE_ID: Style(color="#006f8e"),
            TOKEN_STATUS_BAD: Style(color="#b00020", bold=True),
            TOKEN_STATUS_GOOD: Style(color="#1b7f3b", bold=True),
        }
    )
    return styles


RESULTS_THEME_DARK = TextAreaTheme(
    name=RESULTS_THEME_DARK_NAME,
    base_style=Style(color="#e8f2ff", bgcolor="#0a111f"),
    cursor_line_style=Style(bgcolor="#111b31"),
    selection_style=Style(bgcolor="#24406a"),
    syntax_styles=dict(TOKEN_STYLES),
)

RESULTS_THEME_LIGHT = TextAreaTheme(
    name=RESULTS_THEME_LIGHT_NAME,
    base_style=Style(color="#10233b", bgcolor="#f4f8ff"),
    cursor_line_style=Style(bgcolor="#dce7f6"),
    selection_style=Style(bgcolor="#b7cde9"),
    syntax_styles=_cybernotdark_syntax_styles(),
)

RESULTS_THEME_DEFAULT = TextAreaTheme(
    name=RESULTS_THEME_DEFAULT_NAME,
    syntax_styles=dict(TOKEN_STYLES),
)

FIRST_PARTY_RESULTS_THEMES = (
    RESULTS_THEME_DARK,
    RESULTS_THEME_LIGHT,
    RESULTS_THEME_DEFAULT,
)

APP_THEME_TO_RESULTS_THEME: dict[str, str] = {
    CYBERDARK_THEME_NAME: RESULTS_THEME_DARK_NAME,
    CYBERNOTDARK_THEME_NAME: RESULTS_THEME_LIGHT_NAME,
    "textual-dark": RESULTS_THEME_DARK_NAME,
    "textual-light": RESULTS_THEME_LIGHT_NAME,
}


def results_theme_for_app_theme(app_theme: str | None) -> str:
    """Return the ResultsArea theme name for a given app theme name."""

    if app_theme is None:
        return RESULTS_THEME_DEFAULT_NAME
    return APP_THEME_TO_RESULTS_THEME.get(
        app_theme,
        RESULTS_THEME_DEFAULT_NAME,
    )
