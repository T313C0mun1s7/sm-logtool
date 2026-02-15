#!/usr/bin/env python3
"""Release guard checks for repository defaults."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

from sm_logtool import config


EXPECTED_THEME = "Cyberdark"


def _load_repo_config(path: Path) -> dict[str, object]:
    if not path.exists():
        raise RuntimeError(f"Missing required file: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected mapping in {path}, got {type(payload).__name__}")
    return payload


def main() -> int:
    failures: list[str] = []

    if config.DEFAULT_THEME != EXPECTED_THEME:
        failures.append(
            "sm_logtool.config.DEFAULT_THEME "
            f"is {config.DEFAULT_THEME!r}, expected {EXPECTED_THEME!r}."
        )

    repo_cfg = _load_repo_config(Path("config.yaml"))
    repo_theme = repo_cfg.get("theme")
    if repo_theme != EXPECTED_THEME:
        failures.append(
            f"config.yaml theme is {repo_theme!r}, expected {EXPECTED_THEME!r}."
        )

    if failures:
        print("Release default checks failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Release default checks passed: "
        f"DEFAULT_THEME={config.DEFAULT_THEME!r}, config.yaml theme={repo_theme!r}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
