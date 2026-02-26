"""Checks for public API docstring coverage in production modules."""

from __future__ import annotations

import ast
from pathlib import Path


def _is_property_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "property":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "setter":
            return True
    return False


def _missing_public_docstrings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing: list[str] = []

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child.parent = parent

    for node in tree.body:
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue
        if node.name.startswith("_"):
            continue
        if ast.get_docstring(node) is None:
            missing.append(f"{path}:{node.lineno} top-level {node.name}")

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        parent = getattr(node, "parent", None)
        if not isinstance(parent, ast.ClassDef):
            continue
        if parent.name.startswith("_") or node.name.startswith("_"):
            continue
        if not _is_property_method(node):
            continue
        if ast.get_docstring(node) is None:
            name = f"{parent.name}.{node.name}"
            missing.append(f"{path}:{node.lineno} property {name}")
    return missing


def test_public_api_docstrings_present() -> None:
    project_root = Path(__file__).resolve().parents[1]
    package_root = project_root / "sm_logtool"
    missing: list[str] = []

    for path in sorted(package_root.rglob("*.py")):
        missing.extend(_missing_public_docstrings(path))

    assert not missing, (
        "Missing public API docstrings:\n"
        + "\n".join(missing)
    )
