"""Search mode definitions shared by CLI and TUI."""

from __future__ import annotations

import re

MODE_LITERAL = "literal"
MODE_WILDCARD = "wildcard"
MODE_REGEX = "regex"
MODE_FUZZY = "fuzzy"

DEFAULT_FUZZY_THRESHOLD = 0.75
MIN_FUZZY_THRESHOLD = 0.0
MAX_FUZZY_THRESHOLD = 1.0

SUPPORTED_SEARCH_MODES = (
    MODE_LITERAL,
    MODE_WILDCARD,
    MODE_REGEX,
    MODE_FUZZY,
)

SEARCH_MODE_LABELS = {
    MODE_LITERAL: "Literal",
    MODE_WILDCARD: "Wildcard",
    MODE_REGEX: "Regex",
    MODE_FUZZY: "Fuzzy",
}

SEARCH_MODE_DESCRIPTIONS = {
    MODE_LITERAL: "Exact substring match.",
    MODE_WILDCARD: "'*' matches many chars, '?' matches one char.",
    MODE_REGEX: "Python re syntax (PCRE-like, not full PCRE).",
    MODE_FUZZY: "Approximate line match using similarity threshold.",
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


def normalize_fuzzy_threshold(value: float | None) -> float:
    """Validate and normalize fuzzy threshold."""

    if value is None:
        return DEFAULT_FUZZY_THRESHOLD

    threshold = float(value)
    if MIN_FUZZY_THRESHOLD <= threshold <= MAX_FUZZY_THRESHOLD:
        return threshold

    raise ValueError(
        "Invalid fuzzy threshold: "
        f"{value!r}. Choose a value between "
        f"{MIN_FUZZY_THRESHOLD:.2f} and {MAX_FUZZY_THRESHOLD:.2f}."
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
