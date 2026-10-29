"""
hardHats lead: THE REACH LEAD (keyword `reach`). The can-a-real-person-get-to-it axis - the member
checks that ask whether the path to the work is real and findable: an indexable page, deliverable
email auth, links that resolve, reach that is humans and not bots, an installable PWA, and campaign
links that can actually be attributed. Deterministic (zero model calls); it composes its members.

    python -m hardhats.crews reach <file|dir|url> [--json] [--md out.md]

Members: seo, deliverability, links, traffic, pwa, attribution. `attribution` also catches PII in
a tracked link - a security signal surfaced here. Only the members whose signal is present on the
target run; the rest are listed, not a pass. Exit 1 if any applicable member caught a defect, 2 if
none applied or one could not run, 0 if all cleared.
"""
from __future__ import annotations

import sys

from hardhats.crews import _lead

MEMBERS = ("seo", "deliverability", "links", "traffic", "pwa", "attribution")


def review(target, log=print):
    rep, _ = _lead.compose("reach", MEMBERS, target)
    if log:
        _lead.report(rep, log)
    return rep


def main():
    return _lead.main("reach", MEMBERS, sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
