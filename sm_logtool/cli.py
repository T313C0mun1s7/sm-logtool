"""Command-line entry point for sm-logtool.

Provides a TUI browser (`browse`) and a search workflow (`search`).
"""

from __future__ import annotations

import argparse
from importlib import metadata
import os
import textwrap
from pathlib import Path
import sys
from typing import Callable

from rich.console import Console

from .config import AppConfig, ConfigError, load_config
from .highlighting import highlight_line
from .log_kinds import SUPPORTED_KINDS, normalize_kind
from .logfiles import (
    UnknownLogDate,
    find_log_by_date,
    newest_log,
    parse_log_filename,
    parse_stamp,
    summarize_logs,
)
from .result_rendering import render_search_results
from .search_modes import (
    DEFAULT_FUZZY_THRESHOLD,
    MODE_LITERAL,
    SEARCH_MODE_DESCRIPTIONS,
    SUPPORTED_SEARCH_MODES,
    normalize_fuzzy_threshold,
    normalize_search_mode,
)
from .search import get_search_function
from .staging import stage_log
from .ui.theme_importer import ensure_default_theme_dirs
from .ui.theme_importer import SUPPORTED_THEME_MAPPING_PROFILES


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
            The `themes` subcommand launches the visual theme converter.

            Config-aware defaults:
              - logs_dir and staging_dir come from config.yaml when present.
              - Command-line flags override config values.
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
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
        help=(
            "Path containing SmarterMail log files. Optional when logs_dir "
            "is set in config.yaml."
        ),
    )
    browse_parser.set_defaults(handler=_run_browse)

    themes_parser = subparsers.add_parser(
        "themes",
        help="Open visual theme conversion utility",
    )
    themes_parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=None,
        help=(
            "Theme source file/directory. Repeatable. Supports "
            ".itermcolors/.colors/.colortheme."
        ),
    )
    themes_parser.add_argument(
        "--store-dir",
        type=Path,
        default=None,
        help=(
            "Directory for converted sm-logtool themes. Defaults to "
            "~/.config/sm-logtool/themes."
        ),
    )
    themes_parser.add_argument(
        "--profile",
        choices=SUPPORTED_THEME_MAPPING_PROFILES,
        default="balanced",
        help="Default mapping profile for preview/save.",
    )
    themes_parser.add_argument(
        "--no-ansi256",
        action="store_true",
        help="Disable ANSI-256 quantization and keep truecolor output.",
    )
    themes_parser.set_defaults(handler=_run_themes)

    search_parser = subparsers.add_parser(
        "search",
        help="Search SmarterMail logs for a term",
        description=(
            "Search a SmarterMail log kind using the selected search mode."
        ),
        epilog=_search_help_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    search_parser.add_argument(
        "term",
        nargs="?",
        default=None,
        help=(
            "Search pattern (case-insensitive by default). Pattern syntax "
            "depends on --mode."
        ),
    )
    search_parser.add_argument(
        "--mode",
        choices=SUPPORTED_SEARCH_MODES,
        default=MODE_LITERAL,
        help=(
            "Search mode to use. "
            "literal=substring, wildcard supports '*' and '?', "
            "regex=Python re syntax (PCRE-like, not full PCRE), "
            "fuzzy=approximate similarity matching."
        ),
    )
    search_parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=DEFAULT_FUZZY_THRESHOLD,
        help=(
            "Similarity threshold for --mode fuzzy "
            f"({0.0:.2f} to {1.0:.2f}, default {DEFAULT_FUZZY_THRESHOLD:.2f})."
        ),
    )
    search_parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing source logs. Optional when logs_dir is "
            "set in config.yaml."
        ),
    )
    search_parser.add_argument(
        "--staging-dir",
        type=Path,
        default=None,
        help=(
            "Directory where logs are copied/extracted before analysis. "
            "Optional when staging_dir is set in config.yaml."
        ),
    )
    search_parser.add_argument(
        "--log-file",
        type=Path,
        action="append",
        default=None,
        help=(
            "Specific log file to search. Relative paths resolve under "
            "--logs-dir. Repeat to search multiple files."
        ),
    )
    search_parser.add_argument(
        "--kind",
        default=None,
        help=(
            "Log kind to search. Optional when default_kind is set in "
            "config.yaml. "
            "Use --list-kinds to show supported values."
        ),
    )
    search_parser.add_argument(
        "--date",
        action="append",
        default=None,
        help=(
            "Date (YYYY.MM.DD) of the log file to search. Repeat to search "
            "multiple dates."
        ),
    )
    search_parser.add_argument(
        "--list",
        action="store_true",
        help="List available logs for the selected kind and exit.",
    )
    search_parser.add_argument(
        "--list-kinds",
        action="store_true",
        help="List supported log kinds and exit.",
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


def _package_version() -> str:
    try:
        return metadata.version("sm-logtool")
    except metadata.PackageNotFoundError:
        return "unknown"


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
    theme_store_dir, _ = ensure_default_theme_dirs(config.path)

    return run_tui(
        logs_dir,
        staging_dir=staging_dir,
        default_kind=config.default_kind,
        config_path=config.path,
        theme=config.theme,
        theme_store_dir=theme_store_dir,
        theme_import_paths=config.theme_import_paths,
        theme_mapping_profile=config.theme_mapping_profile,
        theme_quantize_ansi256=config.theme_quantize_ansi256,
        theme_overrides=config.theme_overrides,
        persist_theme_changes=_should_persist_theme_changes(args),
    )


def _run_themes(args: argparse.Namespace) -> int:
    config: AppConfig = getattr(args, CONFIG_ATTR)
    default_store_dir, default_source_dir = ensure_default_theme_dirs(
        config.path
    )
    source_paths = tuple(
        args.source
        or (default_source_dir,)
    )
    store_dir = args.store_dir or default_store_dir

    try:
        from .ui.theme_studio import run as run_studio  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise SystemExit(
            "The theme studio UI could not be loaded. Ensure the 'textual' "
            "package is installed.\n"
            f"Details: {exc}"
        ) from exc

    return run_studio(
        source_paths=source_paths,
        store_dir=store_dir,
        profile=args.profile,
        quantize_ansi256=not args.no_ansi256,
    )


def _should_persist_theme_changes(args: argparse.Namespace) -> bool:
    if args.config is not None:
        return False
    if os.environ.get("SM_LOGTOOL_CONFIG"):
        return False
    return True


def _run_search(args: argparse.Namespace) -> int:
    config: AppConfig = getattr(args, CONFIG_ATTR)
    if getattr(args, "list_kinds", False):
        return _list_kinds()

    try:
        search_mode = normalize_search_mode(
            getattr(args, "mode", MODE_LITERAL),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        fuzzy_threshold = normalize_fuzzy_threshold(
            getattr(args, "fuzzy_threshold", DEFAULT_FUZZY_THRESHOLD),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        logs_dir = _resolve_logs_dir(args, config)
        staging_dir = _resolve_staging_dir(args, config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    log_kind_value = args.kind or config.default_kind
    if log_kind_value is None:
        print("Log kind is required.", file=sys.stderr)
        return 2
    log_kind = normalize_kind(log_kind_value)

    if args.list:
        return _list_logs(logs_dir, log_kind)

    if args.term is None:
        print(
            "Search term is required unless --list is supplied.",
            file=sys.stderr,
        )
        return 2

    search_fn = get_search_function(log_kind)
    if search_fn is None:
        print(f"Unsupported log kind: {log_kind}", file=sys.stderr)
        return 2

    try:
        targets = _resolve_search_targets(args, logs_dir, log_kind)
    except (UnknownLogDate, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not targets:
        print(
            f"No {log_kind} logs found in {logs_dir}",
            file=sys.stderr,
        )
        return 2

    results = []
    for source_path in targets:
        try:
            staged = stage_log(
                source_path,
                staging_dir=staging_dir,
            )
        except Exception as exc:  # pragma: no cover - surface staging failure
            print(f"Failed to stage log {source_path}: {exc}", file=sys.stderr)
            return 1
        try:
            result = search_fn(
                staged.staged_path,
                args.term,
                mode=search_mode,
                fuzzy_threshold=fuzzy_threshold,
                ignore_case=not args.case_sensitive,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        results.append(result)

    _print_search_summary(results, targets, log_kind)
    return 0


def _print_search_summary(
    results,
    source_paths: list[Path],
    log_kind: str,
) -> None:
    console = _build_stdout_console()
    lines = render_search_results(results, source_paths, log_kind)
    for line in lines:
        _write_highlighted(console, log_kind, line)


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
    resolved_kind = normalize_kind(kind)
    logs = summarize_logs(logs_dir, resolved_kind)
    if not logs:
        print(f"No {resolved_kind} logs found in {logs_dir}", file=sys.stderr)
        return 2

    print(f"Available {resolved_kind} logs in {logs_dir}:")
    for info in logs:
        stamp = info.stamp.strftime('%Y.%m.%d') if info.stamp else 'unknown'
        suffix = ' (zip)' if info.is_zipped else ''
        print(f"  {stamp} -> {info.path.name}{suffix}")
    return 0


def _list_kinds() -> int:
    print("Supported log kinds:")
    for kind in SUPPORTED_KINDS:
        print(f"  {kind}")
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


def _resolve_search_targets(
    args: argparse.Namespace,
    logs_dir: Path,
    log_kind: str,
) -> list[Path]:
    log_files = _normalize_path_values(getattr(args, "log_file", None))
    date_values = _normalize_text_values(getattr(args, "date", None))
    if log_files and date_values:
        raise ValueError("--log-file and --date cannot be used together.")

    if log_files:
        return _resolve_log_file_targets(logs_dir, log_kind, log_files)
    if date_values:
        return _resolve_date_targets(logs_dir, log_kind, date_values)
    newest = newest_log(logs_dir, log_kind)
    return [newest.path] if newest is not None else []


def _resolve_log_file_targets(
    logs_dir: Path,
    log_kind: str,
    log_files: list[Path],
) -> list[Path]:
    targets: list[Path] = []
    seen: set[Path] = set()
    kind_key = normalize_kind(log_kind)
    for value in log_files:
        target = value if value.is_absolute() else logs_dir / value
        if not target.exists():
            raise ValueError(f"Log file not found: {target}")
        parsed = parse_log_filename(target)
        if parsed.kind and parsed.kind != kind_key:
            raise ValueError(
                f"Log file {target.name} does not match kind {kind_key}."
            )
        resolved = target.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        targets.append(target)
    return targets


def _resolve_date_targets(
    logs_dir: Path,
    log_kind: str,
    date_values: list[str],
) -> list[Path]:
    targets: list[Path] = []
    seen: set[Path] = set()
    for value in date_values:
        target_date = parse_stamp(value)
        info = find_log_by_date(logs_dir, log_kind, target_date)
        if info is None:
            raise ValueError(
                f"No {log_kind} log found for {target_date:%Y.%m.%d} in "
                f"{logs_dir}"
            )
        resolved = info.path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        targets.append(info.path)
    return targets


def _normalize_path_values(values: object) -> list[Path]:
    if values is None:
        return []
    if isinstance(values, Path):
        return [values]
    return list(values)


def _normalize_text_values(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return list(values)


def _search_help_epilog() -> str:
    kinds = ", ".join(SUPPORTED_KINDS)
    mode_lines = "\n".join(
        f"  - {mode}: {SEARCH_MODE_DESCRIPTIONS[mode]}"
        for mode in SUPPORTED_SEARCH_MODES
    )
    return textwrap.dedent(
        f"""
        Target resolution:
          1. If --log-file is provided (repeatable), those files are searched.
          2. Else if --date is provided (repeatable), those dates are searched.
          3. Else the newest available log for --kind is searched.

        Search modes:
{mode_lines}

        Available kinds:
          {kinds}
        """
    ).strip()


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
