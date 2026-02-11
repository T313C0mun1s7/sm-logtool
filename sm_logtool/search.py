"""Search helpers for SmarterMail logs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Protocol, Tuple

from .log_kinds import (
    KIND_ACTIVATION,
    KIND_ADMINISTRATIVE,
    KIND_AUTOCLEANFOLDERS,
    KIND_CALENDARS,
    KIND_CONTENTFILTER,
    KIND_DELIVERY,
    KIND_EVENT,
    KIND_GENERALERRORS,
    KIND_IMAP,
    KIND_IMAP_RETRIEVAL,
    KIND_INDEXING,
    KIND_LDAP,
    KIND_MAINTENANCE,
    KIND_POP,
    KIND_PROFILER,
    KIND_SMTP,
    KIND_SPAMCHECKS,
    KIND_WEBDAV,
    normalize_kind,
)
from .log_parsers import (
    parse_admin_line,
    parse_imap_retrieval_line,
    parse_delivery_line,
    parse_smtp_line,
    starts_with_timestamp,
)

@dataclass
class Conversation:
    """Log conversation grouped by message identifier."""

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


class SearchFunction(Protocol):
    def __call__(
        self,
        log_path: Path,
        term: str,
        *,
        ignore_case: bool = True,
    ) -> SmtpSearchResult: ...


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
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n")
            entry = parse_smtp_line(line)
            line_owner_id: str | None = None
            if entry is not None:
                current_id = entry.log_id
                line_owner_id = current_id
                builder = builders.get(current_id)
                if builder is None:
                    builder = _ConversationBuilder(
                        message_id=current_id,
                        first_line_number=line_number,
                    )
                    builders[current_id] = builder
                builder.add_line(line)
            else:
                if starts_with_timestamp(line):
                    current_id = None
                elif current_id is not None:
                    line_owner_id = current_id
                    builder = builders.get(current_id)
                    if builder is None:
                        builder = _ConversationBuilder(
                            message_id=current_id,
                            first_line_number=line_number,
                        )
                        builders[current_id] = builder
                    builder.add_line(line)

            if pattern.search(line):
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))

    conversations = [
        builders[mid].as_conversation()
        for mid in matched_ids
        if mid in builders
    ]
    conversations.sort(key=lambda conv: conv.first_line_number)

    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def search_delivery_conversations(
    log_path: Path,
    term: str,
    *,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return delivery conversations containing ``term``."""

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(term), flags)

    builders: dict[str, _ConversationBuilder] = {}
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n")
            entry = parse_delivery_line(line)
            line_owner_id: str | None = None
            if entry is not None:
                current_id = entry.delivery_id
                line_owner_id = current_id
                builder = builders.get(current_id)
                if builder is None:
                    builder = _ConversationBuilder(
                        message_id=current_id,
                        first_line_number=line_number,
                    )
                    builders[current_id] = builder
                builder.add_line(line)
            else:
                if starts_with_timestamp(line):
                    current_id = None
                elif current_id is not None:
                    line_owner_id = current_id
                    builder = builders.get(current_id)
                    if builder is None:
                        builder = _ConversationBuilder(
                            message_id=current_id,
                            first_line_number=line_number,
                        )
                        builders[current_id] = builder
                    builder.add_line(line)

            if pattern.search(line):
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))

    conversations = [
        builders[mid].as_conversation()
        for mid in matched_ids
        if mid in builders
    ]
    conversations.sort(key=lambda conv: conv.first_line_number)

    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def search_admin_entries(
    log_path: Path,
    term: str,
    *,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return administrative log entries containing ``term``."""

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(term), flags)

    builders: dict[str, _ConversationBuilder] = {}
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n")
            entry = parse_admin_line(line)
            line_owner_id: str | None = None
            if entry is not None:
                message_id = f"{entry.ip} {entry.timestamp}"
                current_id = message_id
                line_owner_id = current_id
                builder = builders.get(message_id)
                if builder is None:
                    builder = _ConversationBuilder(
                        message_id=message_id,
                        first_line_number=line_number,
                    )
                    builders[message_id] = builder
                builder.add_line(line)
            else:
                if starts_with_timestamp(line):
                    current_id = None
                elif current_id is not None:
                    line_owner_id = current_id
                    builder = builders.get(current_id)
                    if builder is None:
                        builder = _ConversationBuilder(
                            message_id=current_id,
                            first_line_number=line_number,
                        )
                        builders[current_id] = builder
                    builder.add_line(line)

            if pattern.search(line):
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))

    conversations = [
        builders[mid].as_conversation()
        for mid in matched_ids
        if mid in builders
    ]
    conversations.sort(key=lambda conv: conv.first_line_number)

    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def search_imap_retrieval_entries(
    log_path: Path,
    term: str,
    *,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return IMAP retrieval entries containing ``term``."""

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(term), flags)

    builders: dict[str, _ConversationBuilder] = {}
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n")
            entry = parse_imap_retrieval_line(line)
            line_owner_id: str | None = None
            if entry is not None:
                current_id = entry.retrieval_id
                line_owner_id = current_id
                builder = builders.get(current_id)
                if builder is None:
                    builder = _ConversationBuilder(
                        message_id=current_id,
                        first_line_number=line_number,
                    )
                    builders[current_id] = builder
                builder.add_line(line)
            else:
                if starts_with_timestamp(line):
                    current_id = None
                elif current_id is not None:
                    line_owner_id = current_id
                    builder = builders.get(current_id)
                    if builder is None:
                        builder = _ConversationBuilder(
                            message_id=current_id,
                            first_line_number=line_number,
                        )
                        builders[current_id] = builder
                    builder.add_line(line)

            if pattern.search(line):
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))

    conversations = [
        builders[mid].as_conversation()
        for mid in matched_ids
        if mid in builders
    ]
    conversations.sort(key=lambda conv: conv.first_line_number)

    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def search_ungrouped_entries(
    log_path: Path,
    term: str,
    *,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return ungrouped log entries containing ``term``."""

    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(re.escape(term), flags)

    builders: dict[str, _ConversationBuilder] = {}
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n")
            line_owner_id: str | None = None
            if starts_with_timestamp(line):
                current_id = f"{line_number}"
                line_owner_id = current_id
                builder = _ConversationBuilder(
                    message_id=current_id,
                    first_line_number=line_number,
                )
                builders[current_id] = builder
                builder.add_line(line)
            elif current_id is not None:
                line_owner_id = current_id
                builder = builders.get(current_id)
                if builder is None:
                    builder = _ConversationBuilder(
                        message_id=current_id,
                        first_line_number=line_number,
                    )
                    builders[current_id] = builder
                builder.add_line(line)

            if pattern.search(line):
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))

    conversations = [
        builders[mid].as_conversation()
        for mid in matched_ids
        if mid in builders
    ]
    conversations.sort(key=lambda conv: conv.first_line_number)

    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def get_search_function(
    kind: str,
) -> SearchFunction | None:
    """Return the search function for the given log kind."""

    kind_key = normalize_kind(kind)
    if kind_key == KIND_SMTP:
        return search_smtp_conversations
    if kind_key == KIND_IMAP:
        return search_smtp_conversations
    if kind_key == KIND_POP:
        return search_smtp_conversations
    if kind_key == KIND_DELIVERY:
        return search_delivery_conversations
    if kind_key == KIND_ADMINISTRATIVE:
        return search_admin_entries
    if kind_key == KIND_IMAP_RETRIEVAL:
        return search_imap_retrieval_entries
    if kind_key in {
        KIND_ACTIVATION,
        KIND_AUTOCLEANFOLDERS,
        KIND_CALENDARS,
        KIND_CONTENTFILTER,
        KIND_EVENT,
        KIND_GENERALERRORS,
        KIND_INDEXING,
        KIND_LDAP,
        KIND_MAINTENANCE,
        KIND_PROFILER,
        KIND_SPAMCHECKS,
        KIND_WEBDAV,
    }:
        return search_ungrouped_entries
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
