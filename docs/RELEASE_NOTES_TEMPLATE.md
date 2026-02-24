# Release Notes Template

Use this template for all `sm-logtool` releases so published notes stay
consistent in structure and detail.

## Standard Format

```md
# sm-logtool vX.Y.Z

<1-2 sentence summary of what this release delivers and why it matters.>

## Highlights

- <Top user-visible change #1>
- <Top user-visible change #2>
- <Top user-visible change #3>

## Included Issues

- #<id> <short issue title>
- #<id> <short issue title>

## Included PRs

- #<id> <short PR title>
- #<id> <short PR title>

## Validation

- `pytest -q`
- `python -m unittest discover test`
- <any release-specific checks, if used>

All checks passed.

## Upgrade

```bash
pipx upgrade sm-logtool
# or
python -m pip install --upgrade sm-logtool
```

If this release changes optional speedups behavior:

```bash
pipx install --force "sm-logtool[speedups]"
# or
python -m pip install --upgrade "sm-logtool[speedups]"
```

## Full Changelog

https://github.com/T313C0mun1s7/sm-logtool/compare/vX.Y.(Z-1)...vX.Y.Z
```

## Writing Rules

- Keep `Highlights` focused on user-visible behavior.
- Keep issue and PR lists concise and complete for that release scope.
- Include exact validation commands that were actually run.
- Include upgrade commands in every release note.
- Add sections only when needed, for example:
  - `Breaking Changes`
  - `Known Limitations`
  - `Docs`
  - `Security`

## Process Notes

- Preferred: publish release notes in GitHub Release metadata.
- Do not commit ad-hoc `docs/release_*.md` files unless explicitly requested.
- If a repo-stored release note file is explicitly requested, name it
  `docs/release_X.Y.Z.md` and follow this template.
