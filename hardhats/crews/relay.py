"""
hardHats crew: THE RELAY (keyword `relay`). The 'do' tier - multiply one piece of content across the
free surfaces that already distribute (directories, aggregators, curated lists, launch boards). It
GATES one thing, deterministically: does the content carry what a submission needs - a title, a
description, and an image - or will it bounce? Then it prints the relay playbook, zero model calls.

    python -m hardhats.crews.relay <content-page-or-file> [--run] [--json] [--md out.md]

Mechanical reach only - no paid ads. `--run` tailors the plan to your content; the gate and the
playbook are deterministic. Exit 1 when the content is not submittable.
"""
from __future__ import annotations

import sys

from hardhats.crews import _plays

ROLE = ("You are THE RELAY: you multiply one piece of content across the free surfaces that already "
        "distribute - directories, aggregators, curated lists, launch boards.")
PLAYBOOK = """1. THE SURFACES: match the content to the free-distribution surfaces that fit it - a directory
   for the category, a newsletter/aggregator that curates it, a launch or "show" board, a list someone
   else maintains. Pick the 2 with the most on-topic audience, not the most traffic.
2. THE ONE FIELD: each surface accepts or rejects on ONE field - the one-line title for a launch board,
   the category for a directory, the first sentence for a newsletter. Write that field for THAT surface,
   not a paste.
3. THE SUBMIT: most want a title, a one-line description, a URL, and an image at a set size. Have them
   ready - this seat's gate tells you which you are missing.
4. THE FOLLOW-THROUGH: a submission that goes live with no first comment or vote from you dies. Seed the
   first interaction yourself, honestly.
   🛑 Submit forms and rules change - confirm each surface's current requirements before you submit."""


def review(target, log=print):
    raw = _plays.load_text(target)
    m = _plays.metas(raw)
    title = m.get("og:title") or _plays.page_title(raw)
    desc = m.get("og:description") or m.get("description")
    has_image = bool(m.get("og:image")) or _plays.has_img(raw)
    has_url = bool(m.get("og:url")) or _plays.has_canonical(raw)
    missing = []
    if not title:
        missing.append("a title / one-liner")
    if not desc:
        missing.append("a description")
    if not has_image:
        missing.append("an image")
    verdict = "NOT SUBMITTABLE" if missing else "SUBMITTABLE"
    flags = []
    if title and len(title) > 70:
        flags.append("title is %d chars - many boards cut the one-liner around 70" % len(title))
    if desc and len(desc) > 160:
        flags.append("description is %d chars - trim toward ~160 for the snippet" % len(desc))
    if not has_url:
        flags.append("no canonical / og:url - some surfaces require the canonical link")
    if log:
        print("THE RELAY - syndication readiness (can it be submitted?; zero model calls)")
        print("Content: %s\n" % target)
        print("--- the gate (the hard submit fields) ---")
        if missing:
            print("  [FAIL] missing: %s" % ", ".join(missing))
        else:
            print("  [ok]   has a title, a description and an image - submittable")
        for fl in flags:
            print("  [flag] %s" % fl)
        print("\n--- the relay (deterministic; the same every run) ---")
        print(PLAYBOOK)
        print("\n--- not checked (and not a pass) ---")
        print("  - whether a given surface accepts your category/topic (read its rules live)")
        print("  - the image's real pixel size per surface (declared presence only - see `og`)")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "missing": missing, "flags": flags}


def _exit_code(verdict):
    return 1 if verdict == "NOT SUBMITTABLE" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print("relay: give a content page or file", file=sys.stderr)
        return 2
    target = pos[0]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, log=None)
        return _emit.emit("relay", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(target, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
        return _exit_code(rep["verdict"])
    rep = review(target)
    if "--run" in args:
        _plays.tailor(ROLE, PLAYBOOK, _plays.visible_text(_plays.load_text(target)), print)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
