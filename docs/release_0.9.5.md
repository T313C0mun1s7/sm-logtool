# Release 0.9.5 Notes

## Included Issues

- #48 Create per-user theme directories automatically on first run.
- #49 Prevent sub-search results from flashing back to prior results.
- #51 Add selectable result display modes in CLI and TUI:
  `related` and `matching-only`.
- #54 Refine syntax highlighting to reduce false positives around
  `Blocked`/`Failed` while preserving true failure/block outcomes.

## Highlights

- Theme workflow is smoother on first launch because required per-user
  directories are created automatically.
- Sub-search result transitions are more stable in the TUI.
- Search output can now be switched between grouped related traffic and
  directly matching rows.
- Status highlighting is more context-aware for delivery and auth-related
  lines.

## Validation

- `pytest -q`
- `python -m unittest discover test`
- `python scripts/check_release_defaults.py`
