"""Search helpers for SmarterMail logs."""

from __future__ import annotations

from array import array
from collections import OrderedDict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
import re
from threading import Lock
import time
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
_TIME_PATTERN = r"\d{2}:\d{2}:\d{2}(?:\.\d{3})?"
_SMTP_OWNER_PATTERN = re.compile(
    rf"^(?:{_TIME_PATTERN}) \[[^\]]+\]\[([^\]]+)\] "
)
_DELIVERY_OWNER_PATTERN = re.compile(
    rf"^(?:{_TIME_PATTERN}) \[([^\]]+)\] "
)
_IMAP_RETRIEVAL_OWNER_PATTERN = re.compile(
    rf"^(?:{_TIME_PATTERN}) \[([^\]]*)\] \[[^\]]*\] "
)
_ADMIN_OWNER_PATTERN = re.compile(
    rf"^(?P<time>{_TIME_PATTERN}) \[(?P<ip>[^\]]*)\] "
)
_ADMIN_TRAILING_OWNER_PATTERN = re.compile(
    rf"^\[(?P<ip>[^\]]+)\]\s+.*\s+(?P<time>{_TIME_PATTERN})$"
)
MATERIALIZATION_AUTO = "auto"
MATERIALIZATION_SINGLE_PASS = "single-pass"
MATERIALIZATION_TWO_PASS = "two-pass"
SUPPORTED_MATERIALIZATION_MODES = (
    MATERIALIZATION_AUTO,
    MATERIALIZATION_SINGLE_PASS,
    MATERIALIZATION_TWO_PASS,
)
_AUTO_SAMPLE_LINES = 10000
_AUTO_MAX_LINE_MATCH_RATIO = 0.002
_AUTO_MAX_OWNER_MATCH_RATIO = 0.04
_INDEX_CACHE_MAX_BYTES = 256 * 1024 * 1024
_PROGRESS_REPORT_BYTES = 4 * 1024 * 1024
_PROGRESS_REPORT_SECONDS = 0.2


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
    matching_rows: List[Tuple[int, str]] = field(default_factory=list)

    @property
    def total_conversations(self) -> int:
        """Return the number of grouped conversations in ``conversations``."""

        return len(self.conversations)


class SearchFunction(Protocol):
    """Callable signature used by all search handlers."""

    def __call__(
        self,
        log_path: Path,
        term: str,
        *,
        mode: str = MODE_LITERAL,
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        ignore_case: bool = True,
        materialization: str = MATERIALIZATION_AUTO,
        use_index_cache: bool = False,
        progress_callback: "SearchProgressCallback | None" = None,
        match_callback: "SearchMatchCallback | None" = None,
    ) -> SmtpSearchResult: ...


SearchProgressCallback = Callable[[int, int], None]
SearchMatchCallback = Callable[[int, str], None]


@dataclass
class _SearchProgress:
    callback: SearchProgressCallback
    total_bytes: int
    scanned_bytes: int = 0
    next_report_bytes: int = _PROGRESS_REPORT_BYTES
    last_report_at: float = 0.0


@dataclass(frozen=True)
class _OwnerLineIndex:
    key: str
    signature: tuple[int, int]
    owner_codes: array
    owner_ids: list[str]
    owner_first_lines: list[int]
    line_count: int
    size_bytes: int


_INDEX_CACHE: "OrderedDict[tuple[str, str, int, int], _OwnerLineIndex]" = (
    OrderedDict()
)
_INDEX_CACHE_BYTES = 0
_INDEX_CACHE_LOCK = Lock()


def _safe_file_size(log_path: Path) -> int:
    try:
        return log_path.stat().st_size
    except OSError:
        return 0


def _start_search_progress(
    log_path: Path,
    callback: SearchProgressCallback | None,
    *,
    expected_passes: int,
) -> _SearchProgress | None:
    if callback is None:
        return None
    file_size = _safe_file_size(log_path)
    total_bytes = max(1, file_size * max(1, expected_passes))
    progress = _SearchProgress(
        callback=callback,
        total_bytes=total_bytes,
    )
    callback(0, total_bytes)
    return progress


def _advance_search_progress(
    progress: _SearchProgress | None,
    raw_line: str,
) -> None:
    if progress is None:
        return
    progress.scanned_bytes += len(raw_line)
    if progress.scanned_bytes < progress.next_report_bytes:
        return
    now = time.perf_counter()
    if now - progress.last_report_at < _PROGRESS_REPORT_SECONDS:
        return
    scanned = min(progress.scanned_bytes, progress.total_bytes)
    progress.callback(scanned, progress.total_bytes)
    progress.next_report_bytes = (
        progress.scanned_bytes + _PROGRESS_REPORT_BYTES
    )
    progress.last_report_at = now


def _finish_search_progress(progress: _SearchProgress | None) -> None:
    if progress is None:
        return
    progress.callback(progress.total_bytes, progress.total_bytes)


