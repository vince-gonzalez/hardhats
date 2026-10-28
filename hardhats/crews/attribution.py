"""
hardHats crew: THE LEDGER (keyword `attribution`). The second seat of the distribution-epistemology
crew - it keeps the books on where traffic came from. It audits a file of campaign links for UTM
tagging, so a channel can be given credit instead of guessed at. Deterministic, zero model calls.

A campaign link with no utm_source / utm_medium / utm_campaign is an attribution black hole - the visit
lands in "direct / none" and the channel gets no credit. Inconsistent casing (Email vs email) or a
free-text medium splits one channel into three in the report; an address in a utm value leaks PII into
analytics.

    python -m hardhats.crews.attribution <links-file> [--json] [--md out.md]

🛑 It reads every http(s) URL in the file as a campaign link you meant to tag; it does not confirm the
link resolves or that the analytics property exists. Exit 1 when a campaign link cannot be attributed.
"""
from __future__ import annotations

import os
import re
import sys
from urllib.parse import parse_qs, urlparse

URL = re.compile(r"""https?://[^\s"'<>)\]]+""", re.I)
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
CORE = ("utm_source", "utm_medium", "utm_campaign")
# a controlled vocabulary for utm_medium; free-text mediums fragment the report
VOCAB = {"email", "social", "cpc", "ppc", "paid", "referral", "organic", "affiliate", "display",
         "video", "sms", "qr", "print", "banner", "retargeting", "influencer", "podcast",
         "newsletter", "push", "app"}


def review(path, log=print):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return {"verdict": "COULD NOT READ FILE", "error": str(e)}
    urls = []
    seen = set()
    for u in URL.findall(text):
        u = u.rstrip(".,;")
        if u not in seen:
            seen.add(u)
            urls.append(u)

    hard, flags = [], []
    sources = {}   # lower -> set(original casings)
    mediums = {}
    for u in urls:
        q = parse_qs(urlparse(u).query)
        present = [k for k in CORE if q.get(k) and q[k][0].strip()]
        short = (u[:60] + "...") if len(u) > 60 else u
        if not any(k.startswith("utm_") for k in q):
            hard.append(("untrackable - no UTM tags at all", short))
            continue
        missing = [k for k in CORE if k not in present]
        if missing:
            hard.append(("missing %s" % ", ".join(missing), short))
        src = q.get("utm_source", [""])[0]
        med = q.get("utm_medium", [""])[0]
        if src:
            sources.setdefault(src.lower(), set()).add(src)
        if med:
            mediums.setdefault(med.lower(), set()).add(med)
            if med.lower() not in VOCAB:
                flags.append(("utm_medium=%r is not a standard channel - the report won't group it" % med, short))
        for k, vals in q.items():
            if k.startswith("utm_") and vals and ("@" in vals[0] or EMAIL.search(vals[0])):
                flags.append(("PII in %s (strip the address - it lands in analytics)" % k, short))

    for low, variants in sources.items():
        if len(variants) > 1:
            flags.append(("utm_source split by case: %s (case-sensitive in analytics)"
                          % " / ".join(sorted(variants)), "across links"))
    for low, variants in mediums.items():
        if len(variants) > 1:
            flags.append(("utm_medium split by case: %s" % " / ".join(sorted(variants)), "across links"))

    verdict = ("NO LINKS FOUND" if not urls else
               "UNATTRIBUTABLE LINKS" if hard else
               "REVIEW - tagging drift" if flags else
               "ATTRIBUTION CLEAN")
    if log:
        print("THE LEDGER - campaign-link attribution audit (UTM tagging; zero model calls)")
        print("File: %s   campaign links read: %d\n" % (path, len(urls)))
        print("--- untaggable traffic (a hard miss = the channel gets no credit) ---")
        if hard:
            for label, where in hard:
                print("  [FAIL] %-42s %s" % (label, where))
        elif urls:
            print("  [ok]   every link carries utm_source, utm_medium and utm_campaign")
        if flags:
            print("\n--- tagging drift (splits or leaks the report) ---")
            for label, where in flags:
                print("  [flag] %-52s %s" % (label, where))
        print("\n--- not checked (and not a pass) ---")
        print("  - that each link resolves, or that the analytics property is wired to receive it")
        print("  - whether the attribution MODEL (last-click vs first-touch) fits the funnel")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "links": len(urls), "hard": hard, "flags": flags}


def _exit_code(verdict):
    if verdict in ("NO LINKS FOUND", "COULD NOT READ FILE"):
        return 2
    return 1 if verdict == "UNATTRIBUTABLE LINKS" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print("attribution: give a file of campaign links (one per line, or any text with URLs)",
              file=sys.stderr)
        return 2
    path = pos[0]
    if not os.path.isfile(path):
        print("attribution: not a file: %s" % path, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(path, log=None)
        return _emit.emit("attribution", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(path, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(path)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
