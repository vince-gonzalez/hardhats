"""
Shared engine for the six crew-lead seats (claims, security, contract, reproducible, reach,
safety). A lead is a FOREMAN, not a gate: it points the Router's classifier at the target, keeps
only the member checks that belong to it, runs each through the real dispatcher, and composes ONE
verdict - including the members it did NOT run, because that "not checked" surface is the whole
honesty of the bench and a lead must aggregate it, never bury it.

A lead adds no checking logic of its own. Every verdict is a member seat's; this only composes
them. Starts with "_" so the keyword dispatcher skips it - machinery, not a summonable seat.
"""
from __future__ import annotations

import io
import os
import re
import sys

from hardhats.crews import route, _emit

URL = re.compile(r"^https?://", re.I)


def compose(lead, members, target):
    """Run the lead's applicable members on the target; return (report dict, exit code)."""
    routes, kind = route.classify(target)
    mine = [(kw, a) for (kw, a) in routes if kw in members]
    ran = [route.run_seat(kw, a) for (kw, a) in mine]
    ran_kw = {e.get("seat") for e in ran}
    failed = [e for e in ran if e.get("exit") == 1]
    broke = [e for e in ran if e.get("exit") == 2]
    cleared = [e for e in ran if e.get("exit") == 0]
    not_run = [m for m in members if m not in ran_kw]      # no signal for them on this target
    code = route._overall(ran)
    if not ran:
        verdict = "NOTHING APPLIED - no %s member had a signal on this target" % lead
    elif failed:
        verdict = "%s DEFECT - %d of %d applicable check(s) failed" % (lead.upper(), len(failed), len(ran))
    elif broke:
        verdict = "%s INCOMPLETE - %d applicable check(s) could not run" % (lead.upper(), len(broke))
    else:
        verdict = "%s CLEAR - %d applicable check(s) passed" % (lead.upper(), len(cleared))
    rep = {"verdict": verdict, "lead": lead, "target": target, "kind": kind,
           "members": list(members), "failed": failed, "broke": broke, "cleared": cleared,
           "not_run": not_run, "ran": ran}
    return rep, code


def report(rep, log):
    """The human report. Mirrors a seat's shape: what applied, what did NOT, then the verdict."""
    lead = rep["lead"]
    log("THE %s LEAD - composes its member checks into one verdict (zero model calls)" % lead.upper())
    log("Target: %s   (%s)   members run: %d of %d\n" % (
        rep["target"], rep["kind"], len(rep["ran"]), len(rep["members"])))
    log("--- the checks that applied ---")
    if rep["ran"]:
        for e in rep["ran"]:
            tag = "[FAIL]" if e.get("exit") == 1 else ("[ok]  " if e.get("exit") == 0 else "[????]")
            log("  %s %-11s %s" % (tag, e.get("seat"), e.get("verdict")))
    else:
        log("  (none - no member's signal was present on this target)")
    log("\n--- not checked here (and NOT a pass) ---")
    if rep["not_run"]:
        for m in rep["not_run"]:
            log("  - %-11s no signal on this target; run `hardhats %s <its input>` to check it directly" % (m, m))
    else:
        log("  - every member of this lead had a signal and was run")
    log("\n== VERDICT: %s ==" % rep["verdict"])
    log("   A lead composes; it never re-measures. Each verdict above is the member seat's own.")


def main(lead, members, argv):
    md_out = argv[argv.index("--md") + 1] if "--md" in argv else None
    pos = [a for a in argv if not a.startswith("--") and a != md_out]
    if not pos:
        print("%s: give a file, directory, or URL to inspect" % lead, file=sys.stderr)
        return 2
    target = pos[0]
    if not (os.path.exists(target) or URL.match(target)):
        print("%s: no such path or url: %s" % (lead, target), file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    rep, code = compose(lead, members, target)
    if "--json" in argv:
        return _emit.emit(lead, rep, code)
    if md_out:
        buf = io.StringIO()
        report(rep, lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
        return code
    report(rep, print)
    return code
