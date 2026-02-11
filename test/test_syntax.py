from sm_logtool.syntax import (
    TOKEN_EMAIL,
    TOKEN_IP,
    TOKEN_LINE_NUMBER,
    TOKEN_PROTO_IMAP,
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
