#!/usr/bin/env python3
"""Benchmark sm-logtool search performance on local/server logs.

This tool is intentionally focused on real on-disk logs (no synthetic fixtures)
so baseline numbers reflect production-like workloads.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
import json
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import time
from typing import Iterable

from sm_logtool.log_kinds import normalize_kind
from sm_logtool.logfiles import (
    find_log_by_date,
    newest_log,
    parse_log_filename,
)
from sm_logtool.logfiles import parse_stamp
from sm_logtool.search import _compile_line_matcher
from sm_logtool.search import get_search_function
from sm_logtool.search_modes import DEFAULT_FUZZY_THRESHOLD
from sm_logtool.search_modes import SUPPORTED_SEARCH_MODES
from sm_logtool.search_modes import normalize_search_mode
from sm_logtool.staging import stage_log


@dataclass(frozen=True)
class RunMetrics:
    """Metrics captured for a single benchmark run."""

    mode: str
    run_index: int
    elapsed_seconds: float
    peak_rss_kib: float
    first_match_scan_seconds: float | None
    total_files: int
    total_bytes: int
    total_lines: int
    matched_conversations: int
    orphan_matches: int
    first_visible_result_seconds: float


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Benchmark sm-logtool search modes against local/server logs."
        ),
    )
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--term", required=True)
    parser.add_argument(
        "--mode",
        action="append",
        choices=SUPPORTED_SEARCH_MODES,
        default=None,
        help=(
            "Search mode to benchmark. Repeat for multiple modes. "
            "Default benchmarks all supported modes."
        ),
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=DEFAULT_FUZZY_THRESHOLD,
    )
    parser.add_argument("--case-sensitive", action="store_true")
    parser.add_argument(
        "--date",
        action="append",
        default=None,
        help="YYYY.MM.DD date(s) to benchmark. Repeatable.",
    )
    parser.add_argument(
        "--log-file",
        action="append",
        default=None,
        help="Explicit log file(s) to benchmark. Repeatable.",
    )
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--label", default="")
    parser.add_argument(
        "--today",
        default=None,
        help="Override staging refresh date as YYYY.MM.DD.",
    )
    parser.add_argument(
        "--skip-first-match-scan",
        action="store_true",
        help=(
            "Skip pre-scan estimate for first match timing. "
            "By default, this scan is collected for visibility."
        ),
    )
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--worker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--worker-mode",
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--worker-run-index",
        type=int,
        default=1,
        help=argparse.SUPPRESS,
    )
    return parser


def _parse_today(value: str | None) -> date | None:
    if value is None:
        return None
    return parse_stamp(value)


def _normalize_modes(value: list[str] | None) -> list[str]:
    if not value:
        return [normalize_search_mode(mode) for mode in SUPPORTED_SEARCH_MODES]
    return [normalize_search_mode(mode) for mode in value]


def _resolve_targets(
    logs_dir: Path,
    kind: str,
    dates: list[str] | None,
    log_files: list[str] | None,
) -> list[Path]:
    if dates and log_files:
        raise ValueError("--date and --log-file cannot be used together.")

    if log_files:
        return _resolve_log_files(logs_dir, kind, log_files)
    if dates:
        return _resolve_dates(logs_dir, kind, dates)

    newest = newest_log(logs_dir, kind)
    return [newest.path] if newest is not None else []


def _resolve_log_files(
    logs_dir: Path,
    kind: str,
    values: Iterable[str],
) -> list[Path]:
    kind_key = normalize_kind(kind)
    targets: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        raw_path = Path(value)
        candidate = raw_path if raw_path.is_absolute() else logs_dir / raw_path
        if not candidate.exists():
            raise ValueError(f"Log file not found: {candidate}")
        parsed = parse_log_filename(candidate)
        if parsed.kind and parsed.kind != kind_key:
            raise ValueError(
                f"Log file {candidate.name} does not match kind {kind_key}."
            )
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        targets.append(candidate)
    return targets


def _resolve_dates(
    logs_dir: Path,
    kind: str,
    values: Iterable[str],
) -> list[Path]:
    targets: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        target_date = parse_stamp(value)
        info = find_log_by_date(logs_dir, kind, target_date)
        if info is None:
            raise ValueError(
                f"No {kind} log found for {target_date:%Y.%m.%d} in {logs_dir}"
            )
        resolved = info.path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        targets.append(info.path)
    return targets


def _rss_kib() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return raw / 1024.0
    return float(raw)


def _scan_first_match_seconds(
    staged_paths: list[Path],
    term: str,
    mode: str,
    ignore_case: bool,
    fuzzy_threshold: float,
) -> float | None:
    matcher = _compile_line_matcher(
        term,
        mode,
        ignore_case,
        fuzzy_threshold,
    )
    started = time.perf_counter()
    for path in staged_paths:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for raw_line in handle:
                if matcher(raw_line.rstrip("\n")):
                    return time.perf_counter() - started
    return None


def _run_worker(args: argparse.Namespace) -> int:
    if args.worker_mode is None:
        raise ValueError("Internal error: --worker-mode is required.")

    today_value = _parse_today(args.today)
    kind = normalize_kind(args.kind)
    search_mode = normalize_search_mode(args.worker_mode)
    search_fn = get_search_function(kind)
    if search_fn is None:
        raise ValueError(f"No search handler for log kind: {kind}")

    targets = _resolve_targets(
        args.logs_dir,
        kind,
        args.date,
        args.log_file,
    )
    if not targets:
        raise ValueError(f"No {kind} logs found in {args.logs_dir}")

    staged_paths: list[Path] = []
    for target in targets:
        staged = stage_log(
            target,
            staging_dir=args.staging_dir,
            today=today_value,
        )
        staged_paths.append(staged.staged_path)

    total_bytes = sum(path.stat().st_size for path in staged_paths)
    first_match = None
    if not args.skip_first_match_scan:
        first_match = _scan_first_match_seconds(
            staged_paths,
            args.term,
            search_mode,
            ignore_case=not args.case_sensitive,
            fuzzy_threshold=args.fuzzy_threshold,
        )

    started = time.perf_counter()
    results = []
    for path in staged_paths:
        result = search_fn(
            path,
            args.term,
            mode=search_mode,
            fuzzy_threshold=args.fuzzy_threshold,
            ignore_case=not args.case_sensitive,
        )
        results.append(result)
    elapsed = time.perf_counter() - started

    metrics = RunMetrics(
        mode=search_mode,
        run_index=args.worker_run_index,
        elapsed_seconds=elapsed,
        peak_rss_kib=_rss_kib(),
        first_match_scan_seconds=first_match,
        total_files=len(staged_paths),
        total_bytes=total_bytes,
        total_lines=sum(result.total_lines for result in results),
        matched_conversations=sum(
            len(result.conversations) for result in results
        ),
        orphan_matches=sum(len(result.orphan_matches) for result in results),
        # Current CLI/TUI flow renders in batch after search completes.
        first_visible_result_seconds=elapsed,
    )
    print(json.dumps(asdict(metrics), sort_keys=True))
    return 0


def _worker_command(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    mode: str,
    run_index: int,
) -> list[str]:
    _ = parser
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--worker-mode",
        mode,
        "--worker-run-index",
        str(run_index),
        "--logs-dir",
        str(args.logs_dir),
        "--staging-dir",
        str(args.staging_dir),
        "--kind",
        args.kind,
        "--term",
        args.term,
        "--fuzzy-threshold",
        str(args.fuzzy_threshold),
        "--repeat",
        "1",
        "--warmup",
        "0",
    ]
    if args.case_sensitive:
        command.append("--case-sensitive")
    if args.label:
        command.extend(["--label", args.label])
    if args.today:
        command.extend(["--today", args.today])
    if args.skip_first_match_scan:
        command.append("--skip-first-match-scan")
    for value in args.date or []:
        command.extend(["--date", value])
    for value in args.log_file or []:
        command.extend(["--log-file", value])
    return command


def _run_child(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    mode: str,
    run_index: int,
) -> RunMetrics:
    command = _worker_command(parser, args, mode, run_index)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        message = (
            f"Benchmark worker failed for mode={mode} run={run_index}:\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )
        raise RuntimeError(message)
    payload = completed.stdout.strip().splitlines()
    if not payload:
        raise RuntimeError("Benchmark worker produced no JSON output.")
    data = json.loads(payload[-1])
    return RunMetrics(**data)


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    unit = units[0]
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            break
        value /= 1024.0
    return f"{value:.2f} {unit}"


def _print_summary(
    args: argparse.Namespace,
    modes: list[str],
    runs: list[RunMetrics],
) -> None:
    print("sm-logtool benchmark summary")
    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Started: {started} (UTC)")
    if args.label:
        print(f"Label: {args.label}")
    print(f"Kind: {normalize_kind(args.kind)}")
    print(f"Modes: {', '.join(modes)}")
    print(f"Repeat: {args.repeat}, Warmup: {args.warmup}")
    print(f"Logs dir: {args.logs_dir}")
    print(f"Staging dir: {args.staging_dir}")
    if args.date:
        print(f"Dates: {', '.join(args.date)}")
    if args.log_file:
        print(f"Log files: {', '.join(args.log_file)}")
    print()
    print(
        "Mode       Runs  Mean(s)  Min(s)  Max(s)  "
        "Mean RSS(MiB)  Mean First Match(s)"
    )
    print("-" * 76)
    for mode in modes:
        mode_runs = [run for run in runs if run.mode == mode]
        elapsed = [run.elapsed_seconds for run in mode_runs]
        rss_mib = [run.peak_rss_kib / 1024.0 for run in mode_runs]
        firsts = [
            value
            for value in (run.first_match_scan_seconds for run in mode_runs)
            if value is not None
        ]
        mean_first = statistics.fmean(firsts) if firsts else float("nan")
        print(
            f"{mode:<10} {len(mode_runs):>4}  "
            f"{statistics.fmean(elapsed):>7.3f}  "
            f"{min(elapsed):>6.3f}  "
            f"{max(elapsed):>6.3f}  "
            f"{statistics.fmean(rss_mib):>13.2f}  "
            f"{mean_first:>19.3f}"
        )
    print()

    sample = runs[0]
    print(f"Files searched: {sample.total_files}")
    print(f"Total staged bytes: {_format_bytes(sample.total_bytes)}")
    print(f"Total lines scanned: {sample.total_lines}")
    print(
        "Note: first_visible_result_seconds currently equals elapsed_seconds "
        "because results render after batch completion."
    )


def _write_json(
    path: Path,
    args: argparse.Namespace,
    runs: list[RunMetrics],
) -> None:
    payload = {
        "label": args.label,
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "logs_dir": str(args.logs_dir),
        "staging_dir": str(args.staging_dir),
        "kind": normalize_kind(args.kind),
        "term": args.term,
        "repeat": args.repeat,
        "warmup": args.warmup,
        "runs": [asdict(run) for run in runs],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_parent(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> int:
    if args.repeat < 1:
        raise ValueError("--repeat must be >= 1.")
    if args.warmup < 0:
        raise ValueError("--warmup must be >= 0.")
    if not args.logs_dir.exists():
        raise ValueError(f"Logs directory not found: {args.logs_dir}")
    args.staging_dir.mkdir(parents=True, exist_ok=True)

    modes = _normalize_modes(args.mode)
    for mode in modes:
        for run_index in range(1, args.warmup + 1):
            _run_child(parser, args, mode, run_index)

    runs: list[RunMetrics] = []
    for mode in modes:
        for run_index in range(1, args.repeat + 1):
            metrics = _run_child(parser, args, mode, run_index)
            runs.append(metrics)

    _print_summary(args, modes, runs)
    if args.json_out is not None:
        _write_json(args.json_out, args, runs)
        print(f"Wrote JSON metrics: {args.json_out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.worker:
            return _run_worker(args)
        return _run_parent(parser, args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
