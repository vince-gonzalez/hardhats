"""
hardHats crew: the Resume crew. The one kind of writing a bare chatbot cannot be
trusted with, because the failure is not bad prose - it is a confident claim the
person never made. A resume is defensible only when EVERY line traces to an
attested fact and survives the register rules. Both of those are gates, not
opinions, which is exactly where hardHats earns its keep.

Two deterministic gates do the facts:
  - the REGISTER gate: the banned-term rules (em dash, UK spelling, tenure stated
    as a duration, "nationally", counts recited as a brag, "authored training",
    language overclaim, confession openers, a configurable project banlist). Hard
    fails fail closed; judgement-call patterns are flagged for a human read.
  - the ATTESTATION gate ("the Notary"): every number and every employer-like
    proper noun in the draft must appear in the fact registry. A number welded to
    the wrong employer, or an invented one, has nowhere to hide.
One LLM hat does the judgement a rule cannot: the VERIFIER reads the registry and
the draft and, line by line, cites the backing fact or marks the line UNBACKED.
The voice check (Mode 2) is advisory. Nothing here invents or writes a claim; it
certifies, or refuses, a draft against a registry the author controls.

No facts are baked into this file - it is a generic tool. The registry is the
author's own (resume-kit), read at runtime, and stays private.

    python -m hardhats.crews.resume <draft.txt> --facts <registry.md> [--target "<role>"]

Exit 1 if the draft is NOT defensible.
"""
from __future__ import annotations

import os
import re
import sys

from .council import ask, read_subject, rotate
try:
    from .voice import check as voice_check  # the voice profile is private
except ImportError:
    voice_check = None

# --- the register gate -------------------------------------------------------
# HARD: unambiguous, fail closed. Each is (kind, pattern).
HARD = [
    ("em/en dash (AI tell)", r"[—–]"),
    ("banned project / MCP", r"(?i)\b(mcp|model context protocol|model context|say-?do|saydo)\b"),
    ("language overclaim", r"(?i)\b(bilingual|fluent in spanish|native or bilingual|professional working proficiency)\b"),
    ("credential overclaim", r"(?i)\b(lean certified|six sigma certified|green belt|black belt|dmaic|certified scrum|qdm[- ]certified)\b"),
    ("fabricated training authorship", r"(?i)\b(wrote|write|authored?|develop(?:ed)?|created?|designed?)\b[^.\n]{0,40}\b(training (?:material|curriculum|program)|curriculum)\b"),
    ("confession opener (employer lane)", r"(?i)(where i am short|honest caveat|where i fall short|where i am thin|what i have not done|i am not going to pretend|i do not hold a|\bi lack\b)"),
    ("'nationally' (banned)", r"(?i)\bnationally\b"),
    ("off-limits handle / asset", r"(?i)\b(tredur|safemoon)\b"),
    ("glorifies the employer", r"(?i)own the written record the operation is audited against"),
    ("wrong contact email (must be the me.com address)", r"(?i)[\w.+-]+@gmail\.com"),
]
# SOFT: judgement calls. Flag for a human read, do not auto-fail.
SOFT = [
    ("tenure stated as a duration (prefer a date; 'N years running' may be fine)",
     r"(?i)\b(\d+\+?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty)\s+years?\b"),
    ("count recited as a brag (counts come off the resume)",
     r"(?i)\b\d+\s+(packages|repos|repositories|pypi|npm|servers|applications|commits|merges)\b"),
    ("dollar figure on the page", r"\$\s?\d"),
]
# COMMODITY: true, register-clean, and still worthless - things every person in the
# field already has, so a knowledgeable reader reads them as padding. Strength is not
# the same as defensibility, but shipping filler is its own failure, so these FAIL.
COMMODITY = [
    ("commodity training-module brag (everyone at a big employer has these)",
     r"(?i)(\btraining module|\btraining course|\bqdm\b|agile enablement|lean assessment|\bsix sigma|scrum master)"),
    ("commodity ops filler (everyone works these)",
     r"(?i)(meeting [a-z ,]{0,30}goals|productivity,? safety,? and service|against (a |an )?(hard )?deadlines?|competitive environment|fast[- ]paced|high[- ]volume environment)"),
    ("commodity self-praise (generic, unverifiable)",
     r"(?i)\b(team player|detail[- ]oriented|results[- ]driven|self[- ]starter|go[- ]getter|hard[- ]working|proven track record|strong work ethic)\b"),
]

MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept",
          "oct", "nov", "dec", "january", "february", "march", "april", "june",
          "july", "august", "september", "october", "november", "december"}
# Proper-noun tokens that are not employers and should not need a registry row.
NOUN_STOP = {"i", "the", "a", "an", "and", "or", "of", "to", "in", "for", "on",
             "us", "usa", "ba", "ba.", "gpa", "cpr", "pre-law",
             "operations", "supervisor", "founder", "experience", "education",
             "credentials", "training", "summary", "other",
             # common determiners/adverbs that get capitalized mid-sentence; never
             # proper nouns, so they must not drag a phrase into a false flag.
             "some", "also", "currently", "additional", "many", "held", "ranked",
             "relevant"}


def register_gate(text):
    hard = [(k, m.group(0)) for k, p in HARD for m in re.finditer(p, text)]
    soft = [(k, m.group(0)) for k, p in SOFT for m in re.finditer(p, text)]
    return hard, soft


