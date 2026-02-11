"""Helpers for working with SmarterMail log filenames."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
import re
from typing import List, Optional

from .log_kinds import normalize_kind


class UnknownLogDate(ValueError):
    """Raised when parsing a log filename or stamp fails."""



_LOG_NAME_PATTERN = re.compile(
    r"^(?P<stamp>\d{4}\.\d{2}\.\d{2})-(?P<kind>[A-Za-z]+)\.log(?P<zip>\.zip)?$"
)


@dataclass(frozen=True)
class LogFileInfo:
    """Parsed details about a log file path."""

    path: Path
    stamp: Optional[date]
    kind: str
    is_zipped: bool

    @property
    def base_name(self) -> str:
        return self.path.name[:-4] if self.is_zipped else self.path.name


def parse_log_filename(path: Path) -> LogFileInfo:
    """Parse ``path`` into ``LogFileInfo``.

    If the filename does not match the expected pattern we return the original
    path with ``stamp=None`` and ``kind=""`` so callers can skip it.
    """

    match = _LOG_NAME_PATTERN.match(path.name)
    if not match:
        return LogFileInfo(
            path=path,
            stamp=None,
            kind="",
            is_zipped=path.suffix == ".zip",
        )

    stamp = datetime.strptime(match.group("stamp"), "%Y.%m.%d").date()
    kind = normalize_kind(match.group("kind"))
    is_zipped = bool(match.group("zip"))
    return LogFileInfo(path=path, stamp=stamp, kind=kind, is_zipped=is_zipped)

def parse_stamp(value: str) -> date:
    """Parse a SmarterMail log date stamp (YYYY.MM.DD)."""

    try:
        return datetime.strptime(value, "%Y.%m.%d").date()
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise UnknownLogDate(f"Invalid log date stamp: {value!r}") from exc


def find_log_by_date(
    logs_dir: Path,
    kind: str,
    target_date: date,
) -> Optional[LogFileInfo]:
    """Return the log matching ``target_date`` for ``kind`` if present."""

    candidates = discover_logs(logs_dir, kind)
    for info in candidates:
        if info.stamp == target_date:
            return info
    return None


def summarize_logs(logs_dir: Path, kind: str) -> list[LogFileInfo]:
    """Return available logs for ``kind`` sorted newest first."""

    return discover_logs(logs_dir, kind)



def discover_logs(logs_dir: Path, kind: str) -> List[LogFileInfo]:
    """Return log files of ``kind`` sorted by date (newest first).

    ``kind`` accepts canonical keys (for example ``smtp`` or ``imap``) and
    legacy aliases (for example ``smtpLog`` or ``imapLog``).
    """

    if not logs_dir.exists():
        return []

    requested_kind = normalize_kind(kind)
    infos: list[LogFileInfo] = []
    for path in logs_dir.iterdir():
        if not path.is_file():
            continue
        info = parse_log_filename(path)
        if info.kind != requested_kind:
            continue
        infos.append(info)

    infos.sort(
        key=lambda item: (
            item.stamp or date.min,
            not item.is_zipped,
            item.path.name,
        ),
        reverse=True,
    )
    return infos


def newest_log(logs_dir: Path, kind: str) -> Optional[LogFileInfo]:
    """Return the most recent log file for ``kind`` if available."""

    logs = discover_logs(logs_dir, kind)
    return logs[0] if logs else None
