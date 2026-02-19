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
TOKEN_PROTO_SMTP = "proto_smtp"
TOKEN_PROTO_IMAP = "proto_imap"
TOKEN_PROTO_POP = "proto_pop"
TOKEN_PROTO_USER = "proto_user"
TOKEN_PROTO_WEBMAIL = "proto_webmail"
TOKEN_PROTO_ACTIVESYNC = "proto_activesync"
TOKEN_PROTO_EAS = "proto_eas"
TOKEN_PROTO_CALDAV = "proto_caldav"
TOKEN_PROTO_CARDDAV = "proto_carddav"
TOKEN_PROTO_XMPP = "proto_xmpp"
TOKEN_PROTO_API = "proto_api"
TOKEN_STATUS_BAD = "status_bad"
TOKEN_STATUS_GOOD = "status_good"

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
_RSP_STATUS_CODE = re.compile(r"^\s*([1-5]\d{2})(?=[ -]|$)")
_BRACKET_TAG = re.compile(r"\[[A-Za-z][^\]]*\]")
_MESSAGE_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_STATUS_BAD = re.compile(
    r"\b(failure|error|exception|denied|invalid|warning|warn)\b"
    r"|\bfailed(?!\s*:\s*(?:true|false)\b)\b",
    re.IGNORECASE,
)
_STATUS_BLOCKED_OUTCOME = re.compile(
    r"\baction:\s*movetojunk\b"
    r"|\bon their blocked list\b"
    r"|\bmessage blocked\b",
    re.IGNORECASE,
)
_STATUS_GOOD = re.compile(
    r"\b(success|successful|completed)\b",
    re.IGNORECASE,
)

_PROTOCOL_TOKENS = {
    "SMTP": TOKEN_PROTO_SMTP,
    "IMAP": TOKEN_PROTO_IMAP,
    "POP": TOKEN_PROTO_POP,
    "USER": TOKEN_PROTO_USER,
    "WEBMAIL": TOKEN_PROTO_WEBMAIL,
    "ACTIVESYNC": TOKEN_PROTO_ACTIVESYNC,
    "EAS": TOKEN_PROTO_EAS,
    "CALDAV": TOKEN_PROTO_CALDAV,
    "CARDDAV": TOKEN_PROTO_CARDDAV,
    "XMPP": TOKEN_PROTO_XMPP,
    "API": TOKEN_PROTO_API,
}


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
    spans.extend(
        _message_leading_protocol_spans(
            line[message_start:],
            offset + message_start,
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
    spans.extend(_response_code_spans(line, offset))
    for pattern, token in (
        (_CMD_RSP, TOKEN_COMMAND),
        (_SMTP_VERB, TOKEN_COMMAND),
        (_STATUS_BAD, TOKEN_STATUS_BAD),
        (_STATUS_BLOCKED_OUTCOME, TOKEN_STATUS_BAD),
        (_STATUS_GOOD, TOKEN_STATUS_GOOD),
        (_EMAIL, TOKEN_EMAIL),
        (_IP, TOKEN_IP),
        (_MESSAGE_ID, TOKEN_MESSAGE_ID),
        (_BRACKET_TAG, TOKEN_TAG),
    ):
        spans.extend(_regex_spans(pattern, line, token, offset))
    return spans


def _response_code_spans(line: str, offset: int) -> list[HighlightSpan]:
    spans: list[HighlightSpan] = []
    for rsp_match in re.finditer(r"\brsp:\s*", line, re.IGNORECASE):
        payload_start = rsp_match.end()
        code_match = _RSP_STATUS_CODE.search(line[payload_start:])
        if code_match is None:
            continue
        start = payload_start + code_match.start(1)
        end = payload_start + code_match.end(1)
        spans.append(HighlightSpan(offset + start, offset + end, TOKEN_RESPONSE))
    return spans


def _message_leading_protocol_spans(
    line: str,
    offset: int,
) -> list[HighlightSpan]:
    match = _MESSAGE_WORD.search(line)
    if not match:
        return []
    word = match.group(0)
    token = _PROTOCOL_TOKENS.get(word.upper())
    if token is None:
        return []
    return [
        HighlightSpan(
            offset + match.start(),
            offset + match.end(),
            token,
        )
    ]


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
