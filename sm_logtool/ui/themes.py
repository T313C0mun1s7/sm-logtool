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
    "action-button-background": "#2a2a2a",
    "action-button-foreground": "#f2f5f7",
    "action-button-hover-background": "#3a3a3a",
    "action-button-focus-background": "#4a4a4a",
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
        "top-action-background": "#1c0c2e",
        "top-action-hover-background": "#2a1451",
        "top-action-mnemonic-foreground": "#32f7ff",
        "selection-selected-background": "#201632",
        "selection-selected-foreground": "#f3f8ff",
        "selection-active-background": "#8b2cff",
        "selection-active-foreground": "#f6fcff",
        "selection-selected-active-background": "#00d5ff",
        "selection-selected-active-foreground": "#081423",
        "action-button-background": "#2a1451",
        "action-button-foreground": "#f8ecff",
        "action-button-hover-background": "#4b1f82",
        "action-button-focus-background": "#00bfe5",
        "context-menu-background": "#0e0e0e",
        "context-menu-border": "#8b2cff",
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
    background="#ececec",
    surface="#dedede",
    panel="#d4d4d4",
    dark=False,
    variables={
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": "#d6d6d6",
        "top-action-background": "#c4c4c4",
        "top-action-hover-background": "#b6b6b6",
        "top-action-mnemonic-foreground": "#8b2cff",
        "selection-selected-background": "#cfcfcf",
        "selection-selected-foreground": "#12263f",
        "selection-active-background": "#0079bf",
        "selection-active-foreground": "#ffffff",
        "selection-selected-active-background": "#0f95e0",
        "selection-selected-active-foreground": "#081a2f",
        "action-button-background": "#bf8fff",
        "action-button-foreground": "#1d1033",
        "action-button-hover-background": "#9de9ff",
        "action-button-focus-background": "#ff89d9",
        "context-menu-background": "#e2e2e2",
        "context-menu-border": "#8f63ff",
    },
)

FIRST_PARTY_APP_THEMES = (CYBERDARK_THEME, CYBERNOTDARK_THEME)


def _cyberdark_syntax_styles() -> dict[str, Style]:
    styles = dict(TOKEN_STYLES)
    styles.update(
        {
            TOKEN_TERM: Style(color="#ff5edc", bold=True),
            TOKEN_TIMESTAMP: Style(color="#32f7ff", bold=True),
            TOKEN_BRACKET: Style(color="#7a8491"),
            TOKEN_IP: Style(color="#45b5ff"),
            TOKEN_ID: Style(color="#c78bff"),
            TOKEN_TAG: Style(color="#32f7ff"),
            TOKEN_EMAIL: Style(color="#ff75bd"),
            TOKEN_COMMAND: Style(color="#4cff8a"),
            TOKEN_RESPONSE: Style(color="#ffc759"),
            TOKEN_LINE_NUMBER: Style(color="#7a8491"),
            TOKEN_MESSAGE_ID: Style(color="#00d5ff"),
            TOKEN_STATUS_BAD: Style(color="#ff6b81", bold=True),
            TOKEN_STATUS_GOOD: Style(color="#52ffa8", bold=True),
        }
    )
    return styles


def _cybernotdark_syntax_styles() -> dict[str, Style]:
    styles = _cyberdark_syntax_styles()
    styles.update(
        {
            # Keep the same vivid token family and only tweak utility tokens
            # that lose contrast on lighter backgrounds.
            TOKEN_BRACKET: Style(color="#607d8b"),
            TOKEN_LINE_NUMBER: Style(color="#607d8b"),
        }
    )
    return styles


RESULTS_THEME_DARK = TextAreaTheme(
    name=RESULTS_THEME_DARK_NAME,
    base_style=Style(color="#e8f2ff", bgcolor="#000000"),
    cursor_line_style=Style(bgcolor="#171717"),
    selection_style=Style(bgcolor="#2a1451"),
    syntax_styles=_cyberdark_syntax_styles(),
)

RESULTS_THEME_LIGHT = TextAreaTheme(
    name=RESULTS_THEME_LIGHT_NAME,
    base_style=Style(color="#10233b", bgcolor="#ececec"),
    cursor_line_style=Style(bgcolor="#d4d4d4"),
    selection_style=Style(bgcolor="#b4b4b4"),
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
