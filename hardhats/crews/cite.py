"""
hardHats crew: the Cite crew (keyword `cite`). A reference editor's check - are the citations in a
document REAL: does each resolve, does the record match the words of the reference, and is any of
them retracted. It does NOT roll its own resolver. It DELEGATES to `authorecon` (reference_check),
which parses a reference list and verifies each against Crossref / DataCite / OpenAlex / PubMed /
arXiv, catching not just dead DOIs but FABRICATED references a bare resolver would wave through.

    python -m hardhats.crews.cite <doc|path|-> [--json] [--md out.md]

Uses the network (authorecon does). Without authorecon the seat reports NO ENGINE and refuses.
Exit 1 if any reference is retracted, unlocatable, or resolves to a different work; 2 if authorecon
is absent.
"""
from __future__ import annotations

import sys

try:
    from authorecon import reference_check as _rc
    _HAVE = True
except ImportError:
    _rc = None
    _HAVE = False


def _read(src):
    return sys.stdin.read() if src == "-" else open(src, encoding="utf-8", errors="replace").read()


def review(src, log=print):
    if not _HAVE:
        if log:
            print("THE CITE CREW - reference verification via authorecon")
            print("\n  [FAIL] authorecon is not installed - this seat will not vouch for citations without it.")
            print("         pip install authorecon   (reference_check: resolve, record-match, retraction)")
            print("  \U0001f6d1 'the DOIs look fine' is not a pass - a fabricated reference resolves to nothing.")
            print("\n== VERDICT: NO ENGINE ==")
        return {"verdict": "NO ENGINE", "references": 0, "rows": []}
    rows = _rc.run(_read(src), log=lambda *a: None)
    retracted = [r for r in rows if r.get("state") == _rc.RETRACTED]
    missing = [r for r in rows if r.get("state") in (_rc.UNLOCATABLE, _rc.DIVERGENT)]
    flagged = [r for r in rows if r.get("state") == _rc.REVIEW]
    unchecked = [r for r in rows if r.get("state") == _rc.UNCHECKED]
    verdict = ("NO REFERENCES FOUND" if not rows else
               "RETRACTION PRESENT" if retracted else
               "UNLOCATABLE OR WRONG-WORK CITATIONS" if missing else
               "UNVERIFIED (no index answered)" if unchecked and len(unchecked) == len(rows) else
               "VERIFIED")
    if log:
        print("THE CITE CREW - reference verification via authorecon.reference_check (uses the network)")
        print("Source: %s\n" % src)
        print("--- %d reference(s) ---" % len(rows))
        marks = {_rc.CONFIRMED: "ok  ", _rc.LOCATED: "ok  ", _rc.RETRACTED: "RETR",
                 _rc.UNLOCATABLE: "GONE", _rc.DIVERGENT: "WRONG", _rc.REVIEW: "chk ",
                 _rc.UNCHECKED: "????"}
        for r in rows:
            print("  [%-5s] %s" % (marks.get(r.get("state"), str(r.get("state"))[:5]),
                                   (r.get("ref") or "")[:70]))
            if r.get("says"):
                print("          %s" % r["says"][:96])
        print("\n--- not checked (and not a pass) ---")
        print("  - whether a citation SUPPORTS the claim it is attached to (that is the author's)")
        print("  - a retraction an index has not yet ingested; a clean result is evidence, not proof")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Resolution, record-match and retraction are authorecon's; relevance is the author's.")
    return {"verdict": verdict, "references": len(rows), "retracted": retracted,
            "missing": missing, "flagged": flagged, "rows": rows}


def _exit_code(verdict):
    if verdict == "NO ENGINE":
        return 2
    if verdict in ("RETRACTION PRESENT", "UNLOCATABLE OR WRONG-WORK CITATIONS"):
        return 1
    return 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print(__doc__.strip())
        return 2
    import os
    if pos[0] != "-" and not os.path.isfile(pos[0]):
        print("cite: no such file: %s" % pos[0], file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(pos[0], log=None)
        return _emit.emit("cite", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(pos[0], log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(pos[0])
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
