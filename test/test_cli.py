"""Basic tests for the sm_logtool CLI skeleton."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - fallback for unittest
    from test import _pytest_stub as pytest

from sm_logtool import cli
from sm_logtool.config import AppConfig


def create_smtp_zip(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w') as archive:
        archive.writestr(path.name.replace('.zip', ''), content)




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

    assert [file.name for file in files] == [
        "2024-05-01.log",
        "2024-05-02.log",
    ]


def test_run_search_supports_date_selection(tmp_path, capsys):
    logs_dir = tmp_path / 'logs'
    staging_dir = tmp_path / 'staging'
    zip_path = logs_dir / '2024.01.01-smtpLog.log.zip'
    create_smtp_zip(
        zip_path,
        (
            "00:00:00 [1.1.1.1][MSG1] initial\n"
            "00:00:01 [1.1.1.1][MSG1] HELLO there\n"
        ),
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date='2024.01.01',
        list=False,
        case_sensitive=False,
        term='hello',
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtpLog",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert 'MSG1' in captured.out
    assert 'Search term' in captured.out
