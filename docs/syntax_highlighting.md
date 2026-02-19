**Syntax Highlighting**

Syntax highlighting now has separate but linked pieces:

1. Token spans: `sm_logtool/syntax.py`
2. CLI token styles: `sm_logtool/highlighting.py` (`TOKEN_STYLES`)
3. TUI UI themes and TUI syntax themes: `sm_logtool/ui/themes.py`

In the TUI, app theme changes (for example `Cyberdark` to `dracula`)
automatically switch the Results pane syntax theme to the same name.
This includes Textual's shipping themes and the project's first-party themes.
Converted themes saved by `sm-logtool themes` also work the same way.
`sm-logtool browse` auto-loads saved converted themes from the app theme store
directory (`~/.config/sm-logtool/themes` by default).
The Results syntax theme is built from the active Textual UI theme palette:
- `sm_logtool/ui/app.py` (`_watch_theme` -> `_sync_results_theme`)
- `sm_logtool/ui/themes.py` (`build_results_theme`,
  `results_theme_name_for_app_theme`)

If a selected theme cannot be resolved for any reason, the TUI falls back to a
default results syntax theme (`smlog-default`).

**Tokenizer Overview**

`sm_logtool/syntax.py` emits token spans for:
- timestamps
- bracketed fields (IPs, IDs, tags)
- emails and IPs in message text
- SMTP commands / responses
- message IDs
- status words (success/failure)
- protocol keywords at the start of a log message

SMTP response-code guard:
- Response codes are highlighted only when they appear in an `rsp:` payload.
- Numeric values in timestamp/prefix columns are not treated as response
  codes.

Protocol keywords are matched against a single list:
`SMTP`, `IMAP`, `POP`, `USER`, `WEBMAIL`, `ACTIVESYNC`, `EAS`,
`CALDAV`, `CARDDAV`, `XMPP`, `API`.

If a log line starts with one of these words after the time/bracket fields,
the keyword is tagged and styled so each protocol has a distinct color.

**Adjusting Tokens**

Update the regexes or token lists in:
- `sm_logtool/syntax.py`

For example, to add a new protocol keyword:
- Add it to `_PROTOCOL_TOKENS` in `sm_logtool/syntax.py`.
- Add a style entry for its token in `TOKEN_STYLES` in
  `sm_logtool/highlighting.py` (CLI/default).
- Update palette mapping logic in `sm_logtool/ui/themes.py` if needed for TUI.

**Adjusting Colors and Themes**

CLI/default colors live in `TOKEN_STYLES`:
- `sm_logtool/highlighting.py`

TUI colors are split:
- Widget/chrome colors come from Textual `Theme` values and custom variables
  in `sm_logtool/ui/themes.py`.
- Results syntax token colors are generated from the active Textual theme
  palette in `sm_logtool/ui/themes.py`.
- Source terminal themes are mapped to Textual semantic colors in
  `sm_logtool/ui/theme_importer.py` (used by `sm_logtool/ui/theme_studio.py`)
  with profile-driven heuristics and optional ANSI-256 quantization.
- Selection-state theme variables are normalized before save so selected,
  active, and selected+active rows remain visually distinct.
