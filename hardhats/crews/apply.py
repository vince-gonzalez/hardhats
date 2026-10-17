"""
hardHats crew: the Application crew. For the job hunt - your most active lane. It
scores a drafted answer or cover letter the way a screener would, checks the resume
against the posting for capability fit, and holds the line on the rule that a MISSING
NAMED CREDENTIAL is a STOP, not a stretch. Voice stays yours (ops/academic register),
never a keyword dump.

    python -m hardhats.crews.apply <answer-or-letter> --posting <path> [--resume <path>]
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

CREDENTIAL_RE = re.compile(
    r"(?i)\b(require[sd]?|must have|minimum)\b[^.;:]{0,80}?\b("
    r"bachelor|master|ph\.?d|degree|certifi\w+|license\w*|clearance|"
    r"\d+\+?\s*years?)\b")


def _terms(text, k=40):
    stop = {"the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "with",
            "will", "you", "our", "we", "is", "are", "be", "as", "at", "by", "this",
            "that", "work", "team", "role", "job", "ability", "experience"}
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z+#.\-]{2,}", text.lower())
             if w not in stop]
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=lambda w: -freq[w])[:k]


def fit(posting_text, resume_text, log=print):
    pt = set(_terms(posting_text, 50))
    rt = set(_terms(resume_text, 200)) if resume_text else set()
    missing = sorted(pt - rt)[:20] if rt else []
    creds = [" ".join(m.group(0).split()) for m in CREDENTIAL_RE.finditer(posting_text)]
    if log:
        if resume_text:
            cover = round(100 * len(pt & rt) / max(1, len(pt)))
            print(f"  capability overlap: {cover}% of the posting's top terms appear in the resume")
            if missing:
                print("  posting terms absent from resume: " + ", ".join(missing[:15]))
        if creds:
            print("  🛑 REQUIRED credentials in the posting (a missing NAMED one is a STOP, not a stretch):")
            for c in creds[:6]:
                print("     - " + c[:90])
    return {"missing": missing, "required_credentials": creds}


def review(answer, posting, resume=None, log=print):
    ans, _ = read_subject(answer)
    post, _ = read_subject(posting) if posting else ("", False)
    res, _ = read_subject(resume) if resume else ("", False)
    if log:
        print("--- fit (deterministic) ---")
    fitrep = fit(post, res, log)
    if log:
        print("\n--- screener panel ---")
    scorer, sb = ask(
        "You are the hiring screener scoring this applicant's answer against the "
        "posting below. Score it out of 100 the way a NEOGOV-style rubric would "
        "(specificity, direct evidence, fit to the stated duties). Name the one change "
        "that most raises the score. End: `SCORE: <0-100>`.\n\nPOSTING:\n" + post[:4000],
        ans, rotate(0), require_tag=False, temperature=0.2, max_tokens=320)
    if voice_check:
        v, vb = voice_check(ans, mode=2)
    else:
        v, vb = "(voice profile not installed - skipping voice check)", None
    if log:
        print(f"  screener [{sb}]:")
        print("    " + " ".join(scorer.split())[:300])
        print(f"\n  voice (Mode 2, not a keyword dump) [{vb}]:")
        print("    " + " ".join(v.split())[:260])
    m = re.search(r"SCORE:\s*(\d+)", scorer)
    return {"fit": fitrep, "score": int(m.group(1)) if m else None,
            "screener": scorer, "voice": v}


def main():
    args = sys.argv[1:]
    posting = args[args.index("--posting") + 1] if "--posting" in args else None
    resume = args[args.index("--resume") + 1] if "--resume" in args else None
    pos = [a for a in args if not a.startswith("--") and a not in (posting, resume)]
    if not pos or not posting:
        print("usage: python -m hardhats.crews.apply <answer-or-letter> --posting <path> [--resume <path>]")
        return 2
    print("THE APPLICATION CREW - screener score + capability fit + your voice")
    print("Chip count: ~2 model calls (screener + voice).\n")
    rep = review(pos[0], posting, resume)
    print(f"\n--- SCORE: {rep['score']}/100 ---" if rep["score"] else "\n--- (score not parsed) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
