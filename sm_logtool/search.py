"""Search helpers for SmarterMail logs."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Callable, List, Protocol, Tuple

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
from .search_modes import (
    DEFAULT_FUZZY_THRESHOLD,
    MODE_FUZZY,
    MODE_LITERAL,
    MODE_REGEX,
    MODE_WILDCARD,
    normalize_fuzzy_threshold,
    normalize_search_mode,
    wildcard_to_regex,
)

try:
    from rapidfuzz import fuzz as _rapidfuzz_fuzz
except Exception:  # pragma: no cover - optional dependency
    _rapidfuzz_fuzz = None


_FUZZY_ANCHOR_LIMIT = 120
_FUZZY_STRIDE_DIVISOR = 6


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
        mode: str = MODE_LITERAL,
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        ignore_case: bool = True,
    ) -> SmtpSearchResult: ...


def search_smtp_conversations(
    log_path: Path,
    term: str,
    *,
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return SMTP conversations containing ``term``.

    ``mode`` controls the match syntax. ``literal`` uses exact substring
    matching, ``wildcard`` allows ``*`` and ``?`` wildcards, and ``regex``
    treats ``term`` as a Python regular expression.
    """

    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )

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

            if matcher(line):
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
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return delivery conversations containing ``term``."""

    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )

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

            if matcher(line):
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
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return administrative log entries containing ``term``."""

    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )

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

            if matcher(line):
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
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return IMAP retrieval entries containing ``term``."""

    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )

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

            if matcher(line):
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
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
) -> SmtpSearchResult:
    """Return ungrouped log entries containing ``term``."""

    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )

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

            if matcher(line):
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


def _compile_match_pattern(
    term: str,
    mode: str,
    ignore_case: bool,
) -> re.Pattern[str]:
    flags = re.IGNORECASE if ignore_case else 0
    resolved_mode = normalize_search_mode(mode)

    if resolved_mode == MODE_LITERAL:
        source = re.escape(term)
    elif resolved_mode == MODE_WILDCARD:
        source = wildcard_to_regex(term)
    elif resolved_mode == MODE_REGEX:
        source = term
    else:  # pragma: no cover - normalize_search_mode gates this
        raise ValueError(f"Unsupported search mode: {mode!r}")

    try:
        return re.compile(source, flags)
    except re.error as exc:
        if resolved_mode == MODE_REGEX:
            raise ValueError(f"Invalid regex pattern: {exc}") from exc
        raise


def _compile_line_matcher(
    term: str,
    mode: str,
    ignore_case: bool,
    fuzzy_threshold: float,
) -> Callable[[str], bool]:
    resolved_mode = normalize_search_mode(mode)
    if resolved_mode == MODE_LITERAL:
        return _compile_literal_line_matcher(term, ignore_case)

    if resolved_mode == MODE_FUZZY:
        threshold = normalize_fuzzy_threshold(fuzzy_threshold)
        normalized_term = term.lower() if ignore_case else term
        return _compile_fuzzy_line_matcher(
            normalized_term,
            threshold,
            ignore_case=ignore_case,
        )

    pattern = _compile_match_pattern(term, resolved_mode, ignore_case)
    return lambda line: bool(pattern.search(line))


def _compile_literal_line_matcher(
    term: str,
    ignore_case: bool,
) -> Callable[[str], bool]:
    if ignore_case:
        term = term.lower()
        return lambda line: term in line.lower()
    return lambda line: term in line


def _compile_fuzzy_line_matcher(
    term: str,
    threshold: float,
    *,
    ignore_case: bool,
) -> Callable[[str], bool]:
    if _rapidfuzz_fuzz is not None:
        return _compile_rapidfuzz_line_matcher(
            term,
            threshold,
            ignore_case=ignore_case,
        )
    term_len = len(term)
    if term_len <= 0:
        return lambda _line: False
    stride = max(1, term_len // _FUZZY_STRIDE_DIVISOR)
    anchor_offsets = _build_anchor_offsets(term_len)
    anchor_chars = tuple(term[offset] for offset in anchor_offsets)

    if ignore_case:
        return lambda line: _fuzzy_line_match(
            term,
            line.lower(),
            threshold,
            term_len,
            stride,
            anchor_offsets,
            anchor_chars,
        )
    return lambda line: _fuzzy_line_match(
        term,
        line,
        threshold,
        term_len,
        stride,
        anchor_offsets,
        anchor_chars,
    )


def _compile_rapidfuzz_line_matcher(
    term: str,
    threshold: float,
    *,
    ignore_case: bool,
) -> Callable[[str], bool]:
    term_len = len(term)
    if term_len <= 0:
        return lambda _line: False
    cutoff = threshold * 100.0
    if ignore_case:
        return lambda line: _rapidfuzz_line_match(
            term,
            line.lower(),
            cutoff,
        )
    return lambda line: _rapidfuzz_line_match(term, line, cutoff)


def _rapidfuzz_line_match(
    term: str,
    line: str,
    cutoff: float,
) -> bool:
    if not term:
        return False
    if term in line:
        return True
    score = _rapidfuzz_fuzz.partial_ratio(  # type: ignore[union-attr]
        term,
        line,
        score_cutoff=cutoff,
    )
    return score >= cutoff


def _fuzzy_line_match(
    term: str,
    line: str,
    threshold: float,
    term_len: int,
    stride: int,
    anchor_offsets: tuple[int, ...],
    anchor_chars: tuple[str, ...],
) -> bool:
    if not term:
        return False
    if term in line:
        return True
    if not line:
        return False
    if len(line) <= term_len:
        return SequenceMatcher(None, term, line).ratio() >= threshold

    max_start = len(line) - term_len
    starts = _candidate_window_starts(
        line,
        max_start,
        stride,
        anchor_offsets,
        anchor_chars,
    )
    matcher = SequenceMatcher(None, term)
    best_start = 0
    best_ratio = 0.0

    for start in starts:
        ratio = _window_similarity(matcher, line, start, term_len, threshold)
        if ratio >= threshold:
            return True
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = start

    if best_ratio <= 0.0 or stride <= 1:
        return False

    begin = max(0, best_start - stride + 1)
    end = min(max_start, best_start + stride - 1)
    for start in range(begin, end + 1):
        if start in starts:
            continue
        ratio = _window_similarity(matcher, line, start, term_len, threshold)
        if ratio >= threshold:
            return True
    return False


def _build_anchor_offsets(term_len: int) -> tuple[int, ...]:
    if term_len <= 1:
        return (0,)
    midpoint = term_len // 2
    return (0, midpoint, term_len - 1)


def _candidate_window_starts(
    line: str,
    max_start: int,
    stride: int,
    anchor_offsets: tuple[int, ...],
    anchor_chars: tuple[str, ...],
) -> set[int]:
    starts: set[int] = {0, max_start}
    for start in range(0, max_start + 1, stride):
        starts.add(start)

    for offset, char in zip(anchor_offsets, anchor_chars):
        hits = 0
        position = line.find(char)
        while position != -1 and hits < _FUZZY_ANCHOR_LIMIT:
            start = position - offset
            if start < 0:
                start = 0
            if start > max_start:
                start = max_start
            starts.add(start)
            position = line.find(char, position + 1)
            hits += 1
    return starts


def _window_similarity(
    matcher: SequenceMatcher,
    line: str,
    start: int,
    window: int,
    threshold: float,
) -> float:
    chunk = line[start:start + window]
    matcher.set_seq2(chunk)
    if matcher.real_quick_ratio() < threshold:
        return 0.0
    if matcher.quick_ratio() < threshold:
        return 0.0
    return matcher.ratio()


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
