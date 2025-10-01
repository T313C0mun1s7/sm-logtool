"""Search helpers for SmarterMail SMTP logs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Tuple


_MESSAGE_ID_PATTERN = re.compile(r"\[[^\]]*\]\[(?P<message_id>[^\]]+)\]")


@dataclass
class Conversation:
    """SMTP conversation grouped by message identifier."""

    message_id: str
    lines: List[str]
    first_line_number: int


@dataclass
class SmtpSearchResult:
    """Aggregate information about a search."""

    term: str
    log_path: Path
    conversations: List[Conversation]
    total_lines: int
    orphan_matches: List[Tuple[int, str]]

    @property
    def total_conversations(self) -> int:
        return len(self.conversations)


def search_smtp_conversations(
    log_path: Path,
    term: str,
    *,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return SMTP conversations containing ``term``.

    ``term`` is treated as a literal substring; pass ``ignore_case=False`` to
    require exact casing.
    """

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(term), flags)

    builders: dict[str, _ConversationBuilder] = {}
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n")
            message_id = _extract_message_id(line)
            if message_id:
                builder = builders.get(message_id)
                if builder is None:
                    builder = _ConversationBuilder(message_id=message_id, first_line_number=line_number)
                    builders[message_id] = builder
                builder.add_line(line)

            if pattern.search(line):
                if message_id:
                    matched_ids.add(message_id)
                else:
                    orphan_matches.append((line_number, line))

    conversations = [builders[mid].as_conversation() for mid in matched_ids if mid in builders]
    conversations.sort(key=lambda conv: conv.first_line_number)

    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def _extract_message_id(line: str) -> str | None:
    match = _MESSAGE_ID_PATTERN.search(line)
    if match:
        return match.group("message_id")
    return None


@dataclass
class _ConversationBuilder:
    message_id: str
    first_line_number: int
    lines: List[str]

    def __init__(self, message_id: str, first_line_number: int) -> None:
        self.message_id = message_id
        self.first_line_number = first_line_number
        self.lines = []

    def add_line(self, line: str) -> None:
        self.lines.append(line.rstrip("\r"))

    def as_conversation(self) -> Conversation:
        return Conversation(
            message_id=self.message_id,
            lines=self.lines.copy(),
            first_line_number=self.first_line_number,
        )

