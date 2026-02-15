#!/usr/bin/env python3
"""Release guard checks for repository defaults.

This script intentionally uses only Python's standard library so it can run
early in CI before project dependencies are installed.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys


EXPECTED_THEME = "Cyberdark"


def _load_default_theme_constant(path: Path) -> str:
    """Read ``DEFAULT_THEME`` from ``sm_logtool/config.py``."""

    if not path.exists():
        raise RuntimeError(f"Missing required file: {path}")
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(path))
    for node in module.body:
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            for target in targets:
                if target.id != "DEFAULT_THEME":
                    continue
                if (
                    isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    return node.value.value
                raise RuntimeError(
                    "DEFAULT_THEME must be assigned to a string literal."
                )
    raise RuntimeError("DEFAULT_THEME not found in sm_logtool/config.py.")


def _load_top_level_scalar(path: Path, key: str) -> str:
    """Read a simple top-level ``key: value`` scalar from YAML text."""

    if not path.exists():
        raise RuntimeError(f"Missing required file: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        if left.strip() != key:
            continue
        value = right.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]
        return value
    raise RuntimeError(f"Key {key!r} not found in {path}.")


def main() -> int:
    failures: list[str] = []

    module_theme = _load_default_theme_constant(Path("sm_logtool/config.py"))
    if module_theme != EXPECTED_THEME:
        failures.append(
            "sm_logtool/config.py DEFAULT_THEME "
            f"is {module_theme!r}, expected {EXPECTED_THEME!r}."
        )

    repo_theme = _load_top_level_scalar(Path("config.yaml"), "theme")
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
        f"DEFAULT_THEME={module_theme!r}, config.yaml theme={repo_theme!r}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
