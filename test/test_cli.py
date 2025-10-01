"""Basic tests for the sm_logtool CLI skeleton."""

from __future__ import annotations

import pytest

from sm_logtool import cli


def test_scan_logs_handles_missing_directory(tmp_path):
    missing_dir = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        cli.scan_logs(missing_dir)


def test_scan_logs_lists_files(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "2024-05-01.log").write_text("line1\n", encoding="utf-8")
    (logs_dir / "2024-05-02.log").write_text("line2\n", encoding="utf-8")

    files = cli.scan_logs(logs_dir)

    assert [file.name for file in files] == ["2024-05-01.log", "2024-05-02.log"]
