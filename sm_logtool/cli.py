"""Command-line entry point for sm-logtool.

Provides a `--logs-dir` option and launches the Textual UI. Imports Textual
on-demand so that importing this module (e.g., in tests) doesn't require the
Textual dependency to be present.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path


DEFAULT_LOGS_DIR = Path(__file__).resolve().parent.parent / "sample_logs"


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""

    parser = argparse.ArgumentParser(
        prog="sm-logtool",
        description=textwrap.dedent(
            """
            Explore SmarterMail logs from your terminal. This initial skeleton simply
            checks that a logs directory exists and reports how many log files were
            detected. Future iterations will provide a full TUI experience.
            """
        ).strip(),
    )

    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=DEFAULT_LOGS_DIR,
        help=(
            "Path containing SmarterMail log files. Populate the `sample_logs/` "
            "folder during development or point at a live log directory when ready.""
        ),
    )

    return parser


def scan_logs(logs_dir: Path) -> list[Path]:
    """Return log files underneath ``logs_dir`` sorted by name."""

    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")

    if not logs_dir.is_dir():
        raise NotADirectoryError(f"Logs path is not a directory: {logs_dir}")

    return sorted(
        path
        for path in logs_dir.iterdir()
        if path.is_file() and not path.name.startswith(".")
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point used by console scripts and ``python -m sm_logtool.cli``."""

    parser = build_parser()
    args = parser.parse_args(argv)

    # Lazy import so tests can import this module without having textual installed.
    try:
        from .ui.app import run as run_tui  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive fallback
        parser.error(
            "The Textual UI could not be loaded. Ensure the 'textual' package is installed.\n"
            f"Details: {exc}"
        )
        return 2

    return run_tui(args.logs_dir)


if __name__ == "__main__":
    raise SystemExit(main())
