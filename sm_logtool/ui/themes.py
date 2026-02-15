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
    background="#000000",
    surface="#0b0b0b",
    panel="#141414",
    dark=True,
    variables={
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": "#000000",
        "top-action-background": "#121212",
        "top-action-hover-background": "#1f1f1f",
        "top-action-mnemonic-foreground": "#ffd166",
        "selection-selected-background": "#1e1e1e",
        "selection-selected-foreground": "#f3f8ff",
        "selection-active-background": "#005e9a",
        "selection-active-foreground": "#f6fcff",
        "selection-selected-active-background": "#22b8f2",
        "selection-selected-active-foreground": "#081423",
        "context-menu-background": "#0e0e0e",
        "context-menu-border": "#2b2b2b",
    },
)

CYBERNOTDARK_THEME = Theme(
    name=CYBERNOTDARK_THEME_NAME,
    primary="#0088cc",
    secondary="#8f63ff",
    warning="#9b5b00",
    error="#bf1842",
    success="#007f4f",
    accent="#d238c2",
    foreground="#10233b",
    background="#ebeff3",
    surface="#dfe6ed",
    panel="#d6e0ea",
    dark=False,
    variables={
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": "#d6e0ea",
        "top-action-background": "#c5d3e0",
        "top-action-hover-background": "#b1c4d8",
        "top-action-mnemonic-foreground": "#8a4b00",
        "selection-selected-background": "#c2d4e8",
        "selection-selected-foreground": "#12263f",
        "selection-active-background": "#0079bf",
        "selection-active-foreground": "#ffffff",
        "selection-selected-active-background": "#0f95e0",
        "selection-selected-active-foreground": "#081a2f",
        "context-menu-background": "#e1e8ef",
        "context-menu-border": "#7f97af",
    },
)

FIRST_PARTY_APP_THEMES = (CYBERDARK_THEME, CYBERNOTDARK_THEME)


def _cybernotdark_syntax_styles() -> dict[str, Style]:
    styles = dict(TOKEN_STYLES)
    styles.update(
        {
            # Keep the same vivid token family and only tweak low-contrast
            # utility tokens for light backgrounds.
            TOKEN_BRACKET: Style(color="#607d8b"),
            TOKEN_LINE_NUMBER: Style(color="#607d8b"),
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
    base_style=Style(color="#10233b", bgcolor="#ebeff3"),
    cursor_line_style=Style(bgcolor="#d6e0ea"),
    selection_style=Style(bgcolor="#b1c4d8"),
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
