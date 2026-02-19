from pathlib import Path

from sm_logtool.result_modes import RESULT_MODE_MATCHING_ROWS
from sm_logtool.result_modes import RESULT_MODE_RELATED_TRAFFIC
from sm_logtool.result_rendering import render_search_results
from sm_logtool.search import Conversation
from sm_logtool.search import SmtpSearchResult


def test_render_related_mode_keeps_grouped_conversation_output():
    result = SmtpSearchResult(
        term="blocked",
        log_path=Path("smtp.log"),
        conversations=[
            Conversation(
                message_id="MSG1",
                lines=[
                    "00:00:00 [1.1.1.1][MSG1] Connection initiated",
                    "00:00:01 [1.1.1.1][MSG1] User blocked@example.com",
                ],
                first_line_number=1,
            )
        ],
        total_lines=2,
        orphan_matches=[],
        matching_rows=[
            (2, "00:00:01 [1.1.1.1][MSG1] User blocked@example.com")
        ],
    )

    lines = render_search_results(
        [result],
        [Path("smtp.log")],
        "smtp",
        result_mode=RESULT_MODE_RELATED_TRAFFIC,
    )

    assert any("[MSG1] first seen on line 1" in line for line in lines)
    assert any("Connection initiated" in line for line in lines)
    assert any("blocked@example.com" in line for line in lines)


def test_render_matching_only_mode_for_smtp():
    result = SmtpSearchResult(
        term="blocked",
        log_path=Path("smtp.log"),
        conversations=[
            Conversation(
                message_id="MSG1",
                lines=[
                    "00:00:00 [1.1.1.1][MSG1] Connection initiated",
                    "00:00:01 [1.1.1.1][MSG1] User blocked@example.com",
                ],
                first_line_number=1,
            )
        ],
        total_lines=2,
        orphan_matches=[],
        matching_rows=[
            (2, "00:00:01 [1.1.1.1][MSG1] User blocked@example.com")
        ],
    )

    lines = render_search_results(
        [result],
        [Path("smtp.log")],
        "smtp",
        result_mode=RESULT_MODE_MATCHING_ROWS,
    )

    assert any("matching row(s)" in line for line in lines)
    assert any("blocked@example.com" in line for line in lines)
    assert not any("Connection initiated" in line for line in lines)
    assert not any("first seen on line" in line for line in lines)


def test_render_matching_only_mode_for_delivery():
    result = SmtpSearchResult(
        term="blocked",
        log_path=Path("delivery.log"),
        conversations=[
            Conversation(
                message_id="84012345",
                lines=[
                    "00:00:00.100 [84012345] Queued for domain example.net",
                    "00:00:00.200 [84012345] Delivery blocked by policy",
                ],
                first_line_number=1,
            )
        ],
        total_lines=2,
        orphan_matches=[],
        matching_rows=[
            (2, "00:00:00.200 [84012345] Delivery blocked by policy")
        ],
    )

    lines = render_search_results(
        [result],
        [Path("delivery.log")],
        "delivery",
        result_mode=RESULT_MODE_MATCHING_ROWS,
    )

    assert any("matching row(s)" in line for line in lines)
    assert any("Delivery blocked by policy" in line for line in lines)
    assert not any("Queued for domain example.net" in line for line in lines)
