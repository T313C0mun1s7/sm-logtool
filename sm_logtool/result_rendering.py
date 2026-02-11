"""Shared search result rendering for CLI and TUI output."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .result_formatting import collect_widths, format_conversation_lines
from .search import SmtpSearchResult

UNGROUPED_KINDS = {
    "administrative",
    "activation",
    "autocleanfolders",
    "calendars",
    "contentfilter",
    "event",
    "generalerrors",
    "indexing",
    "ldaplog",
    "maintenance",
    "profiler",
    "spamchecks",
    "webdav",
}


def render_search_results(
    results: Sequence[SmtpSearchResult],
    targets: Sequence[Path],
    kind: str,
) -> list[str]:
    """Render search results as output lines."""

    if len(results) != len(targets):
        raise ValueError("results and targets must have matching lengths")

    rendered_lines: list[str] = []
    kind_key = kind.lower()
    is_ungrouped = kind_key in UNGROUPED_KINDS
    label = "entry" if is_ungrouped else "conversation"

    for result, target in zip(results, targets):
        rendered_lines.append(f"=== {target.name} ===")
        rendered_lines.append(
            f"Search term '{result.term}' -> "
            f"{result.total_conversations} {label}(s)"
        )
        if not result.conversations and not result.orphan_matches:
            rendered_lines.append("No matches found.")
        widths = collect_widths(kind, result.conversations)
        for conversation in result.conversations:
            formatted = format_conversation_lines(
                kind,
                conversation.lines,
                widths,
            )
            if not is_ungrouped:
                rendered_lines.append("")
                rendered_lines.append(
                    f"[{conversation.message_id}] first seen on line "
                    f"{conversation.first_line_number}"
                )
            rendered_lines.extend(formatted)
        if result.orphan_matches:
            if not is_ungrouped:
                rendered_lines.append("")
                rendered_lines.append(
                    "Lines without message identifiers that matched:"
                )
            for line_number, line in result.orphan_matches:
                if is_ungrouped:
                    rendered_lines.append(line)
                else:
                    rendered_lines.append(f"{line_number}: {line}")
        if not is_ungrouped:
            rendered_lines.append("")

    return rendered_lines
