"""Routines for staging logs before analysis."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from .logfiles import LogFileInfo, parse_log_filename


DEFAULT_STAGING_ROOT = Path.home() / ".cache" / "sm-logtool" / "staging"


@dataclass(frozen=True)
class StagedLog:
    """Information about a staged log."""

    source: Path
    staged_path: Path
    info: LogFileInfo


def _needs_refresh(info: LogFileInfo, *, today: date | None = None, force: bool = False) -> bool:
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


def _extract_single_member_zip(zip_path: Path, target: Path) -> None:
    with ZipFile(zip_path) as archive:
        members = [member for member in archive.namelist() if not member.endswith("/")]
        if not members:
            raise ValueError(f"Zip file {zip_path} contains no files")
        if len(members) > 1:
            raise ValueError(f"Zip file {zip_path} contains multiple members; expected one")
        member = members[0]
        with archive.open(member) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst)

