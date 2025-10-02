"""Command-line entry point for sm-logtool.

Provides a TUI browser (`browse`) and a basic SMTP search workflow (`search`).
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
import sys
from typing import Callable

from .config import AppConfig, ConfigError, load_config
from .logfiles import (
    UnknownLogDate,
    find_log_by_date,
    newest_log,
    parse_stamp,
    summarize_logs,
)
from .search import search_smtp_conversations
from .staging import DEFAULT_STAGING_ROOT, stage_log


DEFAULT_LOGS_DIR = Path(__file__).resolve().parent.parent / "sample_logs"
CONFIG_ATTR = "_config"


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""

    parser = argparse.ArgumentParser(
        prog="sm-logtool",
        description=textwrap.dedent(
            """
            Explore SmarterMail logs from your terminal. The `browse` subcommand
            launches the Textual UI while `search` performs a console-based SMTP
            conversation search.
            """
        ).strip(),
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to a YAML configuration file. Defaults to $SM_LOGTOOL_CONFIG or "
            "~/.config/sm-logtool/config.yaml."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    browse_parser = subparsers.add_parser("browse", help="Launch the Textual UI")
    browse_parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="Path containing SmarterMail log files (overrides config).",
    )
    browse_parser.set_defaults(handler=_run_browse)

    search_parser = subparsers.add_parser("search", help="Search SMTP logs for a term")
    search_parser.add_argument(
        "term",
        nargs="?",
        default=None,
        help="Substring to search for (case-insensitive by default)",
    )
    search_parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="Directory containing the original logs (overrides config).",
    )
    search_parser.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        help=(
            "Directory where logs are copied before analysis. Overrides config; "
            f"defaults to {DEFAULT_STAGING_ROOT}"
        ),
    )
    search_parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Specific log file to search (relative to --logs-dir unless absolute).",
    )
    search_parser.add_argument(
        "--kind",
        default=None,
        help="Log kind to search (overrides config default).",
    )
    search_parser.add_argument(
        "--date",
        default=None,
        help="Date (YYYY.MM.DD) of the log file to search.",
    )
    search_parser.add_argument(
        "--list",
        action="store_true",
        help="List available logs for the selected kind and exit.",
    )
    search_parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Treat the search term as case-sensitive.",
    )
    search_parser.set_defaults(handler=_run_search)

    parser.set_defaults(command="browse", handler=_run_browse)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point used by console scripts and ``python -m sm_logtool.cli``."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        parser.error(str(exc))

    setattr(args, CONFIG_ATTR, config)

    handler: Callable[[argparse.Namespace], int] = getattr(args, "handler", _run_browse)

    return handler(args)


def _run_browse(args: argparse.Namespace) -> int:
    config: AppConfig = getattr(args, CONFIG_ATTR)
    logs_dir = _resolve_logs_dir(args, config)

    # Lazy import so tests can import this module without having textual installed.
    try:
        from .ui.app import run as run_tui  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise SystemExit(
            "The Textual UI could not be loaded. Ensure the 'textual' package is installed.\n"
            f"Details: {exc}"
        ) from exc

    staging_dir = _resolve_staging_dir(args, config)
    return run_tui(logs_dir, staging_dir=staging_dir, default_kind=config.default_kind)


def _run_search(args: argparse.Namespace) -> int:
    config: AppConfig = getattr(args, CONFIG_ATTR)
    logs_dir = _resolve_logs_dir(args, config)
    staging_dir = _resolve_staging_dir(args, config)
    log_kind: str = args.kind or config.default_kind

    if args.list:
        return _list_logs(logs_dir, log_kind)

    if args.term is None:
        print("Search term is required unless --list is supplied.", file=sys.stderr)
        return 2

    if args.log_file is not None:
        log_path = args.log_file if args.log_file.is_absolute() else logs_dir / args.log_file
        info_source = log_path
        if not log_path.exists():
            print(f"Log file not found: {log_path}", file=sys.stderr)
            return 2
    else:
        if args.date is not None:
            try:
                target_date = parse_stamp(args.date)
            except UnknownLogDate as exc:
                print(str(exc), file=sys.stderr)
                return 2
            info = find_log_by_date(logs_dir, log_kind, target_date)
            if info is None:
                print(
                    f"No {log_kind} log found for {target_date:%Y.%m.%d} in {logs_dir}",
                    file=sys.stderr,
                )
                return 2
        else:
            info = newest_log(logs_dir, log_kind)
            if info is None:
                print(f"No {log_kind} logs found in {logs_dir}", file=sys.stderr)
                return 2
        log_path = info.path
        info_source = info.path

    try:
        staged = stage_log(
            log_path,
            staging_dir=staging_dir,
        )
    except Exception as exc:  # pragma: no cover - staging failure is surfaced to user
        print(f"Failed to stage log {log_path}: {exc}", file=sys.stderr)
        return 1

    result = search_smtp_conversations(
        staged.staged_path,
        args.term,
        ignore_case=not args.case_sensitive,
    )

    _print_search_summary(result, info_source)
    return 0


def _print_search_summary(result, source_path: Path) -> None:
    print(
        f"Search term '{result.term}' -> {result.total_conversations} conversation(s) in "
        f"{source_path.name}"
    )
    for conversation in result.conversations:
        print()
        print(f"[{conversation.message_id}] first seen on line {conversation.first_line_number}")
        for line in conversation.lines:
            print(line)

    if result.orphan_matches:
        print()
        print("Lines without message identifiers that matched:")
        for line_number, line in result.orphan_matches:
            print(f"{line_number}: {line}")


def _list_logs(logs_dir: Path, kind: str) -> int:
    logs = summarize_logs(logs_dir, kind)
    if not logs:
        print(f"No {kind} logs found in {logs_dir}", file=sys.stderr)
        return 2

    print(f"Available {kind} logs in {logs_dir}:")
    for info in logs:
        stamp = info.stamp.strftime('%Y.%m.%d') if info.stamp else 'unknown'
        suffix = ' (zip)' if info.is_zipped else ''
        print(f"  {stamp} -> {info.path.name}{suffix}")
    return 0


def _resolve_logs_dir(args: argparse.Namespace, config: AppConfig) -> Path:
    candidate = args.logs_dir or config.logs_dir or DEFAULT_LOGS_DIR
    return candidate


def _resolve_staging_dir(args: argparse.Namespace, config: AppConfig) -> Path | None:
    return getattr(args, 'staging_dir', None) or config.staging_dir


def scan_logs(logs_dir: Path) -> list[Path]:
    """Return log files underneath ``logs_dir`` sorted by name."""

    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")

    if not logs_dir.is_dir():
        raise NotADirectoryError(f"Logs path is not a directory: {logs_dir}")

    return sorted(
        path
        for path in logs_dir.iterdir()
        if path.is_file() and not path.name.startswith('.')
    )


if __name__ == "__main__":
    raise SystemExit(main())

