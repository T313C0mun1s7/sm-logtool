from sm_logtool.log_parsers import (
    parse_bracket1_line,
    parse_bracket1_trailing_time_line,
    parse_imap_retrieval_line,
    parse_admin_entries,
    parse_delivery_entries,
    parse_smtp_line,
    parse_time_line,
    starts_with_timestamp,
)


def test_parse_smtp_line_extracts_fields():
    line = "12:34:56.789 [1.2.3.4][ABC123] cmd: EHLO example"
    entry = parse_smtp_line(line)
    assert entry is not None
    assert entry.timestamp == "12:34:56.789"
    assert entry.ip == "1.2.3.4"
    assert entry.log_id == "ABC123"
    assert entry.message == "cmd: EHLO example"


def test_parse_delivery_entries_handles_continuations():
    lines = [
        "00:00:01.100 [84012345] Starting local delivery to user@example.com",
        "   at MailService.RelayServer.MessageQueue.SomeMethod()",
        "   at System.Linq.Enumerable.Any[T](IEnumerable`1 source)",
        "00:00:02.200 [84012346] Delivery started for user@example.com",
    ]
    entries, orphans = parse_delivery_entries(lines)
    assert not orphans
    assert len(entries) == 2
    first = entries[0]
    assert first.delivery_id == "84012345"
    assert len(first.continuation_lines) == 2
    second = entries[1]
    assert second.delivery_id == "84012346"
    assert not second.continuation_lines


def test_parse_delivery_entries_orphan_lines():
    lines = [
        "   at MailService.RelayServer.MessageQueue.SomeMethod()",
        "00:00:03.300 [84012347] Delivery started for user@example.com",
    ]
    entries, orphans = parse_delivery_entries(lines)
    assert len(orphans) == 1
    assert len(entries) == 1
    assert entries[0].delivery_id == "84012347"


def test_parse_admin_entries_handles_continuations():
    lines = [
        "00:00:01.100 [1.2.3.4] SMTP Login failed: bad password",
        "\tBrute force attempts increased to 1 of 5 in 10 minutes.",
        "\tNext clean available at 2/10/2026 12:00:32 AM",
        "00:00:02.200 [5.6.7.8] Webmail Login successful: With user demo",
    ]
    entries, orphans = parse_admin_entries(lines)
    assert not orphans
    assert len(entries) == 2
    first = entries[0]
    assert first.ip == "1.2.3.4"
    assert len(first.continuation_lines) == 2
    second = entries[1]
    assert second.ip == "5.6.7.8"
    assert not second.continuation_lines


def test_parse_admin_entries_handles_trailing_timestamp_lines():
    lines = [
        "00:00:01.100 [1.2.3.4] SMTP Login failed: bad password",
        "[9.8.7.6] IMAP Login successful 00:00:03.300",
    ]
    entries, orphans = parse_admin_entries(lines)
    assert not orphans
    assert len(entries) == 2
    assert entries[1].ip == "9.8.7.6"
    assert entries[1].timestamp == "00:00:03.300"


def test_parse_bracket1_line_extracts_field():
    line = "12:00:00.000 [user@example.com] Example message"
    entry = parse_bracket1_line(line)
    assert entry is not None
    assert entry.timestamp == "12:00:00.000"
    assert entry.field1 == "user@example.com"
    assert entry.message == "Example message"


def test_parse_bracket1_trailing_time_line_extracts_field():
    line = "[1.2.3.4] SMTP Login failed 00:01:02.003"
    entry = parse_bracket1_trailing_time_line(line)
    assert entry is not None
    assert entry.timestamp == "00:01:02.003"
    assert entry.field1 == "1.2.3.4"
    assert entry.message == "SMTP Login failed"


def test_parse_imap_retrieval_line_extracts_fields():
    line = (
        "12:00:00.000 [72] "
        "[user@example.com; 127.0.0.1:other@example.com] "
        "Connection refused 127.0.0.1:143"
    )
    entry = parse_imap_retrieval_line(line)
    assert entry is not None
    assert entry.retrieval_id == "72"
    assert entry.context.startswith("user@example.com;")
    assert entry.message.startswith("Connection refused")


def test_parse_time_line_extracts_message():
    line = "01:02:03.004 Something happened"
    entry = parse_time_line(line)
    assert entry is not None
    assert entry.timestamp == "01:02:03.004"
    assert entry.message == "Something happened"


def test_starts_with_timestamp_accepts_seconds_prefix():
    assert starts_with_timestamp("01:02:03 message")
    assert starts_with_timestamp("01:02:03.456 message")
    assert starts_with_timestamp("01:02:03.")


def test_starts_with_timestamp_rejects_invalid_prefixes():
    assert not starts_with_timestamp("")
    assert not starts_with_timestamp("1:02:03 message")
    assert not starts_with_timestamp("01-02-03 message")
    assert not starts_with_timestamp("xx:yy:zz message")