def _report_match(
    callback: SearchMatchCallback | None,
    line_number: int,
    line: str,
) -> None:
    if callback is None:
        return
    callback(line_number, line)


def _capture_matching_rows(
    callback: SearchMatchCallback | None,
) -> tuple[list[tuple[int, str]], SearchMatchCallback]:
    rows: list[tuple[int, str]] = []

    def _collector(line_number: int, line: str) -> None:
        rows.append((line_number, line))
        _report_match(callback, line_number, line)

    return rows, _collector


def _dedupe_matching_rows(
    rows: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    seen: set[tuple[int, str]] = set()
    deduped: list[tuple[int, str]] = []
    for entry in rows:
        if entry in seen:
            continue
        seen.add(entry)
        deduped.append(entry)
    return deduped


def search_smtp_conversations(
    log_path: Path,
    term: str,
    *,
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
    materialization: str = MATERIALIZATION_AUTO,
    use_index_cache: bool = False,
    progress_callback: SearchProgressCallback | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> SmtpSearchResult:
    """Return SMTP conversations containing ``term``.

    ``mode`` controls the match syntax. ``literal`` uses exact substring
    matching, ``wildcard`` allows ``*`` and ``?`` wildcards, and ``regex``
    treats ``term`` as a Python regular expression.
    """

    matching_rows, collector = _capture_matching_rows(match_callback)
    result = _search_grouped_entries(
        log_path,
        term,
        _smtp_owner_id,
        mode=mode,
        fuzzy_threshold=fuzzy_threshold,
        ignore_case=ignore_case,
        materialization=materialization,
        use_index_cache=use_index_cache,
        progress_callback=progress_callback,
        match_callback=collector,
        owner_key="smtp",
    )
    result.matching_rows = _dedupe_matching_rows(matching_rows)
    return result


def search_delivery_conversations(
    log_path: Path,
    term: str,
    *,
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
    materialization: str = MATERIALIZATION_AUTO,
    use_index_cache: bool = False,
    progress_callback: SearchProgressCallback | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> SmtpSearchResult:
    """Return delivery conversations containing ``term``."""

    matching_rows, collector = _capture_matching_rows(match_callback)
    result = _search_grouped_entries(
        log_path,
        term,
        _delivery_owner_id,
        mode=mode,
        fuzzy_threshold=fuzzy_threshold,
        ignore_case=ignore_case,
        materialization=materialization,
        use_index_cache=use_index_cache,
        progress_callback=progress_callback,
        match_callback=collector,
        owner_key="delivery",
    )
    result.matching_rows = _dedupe_matching_rows(matching_rows)
    return result


def search_admin_entries(
    log_path: Path,
    term: str,
    *,
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
    materialization: str = MATERIALIZATION_AUTO,
    use_index_cache: bool = False,
    progress_callback: SearchProgressCallback | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> SmtpSearchResult:
    """Return administrative log entries containing ``term``."""

    matching_rows, collector = _capture_matching_rows(match_callback)
    result = _search_grouped_entries(
        log_path,
        term,
        _admin_owner_id,
        mode=mode,
        fuzzy_threshold=fuzzy_threshold,
        ignore_case=ignore_case,
        materialization=materialization,
        use_index_cache=use_index_cache,
        progress_callback=progress_callback,
        match_callback=collector,
        owner_key="admin",
    )
    result.matching_rows = _dedupe_matching_rows(matching_rows)
    return result


def search_imap_retrieval_entries(
    log_path: Path,
    term: str,
    *,
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
    materialization: str = MATERIALIZATION_AUTO,
    use_index_cache: bool = False,
    progress_callback: SearchProgressCallback | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> SmtpSearchResult:
    """Return IMAP retrieval entries containing ``term``."""

    matching_rows, collector = _capture_matching_rows(match_callback)
    result = _search_grouped_entries(
        log_path,
        term,
        _imap_retrieval_owner_id,
        mode=mode,
        fuzzy_threshold=fuzzy_threshold,
        ignore_case=ignore_case,
        materialization=materialization,
        use_index_cache=use_index_cache,
        progress_callback=progress_callback,
        match_callback=collector,
        owner_key="imap-retrieval",
    )
    result.matching_rows = _dedupe_matching_rows(matching_rows)
    return result


def search_ungrouped_entries(
    log_path: Path,
    term: str,
    *,
    mode: str = MODE_LITERAL,
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ignore_case: bool = True,
    materialization: str = MATERIALIZATION_AUTO,
    use_index_cache: bool = False,
    progress_callback: SearchProgressCallback | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> SmtpSearchResult:
    """Return ungrouped log entries containing ``term``."""

    matching_rows, collector = _capture_matching_rows(match_callback)
    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )
    resolved_materialization = normalize_materialization_mode(materialization)
    expected_passes = 1
    if (
        use_index_cache
        or resolved_materialization != MATERIALIZATION_SINGLE_PASS
    ):
        expected_passes = 2
    progress = _start_search_progress(
        log_path,
        progress_callback,
        expected_passes=expected_passes,
    )
    try:
        if use_index_cache:
            result = _search_ungrouped_with_index(
                log_path,
                term,
                matcher,
                progress=progress,
                match_callback=collector,
            )
            result.matching_rows = _dedupe_matching_rows(matching_rows)
            return result
        if resolved_materialization == MATERIALIZATION_TWO_PASS:
            result = _search_ungrouped_two_pass(
                log_path,
                term,
                matcher,
                progress=progress,
                match_callback=collector,
            )
            result.matching_rows = _dedupe_matching_rows(matching_rows)
            return result

        result = _search_ungrouped_single_pass(
            log_path,
            term,
            matcher,
            auto_fallback=resolved_materialization == MATERIALIZATION_AUTO,
            progress=progress,
            match_callback=collector,
        )
        result.matching_rows = _dedupe_matching_rows(matching_rows)
        return result
    finally:
        _finish_search_progress(progress)


def normalize_materialization_mode(value: str) -> str:
    """Normalize and validate grouped-search materialization strategy."""

    mode = value.strip().lower()
    if mode in SUPPORTED_MATERIALIZATION_MODES:
        return mode
    supported = ", ".join(SUPPORTED_MATERIALIZATION_MODES)
    raise ValueError(
        f"Unsupported materialization mode: {value!r}. "
        f"Expected one of: {supported}."
    )


def _owner_index_cache_key(
    log_path: Path,
    owner_key: str,
) -> tuple[tuple[str, str, int, int], tuple[int, int]]:
    stat = log_path.stat()
    signature = (stat.st_size, stat.st_mtime_ns)
    cache_key = (
        str(log_path.resolve()),
        owner_key,
        signature[0],
        signature[1],
    )
    return cache_key, signature


def _estimate_owner_index_size(
    owner_codes: array,
    owner_ids: list[str],
    owner_first_lines: list[int],
) -> int:
    owner_bytes = sum(len(value) for value in owner_ids)
    return (
        owner_codes.itemsize * len(owner_codes)
        + len(owner_ids) * 64
        + len(owner_first_lines) * 8
        + owner_bytes
    )


def _evict_index_cache_if_needed() -> None:
    global _INDEX_CACHE_BYTES
    while _INDEX_CACHE and _INDEX_CACHE_BYTES > _INDEX_CACHE_MAX_BYTES:
        _, oldest = _INDEX_CACHE.popitem(last=False)
        _INDEX_CACHE_BYTES = max(0, _INDEX_CACHE_BYTES - oldest.size_bytes)


def _cache_owner_line_index(
    cache_key: tuple[str, str, int, int],
    index: _OwnerLineIndex,
) -> None:
    global _INDEX_CACHE_BYTES
    with _INDEX_CACHE_LOCK:
        previous = _INDEX_CACHE.get(cache_key)
        if previous is not None:
            _INDEX_CACHE_BYTES = max(
                0,
                _INDEX_CACHE_BYTES - previous.size_bytes,
            )
        _INDEX_CACHE[cache_key] = index
        _INDEX_CACHE.move_to_end(cache_key)
        _INDEX_CACHE_BYTES += index.size_bytes
        _evict_index_cache_if_needed()


def _lookup_owner_line_index(
    cache_key: tuple[str, str, int, int],
) -> _OwnerLineIndex | None:
    with _INDEX_CACHE_LOCK:
        cached = _INDEX_CACHE.get(cache_key)
        if cached is None:
            return None
        _INDEX_CACHE.move_to_end(cache_key)
        return cached


def _build_grouped_owner_line_index_with_scan(
    log_path: Path,
    owner_for_line: Callable[[str], str | None],
    owner_key: str,
    signature: tuple[int, int],
    matcher: Callable[[str], bool],
    progress: _SearchProgress | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> tuple[_OwnerLineIndex, set[int], list[tuple[int, str]], int]:
    owner_codes = array("i")
    owner_ids: list[str] = []
    owner_first_lines: list[int] = []
    owner_to_code: dict[str, int] = {}
    matched_codes: set[int] = set()
    orphan_matches: list[tuple[int, str]] = []
    current_code = -1
    line_count = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            line_count += 1
            line = raw_line.rstrip("\r\n")
            owner_id = owner_for_line(line)
            if owner_id is not None:
                code = owner_to_code.get(owner_id)
                if code is None:
                    code = len(owner_ids)
                    owner_to_code[owner_id] = code
                    owner_ids.append(owner_id)
                    owner_first_lines.append(line_number)
                current_code = code
                owner_codes.append(code)
                owner_code = code
            else:
                if starts_with_timestamp(line):
                    current_code = -1
                owner_codes.append(current_code)
                owner_code = current_code

            if not matcher(line):
                continue
            _report_match(match_callback, line_number, line)
            if owner_code >= 0:
                matched_codes.add(owner_code)
            else:
                orphan_matches.append((line_number, line))

    size_bytes = _estimate_owner_index_size(
        owner_codes,
        owner_ids,
        owner_first_lines,
    )
    index = _OwnerLineIndex(
        key=owner_key,
        signature=signature,
        owner_codes=owner_codes,
        owner_ids=owner_ids,
        owner_first_lines=owner_first_lines,
        line_count=line_count,
        size_bytes=size_bytes,
    )
    return index, matched_codes, orphan_matches, line_count


def _build_ungrouped_owner_line_index_with_scan(
    log_path: Path,
    signature: tuple[int, int],
    matcher: Callable[[str], bool],
    progress: _SearchProgress | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> tuple[_OwnerLineIndex, set[int], list[tuple[int, str]], int]:
    owner_codes = array("i")
    owner_ids: list[str] = []
    owner_first_lines: list[int] = []
    matched_codes: set[int] = set()
    orphan_matches: list[tuple[int, str]] = []
    current_code = -1
    line_count = 0

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            line_count += 1
            line = raw_line.rstrip("\r\n")
            if starts_with_timestamp(line):
                current_code = len(owner_ids)
                owner_ids.append(f"{line_number}")
                owner_first_lines.append(line_number)
            owner_codes.append(current_code)
            if not matcher(line):
                continue
            _report_match(match_callback, line_number, line)
            if current_code >= 0:
                matched_codes.add(current_code)
            else:
                orphan_matches.append((line_number, line))

    size_bytes = _estimate_owner_index_size(
        owner_codes,
        owner_ids,
        owner_first_lines,
    )
    index = _OwnerLineIndex(
        key="ungrouped",
        signature=signature,
        owner_codes=owner_codes,
        owner_ids=owner_ids,
        owner_first_lines=owner_first_lines,
        line_count=line_count,
        size_bytes=size_bytes,
    )
    return index, matched_codes, orphan_matches, line_count


def _search_grouped_with_index(
    log_path: Path,
    term: str,
    matcher: Callable[[str], bool],
    owner_for_line: Callable[[str], str | None],
    *,
    owner_key: str,
    progress: _SearchProgress | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> SmtpSearchResult:
    cache_key, signature = _owner_index_cache_key(log_path, owner_key)
    cached = _lookup_owner_line_index(cache_key)
    if cached is None:
        (
            index,
            matched_codes,
            orphan_matches,
            total_lines,
        ) = _build_grouped_owner_line_index_with_scan(
            log_path,
            owner_for_line,
            owner_key,
            signature,
            matcher,
            progress=progress,
            match_callback=match_callback,
        )
        _cache_owner_line_index(cache_key, index)
    else:
        index = cached
        matched_codes = set()
        orphan_matches = []
        total_lines = 0
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for zero_based, raw_line in enumerate(handle):
                _advance_search_progress(progress, raw_line)
                total_lines += 1
                line = raw_line.rstrip("\r\n")
                owner_code = (
                    index.owner_codes[zero_based]
                    if zero_based < len(index.owner_codes)
                    else -1
                )
                if not matcher(line):
                    continue
                _report_match(match_callback, zero_based + 1, line)
                if owner_code >= 0:
                    matched_codes.add(owner_code)
                else:
                    orphan_matches.append((zero_based + 1, line))

    if not matched_codes:
        return SmtpSearchResult(
            term=term,
            log_path=log_path,
            conversations=[],
            total_lines=total_lines,
            orphan_matches=orphan_matches,
        )

    conversations_by_code: dict[int, Conversation] = {}
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for zero_based, raw_line in enumerate(handle):
            _advance_search_progress(progress, raw_line)
            owner_code = (
                index.owner_codes[zero_based]
                if zero_based < len(index.owner_codes)
                else -1
            )
            if owner_code not in matched_codes:
                continue
            conversation = conversations_by_code.get(owner_code)
            if conversation is None:
                conversation = Conversation(
                    message_id=index.owner_ids[owner_code],
                    lines=[],
                    first_line_number=index.owner_first_lines[owner_code],
                )
                conversations_by_code[owner_code] = conversation
            conversation.lines.append(raw_line.rstrip("\r\n"))

    conversations = list(conversations_by_code.values())
    conversations.sort(key=lambda conv: conv.first_line_number)
    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def _search_ungrouped_with_index(
    log_path: Path,
    term: str,
    matcher: Callable[[str], bool],
    *,
    progress: _SearchProgress | None = None,
    match_callback: SearchMatchCallback | None = None,
) -> SmtpSearchResult:
    cache_key, signature = _owner_index_cache_key(log_path, "ungrouped")
    cached = _lookup_owner_line_index(cache_key)
    if cached is None:
        (
            index,
            matched_codes,
            orphan_matches,
            total_lines,
        ) = _build_ungrouped_owner_line_index_with_scan(
            log_path,
            signature,
            matcher,
            progress=progress,
            match_callback=match_callback,
        )
        _cache_owner_line_index(cache_key, index)
    else:
        index = cached
        matched_codes = set()
        orphan_matches = []
        total_lines = 0
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for zero_based, raw_line in enumerate(handle):
                _advance_search_progress(progress, raw_line)
                total_lines += 1
                line = raw_line.rstrip("\r\n")
                owner_code = (
                    index.owner_codes[zero_based]
                    if zero_based < len(index.owner_codes)
                    else -1
                )
                if not matcher(line):
                    continue
                _report_match(match_callback, zero_based + 1, line)
                if owner_code >= 0:
                    matched_codes.add(owner_code)
                else:
                    orphan_matches.append((zero_based + 1, line))

    if not matched_codes:
        return SmtpSearchResult(
            term=term,
            log_path=log_path,
            conversations=[],
            total_lines=total_lines,
            orphan_matches=orphan_matches,
        )

    conversations_by_code: dict[int, Conversation] = {}
    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for zero_based, raw_line in enumerate(handle):
            _advance_search_progress(progress, raw_line)
            owner_code = (
                index.owner_codes[zero_based]
                if zero_based < len(index.owner_codes)
                else -1
            )
            if owner_code not in matched_codes:
                continue
            conversation = conversations_by_code.get(owner_code)
            if conversation is None:
                conversation = Conversation(
                    message_id=index.owner_ids[owner_code],
                    lines=[],
                    first_line_number=index.owner_first_lines[owner_code],
                )
                conversations_by_code[owner_code] = conversation
            conversation.lines.append(raw_line.rstrip("\r\n"))

    conversations = list(conversations_by_code.values())
    conversations.sort(key=lambda conv: conv.first_line_number)
    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def _search_grouped_entries(
    log_path: Path,
    term: str,
    owner_for_line: Callable[[str], str | None],
    *,
    mode: str,
    fuzzy_threshold: float,
    ignore_case: bool,
    materialization: str,
    use_index_cache: bool,
    progress_callback: SearchProgressCallback | None,
    match_callback: SearchMatchCallback | None,
    owner_key: str,
) -> SmtpSearchResult:
    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )
    resolved_materialization = normalize_materialization_mode(materialization)
    expected_passes = 1
    if (
        use_index_cache
        or resolved_materialization != MATERIALIZATION_SINGLE_PASS
    ):
        expected_passes = 2
    progress = _start_search_progress(
        log_path,
        progress_callback,
        expected_passes=expected_passes,
    )
    try:
        if use_index_cache:
            return _search_grouped_with_index(
                log_path,
                term,
                matcher,
                owner_for_line,
                owner_key=owner_key,
                progress=progress,
                match_callback=match_callback,
            )
        if resolved_materialization == MATERIALIZATION_TWO_PASS:
            return _search_grouped_two_pass(
                log_path,
                term,
                matcher,
                owner_for_line,
                progress=progress,
                match_callback=match_callback,
            )
        return _search_grouped_single_pass(
            log_path,
            term,
            matcher,
            owner_for_line,
            auto_fallback=resolved_materialization == MATERIALIZATION_AUTO,
            progress=progress,
            match_callback=match_callback,
        )
    finally:
        _finish_search_progress(progress)


def _search_grouped_two_pass(
    log_path: Path,
    term: str,
    matcher: Callable[[str], bool],
    owner_for_line: Callable[[str], str | None],
    *,
    progress: _SearchProgress | None,
    match_callback: SearchMatchCallback | None,
) -> SmtpSearchResult:
    matched_ids, orphan_matches, total_lines = _scan_grouped_matches(
        log_path,
        matcher,
        owner_for_line,
        progress=progress,
        match_callback=match_callback,
    )
    if not matched_ids:
        return SmtpSearchResult(
            term=term,
            log_path=log_path,
            conversations=[],
            total_lines=total_lines,
            orphan_matches=orphan_matches,
        )

    conversations = _collect_grouped_conversations(
        log_path,
        matched_ids,
        owner_for_line,
        progress=progress,
    )
    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def _scan_grouped_matches(
    log_path: Path,
    matcher: Callable[[str], bool],
    owner_for_line: Callable[[str], str | None],
    *,
    progress: _SearchProgress | None,
    match_callback: SearchMatchCallback | None,
) -> tuple[set[str], list[tuple[int, str]], int]:
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            total_lines += 1
            line = raw_line.rstrip("\r\n")
            line_owner_id: str | None = None
            owner_id = owner_for_line(line)
            if owner_id is not None:
                current_id = owner_id
                line_owner_id = owner_id
            elif starts_with_timestamp(line):
                current_id = None
            elif current_id is not None:
                line_owner_id = current_id

            if matcher(line):
                _report_match(match_callback, line_number, line)
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))
    return matched_ids, orphan_matches, total_lines


def _collect_grouped_conversations(
    log_path: Path,
    matched_ids: set[str],
    owner_for_line: Callable[[str], str | None],
    *,
    progress: _SearchProgress | None,
) -> list[Conversation]:
    builders: dict[str, Conversation] = {}
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            line = raw_line.rstrip("\r\n")
            line_owner_id: str | None = None
            owner_id = owner_for_line(line)
            if owner_id is not None:
                current_id = owner_id
                line_owner_id = owner_id
            elif starts_with_timestamp(line):
                current_id = None
            elif current_id is not None:
                line_owner_id = current_id

            if line_owner_id is None or line_owner_id not in matched_ids:
                continue
            conversation = builders.get(line_owner_id)
            if conversation is None:
                conversation = Conversation(
                    message_id=line_owner_id,
                    lines=[],
                    first_line_number=line_number,
                )
                builders[line_owner_id] = conversation
            conversation.lines.append(line)

    conversations = list(builders.values())
    conversations.sort(key=lambda conv: conv.first_line_number)
    return conversations


def _search_grouped_single_pass(
    log_path: Path,
    term: str,
    matcher: Callable[[str], bool],
    owner_for_line: Callable[[str], str | None],
    *,
    auto_fallback: bool,
    progress: _SearchProgress | None,
    match_callback: SearchMatchCallback | None,
) -> SmtpSearchResult:
    builders: dict[str, Conversation] = {}
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None
    sample_match_lines = 0
    sample_owner_ids: set[str] = set()
    sample_matched_owner_ids: set[str] = set()

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            total_lines += 1
            line = raw_line.rstrip("\r\n")
            line_owner_id: str | None = None
            owner_id = owner_for_line(line)
            if owner_id is not None:
                current_id = owner_id
                line_owner_id = owner_id
                conversation = builders.get(owner_id)
                if conversation is None:
                    conversation = Conversation(
                        message_id=owner_id,
                        lines=[],
                        first_line_number=line_number,
                    )
                    builders[owner_id] = conversation
                conversation.lines.append(line)
            elif starts_with_timestamp(line):
                current_id = None
            elif current_id is not None:
                line_owner_id = current_id
                conversation = builders.get(current_id)
                if conversation is None:
                    conversation = Conversation(
                        message_id=current_id,
                        lines=[],
                        first_line_number=line_number,
                    )
                    builders[current_id] = conversation
                conversation.lines.append(line)

            is_match = matcher(line)
            if is_match:
                _report_match(match_callback, line_number, line)
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))

            if line_number > _AUTO_SAMPLE_LINES:
                continue
            if owner_id is not None:
                sample_owner_ids.add(owner_id)
            if is_match:
                sample_match_lines += 1
                if line_owner_id is not None:
                    sample_matched_owner_ids.add(line_owner_id)
            if (
                auto_fallback
                and line_number == _AUTO_SAMPLE_LINES
                and _looks_like_sparse_query(
                    line_number,
                    sample_match_lines,
                    len(sample_owner_ids),
                    len(sample_matched_owner_ids),
                )
            ):
                return _search_grouped_two_pass(
                    log_path,
                    term,
                    matcher,
                    owner_for_line,
                    progress=progress,
                    match_callback=match_callback,
                )

    conversations = [
        builders[mid]
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


def _looks_like_sparse_query(
    sample_lines: int,
    sample_match_lines: int,
    sample_owner_count: int,
    sample_matched_owner_count: int,
) -> bool:
    if sample_lines <= 0:
        return False
    line_match_ratio = sample_match_lines / sample_lines
    if sample_owner_count <= 0:
        return line_match_ratio <= _AUTO_MAX_LINE_MATCH_RATIO
    owner_match_ratio = sample_matched_owner_count / sample_owner_count
    return (
        line_match_ratio <= _AUTO_MAX_LINE_MATCH_RATIO
        and owner_match_ratio <= _AUTO_MAX_OWNER_MATCH_RATIO
    )


def _search_ungrouped_two_pass(
    log_path: Path,
    term: str,
    matcher: Callable[[str], bool],
    *,
    progress: _SearchProgress | None,
    match_callback: SearchMatchCallback | None,
) -> SmtpSearchResult:
    matched_ids, orphan_matches, total_lines = _scan_ungrouped_matches(
        log_path,
        matcher,
        progress=progress,
        match_callback=match_callback,
    )
    if not matched_ids:
        return SmtpSearchResult(
            term=term,
            log_path=log_path,
            conversations=[],
            total_lines=total_lines,
            orphan_matches=orphan_matches,
        )

    conversations = _collect_ungrouped_conversations(
        log_path,
        matched_ids,
        progress=progress,
    )
    return SmtpSearchResult(
        term=term,
        log_path=log_path,
        conversations=conversations,
        total_lines=total_lines,
        orphan_matches=orphan_matches,
    )


def _scan_ungrouped_matches(
    log_path: Path,
    matcher: Callable[[str], bool],
    *,
    progress: _SearchProgress | None,
    match_callback: SearchMatchCallback | None,
) -> tuple[set[str], list[tuple[int, str]], int]:
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            total_lines += 1
            line = raw_line.rstrip("\r\n")
            line_owner_id: str | None = None
            if starts_with_timestamp(line):
                current_id = f"{line_number}"
                line_owner_id = current_id
            elif current_id is not None:
                line_owner_id = current_id

            if matcher(line):
                _report_match(match_callback, line_number, line)
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))
    return matched_ids, orphan_matches, total_lines


def _collect_ungrouped_conversations(
    log_path: Path,
    matched_ids: set[str],
    *,
    progress: _SearchProgress | None,
) -> list[Conversation]:
    builders: dict[str, Conversation] = {}
    current_id: str | None = None

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            line = raw_line.rstrip("\r\n")
            line_owner_id: str | None = None
            if starts_with_timestamp(line):
                current_id = f"{line_number}"
                line_owner_id = current_id
            elif current_id is not None:
                line_owner_id = current_id

            if line_owner_id is None or line_owner_id not in matched_ids:
                continue
            conversation = builders.get(line_owner_id)
            if conversation is None:
                conversation = Conversation(
                    message_id=line_owner_id,
                    lines=[],
                    first_line_number=line_number,
                )
                builders[line_owner_id] = conversation
            conversation.lines.append(line)

    conversations = list(builders.values())
    conversations.sort(key=lambda conv: conv.first_line_number)
    return conversations


def _search_ungrouped_single_pass(
    log_path: Path,
    term: str,
    matcher: Callable[[str], bool],
    *,
    auto_fallback: bool,
    progress: _SearchProgress | None,
    match_callback: SearchMatchCallback | None,
) -> SmtpSearchResult:
    builders: dict[str, Conversation] = {}
    matched_ids: set[str] = set()
    orphan_matches: list[tuple[int, str]] = []
    total_lines = 0
    current_id: str | None = None
    sample_match_lines = 0
    sample_owner_count = 0
    sample_matched_owner_ids: set[str] = set()

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            _advance_search_progress(progress, raw_line)
            total_lines += 1
            line = raw_line.rstrip("\r\n")
            line_owner_id: str | None = None
            owner_id: str | None = None
            if starts_with_timestamp(line):
                owner_id = f"{line_number}"
                current_id = owner_id
                line_owner_id = owner_id
                sample_owner_count += 1
                conversation = Conversation(
                    message_id=owner_id,
                    lines=[],
                    first_line_number=line_number,
                )
                builders[owner_id] = conversation
                conversation.lines.append(line)
            elif current_id is not None:
                line_owner_id = current_id
                conversation = builders.get(current_id)
                if conversation is None:
                    conversation = Conversation(
                        message_id=current_id,
                        lines=[],
                        first_line_number=line_number,
                    )
                    builders[current_id] = conversation
                conversation.lines.append(line)

            is_match = matcher(line)
            if is_match:
                _report_match(match_callback, line_number, line)
                if line_owner_id is not None:
                    matched_ids.add(line_owner_id)
                else:
                    orphan_matches.append((line_number, line))

            if line_number > _AUTO_SAMPLE_LINES:
                continue
            if is_match:
                sample_match_lines += 1
                if line_owner_id is not None:
                    sample_matched_owner_ids.add(line_owner_id)
            if (
                auto_fallback
                and line_number == _AUTO_SAMPLE_LINES
                and _looks_like_sparse_query(
                    line_number,
                    sample_match_lines,
                    sample_owner_count,
                    len(sample_matched_owner_ids),
                )
            ):
                return _search_ungrouped_two_pass(
                    log_path,
                    term,
                    matcher,
                    progress=progress,
                    match_callback=match_callback,
                )

    conversations = [
        builders[mid]
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
    if resolved_mode == MODE_WILDCARD:
        return _compile_wildcard_line_matcher(term, ignore_case)
    if resolved_mode == MODE_REGEX:
        return _compile_regex_line_matcher(term, ignore_case)

    if resolved_mode == MODE_FUZZY:
        threshold = normalize_fuzzy_threshold(fuzzy_threshold)
        normalized_term = term.lower() if ignore_case else term
        return _compile_fuzzy_line_matcher(
            normalized_term,
            threshold,
            ignore_case=ignore_case,
        )

    pattern = _compile_match_pattern(term, resolved_mode, ignore_case)
    search = pattern.search
    return lambda line: search(line) is not None


def _compile_literal_line_matcher(
    term: str,
    ignore_case: bool,
) -> Callable[[str], bool]:
    if ignore_case:
        term = term.lower()
        lower = str.lower
        return lambda line: term in lower(line)
    return lambda line: term in line


def _compile_wildcard_line_matcher(
    term: str,
    ignore_case: bool,
) -> Callable[[str], bool]:
    if "*" not in term and "?" not in term:
        return _compile_literal_line_matcher(term, ignore_case)
    pattern = _compile_match_pattern(term, MODE_WILDCARD, ignore_case)
    search = pattern.search
    literal_hint = _longest_wildcard_literal(term)
    if len(literal_hint) < 2:
        return lambda line: search(line) is not None
    if ignore_case:
        hint = literal_hint.lower()
        return lambda line: hint in line.lower() and search(line) is not None
    return lambda line: literal_hint in line and search(line) is not None


def _longest_wildcard_literal(term: str) -> str:
    longest = ""
    current: list[str] = []
    for char in term:
        if char in {"*", "?"}:
            token = "".join(current)
            if len(token) > len(longest):
                longest = token
            current.clear()
            continue
        current.append(char)
    token = "".join(current)
    if len(token) > len(longest):
        longest = token
    return longest


def _compile_regex_line_matcher(
    term: str,
    ignore_case: bool,
) -> Callable[[str], bool]:
    if _is_plain_regex_literal(term):
        return _compile_literal_line_matcher(term, ignore_case)
    pattern = _compile_match_pattern(term, MODE_REGEX, ignore_case)
    search = pattern.search
    return lambda line: search(line) is not None


def _is_plain_regex_literal(term: str) -> bool:
    regex_meta = {
        "\\",
        ".",
        "^",
        "$",
        "*",
        "+",
        "?",
        "{",
        "}",
        "[",
        "]",
        "|",
        "(",
        ")",
    }
    return all(char not in regex_meta for char in term)


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


def _owner_strategy_for_kind(
    kind: str,
) -> tuple[str, Callable[[str], str | None] | None]:
    kind_key = normalize_kind(kind)
    if kind_key in {KIND_SMTP, KIND_IMAP, KIND_POP}:
        return "smtp", _smtp_owner_id
    if kind_key == KIND_DELIVERY:
        return "delivery", _delivery_owner_id
    if kind_key == KIND_ADMINISTRATIVE:
        return "admin", _admin_owner_id
    if kind_key == KIND_IMAP_RETRIEVAL:
        return "imap-retrieval", _imap_retrieval_owner_id
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
        return "ungrouped", None
    raise ValueError(f"Unsupported log kind: {kind}")


def has_search_index(log_path: Path, kind: str) -> bool:
    """Return whether an owner index is cached for ``log_path`` and ``kind``."""

    owner_key, _owner_for_line = _owner_strategy_for_kind(kind)
    cache_key, _signature = _owner_index_cache_key(log_path, owner_key)
    return _lookup_owner_line_index(cache_key) is not None


def prime_search_index(log_path: Path, kind: str) -> None:
    """Build and cache a search owner index for ``log_path`` and ``kind``."""

    owner_key, owner_for_line = _owner_strategy_for_kind(kind)
    cache_key, signature = _owner_index_cache_key(log_path, owner_key)
    if _lookup_owner_line_index(cache_key) is not None:
        return

    never_match = lambda _line: False
    if owner_key == "ungrouped":
        index, _matched, _orphans, _count = (
            _build_ungrouped_owner_line_index_with_scan(
                log_path,
                signature,
                never_match,
            )
        )
    else:
        assert owner_for_line is not None
        index, _matched, _orphans, _count = (
            _build_grouped_owner_line_index_with_scan(
                log_path,
                owner_for_line,
                owner_key,
                signature,
                never_match,
            )
        )
    _cache_owner_line_index(cache_key, index)


def _smtp_owner_id(line: str) -> str | None:
    match = _SMTP_OWNER_PATTERN.match(line)
    if match is None:
        return None
    return match.group(1)


def _delivery_owner_id(line: str) -> str | None:
    match = _DELIVERY_OWNER_PATTERN.match(line)
    if match is None:
        return None
    return match.group(1)


def _imap_retrieval_owner_id(line: str) -> str | None:
    match = _IMAP_RETRIEVAL_OWNER_PATTERN.match(line)
    if match is None:
        return None
    return match.group(1)


def _admin_owner_id(line: str) -> str | None:
    match = _ADMIN_OWNER_PATTERN.match(line)
    if match is not None:
        return f"{match.group('ip')} {match.group('time')}"
    trailing_match = _ADMIN_TRAILING_OWNER_PATTERN.match(line)
    if trailing_match is None:
        return None
    return f"{trailing_match.group('ip')} {trailing_match.group('time')}"


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
