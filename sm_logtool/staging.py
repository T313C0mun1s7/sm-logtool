"""Routines for staging logs before analysis."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import math
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from .logfiles import LogFileInfo, parse_log_filename


DEFAULT_STAGING_ROOT = Path.home() / ".cache" / "sm-logtool" / "staging"
DEFAULT_STAGING_RETENTION_DAYS = 14
_SECONDS_PER_DAY = 24 * 60 * 60
_STAMP_NAME_RE = re.compile(r"^(?P<stamp>\d{4}\.\d{2}\.\d{2})-")
_SUBSEARCH_NAME_RE = re.compile(
    r"^subsearch_\d{2}_(?P<stamp>\d{8}_\d{6})\.log$",
)


@dataclass(frozen=True)
class StagedLog:
    """Information about a staged log."""

    source: Path
    staged_path: Path
    info: LogFileInfo


@dataclass(frozen=True)
class StagingPruneReport:
    """Summary of a staging-directory prune operation."""

    scanned_files: int = 0
    removed_files: int = 0
    warnings: tuple[str, ...] = ()


def _needs_refresh(
    info: LogFileInfo,
    *,
    today: date | None = None,
    force: bool = False,
) -> bool:
    if force:
        return True
    if info.stamp is None:
        return False
    return info.stamp == (today or date.today())


def _target_path(staging_dir: Path, info: LogFileInfo) -> Path:
    if info.is_zipped:
        return staging_dir / Path(info.path.name).with_suffix("")
    return staging_dir / info.path.name


def stage_log(
    source_path: Path,
    staging_dir: Optional[Path] = None,
    *,
    force: bool = False,
    today: Optional[date] = None,
) -> StagedLog:
    """Copy ``source_path`` into ``staging_dir`` (unzipping if needed).

    ``today`` is exposed for testing so that we can control the refresh logic
    that keeps the current day's logs in sync. Returns metadata describing the
    staged file.
    """

    staging_dir = staging_dir or DEFAULT_STAGING_ROOT
    staging_dir.mkdir(parents=True, exist_ok=True)

    info = parse_log_filename(source_path)
    target = _target_path(staging_dir, info)
    refresh = _needs_refresh(info, today=today, force=force)

    if target.exists() and not refresh:
        return StagedLog(source=source_path, staged_path=target, info=info)

    if target.exists():
        target.unlink()

    if info.is_zipped:
        _extract_single_member_zip(source_path, target)
    else:
        shutil.copy2(source_path, target)

    return StagedLog(source=source_path, staged_path=target, info=info)


def prune_staging_dir(
    staging_dir: Optional[Path],
    *,
    retention_days: int = DEFAULT_STAGING_RETENTION_DAYS,
    now: datetime | None = None,
) -> StagingPruneReport:
    """Delete staged files older than ``retention_days``.

    Pruning is best-effort: per-file metadata/read/delete failures are recorded
    as warnings and do not raise.
    """

    if retention_days < 0:
        raise ValueError("retention_days must be >= 0")
    if staging_dir is None or not staging_dir.exists():
        return StagingPruneReport()
    if not staging_dir.is_dir():
        warning = f"Skipping prune for non-directory path: {staging_dir}"
        return StagingPruneReport(warnings=(warning,))

    now_utc = now or datetime.now(timezone.utc)
    cutoff = now_utc.timestamp() - (retention_days * _SECONDS_PER_DAY)
    warnings: list[str] = []
    scanned_files = 0
    removed_files = 0

    for entry in staging_dir.rglob("*"):
        if not _is_regular_file(entry, warnings):
            continue
        scanned_files += 1
        timestamp = _entry_timestamp(entry, warnings)
        if timestamp is None or timestamp >= cutoff:
            continue
        try:
            entry.unlink()
        except FileNotFoundError:
            continue
        except OSError as exc:
            warnings.append(f"Could not remove {entry}: {exc}")
            continue
        removed_files += 1

    return StagingPruneReport(
        scanned_files=scanned_files,
        removed_files=removed_files,
        warnings=tuple(warnings),
    )


def prune_warning_lines(
    report: StagingPruneReport,
    *,
    limit: int = 5,
) -> list[str]:
    """Return warning lines for user-facing output with truncation."""

    if limit < 1:
        raise ValueError("limit must be >= 1")
    lines = list(report.warnings[:limit])
    hidden_count = len(report.warnings) - len(lines)
    if hidden_count > 0:
        lines.append(
            f"...plus {hidden_count} additional staging cleanup warning(s)."
        )
    return lines


def _is_regular_file(path: Path, warnings: list[str]) -> bool:
    try:
        return path.is_file()
    except FileNotFoundError:
        return False
    except OSError as exc:
        warnings.append(f"Could not inspect {path}: {exc}")
        return False


def _entry_timestamp(path: Path, warnings: list[str]) -> float | None:
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None
    except OSError as exc:
        warnings.append(f"Could not read metadata for {path}: {exc}")
        return _timestamp_from_name(path.name)
    if math.isfinite(mtime) and mtime > 0:
        return mtime
    return _timestamp_from_name(path.name)


def _timestamp_from_name(filename: str) -> float | None:
    date_stamp = _date_stamp_from_name(filename)
    if date_stamp is not None:
        return date_stamp
    return _subsearch_stamp_from_name(filename)


def _date_stamp_from_name(filename: str) -> float | None:
    match = _STAMP_NAME_RE.match(filename)
    if match is None:
        return None
    stamp = match.group("stamp")
    try:
        parsed = datetime.strptime(stamp, "%Y.%m.%d")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def _subsearch_stamp_from_name(filename: str) -> float | None:
    match = _SUBSEARCH_NAME_RE.match(filename)
    if match is None:
        return None
    stamp = match.group("stamp")
    try:
        parsed = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def _extract_single_member_zip(zip_path: Path, target: Path) -> None:
    with ZipFile(zip_path) as archive:
        members = [
            member
            for member in archive.namelist()
            if not member.endswith("/")
        ]
        if not members:
            raise ValueError(f"Zip file {zip_path} contains no files")
        if len(members) > 1:
            message = (
                f"Zip file {zip_path} contains multiple members; "
                "expected one"
            )
            raise ValueError(message)
        member = members[0]
        with archive.open(member) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)
