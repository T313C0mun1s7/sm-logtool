"""Search mode definitions shared by CLI and TUI."""

from __future__ import annotations

import re

MODE_LITERAL = "literal"
MODE_WILDCARD = "wildcard"
MODE_REGEX = "regex"

SUPPORTED_SEARCH_MODES = (
    MODE_LITERAL,
    MODE_WILDCARD,
    MODE_REGEX,
)

SEARCH_MODE_LABELS = {
    MODE_LITERAL: "Literal",
    MODE_WILDCARD: "Wildcard",
    MODE_REGEX: "Regex",
}

SEARCH_MODE_DESCRIPTIONS = {
    MODE_LITERAL: "Exact substring match.",
    MODE_WILDCARD: "'*' matches many chars, '?' matches one char.",
    MODE_REGEX: "Python re syntax (PCRE-like, not full PCRE).",
}


def normalize_search_mode(value: str | None) -> str:
    """Validate and normalize a search mode value."""

    mode = (value or MODE_LITERAL).strip().lower()
    if mode in SUPPORTED_SEARCH_MODES:
        return mode

    choices = ", ".join(SUPPORTED_SEARCH_MODES)
    raise ValueError(
        f"Unsupported search mode: {value!r}. Choose one of: {choices}."
    )


def wildcard_to_regex(pattern: str) -> str:
    """Convert wildcard text using ``*`` and ``?`` to regex source."""

    parts: list[str] = []
    for char in pattern:
        if char == "*":
            parts.append(".*")
            continue
        if char == "?":
            parts.append(".")
            continue
        parts.append(re.escape(char))
    return "".join(parts)
