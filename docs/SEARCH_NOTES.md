# sm-logtool Search Notes

This file tracks current search behavior and implementation notes.

## Current State

### Search semantics

- Search modes:
  - `literal`: plain substring matching (default).
  - `wildcard`: supports `*` (any sequence) and `?` (single character).
  - `regex`: Python `re` syntax (PCRE-like, not full PCRE).
  - `fuzzy`: approximate matching using a configurable similarity threshold.
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
- Runtime config is per-user (`~/.config/sm-logtool/config.yaml`); use
  `config.example.yaml` as a local bootstrap template.

### Grouping and rendering

- SMTP/IMAP/POP, delivery, administrative, and imapretrieval searches group
  related lines into conversations/entries by parsed identifiers.
- Ungrouped kinds are grouped by timestamp-led entry boundaries so multiline
  entries stay together.
- Results are displayed in first-occurrence order.
- Aligned output formatting is applied per kind.

### Performance and responsiveness

- TUI searches run in a background worker so the UI remains responsive.
- Search can be canceled from the search/results workflow.
- Progress UI includes:
  - percent complete,
  - an inline progress bar,
  - current phase/detail text,
  - execution mode notes (serial/parallel/fallback),
  - live match preview while active targets are scanning.
- Search results stream into the results view as completed targets return.
- Multi-target search uses planned execution:
  - serial for small/single-target workloads,
  - parallel when workload/target count justify it,
  - thread pool first, then process pool fallback, then serial fallback.
- Search indexing is reused where available and warmed in the background after
  search completion.
- Fuzzy matching prefers RapidFuzz when installed (`sm-logtool[speedups]`),
  with built-in fallback when unavailable.

### TUI behavior

- Wizard flow: log kind -> date selection -> search -> results.
- Date selection supports keyboard and mouse toggling.
- Search step includes explicit mode switching
  (`Literal`/`Wildcard`/`Regex`/`Fuzzy`).
- Search step includes explicit result-mode switching
  (`Show all related traffic`/`Only matching rows`).
- Fuzzy mode threshold can be adjusted in TUI with `Ctrl+Up`/`Ctrl+Down`.
- Sub-search chains are supported from results.
- Results pane has syntax highlighting across supported log kinds.
- Copy selection and copy-all actions are available from results, including
  right-click context actions.
- Clipboard transfer uses terminal OSC 52 protocol; behavior depends on
  terminal/multiplexer support in the active session.

### Theme behavior

- `sm-logtool browse` auto-loads saved converted themes from
  `~/.config/sm-logtool/themes` (per-user).
- Theme Studio imports source files from
  `~/.config/sm-logtool/theme-sources` by default (per-user).
- These directories are created automatically on first run of
  `sm-logtool browse` or `sm-logtool themes`.
- Theme Studio supports live semantic remapping against preview elements.
- Saved themes preserve both app chrome and syntax palette behavior.
- Selection-state colors are forced distinct before save so date-selection
  rows remain functional in ANSI-256 terminals.

### CLI behavior

- `search` and `browse` subcommands exist.
- `search` supports explicit `--mode` selection
  (`literal`/`wildcard`/`regex`/`fuzzy`).
- `search` supports `--fuzzy-threshold` to tune fuzzy matching sensitivity.
- `search` supports `--result-mode`
  (`related`/`matching-only`).
- CLI search output uses the same syntax tokenization model as the TUI.
- CLI does not provide interactive TUI workflows like sub-search chaining.

## Completed Milestones

- [x] Bring CLI search/output behavior closer to TUI behavior where practical.
- [x] Add regex search mode with explicit mode flags and clear UX.
- [x] Add wildcard search mode with `*` and `?` support in CLI/TUI.
- [x] Add fuzzy/approximate search mode with configurable thresholds.
- [x] Add explicit search mode switching plus clear CLI/TUI help text.
- [x] Improve large-log performance and responsiveness (progress feedback,
  background work, reduced memory footprint, index reuse).

## Audit Backlog (2026-02-26)

Cross-project tracking items from the standards audit:

- [ ] [Issue #61](https://github.com/T313C0mun1s7/sm-logtool/issues/61):
  ensure unittest discovery runs the real test suite.
- [ ] [Issue #62](https://github.com/T313C0mun1s7/sm-logtool/issues/62):
  refactor `sm_logtool/ui/app.py` into smaller units and reduce nesting.
- [ ] [Issue #63](https://github.com/T313C0mun1s7/sm-logtool/issues/63):
  refactor CLI parser/search orchestration for maintainability.
- [ ] [Issue #64](https://github.com/T313C0mun1s7/sm-logtool/issues/64):
  close public API docstring gaps and add enforcement.
- [ ] [Issue #65](https://github.com/T313C0mun1s7/sm-logtool/issues/65):
  enforce the 79-character line-length policy.
- [ ] [Issue #66](https://github.com/T313C0mun1s7/sm-logtool/issues/66):
  remove tracked environment-specific config and document sample config
  workflow.

Search-focused optimization and structure items:

- [ ] [Issue #67](https://github.com/T313C0mun1s7/sm-logtool/issues/67):
  optimize live search preview rendering to reduce redraw churn.
- [ ] [Issue #68](https://github.com/T313C0mun1s7/sm-logtool/issues/68):
  deduplicate ungrouped log-kind mapping across modules.
- [ ] [Issue #69](https://github.com/T313C0mun1s7/sm-logtool/issues/69):
  move pytest tooling out of runtime dependencies.
- [ ] [Issue #70](https://github.com/T313C0mun1s7/sm-logtool/issues/70):
  add standards-compliance checks to CI.

## Notes

- Historical bash behavior is useful context, but current product behavior is
  defined by the Python codebase and documented in `README.md`.
- For repeatable performance checks, run `scripts/benchmark_search.py` against
  staged real logs and capture wall-clock time, peak RSS, and first-result
  timing across search modes.
