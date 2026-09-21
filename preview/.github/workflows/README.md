# GitHub Actions policy for this template

**Projects derived from `personal-template` consume GitHub Actions minutes
only for the anonymity check.** Everything else runs locally via
`task`.

The intent: AI assisted personal repos need a cheap, fast, local
feedback loop. CI is reserved for the one check that genuinely cannot
be enforced locally with the same trust level — namely, that no
personal identifier or prior-employer org name has slipped into the
public repo.

## What is enabled

(none — the anonymity scan is local-only by design; see below.)

That's it. No matrix tests, no release builds, no version bump
workflow. Those concerns belong to local `task` commands; see the
top-level `README.md` for the catalogue.

## Local replacements

| Concern             | Local replacement                                                  |
|---------------------|--------------------------------------------------------------------|
| Unit tests          | `task test:unit`                                                   |
| Integration tests   | `task test:integration`                                            |
| Lint + format       | `task lint` (black, flake8, anonymity scan)                        |
| Anonymity check     | dispatcher hooks (pre-commit / commit-msg / pre-push) + `task audit:deep` |
| Dependency updates  | manual `pip list --outdated` / `pnpm outdated` / equivalent        |
| Version bump        | derive a `task version:bump` per project when needed               |
| Release packaging   | derive a `task release:cut` per project when needed                |

## When to enable more workflows

Add workflows only when:

1. The check genuinely cannot run locally with the same trust (rare
   — anonymity is the canonical case because human review is bypassed
   for non-final-commit edits).
2. The Actions cost is bounded and predictable (e.g. seconds per run,
   not minutes per push on macOS runners).

For most cases the answer is "do it locally via `task` instead."

## Why the anonymity scan is local-only

The word list is private operator data and is never committed, so CI
has nothing meaningful to scan against — a CI job would either run
with an empty placeholder (always green, pure theatre) or require
publishing the very list the scan exists to protect.

Coverage that used to be claimed by CI is provided locally instead:

- fresh clones / pre-hook history: `task audit:deep` (full-history mode),
- `--no-verify` bypasses: the global dispatcher runs regardless of
  repo-local hook state,
- push boundaries: the pre-push dispatcher deep-scans the outgoing range.
