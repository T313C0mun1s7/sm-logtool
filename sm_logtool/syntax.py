"""Syntax tokenization for SmarterMail log highlighting."""

from __future__ import annotations

from dataclasses import dataclass
import re

TOKEN_HEADER = "header"
TOKEN_SECTION = "section"
TOKEN_SUMMARY = "summary"
TOKEN_TERM = "term"
TOKEN_TIMESTAMP = "timestamp"
TOKEN_BRACKET = "bracket"
TOKEN_IP = "ip"
TOKEN_ID = "id"
TOKEN_TAG = "tag"
TOKEN_EMAIL = "email"
TOKEN_COMMAND = "command"
TOKEN_RESPONSE = "response"
TOKEN_LINE_NUMBER = "line_number"
TOKEN_MESSAGE_ID = "message_id"

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


@dataclass(frozen=True)
class HighlightSpan:
    """A highlighted span for a single line."""

    start: int
    end: int
    token: str


def spans_for_line(kind: str, line: str) -> list[HighlightSpan]:
    """Return highlight spans for a log line."""

    _ = kind
    stripped = line.strip()
    if not stripped:
        return []

    if line.startswith("===") and line.endswith("==="):
        return _header_spans(line)

    if line.startswith("Search term "):
        return _summary_spans(line)

    if line.startswith("Lines without message identifiers"):
        return [HighlightSpan(0, len(line), TOKEN_SECTION)]

    if line.startswith("[") and "first seen on line" in line:
        return _section_spans(line)

    line_match = _LINE_NUMBER.match(line)
    if line_match:
        spans = [
            HighlightSpan(0, line_match.end(), TOKEN_LINE_NUMBER),
        ]
        spans.extend(
            _log_line_spans(line[line_match.end():], line_match.end())
        )
        return spans

    return _log_line_spans(line, 0)


def _header_spans(line: str) -> list[HighlightSpan]:
    spans = [HighlightSpan(0, len(line), TOKEN_HEADER)]
    match = re.match(r"^===\s+(?P<name>.+?)\s+===$", line)
    if match:
        spans.append(
            HighlightSpan(
                match.start("name"),
                match.end("name"),
                TOKEN_TAG,
            )
        )
    return spans


def _summary_spans(line: str) -> list[HighlightSpan]:
    spans = [HighlightSpan(0, len(line), TOKEN_SUMMARY)]
    match = re.search(r"'([^']+)'", line)
    if match:
        spans.append(
            HighlightSpan(
                match.start(1),
                match.end(1),
                TOKEN_TERM,
            )
        )
    return spans


def _section_spans(line: str) -> list[HighlightSpan]:
    spans = [HighlightSpan(0, len(line), TOKEN_SECTION)]
    for match in _BRACKET_FIELD.finditer(line):
        spans.append(
            HighlightSpan(match.start(), match.start() + 1, TOKEN_BRACKET)
        )
        spans.append(
            HighlightSpan(
                match.start("field"),
                match.end("field"),
                TOKEN_MESSAGE_ID,
            )
        )
        spans.append(
            HighlightSpan(match.end() - 1, match.end(), TOKEN_BRACKET)
        )
    return spans


def _log_line_spans(line: str, offset: int) -> list[HighlightSpan]:
    spans: list[HighlightSpan] = []
    time_match = _TIME_START.match(line)
    if not time_match:
        spans.extend(_message_spans(line, offset))
        return spans

    spans.append(
        HighlightSpan(
            offset + time_match.start("time"),
            offset + time_match.end("time"),
            TOKEN_TIMESTAMP,
        )
    )
    pos = time_match.end()
    fields, message_start = _leading_bracket_fields(line, pos)
    for start, end, field_start, field_end in fields:
        spans.append(
            HighlightSpan(
                offset + start,
                offset + start + 1,
                TOKEN_BRACKET,
            )
        )
        value = line[field_start:field_end]
        spans.append(
            HighlightSpan(
                offset + field_start,
                offset + field_end,
                _field_token(value),
            )
        )
        spans.append(
            HighlightSpan(
                offset + end - 1,
                offset + end,
                TOKEN_BRACKET,
            )
        )
    spans.extend(_message_spans(line[message_start:], offset + message_start))
    return spans


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


def _field_token(value: str) -> str:
    if _IP.fullmatch(value):
        return TOKEN_IP
    if _EMAIL.fullmatch(value):
        return TOKEN_EMAIL
    if value.isdigit():
        return TOKEN_ID
    return TOKEN_TAG


def _message_spans(line: str, offset: int) -> list[HighlightSpan]:
    spans: list[HighlightSpan] = []
    for pattern, token in (
        (_CMD_RSP, TOKEN_COMMAND),
        (_SMTP_VERB, TOKEN_COMMAND),
        (_STATUS_CODE, TOKEN_RESPONSE),
        (_EMAIL, TOKEN_EMAIL),
        (_IP, TOKEN_IP),
        (_MESSAGE_ID, TOKEN_MESSAGE_ID),
        (_BRACKET_TAG, TOKEN_TAG),
    ):
        spans.extend(_regex_spans(pattern, line, token, offset))
    return spans


def _regex_spans(
    pattern: re.Pattern[str],
    line: str,
    token: str,
    offset: int,
) -> list[HighlightSpan]:
    spans: list[HighlightSpan] = []
    for match in pattern.finditer(line):
        start, end = match.span(0)
        if start == end:
            continue
        spans.append(HighlightSpan(offset + start, offset + end, token))
    return spans
