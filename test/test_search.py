from __future__ import annotations

from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest

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

    staged = stage_log(
        zip_path,
        staging_dir=staging_dir,
        today=date(2024, 1, 2),
    )
    assert staged.staged_path.exists()
    assert staged.staged_path.read_text() == "first\n"

    # Mutate staged file to confirm a subsequent call without refresh
    # leaves it alone.
    staged.staged_path.write_text("changed\n")
    stage_log(
        zip_path,
        staging_dir=staging_dir,
        today=date(2024, 1, 2),
    )
    assert staged.staged_path.read_text() == "changed\n"


def test_stage_log_refreshes_for_today(tmp_path):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.02-smtpLog.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text("initial\n")

    staged = stage_log(
        log_path,
        staging_dir=staging_dir,
        today=date(2024, 1, 2),
    )
    assert staged.staged_path.read_text() == "initial\n"

    log_path.write_text("updated\n")
    staged = stage_log(
        log_path,
        staging_dir=staging_dir,
        today=date(2024, 1, 2),
    )
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

    assert result.orphan_matches == [
        (5, "00:00:04 No identifier here but hello anyway")
    ]


def test_search_smtp_conversations_continuations(tmp_path):
    log_path = tmp_path / "smtp.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] Start\n"
        "  continuation with needle\n"
        "00:00:01 [1.1.1.1][ABC123] Next\n"
    )

    result = search.search_smtp_conversations(log_path, "needle")

    assert result.total_conversations == 1
    assert result.orphan_matches == []
    assert result.conversations[0].lines[1].startswith("  continuation")


def test_search_literal_mode_treats_regex_tokens_as_plain_text(tmp_path):
    log_path = tmp_path / "generalErrors.log"
    log_path.write_text(
        "00:00:01.100 Message with regex-like token (foo|bar)\n"
        "00:00:02.200 Message without token\n"
    )

    result = search.search_ungrouped_entries(
        log_path,
        "(foo|bar)",
        mode="literal",
    )

    assert result.total_conversations == 1
    assert result.conversations[0].lines[0].endswith("(foo|bar)")


def test_search_literal_mode_respects_case_sensitivity_flag(tmp_path):
    log_path = tmp_path / "smtp.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] User HELLO logged in\n",
    )

    insensitive = search.search_smtp_conversations(
        log_path,
        "hello",
        mode="literal",
    )
    sensitive = search.search_smtp_conversations(
        log_path,
        "hello",
        mode="literal",
        ignore_case=False,
    )

    assert insensitive.total_conversations == 1
    assert sensitive.total_conversations == 0


def test_search_delivery_conversations_continuations(tmp_path):
    log_path = tmp_path / "delivery.log"
    log_path.write_text(
        "00:00:01.100 [84012345] Delivery started\n"
        "  stack trace needle\n"
        "00:00:02.200 [84012346] Delivery started\n"
    )

    result = search.search_delivery_conversations(log_path, "needle")

    assert result.total_conversations == 1
    assert result.orphan_matches == []
    assert result.conversations[0].message_id == "84012345"


def test_search_admin_entries_continuations(tmp_path):
    log_path = tmp_path / "admin.log"
    log_path.write_text(
        "00:00:01.100 [1.2.3.4] Login failed\n"
        "\tneedle detail line\n"
        "00:00:02.200 [5.6.7.8] Login ok\n"
    )

    result = search.search_admin_entries(log_path, "needle")

    assert result.total_conversations == 1
    assert result.orphan_matches == []
    assert result.conversations[0].lines[1].startswith("\tneedle")


def test_search_admin_entries_groups_same_timestamp(tmp_path):
    log_path = tmp_path / "admin.log"
    log_path.write_text(
        "10:13:13.367 [23.127.140.125] IMAP Attempting login\n"
        "10:13:13.367 [23.127.140.125] IMAP Login successful\n"
        "10:13:15.337 [23.127.140.125] IMAP Logout\n"
    )

    result = search.search_admin_entries(log_path, "IMAP")

    assert result.total_conversations == 2
    assert result.conversations[0].lines == [
        "10:13:13.367 [23.127.140.125] IMAP Attempting login",
        "10:13:13.367 [23.127.140.125] IMAP Login successful",
    ]


def test_search_admin_entries_supports_trailing_timestamp_format(tmp_path):
    log_path = tmp_path / "admin.log"
    log_path.write_text(
        "00:00:01.100 [1.2.3.4] SMTP Login failed\n"
        "[9.8.7.6] IMAP Login successful 00:00:03.300\n"
    )

    result = search.search_admin_entries(log_path, "IMAP")

    assert result.total_conversations == 1
    assert result.orphan_matches == []
    assert result.conversations[0].message_id == "9.8.7.6 00:00:03.300"


