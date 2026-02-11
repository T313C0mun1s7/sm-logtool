**Syntax Highlighting**

The results pane uses a read-only `TextArea` with a single SMlog tokenizer.
Highlighting is driven by two pieces:

1. Token spans: `sm_logtool/syntax.py`
2. Token styles: `sm_logtool/highlighting.py` (`TOKEN_STYLES`)

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
  `sm_logtool/highlighting.py`.

**Adjusting Colors**

Colors live in `TOKEN_STYLES`:
- `sm_logtool/highlighting.py`

Each token name maps to a Rich `Style`, so you can change colors,
bolding, or other attributes without touching the tokenizer.
