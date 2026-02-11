"""Command-line entry point for sm-logtool.

Provides a TUI browser (`browse`) and a search workflow (`search`).
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
import sys
from typing import Callable

from rich.console import Console

from .config import AppConfig, ConfigError, load_config
from .highlighting import highlight_line
from .logfiles import (
    UnknownLogDate,
    find_log_by_date,
    newest_log,
    parse_stamp,
    summarize_logs,
)
from .result_formatting import collect_widths, format_conversation_lines
from .search import get_search_function
from .staging import stage_log


CONFIG_ATTR = "_config"


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""

    parser = argparse.ArgumentParser(
        prog="sm-logtool",
        description=textwrap.dedent(
            """
            Explore SmarterMail logs from your terminal.
            The `browse` subcommand launches the Textual UI.
            The `search` subcommand performs a console-based search across
            supported SmarterMail log kinds.
            """
        ).strip(),
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to a YAML config file. Defaults to $SM_LOGTOOL_CONFIG or "
            "~/.config/sm-logtool/config.yaml."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    browse_parser = subparsers.add_parser(
        "browse",
        help="Launch the Textual UI",
    )
    browse_parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="Path containing SmarterMail log files (overrides config).",
    )
    browse_parser.set_defaults(handler=_run_browse)

    search_parser = subparsers.add_parser(
        "search",
        help="Search SmarterMail logs for a term",
    )
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
        help="Directory where logs are copied before analysis.",
    )
    search_parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=(
            "Specific log file to search. Relative paths resolve under "
            "--logs-dir."
        ),
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

    handler: Callable[[argparse.Namespace], int]
    handler = getattr(args, "handler", _run_browse)

    return handler(args)


def _run_browse(args: argparse.Namespace) -> int:
    config: AppConfig = getattr(args, CONFIG_ATTR)
    try:
        logs_dir = _resolve_logs_dir(args, config)
        staging_dir = _resolve_staging_dir(args, config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # Lazy import so tests can import this module without textual installed.
    try:
        from .ui.app import run as run_tui  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise SystemExit(
            "The Textual UI could not be loaded. Ensure the 'textual' package "
            "is installed.\n"
            f"Details: {exc}"
        ) from exc

    return run_tui(
        logs_dir,
        staging_dir=staging_dir,
        default_kind=config.default_kind,
    )


def _run_search(args: argparse.Namespace) -> int:
    config: AppConfig = getattr(args, CONFIG_ATTR)
    try:
        logs_dir = _resolve_logs_dir(args, config)
        staging_dir = _resolve_staging_dir(args, config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    log_kind = args.kind or config.default_kind
    if log_kind is None:
        print("Log kind is required.", file=sys.stderr)
        return 2

    if args.list:
        return _list_logs(logs_dir, log_kind)

    if args.term is None:
        print(
            "Search term is required unless --list is supplied.",
            file=sys.stderr,
        )
        return 2

    if args.log_file is not None:
        log_path = (
            args.log_file
            if args.log_file.is_absolute()
            else logs_dir / args.log_file
        )
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
                message = (
                    f"No {log_kind} log found for {target_date:%Y.%m.%d} in "
                    f"{logs_dir}"
                )
                print(message, file=sys.stderr)
                return 2
        else:
            info = newest_log(logs_dir, log_kind)
            if info is None:
                print(
                    f"No {log_kind} logs found in {logs_dir}",
                    file=sys.stderr,
                )
                return 2
        log_path = info.path
        info_source = info.path

    try:
        staged = stage_log(
            log_path,
            staging_dir=staging_dir,
        )
    except Exception as exc:  # pragma: no cover - surface staging failure
        print(f"Failed to stage log {log_path}: {exc}", file=sys.stderr)
        return 1

    search_fn = get_search_function(log_kind)
    if search_fn is None:
        print(f"Unsupported log kind: {log_kind}", file=sys.stderr)
        return 2

    result = search_fn(
        staged.staged_path,
        args.term,
        ignore_case=not args.case_sensitive,
    )

    _print_search_summary(result, info_source, log_kind)
    return 0


def _print_search_summary(
    result,
    source_path: Path,
    log_kind: str,
) -> None:
    console = _build_stdout_console()
    kind_key = log_kind.lower()
    ungrouped_kinds = {
        "administrative",
        "activation",
        "autocleanfolders",
        "calendars",
        "contentfilter",
        "event",
        "generalerrors",
        "indexing",
        "ldaplog",
        "maintenance",
        "profiler",
        "spamchecks",
        "webdav",
    }
    is_ungrouped = kind_key in ungrouped_kinds
    label = "entry" if is_ungrouped else "conversation"
    _write_highlighted(
        console,
        log_kind,
        f"Search term '{result.term}' -> "
        f"{result.total_conversations} {label}(s) in {source_path.name}",
    )
    widths = collect_widths(log_kind, result.conversations)
    for conversation in result.conversations:
        if not is_ungrouped:
            console.print()
            _write_highlighted(
                console,
                log_kind,
                f"[{conversation.message_id}] first seen on line "
                f"{conversation.first_line_number}",
            )
        formatted = format_conversation_lines(
            log_kind,
            conversation.lines,
            widths,
        )
        for line in formatted:
            _write_highlighted(console, log_kind, line)

    if result.orphan_matches:
        if not is_ungrouped:
            console.print()
            _write_highlighted(
                console,
                log_kind,
                "Lines without message identifiers that matched:",
            )
        for line_number, line in result.orphan_matches:
            if is_ungrouped:
                _write_highlighted(console, log_kind, line)
            else:
                _write_highlighted(
                    console,
                    log_kind,
                    f"{line_number}: {line}",
                )


def _build_stdout_console() -> Console:
    return Console(highlight=False, soft_wrap=True)


def _write_highlighted(
    console: Console,
    log_kind: str,
    line: str,
) -> None:
    if not line:
        console.print()
        return
    console.print(highlight_line(log_kind, line))


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
    candidate = getattr(args, "logs_dir", None) or config.logs_dir
    if candidate is None:
        raise ValueError(
            "Log directory is not configured. Set 'logs_dir' in config.yaml "
            "or pass --logs-dir."
        )
    return candidate


def _resolve_staging_dir(
    args: argparse.Namespace,
    config: AppConfig,
) -> Path:
    candidate = getattr(args, "staging_dir", None) or config.staging_dir
    if candidate is None:
        raise ValueError(
            "Staging directory is not configured. Set 'staging_dir' in "
            "config.yaml or pass --staging-dir."
        )
    return candidate


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
