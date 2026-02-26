from __future__ import annotations

from datetime import datetime
from datetime import timezone
import os
from pathlib import Path
from types import SimpleNamespace

from sm_logtool.staging import prune_staging_dir


def test_prune_staging_dir_missing_directory_is_noop(tmp_path):
    staging_dir = tmp_path / "missing"
    report = prune_staging_dir(staging_dir)

    assert report.scanned_files == 0
    assert report.removed_files == 0
    assert report.warnings == ()


def test_prune_staging_dir_removes_only_files_older_than_cutoff(tmp_path):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    old_file = staging_dir / "2026.02.01-smtpLog.log"
    new_file = staging_dir / "2026.02.20-smtpLog.log"
    old_file.write_text("old\n", encoding="utf-8")
    new_file.write_text("new\n", encoding="utf-8")

    now = datetime(2026, 2, 26, tzinfo=timezone.utc)
    old_stamp = datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp()
    new_stamp = datetime(2026, 2, 20, tzinfo=timezone.utc).timestamp()
    os.utime(old_file, (old_stamp, old_stamp))
    os.utime(new_file, (new_stamp, new_stamp))

    report = prune_staging_dir(staging_dir, retention_days=14, now=now)

    assert report.scanned_files == 2
    assert report.removed_files == 1
    assert report.warnings == ()
    assert old_file.exists() is False
    assert new_file.exists() is True


def test_prune_staging_dir_continues_when_delete_fails(tmp_path, monkeypatch):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    stale_file = staging_dir / "2026.02.01-smtpLog.log"
    stale_file.write_text("stale\n", encoding="utf-8")
    stale_stamp = datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp()
    os.utime(stale_file, (stale_stamp, stale_stamp))
    now = datetime(2026, 2, 26, tzinfo=timezone.utc)

    original_unlink = Path.unlink

    def fake_unlink(self, *args, **kwargs):  # noqa: ANN001
        if self == stale_file:
            raise PermissionError("denied")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    report = prune_staging_dir(staging_dir, retention_days=14, now=now)

    assert report.removed_files == 0
    assert stale_file.exists() is True
    assert len(report.warnings) == 1
    assert "Could not remove" in report.warnings[0]


def test_prune_staging_dir_uses_filename_when_mtime_is_invalid(
    tmp_path,
    monkeypatch,
):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    stale_file = staging_dir / "2026.02.01-smtpLog.log"
    stale_file.write_text("stale\n", encoding="utf-8")
    now = datetime(2026, 2, 26, tzinfo=timezone.utc)
    current_stamp = now.timestamp()
    os.utime(stale_file, (current_stamp, current_stamp))

    original_stat = Path.stat

    def fake_stat(self, *args, **kwargs):  # noqa: ANN001
        if self == stale_file:
            return SimpleNamespace(st_mtime=float("nan"))
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    report = prune_staging_dir(staging_dir, retention_days=14, now=now)

    assert report.removed_files == 1
    assert stale_file.exists() is False
