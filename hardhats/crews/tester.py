"""hardHats crew: the tester.

The house crew asks "does this match the house standards". This one asks
the question you would ask about somebody else's site: is it fit to ship.
Accessibility, legal and policy, privacy, transport, metadata, weight,
phones, usability, and - with --game - the things a browser game fails
that a document never does.

WHY THIS IS A CREW AND NOT A PROMPT. Every dimension here is a gate hat:
a rule decides it, the same way twice, and it can fail. The only LLM in
the room is the foreman, and the foreman is handed the findings AFTER
they exist and is asked to rank and explain them. It cannot overrule a
gate and it is never asked whether something passed. That is the moat: a
chatbot can produce a document that looks like this report, and it cannot
produce the findings in it.

WHAT IT REFUSES TO DO. Every section prints what it did NOT check. A
tester that lists only what it found reads as a clean bill of health for
everything it never opened. Flashing, keyboard completability, whether a
privacy policy is truthful and whether the copy is clear are all named
there rather than quietly scored.

    python -m hardhats.crews.tester https://example.com
    python -m hardhats.crews.tester C:\\path\\to\\site --game --summary
    python -m hardhats.crews.tester . --md report.md --backend cohere

Exit 1 if any gate returns a BLOCK, so it drops into CI.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

from ..crew import Crew, Hat
from ..gates.webtest import GATES, GAME_GATES, Finding, Result, Target, BLOCK, WARN

# The accessibility dimension is delegated rather than reimplemented.
# a11yhat is the shipped WCAG machine and the checker this crew calls: it is
# run in process, once per loaded page, then aggregated. It is not
# pip-installed, so its checkout is put on sys.path (override HARDHATS_A11YHAT).
# If it cannot be imported, the house a11y.py runs as a subprocess instead;
# failing both, the dimension is reported NOT CHECKED, never assumed fine.
TOOLS = os.environ.get("HARDHATS_TOOLS", r"C:\tmp\f-keys\tools")
A11YHAT = os.environ.get("HARDHATS_A11YHAT", r"C:\Users\Admin\Desktop\a11yhat")

FOREMAN = """You are the foreman on a site inspection. Below are findings
from deterministic checks that have already run. You did not find them and
you cannot overrule them.

Write at most eight lines, plain and cold, no preamble and no praise:
1. One line: is this fit to ship, yes or no, and why.
2. The three findings that matter most to a real visitor, in order, each
   with the one sentence that says why it matters rather than what it is.
3. One line naming the cheapest fix that removes the most risk.

Do not invent a finding that is not in the list. Do not say anything is
fine because it is absent from the list: things absent were not checked.
Do not use the words delve, robust, seamless, leverage or tapestry."""


LICENCE_NOTE = """Foreman backends and what is known about their terms.

This is what is recorded in backends.py and in this repository. It is NOT
legal advice and it is NOT a reading of anybody's current terms of
service, which change. Before running this for money, read the terms of
the backend you picked.

  cohere      NOT FOR PAID WORK on the free tier. backends.py marks it
              "non-commercial free tier - perspective/research only, not
              paid products". The CLI refuses it for --summary.
  cloudflare  Workers AI on the account's own plan. The default here.
  ollama      Local. Nothing leaves the machine, no terms to breach, and
              the smallest models of the set.
  gemini,     Free developer tiers. Free tiers commonly differ from paid
  groq,       ones on commercial use AND on whether prompts are retained
  mistral,    for training. If a client's content is going into one,
  openrouter  that is a disclosure you owe them either way.

