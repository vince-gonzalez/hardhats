"""
hardHats lead: THE SECURITY LEAD (keyword `security`). The adversary axis - the member checks
that ask one question in different places: does a hostile or careless input get control, or get
data it should not? A committed secret, an eval/pickle/shell injection sink, an exploitable CI
workflow, a live endpoint missing its secure headers. Deterministic (zero model calls); it
composes its members, it never re-scans.

    python -m hardhats.crews security <file|dir|url> [--json] [--md out.md]

Members: crypteng, inject, ghactions, sec. Only the members whose signal is present on the target
run; the rest are listed, not counted as a pass. Exit 1 if any applicable member caught a defect,
2 if none applied or one could not run, 0 if all cleared.
"""
from __future__ import annotations

import sys

from hardhats.crews import _lead

MEMBERS = ("crypteng", "inject", "ghactions", "sec")


def review(target, log=print):
    rep, _ = _lead.compose("security", MEMBERS, target)
    if log:
        _lead.report(rep, log)
    return rep


def main():
    return _lead.main("security", MEMBERS, sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
