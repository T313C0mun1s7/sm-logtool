"""Shared syntax highlighting styles for CLI and TUI output."""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from .syntax import (
    TOKEN_BRACKET,
    TOKEN_COMMAND,
    TOKEN_EMAIL,
    TOKEN_HEADER,
    TOKEN_ID,
    TOKEN_IP,
    TOKEN_LINE_NUMBER,
    TOKEN_MESSAGE_ID,
    TOKEN_PROTO_ACTIVESYNC,
    TOKEN_PROTO_API,
    TOKEN_PROTO_CALDAV,
    TOKEN_PROTO_CARDDAV,
    TOKEN_PROTO_EAS,
    TOKEN_PROTO_IMAP,
    TOKEN_PROTO_POP,
    TOKEN_PROTO_SMTP,
    TOKEN_PROTO_USER,
    TOKEN_PROTO_WEBMAIL,
    TOKEN_PROTO_XMPP,
    TOKEN_RESPONSE,
    TOKEN_SECTION,
    TOKEN_STATUS_BAD,
    TOKEN_STATUS_GOOD,
    TOKEN_SUMMARY,
    TOKEN_TAG,
    TOKEN_TERM,
    TOKEN_TIMESTAMP,
    spans_for_line,
)

TOKEN_STYLES: dict[str, Style] = {
    TOKEN_HEADER: Style(bold=True),
    TOKEN_SECTION: Style(bold=True),
    TOKEN_SUMMARY: Style(bold=True),
    TOKEN_TERM: Style(color="magenta", bold=True),
    TOKEN_TIMESTAMP: Style(color="cyan", bold=True),
    TOKEN_BRACKET: Style(dim=True),
    TOKEN_IP: Style(color="bright_blue"),
    TOKEN_ID: Style(color="magenta"),
    TOKEN_TAG: Style(color="cyan"),
    TOKEN_EMAIL: Style(color="bright_magenta"),
    TOKEN_COMMAND: Style(color="green"),
    TOKEN_RESPONSE: Style(color="yellow"),
    TOKEN_LINE_NUMBER: Style(dim=True),
    TOKEN_MESSAGE_ID: Style(color="bright_cyan"),
    TOKEN_STATUS_BAD: Style(color="bright_red", bold=True),
    TOKEN_STATUS_GOOD: Style(color="bright_green", bold=True),
    TOKEN_PROTO_SMTP: Style(color="#7bd88f", bold=True),
    TOKEN_PROTO_IMAP: Style(color="#4aa3ff", bold=True),
    TOKEN_PROTO_POP: Style(color="#ffcc66", bold=True),
    TOKEN_PROTO_USER: Style(color="#ff8ec7", bold=True),
    TOKEN_PROTO_WEBMAIL: Style(color="#6be0ff", bold=True),
    TOKEN_PROTO_ACTIVESYNC: Style(color="#ff6b6b", bold=True),
    TOKEN_PROTO_EAS: Style(color="#ffd166", bold=True),
    TOKEN_PROTO_CALDAV: Style(color="#8b7bff", bold=True),
    TOKEN_PROTO_CARDDAV: Style(color="#b388ff", bold=True),
    TOKEN_PROTO_XMPP: Style(color="#4ef0b7", bold=True),
    TOKEN_PROTO_API: Style(color="#ff9f1c", bold=True),
}


def highlight_line(kind: str, line: str) -> Text:
    """Return a Rich ``Text`` line with SmarterMail syntax highlighting."""

    text = Text(line)
    limit = len(line)
    for span in spans_for_line(kind, line):
        style = TOKEN_STYLES.get(span.token)
        if style is None:
            continue
        start = _clamp(span.start, limit)
        end = _clamp(span.end, limit)
        if start >= end:
            continue
        text.stylize(style, start, end)
    return text


def _clamp(value: int, upper: int) -> int:
    if value < 0:
        return 0
    if value > upper:
        return upper
    return value
