"""
hardHats lead: THE CONTRACT LEAD (keyword `contract`). The declared-structure axis - the member
checks that each ask whether a thing that declares a shape actually carries every required part,
consistently: an API spec, a database schema, a normative document's keywords, a locale's key
parity, a page's structured-data and card fields, a worker's bindings, a methods section's
required elements. Presence and consistency, not opinion. Deterministic (zero model calls).

    python -m hardhats.crews contract <file|dir|url> [--json] [--md out.md]

Members: api, schema, spec, i18n, richdata, og, env, method. Only the members whose signal is
present on the target run; the rest are listed, not counted as a pass. Exit 1 if any applicable
member caught a defect, 2 if none applied or one could not run, 0 if all cleared.
"""
from __future__ import annotations

import sys

from hardhats.crews import _lead

MEMBERS = ("api", "schema", "spec", "i18n", "richdata", "og", "env", "method")


def review(target, log=print):
    rep, _ = _lead.compose("contract", MEMBERS, target)
    if log:
        _lead.report(rep, log)
    return rep


def main():
    return _lead.main("contract", MEMBERS, sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
