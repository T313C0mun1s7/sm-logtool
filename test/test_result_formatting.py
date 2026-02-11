from sm_logtool.result_formatting import (
    collect_widths,
    format_conversation_lines,
)
from sm_logtool.search import Conversation


def test_format_smtp_aligns_columns_and_continuations():
    conversations = [
        Conversation(
            message_id="A",
            first_line_number=1,
            lines=[
                "00:00:01.100 [1.2.3.4][ABC] Start",
                "\tcontinuation",
            ],
        ),
        Conversation(
            message_id="B",
            first_line_number=3,
            lines=[
                "00:00:02.200 [11.22.33.44][LONGERID] Next",
            ],
        ),
    ]

    widths = collect_widths("smtpLog", conversations)
    assert widths is not None
    formatted = format_conversation_lines(
        "smtpLog",
        conversations[0].lines,
        widths,
    )
    formatted += format_conversation_lines(
        "smtpLog",
        conversations[1].lines,
        widths,
    )

    msg_col = formatted[0].index("Start")
    assert formatted[1].index("continuation") == msg_col
    assert formatted[2].index("Next") == msg_col
    assert "[1.2.3.4]" in formatted[0]
    assert "[1.2.3.4 " not in formatted[0]


def test_format_admin_aligns_continuations():
    conversation = Conversation(
        message_id="admin",
        first_line_number=1,
        lines=[
            "10:13:13.367 [23.127.140.125] Login failed",
            "    details follow",
        ],
    )

    widths = collect_widths("administrative", [conversation])
    assert widths is not None
    formatted = format_conversation_lines(
        "administrative",
        conversation.lines,
        widths,
    )

    msg_col = formatted[0].index("Login")
    assert formatted[1].index("details") == msg_col


def test_format_admin_moves_trailing_timestamp():
    conversation = Conversation(
        message_id="admin",
        first_line_number=1,
        lines=[
            "[1.2.3.4] SMTP Login failed 00:01:02.003",
        ],
    )

    widths = collect_widths("administrative", [conversation])
    assert widths is not None
    formatted = format_conversation_lines(
        "administrative",
        conversation.lines,
        widths,
    )

    assert formatted[0].startswith("00:01:02.003 ")
    assert "[1.2.3.4]" in formatted[0]
    assert "SMTP Login failed" in formatted[0]


def test_format_imap_retrieval_aligns_context():
    conversation = Conversation(
        message_id="72",
        first_line_number=1,
        lines=[
            "00:00:01.100 [72] [user; host:other] Connection refused",
            "00:00:02.200 [5] [user; host:other] Connection refused",
        ],
    )

    widths = collect_widths("imapRetrieval", [conversation])
    assert widths is not None
    formatted = format_conversation_lines(
        "imapRetrieval",
        conversation.lines,
        widths,
    )

    msg_col = formatted[0].index("Connection")
    assert formatted[1].index("Connection") == msg_col
