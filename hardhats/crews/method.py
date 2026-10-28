"""
hardHats crew: the Method crew (keyword `method`). A methodologist / biostatistician's read on
a methods section: does it REPORT the things a referee checks for before believing a result?
Deterministic (zero model calls); CONSORT + OSF pre-registration grounded.

This is a PRESENCE check, not a soundness judgement. It can tell you the paper never mentions a
power analysis, or reports p-values with no effect size, or runs many tests with no correction -
the omissions a reviewer flags on sight. It CANNOT tell you the analysis was done correctly; that
is the referee's / a statistician's job. Pairs with `review` (peer review) and `repro` (re-run).

    python -m hardhats.crews.method <methods.txt|.md|.html> [--md out.md]

Exit 1 if a blocking item (power justification, effect size w/ p-values, multiple-comparison
handling when many tests appear) is missing from an inferential paper.
"""
from __future__ import annotations

import os
import re
import sys

TAG = re.compile(r"<[^>]+>")
PVAL = re.compile(r"\bp\s*[<=>]\s*0?\.\d|\bp[\- ]values?\b", re.I)
PATS = {
    "power": re.compile(r"power analys|statistical power|sample[- ]size (?:calc|justif|determin)|"
                        r"a[\- ]priori|g\*?power|powered to detect|minimum detectable", re.I),
    "effect": re.compile(r"effect size|confidence interval|\b95\s*%?\s*ci\b|cohen'?s|\bodds ratio\b|"
                         r"\bhedges|\beta[- ]squared|\bη2|\bpartial eta|\bcliff'?s", re.I),
    "mcorr": re.compile(r"bonferroni|holm|false discovery|\bfdr\b|family[- ]?wise|tukey|"
                        r"corrected for multiple|benjamini", re.I),
    "random": re.compile(r"randomi[sz]|random(?:ly)? assign|random allocation", re.I),
    "blind": re.compile(r"\bblind(?:ed|ing)?\b|\bmasked\b|double[- ]blind|single[- ]blind", re.I),
    "prereg": re.compile(r"pre[- ]?regist|osf\.io|aspredicted|clinicaltrials\.gov|registered report|"
                         r"registration number", re.I),
    "avail": re.compile(r"data (?:are|is|will be) available|data availability|openly available|"
                        r"github\.com|osf\.io|zenodo|\brepositor|code (?:is )?available|materials available", re.I),
    "exclude": re.compile(r"exclud|\boutlier|stopping rule|stopped (?:data )?collect|"
                          r"inclusion criteria|drop(?:ped|out)", re.I),
}
# Blocking only in an inferential paper (one that reports p-values / tests)
BLOCKING = ("power", "effect")
LABELS = {
    "power": "sample-size / power justification",
    "effect": "effect size or confidence interval (not p-values alone)",
    "mcorr": "multiple-comparison correction",
    "random": "randomisation / random assignment",
    "blind": "blinding / masking",
    "prereg": "pre-registration (OSF / AsPredicted / registry)",
    "avail": "data / code availability",
    "exclude": "exclusions / stopping rule stated",
}


def review(text, log=print):
    low = text
    hits = {k: bool(rx.search(low)) for k, rx in PATS.items()}
    n_p = len(PVAL.findall(low))
    inferential = n_p > 0 or hits["effect"]
    many_tests = n_p >= 5
    missing_block = []
    if inferential:
        for k in BLOCKING:
            if not hits[k]:
                missing_block.append(k)
        if many_tests and not hits["mcorr"]:
            missing_block.append("mcorr")
    verdict = ("NOT APPLICABLE (no inferential statistics detected)" if not inferential else
               "GAPS" if missing_block else "METHODS DOCUMENTED")
    if log:
        print("THE METHOD CREW - methods-section checklist (CONSORT / OSF; zero model calls)")
        print("inferential: %s   p-values seen: %d%s\n" % (
            "yes" if inferential else "no", n_p, "   (many tests)" if many_tests else ""))
        order = ["power", "effect", "mcorr", "random", "blind", "prereg", "avail", "exclude"]
        for k in order:
            block = (k in BLOCKING or k == "mcorr") and inferential
            if hits[k]:
                print("  [ok]   %s" % LABELS[k])
            elif block and (k in BLOCKING or (k == "mcorr" and many_tests)):
                print("  [FAIL] %s  - a referee flags this on sight" % LABELS[k])
            else:
                print("  [flag] %s  - not mentioned" % LABELS[k])
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the stats were done CORRECTLY (assumptions, model choice) - a statistician")
        print("  - whether the design actually supports the causal claim - a methodologist / referee")
        print("  - whether a reported pre-registration MATCHES what was run (read the registry)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Presence, not soundness. A reviewer still reads it; route to `review`.")
    return {"verdict": verdict, "hits": hits, "pvalues": n_p, "missing": missing_block}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos or not os.path.isfile(pos[0]):
        print("method: need a path to a methods text (.txt/.md/.html)", file=sys.stderr)
        return 2
    raw = open(pos[0], encoding="utf-8-sig", errors="replace").read()
    text = TAG.sub(" ", raw) if pos[0].lower().endswith((".html", ".htm")) else raw
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(text, log=None)
        return _emit.emit("method", rep, 1 if rep["verdict"] == "GAPS" else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(text, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(text)
    return 1 if rep["verdict"] == "GAPS" else 0


if __name__ == "__main__":
    sys.exit(main())
