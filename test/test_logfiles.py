from __future__ import annotations

from datetime import date
from pathlib import Path

from sm_logtool import logfiles


def test_find_log_by_date_returns_matching_file(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "2024.01.01-smtpLog.log").write_text("\n")
    (logs_dir / "2024.01.02-smtpLog.log").write_text("\n")

    info = logfiles.find_log_by_date(logs_dir, "smtp", date(2024, 1, 2))
    assert info is not None
    assert info.path.name == "2024.01.02-smtpLog.log"


def test_discover_logs_sorts_newest_first(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "2024.01.01-smtpLog.log").write_text("\n")
    (logs_dir / "2024.01.03-smtpLog.log.zip").write_text("fake zip")
    (logs_dir / "2024.01.02-smtpLog.log").write_text("\n")

    infos = logfiles.discover_logs(logs_dir, "smtp")
    assert [info.path.name for info in infos] == [
        "2024.01.03-smtpLog.log.zip",
        "2024.01.02-smtpLog.log",
        "2024.01.01-smtpLog.log",
    ]


def test_parse_stamp_rejects_invalid_value():
    try:
        logfiles.parse_stamp("2024-01-01")
    except logfiles.UnknownLogDate as exc:
        assert "Invalid log date stamp" in str(exc)
    else:
        raise AssertionError("Expected UnknownLogDate to be raised")
