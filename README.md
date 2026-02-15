# sm-logtool

`sm-logtool` is a terminal-first log explorer for SmarterMail logs. It ships
with:

- A Textual wizard UI (`browse`) for interactive searching.
- A console search command (`search`) for quick scripted checks.
- Log staging that copies or unzips source logs before analysis.
- Conversation/entry grouping for supported SmarterMail log kinds.
- Syntax-highlighted results in both TUI and CLI output.
- Live progress, execution mode, and cancel support for long TUI searches.
- Parallel multi-target search with safe serial fallback when needed.

## Requirements

- Python 3.10+
- Linux (project classifiers currently target POSIX/Linux)

## Deployment Model

`sm-logtool` does not require installation on the same host as SmarterMail,
but it is designed for that workflow. In practice, you typically SSH to the
mail server and run searches there.

The tool stages logs into a separate working directory so the original
SmarterMail logs remain untouched during analysis and sub-searches.

## Install

Install from PyPI (recommended):

```bash
pipx install sm-logtool
```

Alternative with `pip`:

```bash
python -m pip install sm-logtool
```

This installs the `sm-logtool` command.

### Update

Update an existing install from PyPI:

```bash
pipx upgrade sm-logtool
# or
python -m pip install --upgrade sm-logtool
```

If you use the fuzzy-search speedup extra, update with extras:

```bash
pipx install --force "sm-logtool[speedups]"
# or
python -m pip install --upgrade "sm-logtool[speedups]"
```

### Recommended Speedups (Strongly Recommended)

For significantly better fuzzy-search performance, install with the optional
`speedups` extra:

```bash
pipx install "sm-logtool[speedups]"
# or
python -m pip install "sm-logtool[speedups]"
```

`sm-logtool` automatically uses the accelerator when available and
automatically falls back to the built-in matcher when it is not installed.
Skipping this extra can materially reduce fuzzy-search responsiveness and
overall usability on large logs.

## Configuration

Configuration is YAML with these keys:

- `logs_dir`: source SmarterMail logs directory.
- `staging_dir`: working directory used for copied/unzipped logs.
- `default_kind`: default log kind (for example `smtp`).
- `theme`: Textual UI theme name (for example `Cyberdark`,
  `Cybernotdark`, or `textual-dark`).
  Results syntax highlighting follows the selected UI theme palette and theme
  name.

Example:

```yaml
logs_dir: /var/lib/smartermail/Logs
staging_dir: /var/tmp/sm-logtool/logs
default_kind: smtp
theme: Cyberdark
```

If `staging_dir` does not exist yet, the app creates it automatically.

Config resolution order:

1. `--config /path/to/config.yaml`
2. `SM_LOGTOOL_CONFIG`
3. `~/.config/sm-logtool/config.yaml`

When the default path is used and the file does not exist, `sm-logtool`
creates it automatically with SmarterMail-oriented defaults.

## Usage

Top-level help:

```bash
sm-logtool --help
sm-logtool --version
```

### Launch the TUI

```bash
sm-logtool
# or
sm-logtool browse --logs-dir /var/lib/smartermail/Logs
```

Wizard flow:

1. Choose log kind.
2. Select one or more log dates.
3. Enter search term and choose search mode
   (`Literal`/`Wildcard`/`Regex`/`Fuzzy`).
4. Review results, copy selection/all, and optionally run sub-search.

Core actions are always visible in the top action strip:

- `Ctrl+Q` quit
- `Ctrl+R` reset search state
- `Ctrl+U` open command palette/menu

Search-step footer shortcuts:

- `Ctrl+F` focus search input
- `Ctrl+Left` previous search mode
- `Ctrl+Right` next search mode
- `Ctrl+Up` increase fuzzy threshold (fuzzy mode only)
- `Ctrl+Down` decrease fuzzy threshold (fuzzy mode only)

Date selection shortcuts:

- Arrow keys to move
- `Space` to toggle a date
- `Enter` to continue

### Run console search

```bash
sm-logtool search --kind smtp --date 2024.01.01 "example.com"
```

Minimum examples:

```bash
# Search newest log for default_kind from config.yaml (default: smtp)
sm-logtool search "somebody@example.net"

# Search newest delivery log
sm-logtool search --kind delivery "somebody@example.net"

# Wildcard mode: '*' any chars, '?' single char
sm-logtool search --mode wildcard "Login failed: User * not found"

# Regex mode: Python regular expression
sm-logtool search --mode regex "Login failed: User \\[(sales|billing)\\]"

# Fuzzy mode: approximate matching with configurable threshold
sm-logtool search --mode fuzzy --fuzzy-threshold 0.72 \
  "Authentcation faild for user [sales]"
```

Target resolution:

1. If `--log-file` is provided (repeatable), those files are searched.
2. Else if `--date` is provided (repeatable), those dates are searched.
3. Else the newest available log for `--kind` is searched.

Search options:

- `--logs-dir`: source logs directory. Optional when `logs_dir` is set in
  `config.yaml`.
- `--staging-dir`: staging directory. Optional when `staging_dir` is set in
  `config.yaml`.
- `--kind`: log kind. Optional when `default_kind` is set in `config.yaml`.
- `--date`: `YYYY.MM.DD` date to search. Repeat to search multiple dates.
- `--log-file`: explicit file to search. Repeat to search multiple files.
- `--list`: list available logs for the selected kind and exit.
- `--list-kinds`: list supported kinds and exit.
- `--mode`: search mode (`literal`, `wildcard`, `regex`, or `fuzzy`).
- `--fuzzy-threshold`: similarity threshold for `--mode fuzzy` from `0.00` to
  `1.00` (default `0.75`).
- `--case-sensitive`: disable default case-insensitive matching.

Search mode behavior:

- `literal`: exact substring matching (default).
- `wildcard`: `*` matches any sequence and `?` matches one character.
- `regex`: Python `re` syntax (PCRE-like, but not full PCRE).
- `fuzzy`: approximate line matching using a similarity threshold.
  Installing `sm-logtool[speedups]` is strongly recommended for this mode.

Regex checker note:

- If an online regex builder does not offer Python mode, use PCRE/PCRE2 and
  stick to common features; some PCRE-only constructs may not work.

## Supported Log Kinds

Search handlers currently exist for:

- `smtp`, `imap`, `pop`
- `delivery`
- `administrative`
- `imapretrieval`
- `activation`, `autocleanfolders`, `calendars`, `contentfilter`, `event`,
  `generalerrors`, `indexing`, `ldap`, `maintenance`, `profiler`,
  `spamchecks`, `webdav`

Log discovery expects SmarterMail-style names such as:
`YYYY.MM.DD-kind.log` or `YYYY.MM.DD-kind.log.zip`.

## Development

Run tests with both frameworks used in this repository:

```bash
pytest -q
python -m unittest discover test
```

## Additional Docs

- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Search Design Notes](docs/SEARCH_NOTES.md)
- [Syntax Highlighting Notes](docs/syntax_highlighting.md)

## License

This project is licensed under AGPL-3.0.
See [LICENSE](LICENSE).
