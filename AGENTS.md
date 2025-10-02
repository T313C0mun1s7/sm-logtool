# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `sm_logtool/`: `cli.py` powers the CLI and `ui/` hosts the Textual TUI. Tests stay in `test/`; keep new files runnable by both pytest and unittest. Use `sample_logs/` for fixtures, stage real logs before analysis, and park references in `docs/`.

## Build, Test, and Development Commands
Create a venv (`python -m venv .venv && source .venv/bin/activate`) and install with `python -m pip install -e .`. Add pytest if needed, run `pytest -q`, and mirror CI with `python -m unittest discover test`. Launch the TUI via `python -m sm_logtool.cli --logs-dir sample_logs` or aim it at your staging folder.

## Coding Style & Naming Conventions
- Target Python 3.10+, follow PEP 8, and indent with four spaces.
- Use `snake_case` for modules, functions, and variables, `CapWords` for classes, and
  `UPPER_SNAKE_CASE` for constants.
- Keep lines at or below 79 characters unless there is a strong, documented reason
  to exceed that limit.
- Prefer type hints everywhere they add clarity, and use `pathlib.Path` for filesystem
  work.
- Provide concise docstrings for public modules, classes, functions, and methods in
  line with PEP 257.
- Avoid nesting `if` statements deeper than two levels; refactor with guard clauses,
  flattened conditionals, dispatch tables, or polymorphism instead.

## Engineering Discipline
- Write modular, focused code: apply the Single Responsibility Principle, keep
  functions short (aim for ≤20 lines), and group related behavior into classes instead
  of relying on globals.
- Embrace Pythonic readability: use list comprehensions and generators for sequence
  transforms, context managers for resource handling, and f-strings for formatting.
- Choose descriptive, intention-revealing names (e.g., `total_sales`) and avoid
  ambiguous identifiers such as `l`, `O`, or `I`.
- Handle errors deliberately: catch specific exceptions, log relevant context, and
  use `try`/`except`/`else`/`finally` blocks to manage alternate flows and cleanup.
- Test rigorously: add unit tests under `test/test_*.py`, cover edge cases, and run
  both `pytest -q` and `python -m unittest discover test` before sharing changes.
- Optimize when data demands it: pick the right data structures, profile before
  tuning, and reduce expensive I/O or function calls via caching when it helps.
- Stay pragmatic: treat these standards as tools for clarity and maintainability, and
  document any intentional deviations when they improve the overall design.

## Testing Guidelines
Add cases under `test/test_*.py` with descriptive names. Lean on fixtures such as `tmp_path` to cover both success paths and expected failures. Keep tests discoverable by `python -m unittest discover test`, and run `pytest --cov=sm_logtool` locally if you add coverage tooling.

## Commit & Pull Request Guidelines
`main` is protected, so branch (`git checkout -b feature/log-filter`), push, and open a PR. Use present-tense subjects (`Add log filtering hook`), reference issues with `Closes #123`, and keep commits focused. PRs should summarize changes, note test results, and include screenshots or terminal captures for UI tweaks. Rebase before requesting review.

## Workflow Safeguards
- After any change that modifies repository files, create a local git commit before
  handing control back to the user. This ensures every step is recoverable if an
  iteration goes sideways and prevents repeated mistake loops.
- Before making changes, confirm you are not on `main`. Switch to an appropriate
  feature branch so protected branches stay clean and reviewable.

## Security & Configuration Tips
Treat SmarterMail logs as sensitive—redact personal data before sharing. Always work on staged copies, copying prior-day files once and refreshing today’s log before each search. Keep environment-specific config out of git, and document any operational caveats when changing filesystem behavior.

## Upcoming Work
- [ ] Expand the search pipeline to cover additional SmarterMail log kinds and grouping rules.
- [ ] Add syntax highlighting for SMTP conversations in CLI and TUI views.
- [x] Introduce a YAML config file to store default log paths and other settings.
- [x] Replace the old multipane layout with the new wizard flow so list panels size appropriately while preserving output space.
- [x] Add a navigation legend plus keyboard/mouse multi-select (Tab cycling, Ctrl/Shift modifiers, Space toggle).


## Current State Notes
- Verify toggle-only date selection works smoothly (arrows + space, enter) with the new highlight styling.
- Confirm footer shortcuts (`Q` quit, `R` reset search, `/` focus search) display on every step and function even when the search input or results pane has focus.
- Make sure search results display one log line per row after recent changes.
