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

_DELIVERY_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) "
    r"\[(?P<delivery_id>[^\]]+)\] (?P<message>.*)$"
)


@dataclass(frozen=True)
class SmtpLogEntry:
    """Structured SMTP log entry."""

    timestamp: str
    ip: str
    log_id: str
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


def parse_smtp_line(line: str) -> SmtpLogEntry | None:
    """Parse a single SMTP log line."""

    match = _SMTP_PATTERN.match(line)
    if not match:
        return None
    return SmtpLogEntry(
        timestamp=match.group("time"),
        ip=match.group("ip"),
        log_id=match.group("log_id"),
        message=match.group("message"),
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
            current = DeliveryLogEntry(
                timestamp=match.group("time"),
                delivery_id=match.group("delivery_id"),
                message=match.group("message"),
                raw_lines=[line],
            )
            entries.append(current)
            continue

        if current is None:
            orphans.append(line)
            continue
        current.add_continuation(line)

    return entries, orphans
