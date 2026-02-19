"""Result display mode definitions for CLI and TUI output."""

from __future__ import annotations

RESULT_MODE_RELATED_TRAFFIC = "related"
RESULT_MODE_MATCHING_ROWS = "matching-only"

SUPPORTED_RESULT_MODES = (
    RESULT_MODE_RELATED_TRAFFIC,
    RESULT_MODE_MATCHING_ROWS,
)

RESULT_MODE_LABELS = {
    RESULT_MODE_RELATED_TRAFFIC: "Show all related traffic",
    RESULT_MODE_MATCHING_ROWS: "Only matching rows",
}

RESULT_MODE_DESCRIPTIONS = {
    RESULT_MODE_RELATED_TRAFFIC: (
        "Show full grouped conversations for matched identifiers."
    ),
    RESULT_MODE_MATCHING_ROWS: (
        "Show only rows that directly match the search term."
    ),
}


def normalize_result_mode(value: str) -> str:
    """Return a normalized result mode value or raise ``ValueError``."""

    mode = value.strip().lower()
    if mode in SUPPORTED_RESULT_MODES:
        return mode
    supported = ", ".join(SUPPORTED_RESULT_MODES)
    raise ValueError(
        f"Unsupported result mode: {value!r}. "
        f"Expected one of: {supported}."
    )
