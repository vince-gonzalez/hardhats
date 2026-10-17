"""
hardHats crew: the Outreach crew. Checks a cold email before it goes, and - the part
that matters - checks a BATCH for the mail-merge tell that slopgate cannot see. Your
own finding: 45 shared six-word runs sailed past slopgate because it hunts words, not
sameness across messages. This gate hunts the sameness.

    python -m hardhats.crews.outreach <email-file-or-text>        # one email
    python -m hardhats.crews.outreach --batch <dir-of-emails>     # the dedup gate
"""
from __future__ import annotations

import os
import re
import sys

from .council import ask, read_subject, rotate
from .house import DEFAULT_TOOLS, run_gate
try:
    from .voice import check as voice_check  # the voice profile is private
except ImportError:
    voice_check = None

SHARED_RUN_FLOOR = 6  # a shared 6-word run between two emails is the mail-merge tell


def _ngrams(text, n=SHARED_RUN_FLOOR):
    words = re.findall(r"[a-z']+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def batch_dedup(folder, log=print):
    files = [os.path.join(folder, f) for f in sorted(os.listdir(folder))
             if f.lower().endswith((".txt", ".md", ".html", ".eml"))]
    grams = {}
    for p in files:
        try:
            grams[p] = _ngrams(open(p, encoding="utf-8", errors="replace").read())
        except OSError:
            continue
    flags = []
    names = list(grams)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = grams[a] & grams[b]
            if len(shared) >= 8:
                flags.append((os.path.basename(a), os.path.basename(b), len(shared),
                              [" ".join(g) for g in list(shared)[:3]]))
    if log:
        print(f"  {len(files)} emails, {len(flags)} pair(s) over the mail-merge floor\n")
        for a, b, n, ex in sorted(flags, key=lambda x: -x[2]):
            print(f"  FAIL {a} <-> {b}: {n} shared 6-word runs")
            for e in ex:
                print(f"         e.g. \"{e}\"")
    return {"files": files, "flags": flags}


def review_one(target, tools=DEFAULT_TOOLS, log=print):
    text, _ = read_subject(target)
    checks = []
    if os.path.isfile(target):
        checks.append(("slopgate", run_gate("slopgate.py", target, tools).splitlines()[0].strip()))
    if voice_check:
        v, vb = voice_check(text, mode=2)  # ops/professional register for a vendor email
    else:
        v, vb = "(voice profile not installed - skipping voice check)", None
    reply, rb = ask(
        "You are a busy recipient of this cold email. In 3 lines: would you reply, "
        "and what is the one thing that would make you hit delete? Then: `REPLY: "
        "LIKELY` or `REPLY: UNLIKELY`.", text, rotate(1), require_tag=False,
        temperature=0.3, max_tokens=220)
    if log:
        for n, r in checks:
            print(f"  [{r.split()[0]:5}] {n}")
        print(f"\n  voice (Mode 2) [{vb}]:")
        print("    " + " ".join(v.split())[:280])
        print(f"\n  recipient read [{rb}]:")
        print("    " + " ".join(reply.split())[:280])
    return {"target": target, "checks": checks, "voice": v, "reply": reply}


def main():
    args = sys.argv[1:]
    if "--batch" in args:
        folder = args[args.index("--batch") + 1]
        if not os.path.isdir(folder):
            print(f"not a directory: {folder}")
            return 2
        print("THE OUTREACH CREW - batch mail-merge dedup (zero model calls)\n")
        rep = batch_dedup(folder)
        return 1 if rep["flags"] else 0
    pos = [a for a in args if not a.startswith("--")]
    if not pos:
        print("usage: python -m hardhats.crews.outreach <email>  |  --batch <dir>")
        return 2
    print("THE OUTREACH CREW - one email (slopgate + your voice + a recipient read)\n")
    review_one(pos[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
