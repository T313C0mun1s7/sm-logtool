# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `sm_logtool/`: `cli.py` powers the CLI and `ui/` hosts the Textual TUI. Tests stay in `test/`; keep new files runnable by both pytest and unittest. Use `sample_logs/` for fixtures, stage real logs before analysis, and park references in `docs/`.

## Build, Test, and Development Commands
Create a venv (`python -m venv .venv && source .venv/bin/activate`) and install with `python -m pip install -e .`. Add pytest if needed, run `pytest -q`, and mirror CI with `python -m unittest discover test`. Launch the TUI via `python -m sm_logtool.cli --logs-dir sample_logs` or aim it at your staging folder.

## Coding Style & Naming Conventions
Target Python 3.10+, follow PEP 8, and use four-space indentation. Stick to `lower_snake_case` for modules, functions, and variables, `CapWords` for classes, and `UPPER_SNAKE_CASE` for constants. Prefer type hints, rely on `pathlib.Path` for filesystem work, and keep docstrings concise.

## Testing Guidelines
Add cases under `test/test_*.py` with descriptive names. Lean on fixtures such as `tmp_path` to cover both success paths and expected failures. Keep tests discoverable by `python -m unittest discover test`, and run `pytest --cov=sm_logtool` locally if you add coverage tooling.

## Commit & Pull Request Guidelines
`main` is protected, so branch (`git checkout -b feature/log-filter`), push, and open a PR. Use present-tense subjects (`Add log filtering hook`), reference issues with `Closes #123`, and keep commits focused. PRs should summarize changes, note test results, and include screenshots or terminal captures for UI tweaks. Rebase before requesting review.

## Security & Configuration Tips
Treat SmarterMail logs as sensitive—redact personal data before sharing. Always work on staged copies, copying prior-day files once and refreshing today’s log before each search. Keep environment-specific config out of git, and document any operational caveats when changing filesystem behavior.

## Upcoming Work
- [ ] Expand the search pipeline to cover additional SmarterMail log kinds and grouping rules.
- [ ] Add syntax highlighting for SMTP conversations in CLI and TUI views.
- [ ] Introduce a YAML config file to store default log paths and other settings.
- [ ] Resize the TUI panels so kind/date lists match their content width while maximizing output space.
- [ ] Add a navigation legend plus keyboard/mouse multi-select (Tab cycling, Ctrl/Shift modifiers, Space toggle).
