from sm_logtool.ui.app import _osc52_sequence
from sm_logtool.ui.app import LogBrowser


def test_osc52_sequence_uses_standard_st_terminator():
    sequence = _osc52_sequence("YWJj", env={})
    assert sequence.startswith("\x1b]52;c;YWJj")
    assert sequence.endswith("\x1b\\")


def test_osc52_sequence_wraps_for_tmux():
    sequence = _osc52_sequence("YWJj", env={"TMUX": "/tmp/tmux-1000/default"})
    assert sequence.startswith("\x1bPtmux;\x1b\x1b]52;c;YWJj")
    assert sequence.endswith("\x1b\\\x1b\\")


def test_osc52_sequence_wraps_for_screen():
    sequence = _osc52_sequence("YWJj", env={"TERM": "screen-256color"})
    assert sequence.startswith("\x1bP\x1b]52;c;YWJj")
    assert sequence.endswith("\x1b\\\x1b\\")


def test_copy_status_message_for_too_large_payload(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    app = LogBrowser(logs_dir=logs_dir)
    message = app._copy_status_message(selection_only=True, mode="too-large")
    assert "too large" in message
