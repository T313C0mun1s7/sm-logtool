# sm-logtool Search Notes

This file tracks current search behavior and near-term design goals.

## Current State

### Search semantics

- Search terms are plain substrings, not regex.
- Matching is case-insensitive by default.
- CLI supports `--case-sensitive` for exact-case matching.

### Supported log kinds

Search handlers currently exist for:

- `smtp`, `imap`, `pop`
- `delivery`
- `administrative`
- `imapretrieval`
- `activation`, `autocleanfolders`, `calendars`, `contentfilter`, `event`,
  `generalerrors`, `indexing`, `ldap`, `maintenance`, `profiler`,
  `spamchecks`, `webdav`

### Discovery and staging

- Log discovery expects SmarterMail-style filenames:
  `YYYY.MM.DD-kind.log` and `YYYY.MM.DD-kind.log.zip`.
- Logs are sorted newest-first per kind.
- Search runs on staged copies so source logs stay untouched.
- `.zip` inputs are extracted to staging before search.
- Staging directories are created automatically if missing.

### Grouping and rendering

- SMTP/IMAP/POP, delivery, administrative, and imapretrieval searches group
  related lines into conversations/entries by parsed identifiers.
- Ungrouped kinds are grouped by timestamp-led entry boundaries so multiline
  entries stay together.
- Results are displayed in first-occurrence order.
- Aligned output formatting is applied per kind.

### TUI behavior

- Wizard flow: log kind -> date selection -> search -> results.
- Date selection supports keyboard and mouse toggling.
- Sub-search chains are supported from results.
- Results pane has syntax highlighting across supported log kinds.
- Copy selection and copy-all actions are available from results.

### CLI behavior

- `search` and `browse` subcommands exist.
- CLI search output uses the same syntax highlighting tokens as the TUI.
- CLI does not provide interactive TUI workflows like sub-search chaining.

## Roadmap Items

- [x] Bring CLI search/output behavior closer to TUI behavior where practical.
- [ ] Add regex search mode with explicit mode flags and clear UX.
- [ ] Add wildcard search mode with `*` and `?` support in CLI/TUI.
- [ ] Add fuzzy/approximate search mode with configurable thresholds.
- [ ] Add explicit search mode switching plus clear CLI/TUI help text.
- [x] Add support for additional compressed formats (for example `.gz`)
  [Issue #20 closed as not planned; reopen if needed].
- [ ] Improve large-log performance and responsiveness (progress feedback,
  background work, reduced memory footprint).
- [x] Add export controls (matched lines vs full conversations, optional
  structured output) [Issue #23 closed as not planned; reopen if needed].

## Notes

- Historical bash behavior is useful context, but current product behavior is
  defined by the Python codebase and documented in `README.md`.
