from sm_logtool.log_parsers import parse_delivery_entries, parse_smtp_line


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