def test_search_imap_retrieval_entries_groups_by_id(tmp_path):
    log_path = tmp_path / "imapRetrieval.log"
    log_path.write_text(
        "00:00:01.100 [72] [user; host:other] Connection refused\n"
        "   at System.Net.Sockets.Socket.Connect(EndPoint remoteEP)\n"
        "00:00:02.200 [99] [user; host:other] Connection refused\n"
    )

    result = search.search_imap_retrieval_entries(log_path, "Socket.Connect")

    assert result.total_conversations == 1
    assert result.conversations[0].message_id == "72"
    assert result.orphan_matches == []


def test_search_ungrouped_entries_groups_continuations(tmp_path):
    log_path = tmp_path / "generalErrors.log"
    log_path.write_text(
        "00:00:01.100 Something failed\n"
        "   at Example.Stacktrace()\n"
        "00:00:02.200 Another failure\n"
    )

    result = search.search_ungrouped_entries(log_path, "Stacktrace")

    assert result.total_conversations == 1
    assert result.conversations[0].lines[1].lstrip().startswith("at")


def test_search_ungrouped_entries_supports_wildcard_mode(tmp_path):
    log_path = tmp_path / "generalErrors.log"
    log_path.write_text(
        "00:00:01.100 Login failed: User [sales] not found\n"
        "00:00:02.200 Login failed: User [billing] not found\n"
        "00:00:03.300 Login successful: User [sales]\n"
    )

    result = search.search_ungrouped_entries(
        log_path,
        "Login failed: User [*] not found",
        mode="wildcard",
    )

    assert result.total_conversations == 2

    single_char = search.search_ungrouped_entries(
        log_path,
        "Login failed: User [sale?] not found",
        mode="wildcard",
    )
    assert single_char.total_conversations == 1


def test_search_ungrouped_entries_supports_regex_mode(tmp_path):
    log_path = tmp_path / "generalErrors.log"
    log_path.write_text(
        "00:00:01.100 Login failed: User [sales] not found\n"
        "00:00:02.200 Login failed: User [billing] not found\n"
        "00:00:03.300 Login successful: User [sales]\n"
    )

    result = search.search_ungrouped_entries(
        log_path,
        r"Login failed: User \[(sales|billing)\] not found",
        mode="regex",
    )

    assert result.total_conversations == 2


def test_search_ungrouped_entries_supports_fuzzy_mode(tmp_path):
    log_path = tmp_path / "generalErrors.log"
    log_path.write_text(
        "00:00:01.100 Authentication failed for user [sales]\n"
        "00:00:02.200 Login successful for user [sales]\n"
    )

    result = search.search_ungrouped_entries(
        log_path,
        "Authentcation faild for user [sales]",
        mode="fuzzy",
        fuzzy_threshold=0.72,
    )

    assert result.total_conversations == 1


def test_fuzzy_matcher_uses_accelerator_when_available(monkeypatch):
    class StubFuzz:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, float]] = []

        def partial_ratio(
            self,
            term: str,
            line: str,
            *,
            score_cutoff: float,
        ) -> float:
            self.calls.append((term, line, score_cutoff))
            return 80.0

    stub = StubFuzz()
    monkeypatch.setattr(search, "_rapidfuzz_fuzz", stub)
    matcher = search._compile_line_matcher(
        "authentication failed",
        "fuzzy",
        True,
        0.75,
    )

    assert matcher("authentcation faild for user")
    assert stub.calls
    called_term, called_line, called_cutoff = stub.calls[0]
    assert called_term == "authentication failed"
    assert called_line == "authentcation faild for user"
    assert called_cutoff == pytest.approx(75.0)


def test_search_fuzzy_threshold_changes_match_sensitivity(tmp_path):
    log_path = tmp_path / "generalErrors.log"
    log_path.write_text(
        "00:00:01.100 Authentication failed for user [sales]\n",
    )

    strict = search.search_ungrouped_entries(
        log_path,
        "Authentcation faild for user [sales]",
        mode="fuzzy",
        fuzzy_threshold=0.95,
    )
    relaxed = search.search_ungrouped_entries(
        log_path,
        "Authentcation faild for user [sales]",
        mode="fuzzy",
        fuzzy_threshold=0.70,
    )

    assert strict.total_conversations == 0
    assert relaxed.total_conversations == 1


def test_search_rejects_invalid_fuzzy_threshold(tmp_path):
    log_path = tmp_path / "smtp.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] Connection initiated\n",
    )

    with pytest.raises(ValueError, match="Invalid fuzzy threshold"):
        search.search_smtp_conversations(
            log_path,
            "Connection initiated",
            mode="fuzzy",
            fuzzy_threshold=1.5,
        )


def test_search_rejects_invalid_regex_mode_pattern(tmp_path):
    log_path = tmp_path / "smtp.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] Connection initiated\n",
    )

    with pytest.raises(ValueError, match="Invalid regex pattern"):
        search.search_smtp_conversations(log_path, "(", mode="regex")


def test_search_rejects_unknown_mode(tmp_path):
    log_path = tmp_path / "smtp.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][ABC123] Connection initiated\n",
    )

    with pytest.raises(ValueError):
        search.search_smtp_conversations(log_path, "Connection", mode="bad")
