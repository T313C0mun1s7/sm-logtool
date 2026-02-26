"""Canonical SmarterMail log kind helpers."""

from __future__ import annotations

from typing import Final

KIND_SMTP: Final[str] = "smtp"
KIND_IMAP: Final[str] = "imap"
KIND_POP: Final[str] = "pop"
KIND_DELIVERY: Final[str] = "delivery"
KIND_ADMINISTRATIVE: Final[str] = "administrative"
KIND_IMAP_RETRIEVAL: Final[str] = "imapretrieval"
KIND_ACTIVATION: Final[str] = "activation"
KIND_AUTOCLEANFOLDERS: Final[str] = "autocleanfolders"
KIND_CALENDARS: Final[str] = "calendars"
KIND_CONTENTFILTER: Final[str] = "contentfilter"
KIND_EVENT: Final[str] = "event"
KIND_GENERALERRORS: Final[str] = "generalerrors"
KIND_INDEXING: Final[str] = "indexing"
KIND_LDAP: Final[str] = "ldap"
KIND_MAINTENANCE: Final[str] = "maintenance"
KIND_PROFILER: Final[str] = "profiler"
KIND_SPAMCHECKS: Final[str] = "spamchecks"
KIND_WEBDAV: Final[str] = "webdav"

SUPPORTED_KINDS: Final[tuple[str, ...]] = (
    KIND_SMTP,
    KIND_IMAP,
    KIND_POP,
    KIND_DELIVERY,
    KIND_ADMINISTRATIVE,
    KIND_IMAP_RETRIEVAL,
    KIND_ACTIVATION,
    KIND_AUTOCLEANFOLDERS,
    KIND_CALENDARS,
    KIND_CONTENTFILTER,
    KIND_EVENT,
    KIND_GENERALERRORS,
    KIND_INDEXING,
    KIND_LDAP,
    KIND_MAINTENANCE,
    KIND_PROFILER,
    KIND_SPAMCHECKS,
    KIND_WEBDAV,
)

SEARCH_UNGROUPED_KINDS: Final[tuple[str, ...]] = (
    KIND_ACTIVATION,
    KIND_AUTOCLEANFOLDERS,
    KIND_CALENDARS,
    KIND_CONTENTFILTER,
    KIND_EVENT,
    KIND_GENERALERRORS,
    KIND_INDEXING,
    KIND_LDAP,
    KIND_MAINTENANCE,
    KIND_PROFILER,
    KIND_SPAMCHECKS,
    KIND_WEBDAV,
)

ENTRY_RENDER_KINDS: Final[tuple[str, ...]] = (
    KIND_ADMINISTRATIVE,
    *SEARCH_UNGROUPED_KINDS,
)

_KIND_ALIASES: Final[dict[str, str]] = {
    KIND_SMTP: KIND_SMTP,
    "smtplog": KIND_SMTP,
    KIND_IMAP: KIND_IMAP,
    "imaplog": KIND_IMAP,
    KIND_POP: KIND_POP,
    "poplog": KIND_POP,
    KIND_DELIVERY: KIND_DELIVERY,
    KIND_ADMINISTRATIVE: KIND_ADMINISTRATIVE,
    KIND_IMAP_RETRIEVAL: KIND_IMAP_RETRIEVAL,
    "imapretrievallog": KIND_IMAP_RETRIEVAL,
    KIND_ACTIVATION: KIND_ACTIVATION,
    KIND_AUTOCLEANFOLDERS: KIND_AUTOCLEANFOLDERS,
    KIND_CALENDARS: KIND_CALENDARS,
    KIND_CONTENTFILTER: KIND_CONTENTFILTER,
    KIND_EVENT: KIND_EVENT,
    KIND_GENERALERRORS: KIND_GENERALERRORS,
    KIND_INDEXING: KIND_INDEXING,
    KIND_LDAP: KIND_LDAP,
    "ldaplog": KIND_LDAP,
    KIND_MAINTENANCE: KIND_MAINTENANCE,
    KIND_PROFILER: KIND_PROFILER,
    KIND_SPAMCHECKS: KIND_SPAMCHECKS,
    KIND_WEBDAV: KIND_WEBDAV,
}


def normalize_kind(value: str) -> str:
    """Return the canonical log kind key for ``value``."""

    key = value.strip().lower()
    return _KIND_ALIASES.get(key, key)


def is_search_ungrouped_kind(value: str) -> bool:
    """Return whether ``value`` uses ungrouped search entry strategy."""

    return normalize_kind(value) in SEARCH_UNGROUPED_KINDS


def is_entry_render_kind(value: str) -> bool:
    """Return whether ``value`` renders as entry-style results."""

    return normalize_kind(value) in ENTRY_RENDER_KINDS
