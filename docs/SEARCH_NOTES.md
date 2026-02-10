# sm-logtool: Search Design Notes

Purpose: capture requirements and design direction for the TUI search app based on the existing Bash workflow and planned multi–log-type support. This document is a living reference for development decisions.

---

## Key Behaviors From Existing Bash Script

Source characteristics we want to preserve or generalize:

- Directory selection: searches under a SmarterMail logs directory (e.g., `/var/lib/smartermail/Logs`).
- File selection: lists matching logs (script uses `*-smtpLog.log*`) and sorts newest first (`sort -r`).
- Zipped logs: if a selected file ends with `.zip`, unzip first, then search the unzipped content.
- Search term: case-insensitive, treated as a regex (AWK sets `IGNORECASE=1`; `if ($0 ~ regex) …`).
- Conversation grouping: lines are grouped by a correlation key extracted from bracketed fields (script uses `$4` with `-F'[][]'`). All lines sharing the same key are considered one “conversation”.
- Ordering: conversations are written in the order of their first occurrence in the log (tracked via `NR`), not by final match time.
- Output: results written to a derived filename using the search term sanitized to filesystem-safe characters.

Notes:
- The Bash claim of “fuzzy search” isn’t reflected in AWK (regex match is exact/regex). We should add true fuzzy/approximate matching as an option.
- The bracket field used as a conversation key may differ per log type; we’ll formalize this per-type.

---

## Derived Requirements for sm-logtool

- Multi-log-type support: SMTP and beyond (IMAP, POP, delivery, auth, etc.). Each type defines:
  - File matching pattern(s) for discovery (e.g., `*-smtpLog.log*`).
  - Parser for extracting a correlation key (message/conversation ID) and useful fields for highlighting.
  - Syntax highlighting rules (status codes, IPs, emails, event keywords).
- File discovery and sorting: list newest files first; optionally group by type and by day.
- Zipped logs: support `.zip` (and potentially `.gz`) without permanently extracting to the logs directory.
  - Prefer streaming reads via `zipfile`/`gzip` or extraction to a temporary workspace (`/tmp` or configurable) with cleanup.
- Staging workspace: copy or unzip logs into a temp directory (e.g.,
  `/var/tmp/sm-logtool/Temp`) so searches use a stable snapshot and
  sub-searches can operate on already-filtered files without mutating
  production logs.
- Search modes:
  - Plain text (case-insensitive substring).
  - Regex (case-sensitive toggle + flags).
  - Fuzzy/approximate matching with adjustable threshold (e.g., Levenshtein/token-based via `rapidfuzz`).
- Sub-search: allow additional filters over current results without rescanning the entire file.
- Conversation grouping: accumulate lines by correlation key; display and export grouped conversations.
- Ordering: default sort conversations by first occurrence; allow alternate sorts (recent activity, number of matches).
- Performance and scale:
  - Stream large files; do not load entire logs into memory.
  - Consider two-phase approach: (1) detect matching IDs, (2) collect and present their conversations. For very large logs, store offsets or spill per-ID buffers to disk to limit memory.
  - Background workers to keep the UI responsive while scanning.
- Output/export:
  - Derive safe filenames from source log + search term.
  - Optionally export only matched lines, or full conversations.

---

## Textual UI Plan

- Layout (initial):
  - Left: file list (filtered by log type).
  - Right (top): results pane (conversation list, with counts and preview of first match).
  - Right (bottom): details/preview of selected conversation with highlighting.
  - Footer: status, key hints, search mode indicators.
- Key bindings (initial set):
  - `q` quit, `/` search, `r` refresh, `f` toggle fuzzy, `g` toggle grouping on/off, `t` cycle log types.
- Interactions:
  - Select a file → start scan in a worker → stream results into the results pane.
  - Enter search → apply mode (text/regex/fuzzy) → incremental updates.
  - Sub-search applies over current result set.
- Highlighting: Rich markup rules per log type (IP, email, status codes, severity, IDs).

---

## Parsing and Correlation Keys

- SMTP (from script): correlation key appears to be the second bracketed token (`$4` with delimiter `[]`). We will validate this against real samples and adjust as needed.
- Other log types: define per-type regex to extract an ID (message/session/transaction). Document for each type and unit-test.
- Fallback: if no correlation key can be extracted, treat each line independently (no grouping).

Data model sketch:
- LogType: name, file_globs, id_extractor(line) -> str|None, highlight_rules.
- Conversation: id, first_offset/line_number, lines (streamed or referenced offsets), match_count.

---

## Implementation Phases

1. MVP parity with Bash (SMTP only):
   - Read plain and zipped SMTP logs.
   - Case-insensitive search; group by correlation ID; export conversations; newest-first file list.
2. Add sub-search and result table UI; add syntax highlighting for SMTP lines.
3. Introduce fuzzy and regex modes with thresholds/options; expose toggles in the footer.
4. Extend to additional log types with per-type parsers and highlighting.
5. Scale improvements: index/offset tracking, streaming previews, progress indicators.
6. Configuration file (paths, defaults, highlights) and packaging polish.

---

## Open Questions / Inputs Needed

- Enumerate all SmarterMail log types you want supported and their filename patterns.
- Confirm the correlation key extraction for each type (examples help).
- Acceptable temp directory for zipped logs (and any storage limits/policies).
- Desired defaults for search mode (text vs regex vs fuzzy) and thresholds.
- Export format preferences (full conversations vs matched lines only; JSON/text).

---

## References

- Existing Bash script behavior summarized above (AWK two-phase matching and grouping by first occurrence).
- Textual for TUI scaffolding; Rich for highlighting.
