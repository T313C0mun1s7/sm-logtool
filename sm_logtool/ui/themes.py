"""First-party Textual themes used by the TUI."""

from __future__ import annotations

from rich.color import Color
from rich.color_triplet import ColorTriplet
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
from ..syntax import TOKEN_PROTO_ACTIVESYNC
from ..syntax import TOKEN_PROTO_API
from ..syntax import TOKEN_PROTO_CALDAV
from ..syntax import TOKEN_PROTO_CARDDAV
from ..syntax import TOKEN_PROTO_EAS
from ..syntax import TOKEN_PROTO_IMAP
from ..syntax import TOKEN_PROTO_POP
from ..syntax import TOKEN_PROTO_SMTP
from ..syntax import TOKEN_PROTO_USER
from ..syntax import TOKEN_PROTO_WEBMAIL
from ..syntax import TOKEN_PROTO_XMPP
from ..syntax import TOKEN_RESPONSE
from ..syntax import TOKEN_STATUS_BAD
from ..syntax import TOKEN_STATUS_GOOD
from ..syntax import TOKEN_TAG
from ..syntax import TOKEN_TERM
from ..syntax import TOKEN_TIMESTAMP

CYBERDARK_THEME_NAME = "Cyberdark"
CYBERNOTDARK_THEME_NAME = "Cybernotdark"

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
    foreground="#32f7ff",
    background="#005f00",
    surface="#005f00",
    panel="#000000",
    dark=True,
    variables={
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": "#005f00",
        "top-action-background": "#87005f",
        "top-action-hover-background": "#af005f",
        "top-action-mnemonic-foreground": "#32f7ff",
        "selection-selected-background": "#87005f",
        "selection-selected-foreground": "#f3f8ff",
        "selection-active-background": "#af005f",
        "selection-active-foreground": "#f6fcff",
        "selection-selected-active-background": "#d700af",
        "selection-selected-active-foreground": "#1a0a1f",
        "action-button-background": "#c78bff",
        "action-button-foreground": "#1a0a1f",
        "action-button-hover-background": "#ff4fd8",
        "action-button-focus-background": "#ff4fd8",
        "context-menu-background": "#0e0e0e",
        "context-menu-border": "#af00af",
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
    background="#8deeee",
    surface="#8deeee",
    panel="#ffffe0",
    dark=False,
    variables={
        **CYBER_THEME_VARIABLE_DEFAULTS,
        "top-actions-background": "#8deeee",
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

_WHITE = ColorTriplet(255, 255, 255)
_BLACK = ColorTriplet(0, 0, 0)
_DEFAULT_DARK_FG = ColorTriplet(232, 242, 255)
_DEFAULT_LIGHT_FG = ColorTriplet(16, 35, 59)
_DEFAULT_DARK_BG = ColorTriplet(18, 18, 18)
_DEFAULT_LIGHT_BG = ColorTriplet(244, 244, 244)


def _parse_triplet(
    value: str | None,
    fallback: ColorTriplet,
) -> ColorTriplet:
    if not value:
        return fallback
    try:
        parsed = Color.parse(value)
    except Exception:
        return fallback
    return parsed.get_truecolor()


def _as_hex(color: ColorTriplet) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        color.red,
        color.green,
        color.blue,
    )


def _blend(
    start: ColorTriplet,
    end: ColorTriplet,
    amount: float,
) -> ColorTriplet:
    weight = max(0.0, min(1.0, amount))
    red = round(start.red + (end.red - start.red) * weight)
    green = round(start.green + (end.green - start.green) * weight)
    blue = round(start.blue + (end.blue - start.blue) * weight)
    return ColorTriplet(red, green, blue)


def _linear_channel(channel: int) -> float:
    scaled = channel / 255
    if scaled <= 0.03928:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


def _luminance(color: ColorTriplet) -> float:
    return (
        (0.2126 * _linear_channel(color.red))
        + (0.7152 * _linear_channel(color.green))
        + (0.0722 * _linear_channel(color.blue))
    )


def _contrast_ratio(left: ColorTriplet, right: ColorTriplet) -> float:
    left_luma = _luminance(left)
    right_luma = _luminance(right)
    light = max(left_luma, right_luma)
    dark = min(left_luma, right_luma)
    return (light + 0.05) / (dark + 0.05)


def _ensure_contrast(
    color: ColorTriplet,
    background: ColorTriplet,
    minimum_ratio: float,
    prefer_light: bool,
) -> ColorTriplet:
    if _contrast_ratio(color, background) >= minimum_ratio:
        return color
    target = _WHITE if prefer_light else _BLACK
    for step in range(1, 21):
        candidate = _blend(color, target, step / 20)
        if _contrast_ratio(candidate, background) >= minimum_ratio:
            return candidate
    return target


def _protocol_styles(
    *,
    primary: ColorTriplet,
    secondary: ColorTriplet,
    accent: ColorTriplet,
    success: ColorTriplet,
    warning: ColorTriplet,
    error: ColorTriplet,
    background: ColorTriplet,
    prefer_light: bool,
) -> dict[str, Style]:
    webmail = _ensure_contrast(
        _blend(primary, accent, 0.35),
        background,
        3.0,
        prefer_light,
    )
    xmpp = _ensure_contrast(
        _blend(success, primary, 0.3),
        background,
        3.0,
        prefer_light,
    )
    api = _ensure_contrast(
        _blend(warning, accent, 0.3),
        background,
        3.0,
        prefer_light,
    )
    return {
        TOKEN_PROTO_SMTP: Style(color=_as_hex(success), bold=True),
        TOKEN_PROTO_IMAP: Style(color=_as_hex(primary), bold=True),
        TOKEN_PROTO_POP: Style(color=_as_hex(warning), bold=True),
        TOKEN_PROTO_USER: Style(color=_as_hex(accent), bold=True),
        TOKEN_PROTO_WEBMAIL: Style(color=_as_hex(webmail), bold=True),
        TOKEN_PROTO_ACTIVESYNC: Style(color=_as_hex(error), bold=True),
        TOKEN_PROTO_EAS: Style(color=_as_hex(warning), bold=True),
        TOKEN_PROTO_CALDAV: Style(color=_as_hex(secondary), bold=True),
        TOKEN_PROTO_CARDDAV: Style(color=_as_hex(secondary), bold=True),
        TOKEN_PROTO_XMPP: Style(color=_as_hex(xmpp), bold=True),
        TOKEN_PROTO_API: Style(color=_as_hex(api), bold=True),
    }


def build_results_theme(theme: Theme) -> TextAreaTheme:
    """Build a readable syntax theme from a Textual app theme palette."""

    background = _parse_triplet(
        theme.surface or theme.panel or theme.background,
        _DEFAULT_DARK_BG if theme.dark else _DEFAULT_LIGHT_BG,
    )
    foreground = _parse_triplet(
        theme.foreground,
        _DEFAULT_DARK_FG if theme.dark else _DEFAULT_LIGHT_FG,
    )
    prefer_light = _luminance(background) < 0.45
    foreground = _ensure_contrast(
        foreground,
        background,
        7.0,
        prefer_light,
    )

    primary = _ensure_contrast(
        _parse_triplet(theme.primary, foreground),
        background,
        3.0,
        prefer_light,
    )
    secondary = _ensure_contrast(
        _parse_triplet(theme.secondary or theme.primary, primary),
        background,
        3.0,
        prefer_light,
    )
    accent = _ensure_contrast(
        _parse_triplet(
            theme.accent or theme.secondary or theme.primary,
            primary,
        ),
        background,
        3.0,
        prefer_light,
    )
    success = _ensure_contrast(
        _parse_triplet(theme.success or theme.primary, primary),
        background,
        3.0,
        prefer_light,
    )
    warning = _ensure_contrast(
        _parse_triplet(theme.warning or theme.accent or theme.primary, accent),
        background,
        3.0,
        prefer_light,
    )
    error = _ensure_contrast(
        _parse_triplet(theme.error or theme.accent or theme.primary, accent),
        background,
        3.0,
        prefer_light,
    )

    muted = _ensure_contrast(
        _blend(foreground, background, 0.55),
        background,
        2.2,
        prefer_light,
    )
    timestamp = _ensure_contrast(
        _blend(primary, foreground, 0.25),
        background,
        3.2,
        prefer_light,
    )
    id_color = _ensure_contrast(
        _blend(secondary, accent, 0.35),
        background,
        3.2,
        prefer_light,
    )
    message_id = _ensure_contrast(
        _blend(primary, accent, 0.45),
        background,
        3.2,
        prefer_light,
    )
    ip = _ensure_contrast(
        _blend(primary, foreground, 0.15),
        background,
        3.0,
        prefer_light,
    )
    email = _ensure_contrast(
        _blend(accent, secondary, 0.35),
        background,
        3.0,
        prefer_light,
    )
    tag = _ensure_contrast(
        _blend(primary, secondary, 0.4),
        background,
        3.0,
        prefer_light,
    )
    cursor_bg = _ensure_contrast(
        _blend(background, primary, 0.25),
        background,
        1.35,
        not prefer_light,
    )
    selection_bg = _ensure_contrast(
        _blend(background, accent, 0.3),
        background,
        1.55,
        not prefer_light,
    )

    syntax_styles = dict(TOKEN_STYLES)
    syntax_styles.update(
        {
            TOKEN_TERM: Style(color=_as_hex(accent), bold=True),
            TOKEN_TIMESTAMP: Style(color=_as_hex(timestamp), bold=True),
            TOKEN_BRACKET: Style(color=_as_hex(muted)),
            TOKEN_IP: Style(color=_as_hex(ip)),
            TOKEN_ID: Style(color=_as_hex(id_color)),
            TOKEN_TAG: Style(color=_as_hex(tag)),
            TOKEN_EMAIL: Style(color=_as_hex(email)),
            TOKEN_COMMAND: Style(color=_as_hex(success)),
            TOKEN_RESPONSE: Style(color=_as_hex(warning)),
            TOKEN_LINE_NUMBER: Style(color=_as_hex(muted)),
            TOKEN_MESSAGE_ID: Style(color=_as_hex(message_id)),
            TOKEN_STATUS_BAD: Style(color=_as_hex(error), bold=True),
            TOKEN_STATUS_GOOD: Style(color=_as_hex(success), bold=True),
        }
    )
    syntax_styles.update(
        _protocol_styles(
            primary=primary,
            secondary=secondary,
            accent=accent,
            success=success,
            warning=warning,
            error=error,
            background=background,
            prefer_light=prefer_light,
        )
    )

    return TextAreaTheme(
        name=theme.name,
        base_style=Style(
            color=_as_hex(foreground),
            bgcolor=_as_hex(background),
        ),
        cursor_line_style=Style(bgcolor=_as_hex(cursor_bg)),
        selection_style=Style(bgcolor=_as_hex(selection_bg)),
        syntax_styles=syntax_styles,
    )


RESULTS_THEME_DEFAULT = TextAreaTheme(
    name=RESULTS_THEME_DEFAULT_NAME,
    syntax_styles=dict(TOKEN_STYLES),
)


def results_theme_name_for_app_theme(app_theme: str | None) -> str:
    """Return the ResultsArea theme name for a given app theme name."""

    if app_theme is None:
        return RESULTS_THEME_DEFAULT_NAME
    return app_theme
