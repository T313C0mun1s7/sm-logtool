from sm_logtool.syntax import (
    STYLE_EMAIL,
    STYLE_IP,
    STYLE_LINE_NUMBER,
    STYLE_TIMESTAMP,
    highlight_result_line,
)


def _has_style(text, style, start, end):
    for span in text.spans:
        if str(span.style) != style:
            continue
        if span.start <= start and span.end >= end:
            return True
    return False


def test_highlight_smtp_line_styles_timestamp_and_ip():
    line = (
        "23:59:56.065 [111.70.33.193][39603817] cmd: "
        "EHLO example.com"
    )
    text = highlight_result_line("smtpLog", line)
    assert text.plain == line
    assert _has_style(text, STYLE_TIMESTAMP, 0, len("23:59:56.065"))
    ip_start = line.index("111.70.33.193")
    ip_end = ip_start + len("111.70.33.193")
    assert _has_style(text, STYLE_IP, ip_start, ip_end)


def test_highlight_delivery_line_styles_email():
    line = (
        "23:59:59.117 [72495970] Starting local delivery to "
        "andy@shasta.com"
    )
    text = highlight_result_line("delivery", line)
    assert text.plain == line
    email_start = line.index("andy@shasta.com")
    email_end = email_start + len("andy@shasta.com")
    assert _has_style(text, STYLE_EMAIL, email_start, email_end)


def test_highlight_orphan_prefix_dim():
    line = (
        "123: 00:00:01 [1.1.1.1][ABC] Connection initiated"
    )
    text = highlight_result_line("smtpLog", line)
    assert text.plain == line
    prefix_end = len("123: ")
    assert _has_style(text, STYLE_LINE_NUMBER, 0, prefix_end)
