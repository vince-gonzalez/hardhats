"""
hardHats lead: THE CLAIMS LEAD (keyword `claims`). The falsifier axis - the member checks that
each take a claim and force it against a real measurement, then fail if the measurement refuses
the claim. A theorem against a kernel, a colour against the perceptual engine, a test suite
against a mutation, a load plan against the geometry. Deterministic (zero model calls); it
composes its members, it never re-measures.

    python -m hardhats.crews claims <file|dir|url> [--json] [--md out.md]

Members: proof, geom, vision, tests, ops, balance, perf, gameperf, resilient. Only the members
whose signal is present on the target run; the rest are listed, not counted as a pass. Exit 1 if
any applicable member caught a defect, 2 if none applied or one could not run, 0 if all cleared.
"""
from __future__ import annotations

import sys

from hardhats.crews import _lead

MEMBERS = ("proof", "geom", "vision", "tests", "ops", "balance", "perf", "gameperf", "resilient")


def review(target, log=print):
    rep, _ = _lead.compose("claims", MEMBERS, target)
    if log:
        _lead.report(rep, log)
    return rep


def main():
    return _lead.main("claims", MEMBERS, sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
