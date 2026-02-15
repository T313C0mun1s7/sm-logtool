"""Parsers for SmarterMail log formats."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable, List, Tuple


_TIME_PATTERN = r"\d{2}:\d{2}:\d{2}(?:\.\d{3})?"

_SMTP_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) "
    r"\[(?P<ip>[^\]]+)\]\[(?P<log_id>[^\]]+)\] (?P<message>.*)$"
)

_BRACKET2_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) "
    r"\[(?P<field1>[^\]]*)\] \[(?P<field2>[^\]]*)\] (?P<message>.*)$"
)

_BRACKET1_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) "
    r"\[(?P<field1>[^\]]*)\] (?P<message>.*)$"
)

_BRACKET1_TRAILING_TIME_PATTERN = re.compile(
    rf"^\[(?P<field1>[^\]]+)\]\s+(?P<message>.*)\s+"
    rf"(?P<time>{_TIME_PATTERN})$"
)

_DELIVERY_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) "
    r"\[(?P<delivery_id>[^\]]+)\] (?P<message>.*)$"
)

_ADMIN_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) "
    r"\[(?P<ip>[^\]]+)\] (?P<message>.*)$"
)

_TIME_ONLY_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) (?P<message>.*)$"
)


@dataclass(frozen=True)
class SmtpLogEntry:
    """Structured SMTP log entry."""

    timestamp: str
    ip: str
    log_id: str
    message: str
    raw: str


@dataclass(frozen=True)
class Bracket2LogLine:
    """Structured log line with two bracketed fields."""

    timestamp: str
    field1: str
    field2: str
    message: str
    raw: str


@dataclass(frozen=True)
class Bracket1LogLine:
    """Structured log line with one bracketed field."""

    timestamp: str
    field1: str
    message: str
    raw: str


@dataclass(frozen=True)
class TimeLogLine:
    """Structured log line with timestamp only."""

    timestamp: str
    message: str
    raw: str


@dataclass(frozen=True)
class DeliveryLogLine:
    """Structured delivery log line."""

    timestamp: str
    delivery_id: str
    message: str
    raw: str


@dataclass(frozen=True)
class AdminLogLine:
    """Structured administrative log line."""

    timestamp: str
    ip: str
    message: str
    raw: str


@dataclass(frozen=True)
class ImapRetrievalLogLine:
    """Structured IMAP retrieval log line."""

    timestamp: str
    retrieval_id: str
    context: str
    message: str
    raw: str


@dataclass
class DeliveryLogEntry:
    """Structured delivery log entry with optional continuation lines."""

    timestamp: str
    delivery_id: str
    message: str
    raw_lines: List[str] = field(default_factory=list)
    continuation_lines: List[str] = field(default_factory=list)

    def add_continuation(self, line: str) -> None:
        """Append a continuation line (stack trace, etc.)."""

        self.continuation_lines.append(line)
        self.raw_lines.append(line)


@dataclass
class AdminLogEntry:
    """Structured administrative log entry with continuation lines."""

    timestamp: str
    ip: str
    message: str
    raw_lines: List[str] = field(default_factory=list)
    continuation_lines: List[str] = field(default_factory=list)

    def add_continuation(self, line: str) -> None:
        """Append a continuation line."""

        self.continuation_lines.append(line)
        self.raw_lines.append(line)


def parse_smtp_line(line: str) -> SmtpLogEntry | None:
    """Parse a single SMTP log line."""

    match = _SMTP_PATTERN.match(line)
    if not match:
        return None
    timestamp, ip, log_id, message = match.groups()
    return SmtpLogEntry(
        timestamp=timestamp,
        ip=ip,
        log_id=log_id,
        message=message,
        raw=line,
    )


def parse_bracket2_line(line: str) -> Bracket2LogLine | None:
    """Parse a log line with two bracketed fields."""

    match = _BRACKET2_PATTERN.match(line)
    if not match:
        return None
    timestamp, field1, field2, message = match.groups()
    return Bracket2LogLine(
        timestamp=timestamp,
        field1=field1,
        field2=field2,
        message=message,
        raw=line,
    )


def parse_bracket1_line(line: str) -> Bracket1LogLine | None:
    """Parse a log line with one bracketed field."""

    match = _BRACKET1_PATTERN.match(line)
    if not match:
        return None
    timestamp, field1, message = match.groups()
    return Bracket1LogLine(
        timestamp=timestamp,
        field1=field1,
        message=message,
        raw=line,
    )


def parse_bracket1_trailing_time_line(
    line: str,
) -> Bracket1LogLine | None:
    """Parse a log line with one bracketed field and trailing timestamp."""

    match = _BRACKET1_TRAILING_TIME_PATTERN.match(line)
    if not match:
        return None
    field1, message, timestamp = match.groups()
    return Bracket1LogLine(
        timestamp=timestamp,
        field1=field1,
        message=message,
        raw=line,
    )


def parse_time_line(line: str) -> TimeLogLine | None:
    """Parse a log line with timestamp only."""

    match = _TIME_ONLY_PATTERN.match(line)
    if not match:
        return None
    timestamp, message = match.groups()
    return TimeLogLine(
        timestamp=timestamp,
        message=message,
        raw=line,
    )


def starts_with_timestamp(line: str) -> bool:
    """Return True when a line begins with the timestamp format."""

    if len(line) < 8:
        return False
    return (
        line[0].isdigit()
        and line[1].isdigit()
        and line[2] == ":"
        and line[3].isdigit()
        and line[4].isdigit()
        and line[5] == ":"
        and line[6].isdigit()
        and line[7].isdigit()
    )


def parse_delivery_line(line: str) -> DeliveryLogLine | None:
    """Parse a single delivery log line."""

    match = _DELIVERY_PATTERN.match(line)
    if not match:
        return None
    timestamp, delivery_id, message = match.groups()
    return DeliveryLogLine(
        timestamp=timestamp,
        delivery_id=delivery_id,
        message=message,
        raw=line,
    )


def parse_admin_line(line: str) -> AdminLogLine | None:
    """Parse a single administrative log line."""

    entry = parse_bracket1_line(line)
    if entry is None:
        entry = parse_bracket1_trailing_time_line(line)
    if entry is None:
        return None
    return AdminLogLine(
        timestamp=entry.timestamp,
        ip=entry.field1,
        message=entry.message,
        raw=line,
    )


def parse_imap_retrieval_line(line: str) -> ImapRetrievalLogLine | None:
    """Parse a single IMAP retrieval log line."""

    match = _BRACKET2_PATTERN.match(line)
    if not match:
        return None
    timestamp, retrieval_id, context, message = match.groups()
    return ImapRetrievalLogLine(
        timestamp=timestamp,
        retrieval_id=retrieval_id,
        context=context,
        message=message,
        raw=line,
    )


def parse_delivery_entries(
    lines: Iterable[str],
) -> Tuple[List[DeliveryLogEntry], List[str]]:
    """Parse delivery log lines into structured entries.

    Lines that do not begin with a timestamp are treated as continuation
    lines for the previous entry. If no prior entry exists, they are
    returned as orphans.
    """

    entries: List[DeliveryLogEntry] = []
    orphans: List[str] = []
    current: DeliveryLogEntry | None = None

    for line in lines:
        match = _DELIVERY_PATTERN.match(line)
        if match:
            timestamp, delivery_id, message = match.groups()
            current = DeliveryLogEntry(
                timestamp=timestamp,
                delivery_id=delivery_id,
                message=message,
                raw_lines=[line],
            )
            entries.append(current)
            continue

        if current is None:
            orphans.append(line)
            continue
        current.add_continuation(line)

    return entries, orphans


def parse_admin_entries(
    lines: Iterable[str],
) -> Tuple[List[AdminLogEntry], List[str]]:
    """Parse administrative log lines into structured entries.

    Lines that do not begin with a timestamp are treated as continuation
    lines for the previous entry. If no prior entry exists, they are
    returned as orphans.
    """

    entries: List[AdminLogEntry] = []
    orphans: List[str] = []
    current: AdminLogEntry | None = None

    for line in lines:
        entry = parse_admin_line(line)
        if entry is not None:
            current = AdminLogEntry(
                timestamp=entry.timestamp,
                ip=entry.ip,
                message=entry.message,
                raw_lines=[line],
            )
            entries.append(current)
            continue

        if current is None:
            orphans.append(line)
            continue
        current.add_continuation(line)

    return entries, orphans
