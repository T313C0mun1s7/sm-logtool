"""Formatting helpers for aligned log output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .log_kinds import (
    KIND_ADMINISTRATIVE,
    KIND_AUTOCLEANFOLDERS,
    KIND_DELIVERY,
    KIND_IMAP,
    KIND_IMAP_RETRIEVAL,
    KIND_INDEXING,
    KIND_POP,
    KIND_SMTP,
    KIND_WEBDAV,
    normalize_kind,
)
from .log_parsers import (
    TimeLogLine,
    parse_bracket1_line,
    parse_bracket1_trailing_time_line,
    parse_delivery_line,
    parse_imap_retrieval_line,
    parse_smtp_line,
    parse_time_line,
    starts_with_timestamp,
)
from .search import Conversation


@dataclass
class ColumnWidths:
    """Maximum widths used to align parsed log columns."""

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
    kind_key = normalize_kind(kind)

    for conversation in conversations:
        for line in conversation.lines:
            entry = _parse_line(kind_key, line)
            if entry is not None:
                found = True
                widths.time = max(widths.time, len(entry["time"]))
                widths.ip = max(widths.ip, len(entry.get("ip", "")))
                widths.log_id = max(
                    widths.log_id,
                    len(entry.get("log_id", "")),
                )
                continue
            time_entry = parse_time_line(line)
            if time_entry is None:
                continue
            found = True
            widths.time = max(widths.time, len(time_entry.timestamp))

    return widths if found else None


def format_conversation_lines(
    kind: str,
    lines: Sequence[str],
    widths: ColumnWidths | None,
) -> list[str]:
    """Return formatted lines with aligned columns."""

    if widths is None:
        return [line.rstrip("\n") for line in lines]

    kind_key = normalize_kind(kind)
    prefix = _continuation_prefix(kind_key, widths)
    formatted: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        entry = _parse_line(kind_key, line)
        if entry is None:
            time_entry = parse_time_line(line)
            if time_entry is not None:
                formatted.append(_format_time_only(time_entry, widths))
                continue
            if starts_with_timestamp(line):
                formatted.append(line)
                continue
            formatted.append(prefix + line.lstrip())
        else:
            formatted.append(_format_entry(kind_key, entry, widths))

    return formatted


def _parse_line(kind_key: str, line: str) -> dict[str, str] | None:
    if kind_key in {KIND_SMTP, KIND_IMAP, KIND_POP}:
        smtp_entry = parse_smtp_line(line)
        if smtp_entry is None:
            return None
        return {
            "time": smtp_entry.timestamp,
            "ip": smtp_entry.ip,
            "log_id": smtp_entry.log_id,
            "message": smtp_entry.message,
        }
    if kind_key == KIND_DELIVERY:
        delivery_entry = parse_delivery_line(line)
        if delivery_entry is None:
            return None
        return {
            "time": delivery_entry.timestamp,
            "log_id": delivery_entry.delivery_id,
            "message": delivery_entry.message,
        }
    if kind_key == KIND_IMAP_RETRIEVAL:
        retrieval_entry = parse_imap_retrieval_line(line)
        if retrieval_entry is None:
            return None
        return {
            "time": retrieval_entry.timestamp,
            "ip": retrieval_entry.retrieval_id,
            "log_id": retrieval_entry.context,
            "message": retrieval_entry.message,
        }
    if kind_key in {
        KIND_ADMINISTRATIVE,
        KIND_AUTOCLEANFOLDERS,
        KIND_INDEXING,
        KIND_WEBDAV,
    }:
        bracket_entry = parse_bracket1_line(line)
        if bracket_entry is None:
            bracket_entry = parse_bracket1_trailing_time_line(line)
        if bracket_entry is None:
            return None
        return {
            "time": bracket_entry.timestamp,
            "ip": bracket_entry.field1,
            "message": bracket_entry.message,
        }
    return None


def _format_entry(
    kind_key: str,
    entry: dict[str, str],
    widths: ColumnWidths,
) -> str:
    time = entry["time"]
    message = entry["message"]

    if kind_key in {KIND_SMTP, KIND_IMAP, KIND_POP}:
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
    if kind_key == KIND_DELIVERY:
        log_id = entry["log_id"]
        id_pad = " " * (widths.log_id - len(log_id) + 1)
        return (
            f"{time:<{widths.time}} "
            f"[{log_id}]{id_pad}"
            f"{message}"
        )
    if kind_key == KIND_IMAP_RETRIEVAL:
        retrieval_id = entry["ip"]
        context = entry["log_id"]
        id_pad = " " * (widths.ip - len(retrieval_id) + 1)
        context_pad = " " * (widths.log_id - len(context) + 1)
        return (
            f"{time:<{widths.time}} "
            f"[{retrieval_id}]{id_pad}"
            f"[{context}]{context_pad}"
            f"{message}"
        )
    if kind_key in {
        KIND_ADMINISTRATIVE,
        KIND_AUTOCLEANFOLDERS,
        KIND_INDEXING,
        KIND_WEBDAV,
    }:
        ip = entry["ip"]
        ip_pad = " " * (widths.ip - len(ip) + 1)
        return (
            f"{time:<{widths.time}} "
            f"[{ip}]{ip_pad}"
            f"{message}"
        )
    return f"{time} {message}"


def _format_time_only(entry: TimeLogLine, widths: ColumnWidths) -> str:
    return f"{entry.timestamp:<{widths.time}} {entry.message}"


def _continuation_prefix(
    kind_key: str,
    widths: ColumnWidths,
) -> str:
    return " " * _message_column(kind_key, widths)


def _message_column(kind_key: str, widths: ColumnWidths) -> int:
    if kind_key in {KIND_SMTP, KIND_IMAP, KIND_POP}:
        return widths.time + widths.ip + widths.log_id + 7
    if kind_key == KIND_DELIVERY:
        return widths.time + widths.log_id + 4
    if kind_key == KIND_IMAP_RETRIEVAL:
        return widths.time + widths.ip + widths.log_id + 7
    if kind_key in {
        KIND_ADMINISTRATIVE,
        KIND_AUTOCLEANFOLDERS,
        KIND_INDEXING,
        KIND_WEBDAV,
    }:
        return widths.time + widths.ip + 4
    return widths.time + 1