NONE of the backends wired here is a frontier model. Everything live is
flash-tier or open weight at 120B or below. The gates do not care. The
foreman is the only part that would notice."""


def _ensure_a11yhat_on_path():
    """a11yhat is not pip-installed; put its checkout on sys.path so it imports."""
    if A11YHAT and os.path.isdir(A11YHAT) and A11YHAT not in sys.path:
        sys.path.insert(0, A11YHAT)


def a11y_dimension(t: Target) -> Result:
    """The accessibility dimension, delegated to a11yhat.

    a11yhat is the shipped WCAG 2.2 POUR machine. It audits ONE document, so
    this runs it over every page the Target already loaded and aggregates the
    per-criterion results. If a11yhat cannot be imported (its checkout is not on
    the path) the house a11y.py runs as a subprocess instead; if neither is
    available the dimension is reported NOT CHECKED rather than assumed fine.

    a11yhat marks what it cannot settle from static HTML as CHECK (a human
    confirms it), never as a pass. Contrast is reported CHECK, not pass or fail,
    when the real backdrop behind an element is not knowable from the CSS - a
    translucent fill, or text over a dark section or an image - because the pair
    is composited over an assumed-white page. Those CHECK items are surfaced in
    this dimension's not-checked list, never counted as passing.
    """
    _ensure_a11yhat_on_path()
    try:
        from a11yhat.run import audit
        from a11yhat.base import FAIL, REVIEW
    except Exception:                                         # noqa: BLE001
        audit = None
    if audit is not None:
        return _a11yhat_dimension(t, audit, FAIL, REVIEW)

    script = os.path.join(TOOLS, "a11y.py")
    if not os.path.isfile(script):
        return Result("Accessibility", [], [
            "ALL of it. a11yhat could not be imported from %s and no a11y.py "
            "was found at %s. Put a11yhat on the path (HARDHATS_A11YHAT) or "
            "point HARDHATS_TOOLS at a checkout with a11y.py. Nothing here was "
            "checked and nothing here passed." % (A11YHAT, TOOLS)], ran=False)
    return _a11y_py_dimension(t.ref, t.is_url, script)


def _a11yhat_dimension(t: Target, audit, FAIL, REVIEW) -> Result:
    """Run a11yhat.audit() on every loaded page and aggregate per criterion.

    One BLOCK finding per criterion that FAILs anywhere; a11yhat's CHECK items
    (a human must settle them) go to the not-checked list, never counted as a
    pass; "clean pages" is pages with zero machine FAILs.
    """
    pages = t.pages or []
    if not pages:
        return Result("Accessibility",
                      [Finding(WARN, "a11yhat loaded but no page was read")],
                      ["everything, because no page was read"], ran=False)
    crit = {}            # sc -> name, level, failing pages, finding count, review pages
    pages_with_fail = 0
    for name, html in pages:
        failed_here = False
        try:
            found = audit(html)
        except Exception as e:                                # noqa: BLE001
            c = crit.setdefault("a11yhat-error", {
                "name": "a11yhat raised while reading the page (%s)"
                        % type(e).__name__,
                "level": "A", "fail": set(), "n": 0, "rev": set()})
            c["fail"].add(name); c["n"] += 1; pages_with_fail += 1
            continue
        for f in found:
            c = crit.setdefault(f.sc, {"name": f.name, "level": f.level,
                                       "fail": set(), "n": 0, "rev": set()})
            if f.status == FAIL:
                c["fail"].add(name); c["n"] += max(1, len(f.detail))
                failed_here = True
            elif f.status == REVIEW:
                c["rev"].add(name)
        if failed_here:
            pages_with_fail += 1
    findings = []
    for sc in sorted(crit):
        c = crit[sc]
        if c["fail"]:
            findings.append(Finding(
                BLOCK, "%s %s fails on %d page(s), %d finding(s)"
                % (sc, c["name"], len(c["fail"]), c["n"]), "",
                "WCAG level %s" % c["level"]))
    review = sorted(sc for sc in crit if crit[sc]["rev"] and not crit[sc]["fail"])
    unchecked = ["%s %s - a11yhat marks this CHECK on %d page(s); a human must "
                 "confirm it, it is not a pass"
                 % (sc, crit[sc]["name"], len(crit[sc]["rev"])) for sc in review]
    unchecked.append("a11yhat reports CHECK (not pass, not fail) for contrast it "
                     "cannot settle statically - a translucent fill, or text over "
                     "a dark or image background, where the real backdrop is not "
                     "knowable from the CSS - confirm those at the page")
    failing = sum(1 for sc in crit if crit[sc]["fail"])
    facts = {"checker": "a11yhat (POUR, WCAG 2.2 A/AA)",
             "criteria failing": "%d" % failing,
             "clean pages": "%d of %d" % (len(pages) - pages_with_fail, len(pages))}
    return Result("Accessibility", findings, unchecked, facts)


def _a11y_py_dimension(target: str, is_url: bool, script: str) -> Result:
    """Fallback: the house a11y.py as a subprocess, its output parsed. Used only
    when a11yhat is not importable; behaviour is unchanged from before."""
    cmd = [sys.executable, script] + (["--url", target] if is_url else [target])
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                           encoding="utf-8", errors="replace")
    except Exception as e:                                    # noqa: BLE001
        return Result("Accessibility", [
            Finding(WARN, "the accessibility checker could not be run: %s" % e)],
            ["everything, because the checker did not run"], ran=False)

    out = (p.stdout or "") + (p.stderr or "")
    findings, unchecked, facts = [], [], {}
    for line in out.splitlines():
        s = line.strip()
        m = None
        import re as _re
        m = _re.match(r"^([0-9.]+-[a-z]+)\s+(A|AA)\s+(\d+)\s+(\d+)", s)
        if m:
            findings.append(Finding(
                BLOCK, "%s fails on %s page(s), %s finding(s)"
                % (m.group(1), m.group(3), m.group(4)), "",
                "WCAG level %s" % m.group(2)))
        if s.startswith("PASS:"):
            facts["criteria"] = s[5:].strip()
        if _re.match(r"^pages with zero findings", s):
            facts["clean pages"] = s.split(":", 1)[1].strip()
    grab = False
    for line in out.splitlines():
        if "NOT TESTED" in line:
            grab = True
            continue
        if grab:
            if not line.strip():
                if unchecked:
                    break
                continue
            if line.startswith(" " * 4):
                unchecked.append(line.strip())
            else:
                break
    if not unchecked:
        unchecked = ["whatever the checker lists as not tested; its output "
                     "could not be parsed, so read it directly"]
    return Result("Accessibility", findings, unchecked, facts)


def _hat(name, fn, target):
    return Hat(name, gate=lambda _p, f=fn, t=target: f(t))


def tester_crew(ref: str, game: bool = False, foreman=None) -> tuple:
    """Return (crew, results). The gates run here; the crew carries the foreman."""
    t = Target(ref)
    results = [a11y_dimension(t)]
    for _name, fn in (GAME_GATES if game else GATES):
        try:
            results.append(fn(t))
        except Exception as e:                                # noqa: BLE001
            results.append(Result(_name, [Finding(
                WARN, "this check raised %s: %s" % (type(e).__name__, e))],
                ["everything in this dimension, because the check crashed"]))
    hats = []
    if foreman:
        # 1400, not 500. The best free backend here is a reasoning model:
        # it writes out its working first and the answer last, so a tight
        # cap truncates it mid-thought and the report ends up printing the
        # model's notes to itself instead of its verdict. Asked for a
        # five-line answer it used about nine hundred tokens getting
        # there. Headroom is cheaper than a report that looks broken.
        hats.append(Hat("foreman", model=foreman, instruction=FOREMAN,
                        max_tokens=1400, temperature=0.2))
    return Crew("tester", hats), results


def render(ref: str, results, game: bool) -> str:
    L = ["# Tester report", "", "**Target:** `%s`" % ref,
         "**Mode:** %s" % ("site and browser game" if game else "site"), ""]
    blocks = sum(len(r.blocks) for r in results)
    warns = sum(len(r.warns) for r in results)
    L += ["## Verdict", "",
          "**%s** - %d blocking, %d worth fixing, across %d dimensions."
          % ("NOT FIT TO SHIP" if blocks else
             ("SHIPPABLE, WITH WORK" if warns else "CLEAN"),
             blocks, warns, len(results)), "",
          "A blocking finding means a person is shut out or an obligation is "
          "unmet. Everything each check did NOT look at is listed under it, "
          "because a report that prints only findings reads as a pass for the "
          "things it never opened.", ""]
    L += ["## Summary", "", "| Dimension | Verdict | Blocking | Worth fixing |",
          "|---|---|---|---|"]
    for r in results:
        L.append("| %s | %s | %d | %d |"
                 % (r.name, r.verdict, len(r.blocks), len(r.warns)))
    L.append("")
    for r in results:
        L += ["## %s" % r.name, ""]
        if r.facts:
            L.append("  ".join("**%s:** %s" % (k, v) for k, v in r.facts.items()))
            L.append("")
        if r.findings:
            for lvl in (BLOCK, WARN, "NOTE"):
                got = [f for f in r.findings if f.level == lvl]
                if not got:
                    continue
                L.append("**%s**" % {BLOCK: "Blocking", WARN: "Worth fixing",
                                     "NOTE": "Noted"}[lvl])
                L.append("")
                for f in got:
                    bits = [f.what]
                    if f.where:
                        bits.append("`%s`" % f.where)
                    if f.fix:
                        bits.append("*%s*" % f.fix)
                    L.append("- " + " - ".join(bits))
                L.append("")
        else:
            L += ["Nothing found by the checks that ran.", ""]
        if r.unchecked:
            L += ["**Not checked here, and not counted as passing**", ""]
            L += ["- " + u for u in r.unchecked]
            L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Inspect a site or a browser game and report everything a "
                    "rule can decide.")
    ap.add_argument("target", nargs="?", help="a URL, a file, or a directory")
    ap.add_argument("--game", action="store_true",
                    help="also run the browser-game checks")
    ap.add_argument("--summary", action="store_true",
                    help="add an LLM foreman that ranks the findings")
    # NOT cohere. Its free tier is marked non-commercial in backends.py
    # ("perspective/research only, not paid products"), and this crew is
    # meant to be run for clients. A default that quietly breaches a
    # licence the moment somebody pays is a defect, not a convenience.
    ap.add_argument("--backend", default="cloudflare",
                    help="backend for the foreman (default cloudflare; see "
                         "--licence-note)")
    ap.add_argument("--licence-note", action="store_true",
                    help="print what is known about each backend's terms")
    ap.add_argument("--model", default=None, help="model for the foreman")
    ap.add_argument("--md", default=None, help="write the report to this file")
    a = ap.parse_args(argv)

    if a.licence_note:
        print(LICENCE_NOTE)
        return 0
    if not a.target:
        ap.error("a target is required (a URL, a file, or a directory)")
    if a.summary and a.backend == "cohere":
        print("REFUSING: the cohere free tier is marked non-commercial in\n"
              "backends.py, and this crew exists to be run for clients.\n"
              "Pick another backend, or use a paid cohere key knowingly.\n"
              "Run --licence-note for what is and is not known.",
              file=sys.stderr)
        return 2

    foreman = (a.backend, a.model) if a.summary else None
    crew, results = tester_crew(a.target, game=a.game, foreman=foreman)
    report = render(a.target, results, a.game)

    if a.summary and crew.hats:
        payload = "\n".join(
            "%s: %s" % (f.level, f.what)
            for r in results for f in r.findings)
        try:
            verdict = crew.hats[0].wear(payload or "No findings.")
            report += "\n## Foreman\n\n%s\n" % verdict.strip()
        except Exception as e:                                # noqa: BLE001
            report += ("\n## Foreman\n\nThe foreman could not be reached (%s). "
                       "The gate findings above are unaffected; the foreman is "
                       "advisory and the gates govern.\n" % e)

    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(report)
        print("wrote %s" % a.md)
    else:
        print(report)

    return 1 if any(r.blocks for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
