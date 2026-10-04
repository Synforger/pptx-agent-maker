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

## Telling a refactor from a change

Two more checks are run by hand before a pull request, because they answer what the tests cannot:

- `task snapshot:check` bakes the made-up project under `tests/corpus/` and compares every page's XML with what is kept in `tests/corpus/snapshot/`. A refactor leaves it identical, to the byte. A change that is meant to move a page is followed by `task snapshot`, and the pages it moved show in the pull request's diff.
- `task mutate -- tests/mutants/_example.toml` breaks the code the ways a table lists and expects the tests to go red each time. A mutant that stays green is something no test is watching; write the table for what you changed next to that one.

A new page type, part or look goes into the corpus in the same pull request — `tests/test_corpus.py` stays red until it does.

## Keeping private decks out of a push

Test with made-up decks. Text copied out of a real document is stopped machine-wide at push time by the guard every repository on the maintainer's machine goes through, so this repository carries no check of its own.