def attestation_gate(draft, facts_text):
    """Every number (2+ digits) and every capitalized proper-noun phrase in the
    draft must appear in the registry. Returns (unbacked_numbers, unbacked_nouns)."""
    low = facts_text.lower()
    nums = sorted({n for n in re.findall(r"\b\d{2,}\b", draft)})
    bad_nums = [n for n in nums if n not in facts_text]
    # Only MULTI-word capitalized phrases (where real employer fabrication shows);
    # a single sentence-initial verb ("Facilitate", "Held") is not a proper noun.
    # No "." in the class and spaces-only between words, so a trailing period cannot
    # merge a word into the next line's section heading.
    phrases = re.findall(r"\b[A-Z][A-Za-z&'-]+(?:[ \t]+[A-Z][A-Za-z&'-]+)+", draft)
    seen, bad_nouns = set(), []
    for ph in phrases:
        strip = lambda t: t.lower().strip(".,:;")
        toks = [t for t in ph.split() if strip(t) not in MONTHS]
        core = [t for t in toks if strip(t) not in NOUN_STOP]
        if not core:
            continue
        key = ph.lower().strip(".,:;")
        if key in seen:
            continue
        seen.add(key)
        # backed if the phrase, or its distinctive core, appears in the registry
        if key in low or all(strip(t) in low for t in core):
            continue
        bad_nouns.append(ph)
    return bad_nums, bad_nouns


def verify(draft, facts_text, log=print):
    """LLM hat: cite the backing fact for each claim line, or mark it UNBACKED."""
    instr = (
        "You are the attestation verifier for a resume. Below is a FACT REGISTRY "
        "(the only claimable facts) and a DRAFT. Ignore the name, contact lines, "
        "tagline, and all-caps section headings; judge only substantive claim lines. "
        "For each such line, output one line: the claim in <=6 words, then `<=` and the "
        "registry fact that backs it, or `UNBACKED` if no registry line supports it. Do "
        "not assess style. A date, number, employer, title, or award that is not in the "
        "registry is UNBACKED. End with exactly one line: `VERDICT: ALL BACKED` or "
        "`VERDICT: UNBACKED LINES PRESENT`.\n\n=== FACT REGISTRY ===\n"
        + facts_text[:7000] + "\n\n=== DRAFT ===\n" + draft[:4000])
    return ask(instr, "", rotate(0), require_tag=False, temperature=0.0, max_tokens=700)


def review(draft_target, facts_path, target=None, log=print):
    draft, _ = read_subject(draft_target)
    if not os.path.isfile(facts_path):
        return {"error": f"registry not found: {facts_path}"}
    facts_text = open(facts_path, encoding="utf-8", errors="replace").read()

    hard, soft = register_gate(draft)
    commodity = [(k, m.group(0)) for k, p in COMMODITY for m in re.finditer(p, draft)]
    bad_nums, bad_nouns = attestation_gate(draft, facts_text)

    if log:
        print("--- register gate (deterministic) ---")
        if hard:
            for k, snip in hard:
                print(f"  [FAIL] {k}: {snip!r}")
        else:
            print("  [PASS] no hard register violations")
        for k, snip in soft:
            print(f"  [flag] {k}: {snip!r}")
        print("\n--- commodity filter (strength, not just truth) ---")
        if commodity:
            for k, snip in commodity:
                print(f"  [FAIL] {k}: {snip!r}")
        else:
            print("  [PASS] no commodity filler (nothing every peer already has)")
        print("\n--- attestation gate / the Notary (deterministic) ---")
        if bad_nums:
            print("  [FAIL] numbers not found in the registry: " + ", ".join(bad_nums))
        if bad_nouns:
            print("  [FAIL] proper nouns not found in the registry: " + ", ".join(bad_nouns))
        if not bad_nums and not bad_nouns:
            print("  [PASS] every number and employer traces to the registry")

    if log:
        print("\n--- verifier (one LLM hat, line-by-line citation) ---")
    vtext, vb = verify(draft, facts_text)
    if log:
        print(f"  [{vb}]")
        for line in vtext.splitlines():
            if line.strip():
                print("    " + line.strip()[:160])

    if voice_check and log:
        print("\n--- voice check (Mode 2, advisory) ---")
        vv, vvb = voice_check(draft, mode=2)
        print(f"  [{vvb}] " + " ".join(vv.split())[:300])

    # The deterministic gates govern (a rule a model cannot talk past). The verifier
    # and the voice check are advisory, printed above for a human read.
    defensible = not hard and not commodity and not bad_nums and not bad_nouns
    return {"defensible": defensible, "hard": hard, "soft": soft,
            "bad_numbers": bad_nums, "bad_nouns": bad_nouns, "verifier": vtext}


def main():
    args = sys.argv[1:]
    facts = args[args.index("--facts") + 1] if "--facts" in args else None
    target = args[args.index("--target") + 1] if "--target" in args else None
    pos = [a for a in args if not a.startswith("--") and a not in (facts, target)]
    if not pos or not facts:
        print("usage: python -m hardhats.crews.resume <draft.txt> --facts <registry.md> [--target \"<role>\"]")
        return 2
    print("THE RESUME CREW - every line traces to an attested fact, or it does not ship")
    print(f"Draft: {pos[0]}   Registry: {facts}" + (f"   Target: {target}" if target else ""))
    print("Chip count: ~2 model calls (verifier + voice); the gates are deterministic.\n")
    rep = review(pos[0], facts, target)
    if "error" in rep:
        print(rep["error"])
        return 2
    print()
    if rep["defensible"]:
        print("  DEFENSIBLE - every claim traces to the registry and the register holds.")
        print("  (Soft flags above, if any, are judgement calls for a human read.)")
        return 0
    print("  NOT DEFENSIBLE - resolve the FAIL lines above before this goes out.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
