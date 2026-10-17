"""
hardHats crew: the Grant crew. Reviews a grant narrative the way a program officer
and a careful co-PI would - before submission. Deterministic gates (word limit,
required sections, slop, quantified-claim extraction for SWORN-FACTS verification)
plus an LLM reviewer panel. The grant register is the INVERSE of the employer
register: stating a limitation is REQUIRED and "we" is allowed - no humiliation
ritual here. Verdict: COMPETITIVE / NOT YET, with the single highest-value fix.

    python -m hardhats.crews.grant <narrative> [--limit WORDS] [--sections "need,aims,eval"] [--funder NAME]
"""
from __future__ import annotations

import os
import re
import sys

from .council import ask, convene, read_subject, rotate
from .house import DEFAULT_TOOLS, run_gate

REVIEWERS = [
    ("Statement of Need", "a program officer reading the Statement of Need. Is the problem real, specific, quantified, and tied to this funder's mission? Is the need established with evidence, not assertion?"),
    ("Specific Aims", "a co-PI reading the aims. Are they concrete, measurable, achievable in the period and budget, and does each aim map back to the need?"),
    ("Evaluation & Measurement", "an evaluator. How is success measured? Are there baselines, instruments, and outcomes a skeptic would accept? This kind of funder rewards measurement over promise."),
    ("Feasibility & Budget", "a grants officer. Is the plan feasible for the team and timeline? Is the budget justified and proportionate? Any disallowed or unjustified cost?"),
    ("Alignment & Competitiveness", "a review-panel chair comparing this to the field. Against typical funded proposals in this program, where does it rank, and what one change most raises its score?"),
]

REVIEWER_RULE = ("Review in the GRANT register - stating a limitation is REQUIRED, "
                 "'we' is allowed, no boasting. Be specific and cite the text. Name the "
                 "single most important fix in your lane. 3-4 lines. End with one line: "
                 "`SCORE: <0-10>`.")


def deterministic(target, text, limit, sections, tools, log=print):
    checks = []
    words = len(re.findall(r"[A-Za-z']+", text))
    if limit:
        over = words - int(limit)
        checks.append(("word limit", f"PASS ({words}/{limit})" if over <= 0
                       else f"FAIL {words} words, {over} over the {limit} limit"))
    else:
        checks.append(("word count", f"{words} words (pass --limit to gate it)"))
    if sections:
        want = [s.strip() for s in sections.split(",") if s.strip()]
        low = text.lower()
        missing = [s for s in want if s.lower() not in low]
        checks.append(("required sections",
                       "PASS" if not missing else "FAIL missing: " + ", ".join(missing)))
    if os.path.isfile(target):
        head = run_gate("slopgate.py", target, tools).splitlines()[0]
        checks.append(("slopgate (AI-tells apply here too)", head.strip()))
    sents = re.split(r"(?<=[.!?])\s+", text)
    claims = [s.strip() for s in sents
              if re.search(r"\d|\btop\b|nationall?y|percent|clients?|states?|\$", s, re.I)][:12]
    if log:
        for name, res in checks:
            print(f"  [{res.split()[0]:5}] {name}: {res}")
    return checks, claims


def review(target, limit=None, sections=None, funder=None, tools=DEFAULT_TOOLS, log=print):
    text, truncated = read_subject(target)
    if log:
        print("--- deterministic gates ---")
    checks, claims = deterministic(target, text, limit, sections, tools, log)
    ctx = (f"Funder: {funder}\n\n" if funder else "") + text
    members = [(name, f"You are {name} reviewer on a grant panel - {role}\n\n{REVIEWER_RULE}")
               for name, role in REVIEWERS]
    if log:
        print("\n--- reviewer panel ---")
    results = convene(members, ctx, require_tag=False, temperature=0.2,
                      max_tokens=300, log=log)
    scores = []
    for _n, (t, _b) in results.items():
        m = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", t)
        if m:
            scores.append(float(m.group(1)))
    avg = round(sum(scores) / len(scores), 1) if scores else None
    panel = "\n".join(f"{n}: {t}" for n, (t, _b) in results.items())
    chair = ("You are the review-panel chair. Below are five reviewers' reads of a "
             "grant narrative. Give the verdict: `COMPETITIVE` or `NOT YET`, then the "
             "single highest-value fix, then the two next. Grant register, terse.")
    verdict, vb = ask(chair, panel, rotate(0), require_tag=False, temperature=0.1,
                      max_tokens=350)
    return {"target": target, "checks": checks, "claims": claims, "results": results,
            "avg_score": avg, "verdict": verdict}


def main():
    args = sys.argv[1:]
    opt = {"--limit": None, "--sections": None, "--funder": None, "--tools": DEFAULT_TOOLS}
    for k in list(opt):
        if k in args:
            opt[k] = args[args.index(k) + 1]
    pos = [a for a in args if not a.startswith("--")]
    taken = {v for v in opt.values() if v}
    pos = [a for a in pos if a not in taken]
    if not pos:
        print("usage: python -m hardhats.crews.grant <narrative> [--limit N] "
              "[--sections \"need,aims,eval\"] [--funder NAME]")
        return 2
    target = pos[0]
    print("THE GRANT CREW - program-officer review before submission")
    print(f"Narrative: {target}" + (f"  (funder: {opt['--funder']})" if opt["--funder"] else ""))
    print("Chip count: 5 reviewers + the chair = ~6 model calls.\n")
    rep = review(target, opt["--limit"], opt["--sections"], opt["--funder"], opt["--tools"])
    if rep["claims"]:
        print("\n--- QUANTIFIED CLAIMS to verify against SWORN-FACTS.md (attested only) ---")
        for c in rep["claims"]:
            print("  * " + " ".join(c.split())[:140])
    print("\n--- VERDICT" + (f"  (panel avg {rep['avg_score']}/10)" if rep["avg_score"] else "") + " ---")
    print(rep["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
