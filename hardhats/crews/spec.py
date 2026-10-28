"""
hardHats crew: the Spec crew (keyword `spec`). A standards editor's read on a normative
document - is it actually normative, and is it consistent about it. Deterministic (zero
model calls), grounded in RFC 2119 / RFC 8174 (BCP 14): the requirement keywords and the
boilerplate that gives them force.

It reports the requirement counts, flags mixed-case keyword use (only the UPPERCASE forms
are normative per RFC 8174) and a missing BCP 14 reference, and lists subjective MUSTs that
a conformance test could not settle. It does not judge whether the requirements are correct
or complete - that is the author's and the reviewers' call.

    python -m hardhats.crews.spec <doc.md|path|-> [--md out.md]

Exit 1 if the document uses requirement keywords but is not normatively sound
(no BCP 14 reference, or mixed-case keywords).
"""
from __future__ import annotations

import re
import sys

STRONG = ["MUST NOT", "MUST", "SHALL NOT", "SHALL", "REQUIRED"]
SOFT = ["SHOULD NOT", "SHOULD", "RECOMMENDED"]
OPT = ["MAY", "OPTIONAL"]
ALL_KW = STRONG + SOFT + OPT

# RFC 8174: lowercase forms are NOT normative. Flag a lowercase keyword used as a verb,
# which reads normative but carries no force - the ambiguity RFC 8174 exists to kill.
LOWER_RE = re.compile(r"(?<![A-Za-z])(must not|must|shall not|shall|should not|should|"
                      r"may)\s+(?:be|not|have|use|include|support|provide|return|contain)\b")
SUBJECTIVE = re.compile(r"(?i)\b(MUST|SHALL|REQUIRED)\b[^.\n]{0,40}\b(appropriate|reasonable|"
                        r"robust|secure|efficient|user[- ]friendly|as needed|where possible|"
                        r"sufficient|adequate|good|best)\b")
BCP14 = re.compile(r"(?i)\b(RFC\s?2119|RFC\s?8174|BCP\s?14)\b")


def _count(text, phrases):
    n = 0
    for p in phrases:
        n += len(re.findall(r"(?<![A-Za-z])" + re.escape(p) + r"(?![A-Za-z])", text))
    return n


def review(text, log=print):
    strong = _count(text, STRONG)
    soft = _count(text, SOFT)
    opt = _count(text, OPT)
    total = strong + soft + opt
    has_bcp14 = bool(BCP14.search(text))
    lower_hits = sorted({" ".join(m.group(0).split())[:50] for m in LOWER_RE.finditer(text)})
    subjective = sorted({" ".join(m.group(0).split())[:60] for m in SUBJECTIVE.finditer(text)})

    normative = total > 0
    unsound = normative and (not has_bcp14 or lower_hits)
    verdict = ("NOT NORMATIVE (no requirement keywords)" if not normative else
               "AMBIGUOUS" if unsound else
               "NORMATIVE AND CONSISTENT")
    if log:
        print("THE SPEC CREW - standards-editor read, grounded in RFC 2119 / 8174 (zero model calls)")
        print("--- requirements (facts) ---")
        print("  strong (MUST / SHALL / REQUIRED): %d   soft (SHOULD / RECOMMENDED): %d   "
              "optional (MAY / OPTIONAL): %d" % (strong, soft, opt))
        if not normative:
            print("  [FLAG] no RFC 2119 requirement keywords - this document states nothing normative")
        print("\n--- consistency ---")
        if normative and has_bcp14:
            print("  [ok]   cites RFC 2119 / 8174 / BCP 14 (the keywords have defined force)")
        elif normative:
            print("  [FLAG] uses requirement keywords but never cites BCP 14 - the keywords have no defined meaning")
        if lower_hits:
            print("  [FLAG] lowercase keywords used normatively (RFC 8174: only UPPERCASE is normative):")
            for h in lower_hits[:10]:
                print("     - %r" % h)
        elif normative:
            print("  [ok]   no lowercase keyword used where a normative one was meant")
        print("\n--- testability ---")
        if subjective:
            print("  [flag] subjective MUST/SHALL (a conformance test cannot settle these):")
            for s in subjective[:10]:
                print("     - %r" % s)
        else:
            print("  [ok]   no obviously subjective MUST found")
        print("\n--- not checked (and not a pass) ---")
        print("  - whether each requirement is CORRECT, complete, or free of conflicts")
        print("  - whether two requirements contradict each other")
        print("  - that every MUST has a matching conformance test")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Editorial soundness only. Whether the spec is RIGHT is the author's and reviewers' call.")
    return {"verdict": verdict, "strong": strong, "soft": soft, "opt": opt,
            "has_bcp14": has_bcp14, "lower": lower_hits, "subjective": subjective}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print(__doc__.strip())
        return 2
    src = pos[0]
    try:
        if src == "-":
            text = sys.stdin.read()
        else:
            import os
            if not os.path.isfile(src):
                print("spec: no such file: %s" % src, file=sys.stderr)
                return 2
            text = open(src, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print("spec: could not read %s (%s)" % (src, e), file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(text, log=None)
        return _emit.emit("spec", rep, 1 if rep["verdict"] == "AMBIGUOUS" else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(text, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(text)
    return 1 if rep["verdict"] == "AMBIGUOUS" else 0


if __name__ == "__main__":
    sys.exit(main())
