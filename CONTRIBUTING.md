# Contributing

Issues welcome — bug reports, feature requests, and technical-debt notes go to the templates under `.github/ISSUE_TEMPLATE/`.

Pull requests should be based on an existing issue; trivial fixes (typos, small doc tweaks) may be sent directly. Merge decisions rest with the repo owner.

By contributing you agree that your contribution is licensed under the terms in `LICENSE`.

## How changes are verified

This repository intentionally runs no CI — every quality gate (lint,
tests, docs freshness, audits) is local-first so the whole suite works
offline and in forks. For external pull requests the maintainer checks
out the branch and runs the full gate suite locally before merging, so
expect review comments quoting concrete gate output instead of a bot
status check. You can run the same gates yourself with `task --list`.

## Keeping private decks out of a push

Trying the toolkit on a real deck is how most of its defects were found, and it is also how a
value from that deck ends up in a test or an example. The anonymity guard checks names from a
list; a copied measurement is on no list.

`.githooks/pre-push` runs `.tooling/local-ci/private-corpus-check.py` on every commit a push is
about to send, and stops it when an added line or a commit message holds text or a value from
the decks named on this machine:

```
~/.config/private-corpus/sources.txt   one .pptx, or a folder of them, per line
~/.config/private-corpus/words.txt     extra words, one per line (optional)
~/.config/private-corpus/allow.txt     phrases that are fine (optional)
```

Nothing about those decks is written in this repository. A machine with no `sources.txt` is
told the check did not run, and the push goes on.
