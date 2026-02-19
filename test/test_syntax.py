from sm_logtool.syntax import (
    TOKEN_EMAIL,
    TOKEN_IP,
    TOKEN_LINE_NUMBER,
    TOKEN_PROTO_IMAP,
    TOKEN_RESPONSE,
    TOKEN_STATUS_BAD,
    TOKEN_TIMESTAMP,
    spans_for_line,
)


def _has_span(spans, token, start, end):
    for span in spans:
        if span.token != token:
            continue
        if span.start <= start and span.end >= end:
            return True
    return False


def test_highlight_smtp_line_styles_timestamp_and_ip():
    line = (
        "23:59:56.065 [111.70.33.193][39603817] cmd: "
        "EHLO example.com"
    )
    spans = spans_for_line("smtp", line)
    assert _has_span(spans, TOKEN_TIMESTAMP, 0, len("23:59:56.065"))
    ip_start = line.index("111.70.33.193")
    ip_end = ip_start + len("111.70.33.193")
    assert _has_span(spans, TOKEN_IP, ip_start, ip_end)


def test_highlight_delivery_line_styles_email():
    line = (
        "23:59:59.117 [72495970] Starting local delivery to "
        "andy@shasta.com"
    )
    spans = spans_for_line("delivery", line)
    email_start = line.index("andy@shasta.com")
    email_end = email_start + len("andy@shasta.com")
    assert _has_span(spans, TOKEN_EMAIL, email_start, email_end)


def test_highlight_orphan_prefix_dim():
    line = (
        "123: 00:00:01 [1.1.1.1][ABC] Connection initiated"
    )
    spans = spans_for_line("smtp", line)
    prefix_end = len("123: ")
    assert _has_span(spans, TOKEN_LINE_NUMBER, 0, prefix_end)


def test_highlight_admin_protocol_and_status():
    line = (
        "23:59:57.727 [178.216.28.19] IMAP Login failed: "
        "User [204be204] not found"
    )
    spans = spans_for_line("administrative", line)
    proto_start = line.index("IMAP")
    proto_end = proto_start + len("IMAP")
    assert _has_span(spans, TOKEN_PROTO_IMAP, proto_start, proto_end)
    status_start = line.index("failed")
    status_end = status_start + len("failed")
    assert _has_span(spans, TOKEN_STATUS_BAD, status_start, status_end)


def test_response_code_not_highlighted_in_timestamp_columns():
    line = (
        "[2026.02.18] 05:01:30.507 [198.51.100.23][30216663] "
        "rsp: 334 VXNlcm5hbWU6"
    )
    spans = spans_for_line("smtp", line)

    ts_code_start = line.index("507")
    ts_code_end = ts_code_start + len("507")
    assert not _has_span(spans, TOKEN_RESPONSE, ts_code_start, ts_code_end)

    rsp_code_start = line.index("334")
    rsp_code_end = rsp_code_start + len("334")
    assert _has_span(spans, TOKEN_RESPONSE, rsp_code_start, rsp_code_end)


def test_blocked_sender_checks_not_highlighted_as_bad_status():
    line = (
        "00:05:58.836 [84012980] Blocked Sender Checks started."
    )
    spans = spans_for_line("delivery", line)
    blocked_start = line.index("Blocked")
    blocked_end = blocked_start + len("Blocked")
    assert not _has_span(
        spans,
        TOKEN_STATUS_BAD,
        blocked_start,
        blocked_end,
    )


def test_failed_false_status_field_not_highlighted_as_bad_status():
    line = (
        "00:06:07.424 [84012980] Removing Spool message: "
        "Killed: False, Failed: False, Finished: True"
    )
    spans = spans_for_line("delivery", line)
    failed_start = line.index("Failed")
    failed_end = failed_start + len("Failed")
    assert not _has_span(
        spans,
        TOKEN_STATUS_BAD,
        failed_start,
        failed_end,
    )


def test_block_outcome_markers_are_highlighted_as_bad_status():
    action_line = (
        "00:06:03.076 [84012980] Blocking sender <sender@example.test> "
        "for <recipient@example.test>. Action: MoveToJunk"
    )
    action_spans = spans_for_line("delivery", action_line)
    action_start = action_line.index("Action: MoveToJunk")
    action_end = action_start + len("Action: MoveToJunk")
    assert _has_span(
        action_spans,
        TOKEN_STATUS_BAD,
        action_start,
        action_end,
    )

    reason_line = (
        "00:06:03.077 [84012980] REASON: User "
        "'<recipient@example.test>' has <sender@example.test> "
        "on their blocked list."
    )
    reason_spans = spans_for_line("delivery", reason_line)
    reason_start = reason_line.index("on their blocked list")
    reason_end = reason_start + len("on their blocked list")
    assert _has_span(
        reason_spans,
        TOKEN_STATUS_BAD,
        reason_start,
        reason_end,
    )
