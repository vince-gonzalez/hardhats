"""
hardHats lead: THE SAFETY LEAD (keyword `safety`). The will-it-harm-the-person axis - the member
checks that ask whether the work hurts or breaks the law against the human on the other end: a
photosensitive flash, an accessibility-conformance gap, an unlabelled allergen, a licence that
does not permit the use, and child or student data with no policy behind it. Deterministic (zero
model calls); it composes its members. `privacy` also surfaces a PII-exposure (security) signal.

    python -m hardhats.crews safety <file|dir|url> [--json] [--md out.md]

Members: seizure, vpat, food, license, privacy. (`vpat` lives in the a11yhat repo; run it there.)
Only the members whose signal is present on the target run; the rest are listed, not a pass. Exit
1 if any applicable member caught a defect, 2 if none applied or one could not run, 0 if all cleared.
"""
from __future__ import annotations

import sys

from hardhats.crews import _lead

MEMBERS = ("seizure", "vpat", "food", "license", "privacy")


def review(target, log=print):
    rep, _ = _lead.compose("safety", MEMBERS, target)
    if log:
        _lead.report(rep, log)
    return rep


def main():
    return _lead.main("safety", MEMBERS, sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
