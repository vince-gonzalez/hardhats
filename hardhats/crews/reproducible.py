"""
hardHats lead: THE REPRODUCIBLE LEAD (keyword `reproducible`). The will-it-run-again axis - the
member checks that ask whether someone else, later, gets the same thing: dependencies pinned
rather than floating, a re-run checklist that names the steps and the environment, and archival
fixity plus open formats so the bits survive. Deterministic (zero model calls); it composes.

    python -m hardhats.crews reproducible <file|dir|url> [--json] [--md out.md]

Members: deps, repro, archive. Only the members whose signal is present on the target run; the
rest are listed, not counted as a pass. Exit 1 if any applicable member caught a defect, 2 if none
applied or one could not run, 0 if all cleared.
"""
from __future__ import annotations

import sys

from hardhats.crews import _lead

MEMBERS = ("deps", "repro", "archive")


def review(target, log=print):
    rep, _ = _lead.compose("reproducible", MEMBERS, target)
    if log:
        _lead.report(rep, log)
    return rep


def main():
    return _lead.main("reproducible", MEMBERS, sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
