"""Formatting helpers for aligned log output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .log_parsers import (
    parse_admin_line,
    parse_delivery_line,
    parse_smtp_line,
)
from .search import Conversation


@dataclass
class ColumnWidths:
    time: int = 0
    ip: int = 0
    log_id: int = 0


def collect_widths(
    kind: str,
    conversations: Iterable[Conversation],
) -> ColumnWidths | None:
    """Collect max column widths for the given log kind."""

    widths = ColumnWidths()
    found = False
    kind_key = kind.lower()

    for conversation in conversations:
        for line in conversation.lines:
            entry = _parse_line(kind_key, line)
            if entry is None:
                continue
            found = True
            widths.time = max(widths.time, len(entry["time"]))
            widths.ip = max(widths.ip, len(entry.get("ip", "")))
            widths.log_id = max(widths.log_id, len(entry.get("log_id", "")))

    return widths if found else None


def format_conversation_lines(
    kind: str,
    lines: Sequence[str],
    widths: ColumnWidths | None,
) -> list[str]:
    """Return formatted lines with aligned columns."""

    if widths is None:
        return [line.rstrip("\n") for line in lines]

    kind_key = kind.lower()
    prefix = _continuation_prefix(kind_key, widths)
    formatted: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        entry = _parse_line(kind_key, line)
        if entry is None:
            formatted.append(prefix + line.lstrip())
        else:
            formatted.append(_format_entry(kind_key, entry, widths))

    return formatted


def _parse_line(kind_key: str, line: str) -> dict[str, str] | None:
    if kind_key == "smtplog":
        entry = parse_smtp_line(line)
        if entry is None:
            return None
        return {
            "time": entry.timestamp,
            "ip": entry.ip,
            "log_id": entry.log_id,
            "message": entry.message,
        }
    if kind_key == "delivery":
        entry = parse_delivery_line(line)
        if entry is None:
            return None
        return {
            "time": entry.timestamp,
            "log_id": entry.delivery_id,
            "message": entry.message,
        }
    if kind_key == "administrative":
        entry = parse_admin_line(line)
        if entry is None:
            return None
        return {
            "time": entry.timestamp,
            "ip": entry.ip,
            "message": entry.message,
        }
    return None


def _format_entry(
    kind_key: str,
    entry: dict[str, str],
    widths: ColumnWidths,
) -> str:
    time = entry["time"]
    message = entry["message"]

    if kind_key == "smtplog":
        ip = entry["ip"]
        log_id = entry["log_id"]
        ip_pad = " " * (widths.ip - len(ip) + 1)
        id_pad = " " * (widths.log_id - len(log_id) + 1)
        return (
            f"{time:<{widths.time}} "
            f"[{ip}]{ip_pad}"
            f"[{log_id}]{id_pad}"
            f"{message}"
        )
    if kind_key == "delivery":
        log_id = entry["log_id"]
        id_pad = " " * (widths.log_id - len(log_id) + 1)
        return (
            f"{time:<{widths.time}} "
            f"[{log_id}]{id_pad}"
            f"{message}"
        )
    if kind_key == "administrative":
        ip = entry["ip"]
        ip_pad = " " * (widths.ip - len(ip) + 1)
        return (
            f"{time:<{widths.time}} "
            f"[{ip}]{ip_pad}"
            f"{message}"
        )
    return f"{time} {message}"


def _continuation_prefix(
    kind_key: str,
    widths: ColumnWidths,
) -> str:
    return " " * _message_column(kind_key, widths)


def _message_column(kind_key: str, widths: ColumnWidths) -> int:
    if kind_key == "smtplog":
        return widths.time + widths.ip + widths.log_id + 7
    if kind_key == "delivery":
        return widths.time + widths.log_id + 4
    if kind_key == "administrative":
        return widths.time + widths.ip + 4
    return 0
