"""Enforce the 79-character limit for production Python files."""

from __future__ import annotations

from pathlib import Path

MAX_LINE_LENGTH = 79
TARGET_DIRECTORIES = ("sm_logtool", "scripts")
LINE_LENGTH_EXCEPTIONS: dict[str, set[int]] = {}


def _line_length_violations(path: Path, root: Path) -> list[str]:
    relative_path = path.relative_to(root).as_posix()
    exceptions = LINE_LENGTH_EXCEPTIONS.get(relative_path, set())
    violations: list[str] = []

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        if len(line) <= MAX_LINE_LENGTH:
            continue
        if line_number in exceptions:
            continue
        length = len(line)
        violations.append(
            f"{relative_path}:{line_number} has {length} characters",
        )
    return violations


def test_production_python_line_lengths() -> None:
    project_root = Path(__file__).resolve().parents[1]
    violations: list[str] = []

    for directory in TARGET_DIRECTORIES:
        base = project_root / directory
        for path in sorted(base.rglob("*.py")):
            violations.extend(_line_length_violations(path, project_root))

    assert not violations, (
        "Production line-length violations detected:\n"
        + "\n".join(violations)
    )
