"""Basic tests for the sm_logtool CLI skeleton."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest
from rich.console import Console

from sm_logtool import cli
from sm_logtool.config import AppConfig


def create_smtp_zip(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w') as archive:
        archive.writestr(path.name.replace('.zip', ''), content)


def test_build_parser_supports_themes_subcommand():
    parser = cli.build_parser()
    args = parser.parse_args(["themes"])

    assert args.command == "themes"
    assert args.profile == "balanced"
    assert args.no_ansi256 is False


def test_should_persist_theme_changes_default(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["browse"])
    monkeypatch.delenv("SM_LOGTOOL_CONFIG", raising=False)

    assert cli._should_persist_theme_changes(args) is True


def test_should_persist_theme_changes_disabled_for_custom_config(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["--config", "config.yaml", "browse"])
    monkeypatch.delenv("SM_LOGTOOL_CONFIG", raising=False)

    assert cli._should_persist_theme_changes(args) is False


def test_should_persist_theme_changes_disabled_for_env(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["browse"])
    monkeypatch.setenv("SM_LOGTOOL_CONFIG", "/tmp/custom.yaml")

    assert cli._should_persist_theme_changes(args) is False


def test_scan_logs_handles_missing_directory(tmp_path):
    missing_dir = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        cli.scan_logs(missing_dir)


def test_scan_logs_lists_files(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "2024-05-01.log").write_text("line1\n", encoding="utf-8")
    (logs_dir / "2024-05-02.log").write_text("line2\n", encoding="utf-8")

    files = cli.scan_logs(logs_dir)

    assert [file.name for file in files] == [
        "2024-05-01.log",
        "2024-05-02.log",
    ]


def test_run_search_supports_date_selection(tmp_path, capsys):
    logs_dir = tmp_path / 'logs'
    staging_dir = tmp_path / 'staging'
    zip_path = logs_dir / '2024.01.01-smtpLog.log.zip'
    create_smtp_zip(
        zip_path,
        (
            "00:00:00 [1.1.1.1][MSG1] initial\n"
            "00:00:01 [1.1.1.1][MSG1] HELLO there\n"
        ),
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date='2024.01.01',
        list=False,
        case_sensitive=False,
        term='hello',
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "=== 2024.01.01-smtpLog.log.zip ===" in captured.out
    assert 'MSG1' in captured.out
    assert 'Search term' in captured.out


def test_run_search_supports_wildcard_mode(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-administrative.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        (
            "00:00:01.100 [1.2.3.4] Login failed: User [sales] not found\n"
            "00:00:02.200 [1.2.3.5] Login failed: User [billing] not found\n"
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        mode="wildcard",
        term="Login failed: User [*] not found",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="administrative",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "-> 2 entry(s)" in captured.out


def test_run_search_supports_regex_mode(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-administrative.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        (
            "00:00:01.100 [1.2.3.4] Login failed: User [sales] not found\n"
            "00:00:02.200 [1.2.3.5] Login failed: User [billing] not found\n"
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        mode="regex",
        term=r"Login failed: User \[(sales|billing)\] not found",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="administrative",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "-> 2 entry(s)" in captured.out


def test_run_search_supports_fuzzy_mode(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-administrative.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "00:00:01.100 [1.2.3.4] Authentication failed for user [sales]\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        mode="fuzzy",
        fuzzy_threshold=0.72,
        term="Authentcation faild for user [sales]",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="administrative",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "-> 1 entry(s)" in captured.out


def test_run_search_rejects_invalid_regex(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-smtpLog.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "00:00:00 [1.1.1.1][MSG1] hello\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        mode="regex",
        term="(",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 2

    captured = capsys.readouterr()
    assert "Invalid regex pattern" in captured.err


def test_run_search_rejects_invalid_fuzzy_threshold(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-smtpLog.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "00:00:00 [1.1.1.1][MSG1] hello\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        mode="fuzzy",
        fuzzy_threshold=1.5,
        term="hello",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 2

    captured = capsys.readouterr()
    assert "Invalid fuzzy threshold" in captured.err


def test_run_search_rejects_unknown_mode(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-smtpLog.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "00:00:00 [1.1.1.1][MSG1] hello\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        mode="bogus",
        term="hello",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 2

    captured = capsys.readouterr()
    assert "Unsupported search mode" in captured.err


def test_run_search_supports_imap_retrieval_kind(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-imapRetrieval.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        (
            "00:00:01.100 [72] [user; host:other] Connection refused\n"
            "   at System.Net.Sockets.Socket.Connect(EndPoint remoteEP)\n"
        ),
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        term="Socket.Connect",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="imapretrieval",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "=== 2024.01.01-imapRetrieval.log ===" in captured.out
    assert "Search term" in captured.out
    assert "[72]" in captured.out


def test_run_search_displays_no_matches_message(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    log_path = logs_dir / "2024.01.01-smtpLog.log"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "00:00:00 [1.1.1.1][MSG1] no target here\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        term="missing-term",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "No matches found." in captured.out


def test_run_search_supports_multiple_dates(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    logs_dir.mkdir(parents=True, exist_ok=True)
    first = logs_dir / "2024.01.01-smtpLog.log"
    second = logs_dir / "2024.01.02-smtpLog.log"
    first.write_text(
        "00:00:00 [1.1.1.1][MSG1] hello\n",
        encoding="utf-8",
    )
    second.write_text(
        "00:00:00 [2.2.2.2][MSG2] hello\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date=["2024.01.01", "2024.01.02"],
        list=False,
        case_sensitive=False,
        term="hello",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "=== 2024.01.01-smtpLog.log ===" in captured.out
    assert "=== 2024.01.02-smtpLog.log ===" in captured.out


def test_run_search_supports_multiple_log_files(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    logs_dir.mkdir(parents=True, exist_ok=True)
    first = logs_dir / "2024.01.01-smtpLog.log"
    second = logs_dir / "2024.01.02-smtpLog.log"
    first.write_text(
        "00:00:00 [1.1.1.1][MSG1] hello\n",
        encoding="utf-8",
    )
    second.write_text(
        "00:00:00 [2.2.2.2][MSG2] hello\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=[Path(first.name), Path(second.name)],
        date=None,
        list=False,
        case_sensitive=False,
        term="hello",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "=== 2024.01.01-smtpLog.log ===" in captured.out
    assert "=== 2024.01.02-smtpLog.log ===" in captured.out


def test_run_search_rejects_mismatched_log_file_kind(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "2024.01.01-imapLog.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][MSG1] hello\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=[Path(log_path.name)],
        date=None,
        list=False,
        case_sensitive=False,
        term="hello",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "does not match kind smtp" in captured.err


def test_run_search_rejects_mixed_date_and_log_file(tmp_path, capsys):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "2024.01.01-smtpLog.log"
    log_path.write_text(
        "00:00:00 [1.1.1.1][MSG1] hello\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=[Path(log_path.name)],
        date=["2024.01.01"],
        list=False,
        case_sensitive=False,
        term="hello",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "--log-file and --date cannot be used together." in captured.err


def test_run_search_uses_syntax_highlighting_in_cli_output(
    tmp_path,
    capsys,
    monkeypatch,
):
    logs_dir = tmp_path / "logs"
    staging_dir = tmp_path / "staging"
    zip_path = logs_dir / "2024.01.01-smtpLog.log.zip"
    create_smtp_zip(
        zip_path,
        (
            "00:00:00 [1.1.1.1][MSG1] cmd: EHLO example.com\n"
            "00:00:01 [1.1.1.1][MSG1] rsp: 250 Success\n"
        ),
    )

    def build_console() -> Console:
        return Console(
            file=sys.stdout,
            force_terminal=True,
            color_system="truecolor",
            highlight=False,
            soft_wrap=True,
        )

    monkeypatch.setattr(cli, "_build_stdout_console", build_console)

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date="2024.01.01",
        list=False,
        case_sensitive=False,
        term="EHLO",
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=staging_dir,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "\x1b[" in captured.out
    assert "EHLO" in captured.out


def test_run_search_requires_logs_dir_from_config_or_flag(capsys):
    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date=None,
        list=True,
        case_sensitive=False,
        term=None,
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=None,
        staging_dir=None,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Log directory is not configured." in captured.err


def test_run_search_requires_staging_dir_from_config_or_flag(
    tmp_path,
    capsys,
):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date=None,
        list=True,
        case_sensitive=False,
        term=None,
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=logs_dir,
        staging_dir=None,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Staging directory is not configured." in captured.err


def test_search_help_mentions_latest_and_supported_kinds(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["search", "--help"])
    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "newest available log for --kind is searched." in captured.out
    assert "Search modes:" in captured.out
    assert "wildcard" in captured.out
    assert "regex" in captured.out
    assert "fuzzy" in captured.out
    assert "--fuzzy-threshold" in captured.out
    assert "--mode" in captured.out
    assert "Available kinds:" in captured.out
    assert "logs_dir is set in" in captured.out
    assert "staging_dir is set in" in captured.out
    assert "default_kind is set" in captured.out
    assert "config.yaml." in captured.out
    assert "smtp" in captured.out


def test_run_search_list_kinds_does_not_require_dirs(capsys):
    args = argparse.Namespace(
        logs_dir=None,
        staging_dir=None,
        kind=None,
        log_file=None,
        date=None,
        list=False,
        list_kinds=True,
        case_sensitive=False,
        term=None,
    )
    args._config = AppConfig(
        path=Path("config.yaml"),
        logs_dir=None,
        staging_dir=None,
        default_kind="smtp",
    )

    exit_code = cli._run_search(args)

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Supported log kinds:" in captured.out
    assert "smtp" in captured.out


def test_main_version_flag_prints_version_and_exits_zero(
    capsys,
    monkeypatch,
):
    monkeypatch.setattr(cli, "_package_version", lambda: "9.9.9")

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "sm-logtool 9.9.9"
