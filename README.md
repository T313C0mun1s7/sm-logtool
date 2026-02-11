# sm-logtool

`sm-logtool` is a terminal-first log explorer for SmarterMail logs. It ships
with:

- A Textual wizard UI (`browse`) for interactive searching.
- A console search command (`search`) for quick scripted checks.
- Log staging that copies or unzips source logs before analysis.
- Conversation/entry grouping for supported SmarterMail log kinds.
- Syntax-highlighted results in both TUI and CLI output.

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

Install from this repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

This installs the `sm-logtool` command and allows `python -m sm_logtool.cli`.

## Configuration

Configuration is YAML with these keys:

- `logs_dir`: source SmarterMail logs directory.
- `staging_dir`: working directory used for copied/unzipped logs.
- `default_kind`: default log kind (for example `smtp`).

Example:

```yaml
logs_dir: /var/lib/smartermail/Logs
staging_dir: /var/tmp/sm-tool/logs
default_kind: smtp
```

If `staging_dir` does not exist yet, the app creates it automatically.

Config resolution order:

1. `--config /path/to/config.yaml`
2. `SM_LOGTOOL_CONFIG`
3. Repository `config.yaml`

## Usage

Top-level help:

```bash
sm-logtool --help
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
3. Enter search term.
4. Review results, copy selection/all, and optionally run sub-search.

Global shortcuts shown in the footer:

- `Ctrl+Q` quit
- `Ctrl+R` reset search state
- `Ctrl+F` focus search input (when search step is active)
- `Ctrl+U` open command palette/menu

Date selection shortcuts:

- Arrow keys to move
- `Space` to toggle a date
- `Enter` to continue

### Run console search

```bash
sm-logtool search --kind smtp --date 2024.01.01 "example.com"
```

Useful options:

- `--list` list available logs for a kind and exit
- `--log-file` target one explicit file
- `--case-sensitive` disable default case-insensitive matching
- `--staging-dir` override staging directory for this run

Search terms are literal substrings (regex/fuzzy modes are not enabled in the
current CLI/TUI search path).

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
