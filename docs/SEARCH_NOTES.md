# sm-logtool Search Notes

This file tracks current search behavior and near-term design goals.

## Current State

### Search semantics

- Search terms are plain substrings, not regex.
- Matching is case-insensitive by default.
- CLI supports `--case-sensitive` for exact-case matching.

### Supported log kinds

Search handlers currently exist for:

- `smtpLog`, `imapLog`, `popLog`
- `delivery`
- `administrative`
- `imapRetrieval`
- `activation`, `autoCleanFolders`, `calendars`, `contentFilter`, `event`,
  `generalErrors`, `indexing`, `ldapLog`, `maintenance`, `profiler`,
  `spamChecks`, `webdav`

### Discovery and staging

- Log discovery expects SmarterMail-style filenames:
  `YYYY.MM.DD-kind.log` and `YYYY.MM.DD-kind.log.zip`.
- Logs are sorted newest-first per kind.
- Search runs on staged copies so source logs stay untouched.
- `.zip` inputs are extracted to staging before search.
- Staging directories are created automatically if missing.

### Grouping and rendering

- SMTP/IMAP/POP, delivery, administrative, and imapRetrieval searches group
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
- CLI search output is plain formatted text (no syntax colorization yet).
- CLI does not provide interactive TUI workflows like sub-search chaining.

## Roadmap Items

- Add syntax-highlighted output for CLI search results.
- Bring CLI search/output behavior closer to TUI behavior where practical.
- Add regex search mode with explicit mode flags and clear UX.
- Add fuzzy/approximate search mode with configurable thresholds.
- Add support for additional compressed formats (for example `.gz`).
- Improve large-log performance and responsiveness (progress feedback,
  background work, reduced memory footprint).
- Add export controls (matched lines vs full conversations, optional
  structured output).

## Notes

- Historical bash behavior is useful context, but current product behavior is
  defined by the Python codebase and documented in `README.md`.
