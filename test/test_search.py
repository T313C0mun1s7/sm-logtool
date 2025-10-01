from __future__ import annotations

from datetime import date
from pathlib import Path
from zipfile import ZipFile

from sm_logtool import search
from sm_logtool.staging import stage_log


def write_zip(path: Path, member_name: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr(member_name, content)


def test_stage_log_extracts_zip_and_skips_refresh(tmp_path):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    zip_path = logs_dir / "2024.01.01-smtpLog.log.zip"
    write_zip(zip_path, "2024.01.01-smtpLog.log", "first\n")

    staged = stage_log(zip_path, staging_dir=staging_dir, today=date(2024, 1, 2))
    assert staged.staged_path.exists()
    assert staged.staged_path.read_text() == "first\n"

    # Mutate staged file to confirm a subsequent call without refresh leaves it alone.
    staged.staged_path.write_text("changed\n")
    stage_log(zip_path, staging_dir=staging_dir, today=date(2024, 1, 2))
    assert staged.staged_path.read_text() == "changed\n"


def test_stage_log_refreshes_for_today(tmp_path):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.02-smtpLog.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text("initial\n")

    staged = stage_log(log_path, staging_dir=staging_dir, today=date(2024, 1, 2))
    assert staged.staged_path.read_text() == "initial\n"

    log_path.write_text("updated\n")
    staged = stage_log(log_path, staging_dir=staging_dir, today=date(2024, 1, 2))
    assert staged.staged_path.read_text() == "updated\n"


def test_search_smtp_conversations_groups_lines(tmp_path):
    log_path = tmp_path / "smtp.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] Connection initiated\n"
        "00:00:01 [1.1.1.1][ABC123] User HELLO logged in\n"
        "00:00:02 [2.2.2.2][XYZ789] Another line\n"
        "00:00:03 [2.2.2.2][XYZ789] hello world\n"
        "00:00:04 No identifier here but hello anyway\n"
    )

    result = search.search_smtp_conversations(log_path, "hello")

    assert result.total_conversations == 2
    first = result.conversations[0]
    assert first.message_id == "ABC123"
    assert first.first_line_number == 1
    assert first.lines == [
        "00:00:00 [1.1.1.1][ABC123] Connection initiated",
        "00:00:01 [1.1.1.1][ABC123] User HELLO logged in",
    ]

    second = result.conversations[1]
    assert second.message_id == "XYZ789"
    assert second.lines[-1].endswith("hello world")

    assert result.orphan_matches == [(5, "00:00:04 No identifier here but hello anyway")]

