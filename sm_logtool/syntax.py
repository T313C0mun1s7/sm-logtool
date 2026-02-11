"""Syntax highlighting helpers for log output."""

from __future__ import annotations

import re

from rich.text import Text


STYLE_HEADER = "bold"
STYLE_SECTION = "bold"
STYLE_SUMMARY = "bold"
STYLE_TERM = "bold magenta"
STYLE_TIMESTAMP = "bold cyan"
STYLE_BRACKET = "dim"
STYLE_IP = "bright_blue"
STYLE_ID = "magenta"
STYLE_TAG = "cyan"
STYLE_EMAIL = "bright_magenta"
STYLE_COMMAND = "green"
STYLE_RESPONSE = "yellow"
STYLE_LINE_NUMBER = "dim"
STYLE_MESSAGE_ID = "bright_cyan"


_TIME_START = re.compile(
    r"^(?P<time>\d{2}:\d{2}:\d{2}(?:\.\d{3})?)"
)
_LINE_NUMBER = re.compile(r"^(?P<line>\d+):\s+")
_BRACKET_FIELD = re.compile(r"\[(?P<field>[^\]]*)\]")
_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_MESSAGE_ID = re.compile(r"<[^>]+>")
_CMD_RSP = re.compile(r"\b(cmd|rsp):", re.IGNORECASE)
_SMTP_VERB = re.compile(
    r"\b(?:EHLO|HELO|DATA|AUTH|RSET|NOOP|QUIT|STARTTLS|"
    r"VRFY|EXPN)\b|MAIL FROM|RCPT TO",
    re.IGNORECASE,
)
_STATUS_CODE = re.compile(r"(?<!\d)([245]\d{2})(?=[ -])")
_BRACKET_TAG = re.compile(r"\[[A-Za-z][^\]]*\]")


def highlight_result_line(kind: str, line: str) -> Text:
    """Return a Rich Text line with syntax styling applied."""

    stripped = line.strip()
    if not stripped:
        return Text("")

    if line.startswith("===") and line.endswith("==="):
        return _style_file_header(line)

    if line.startswith("Search term "):
        return _style_summary(line)

    if line.startswith("Lines without message identifiers"):
        return _style_label(line)

    if line.startswith("[") and "first seen on line" in line:
        return _style_section(line)

    match = _LINE_NUMBER.match(line)
    if match:
        prefix = line[: match.end()]
        remainder = line[match.end():]
        text = Text(prefix)
        text.stylize(STYLE_LINE_NUMBER, 0, len(prefix))
        text.append(highlight_log_line(kind, remainder))
        return text

    return highlight_log_line(kind, line)


def highlight_log_line(kind: str, line: str) -> Text:
    """Highlight a formatted log line with structural tokens."""

    _ = kind
    time_match = _TIME_START.match(line)
    if not time_match:
        text = Text(line)
        _stylize_message(text)
        return text

    text = Text()
    time_end = time_match.end("time")
    text.append(line[:time_end], style=STYLE_TIMESTAMP)
    pos = time_match.end()
    fields, message_start = _leading_bracket_fields(line, pos)
    text.append(line[time_end:fields[0][0]] if fields else line[time_end:pos])

    for idx, (start, end, field_start, field_end) in enumerate(fields):
        text.append("[", style=STYLE_BRACKET)
        field_value = line[field_start:field_end]
        style = _field_style(field_value)
        text.append(field_value, style=style)
        text.append("]", style=STYLE_BRACKET)
        pos = end
        if idx + 1 < len(fields):
            next_start = fields[idx + 1][0]
            text.append(line[pos:next_start])
            pos = next_start

    if message_start > pos:
        text.append(line[pos:message_start])
    message_text = Text(line[message_start:])
    _stylize_message(message_text)
    text.append(message_text)
    return text


def _leading_bracket_fields(
    line: str,
    pos: int,
) -> tuple[list[tuple[int, int, int, int]], int]:
    fields: list[tuple[int, int, int, int]] = []
    length = len(line)
    cursor = pos

    while cursor < length:
        while cursor < length and line[cursor] == " ":
            cursor += 1
        if cursor >= length or line[cursor] != "[":
            break
        match = _BRACKET_FIELD.match(line, cursor)
        if not match:
            break
        fields.append(
            (
                match.start(),
                match.end(),
                match.start("field"),
                match.end("field"),
            )
        )
        cursor = match.end()

    message_start = cursor
    while message_start < length and line[message_start] == " ":
        message_start += 1
    return fields, message_start


def _field_style(value: str) -> str:
    if _IP.fullmatch(value):
        return STYLE_IP
    if _EMAIL.fullmatch(value):
        return STYLE_EMAIL
    if value.isdigit():
        return STYLE_ID
    return STYLE_TAG


def _stylize_message(text: Text) -> None:
    for pattern, style in (
        (_CMD_RSP, STYLE_COMMAND),
        (_SMTP_VERB, STYLE_COMMAND),
        (_STATUS_CODE, STYLE_RESPONSE),
        (_EMAIL, STYLE_EMAIL),
        (_IP, STYLE_IP),
        (_MESSAGE_ID, STYLE_MESSAGE_ID),
        (_BRACKET_TAG, STYLE_TAG),
    ):
        _apply_regex(text, pattern, style)


def _apply_regex(text: Text, pattern: re.Pattern[str], style: str) -> None:
    for match in pattern.finditer(text.plain):
        start, end = match.span(0)
        if start == end:
            continue
        text.stylize(style, start, end)


def _style_file_header(line: str) -> Text:
    text = Text(line)
    text.stylize(STYLE_HEADER, 0, len(line))
    match = re.match(r"^===\s+(?P<name>.+?)\s+===$", line)
    if match:
        text.stylize(STYLE_TAG, match.start("name"), match.end("name"))
    return text


def _style_summary(line: str) -> Text:
    text = Text(line)
    text.stylize(STYLE_SUMMARY, 0, len(line))
    match = re.search(r"'([^']+)'", line)
    if match:
        text.stylize(STYLE_TERM, match.start(1), match.end(1))
    return text


def _style_label(line: str) -> Text:
    text = Text(line)
    text.stylize(STYLE_SECTION, 0, len(line))
    return text


def _style_section(line: str) -> Text:
    text = Text(line)
    text.stylize(STYLE_SECTION, 0, len(line))
    for match in _BRACKET_FIELD.finditer(line):
        text.stylize(STYLE_BRACKET, match.start(), match.start() + 1)
        text.stylize(
            STYLE_MESSAGE_ID,
            match.start("field"),
            match.end("field"),
        )
        text.stylize(STYLE_BRACKET, match.end() - 1, match.end())
    return text
