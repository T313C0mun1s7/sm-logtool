**Syntax Highlighting**

Syntax highlighting now has separate but linked pieces:

1. Token spans: `sm_logtool/syntax.py`
2. CLI token styles: `sm_logtool/highlighting.py` (`TOKEN_STYLES`)
3. TUI UI themes and TUI syntax themes: `sm_logtool/ui/themes.py`

In the TUI, app theme changes (for example `Cyberdark` to `Cybernotdark`)
automatically switch the Results pane syntax theme via an app-theme-name map
with an explicit default fallback syntax theme via:
- `sm_logtool/ui/app.py` (`_watch_theme` -> `_sync_results_theme`)
- `sm_logtool/ui/themes.py` (`APP_THEME_TO_RESULTS_THEME`,
  `results_theme_for_app_theme`)

**Tokenizer Overview**

`sm_logtool/syntax.py` emits token spans for:
- timestamps
- bracketed fields (IPs, IDs, tags)
- emails and IPs in message text
- SMTP commands / responses
- message IDs
- status words (success/failure)
- protocol keywords at the start of a log message

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
- Add/update the corresponding style in `sm_logtool/ui/themes.py`
  (`RESULTS_THEME_DARK` / `RESULTS_THEME_LIGHT`) if TUI colors should differ.

**Adjusting Colors and Themes**

CLI/default colors live in `TOKEN_STYLES`:
- `sm_logtool/highlighting.py`

TUI colors are split:
- Widget/chrome colors come from Textual `Theme` values and custom variables
  in `sm_logtool/ui/themes.py`.
- Results syntax token colors come from TUI `TextAreaTheme` definitions in
  `sm_logtool/ui/themes.py`.

Important: Textual theme variables do not automatically style syntax tokens in
`TextAreaTheme`; they are related by app logic, not by automatic variable
binding.
