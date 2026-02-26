"""Unittest bridge that executes the pytest suite."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


def _running_under_pytest() -> bool:
    argv = " ".join(sys.argv).lower()
    return "pytest" in argv


@unittest.skipIf(
    _running_under_pytest(),
    "Bridge test is only used by unittest discover.",
)
class TestPytestBridge(unittest.TestCase):
    """Run pytest from unittest discover to keep both entrypoints valid."""

    def test_pytest_suite_passes(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        bridge_path = Path(__file__).resolve()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--ignore",
            str(bridge_path),
        ]
        completed = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return

        details = "\n".join(
            [
                "pytest bridge failed.",
                f"Command: {' '.join(command)}",
                f"Exit code: {completed.returncode}",
                f"stdout:\n{completed.stdout}",
                f"stderr:\n{completed.stderr}",
            ]
        )
        self.fail(details)
