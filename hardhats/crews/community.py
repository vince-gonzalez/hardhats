"""
hardHats crew: THE REGULAR (keyword `community`). The 'do' tier - get content in front of a community
WITHOUT getting banned: earn the room, then post. It GATES one thing, deterministically: does the
content read as a pitch (a community removes that on sight) or as something value-first worth posting?
Then it prints the ramp - the real click-by-click, zero model calls.

    python -m hardhats.crews.community <content-page-or-file> [--run] [--json] [--md out.md]

`--run` asks one model to tailor the ramp to your content; the gate and the ramp are deterministic and
never call a model. 🛑 Community rules and UIs change - read the room's current rules before you post.
Exit 1 when the content reads as a pitch.
"""
from __future__ import annotations

import sys

from hardhats.crews import _plays

PROMO = ("buy now", "sign up", "sign-up", "signup", "limited time", "don't miss", "dont miss",
         "click here", "order now", "free trial", "act now", "subscribe", "best deal", "on sale",
         "% off", "shop now", "pre-order", "download now", "join now", "register now",
         "special offer", "hurry", "discount", "guarantee", "get yours", "start free", "try free",
         "book a demo", "contact sales", "limited offer")

ROLE = ("You are THE REGULAR: you get content into a community without getting banned, by earning the "
        "room before you ever post a link.")
PLAYBOOK = """1. FIND THE ROOM: name the 2-3 kinds of place this audience already gathers - the forum or
   board for the exact niche, the chat server for the tool category, the professional group or list
   for the field. The on-topic room, not the biggest one.
2. READ THE RULES FIRST: every room has a self-promo rule (a ratio, a day-of-week, a required tag, a
   dedicated thread). Find it before you post - breaking it is the fast ban.
3. LURK AND CONTRIBUTE (days, not minutes): answer 3-5 questions with real help and no link. You are
   buying the right to post.
4. THE ONE POST: lead with the thing itself (a finding, a tool, a free resource), not the pitch. The
   link is the last line - "I made this, here's what I learned," never "check out my X".
5. STAY: reply to every comment for the first hour. A post you abandon reads as a drop.
   🛑 NEVER drop a cold link into a room you have not earned. That is the ban, every time."""


def review(target, log=print):
    text = _plays.visible_text(_plays.load_text(target))
    low = text.lower()
    words = len(text.split())
    hits = [(t, low.count(t)) for t in PROMO if low.count(t)]
    total = sum(c for _, c in hits)
    pitch = total >= 4 or (total >= 2 and words < 120) or (words < 40 and total >= 1)
    verdict = "READS AS A PITCH" if pitch else "VALUE-FIRST"
    if log:
        print("THE REGULAR - community readiness (does it read as a pitch?; zero model calls)")
        print("Content: %s   words: %d   promo phrases: %d\n" % (target, words, total))
        print("--- the gate ---")
        if pitch:
            print("  [FAIL] reads as a pitch - a community will remove it on sight")
            if hits:
                print("         promo phrases: %s" % ", ".join("%s x%d" % (t, c) for t, c in hits[:8]))
            if words < 120:
                print("         and little substance (%d words) - nothing to earn the room with" % words)
        else:
            print("  [ok]   value-first (%d words, %d promo phrase%s) - safe to earn a room"
                  % (words, total, "" if total == 1 else "s"))
        print("\n--- the ramp (deterministic; the same every run) ---")
        print(PLAYBOOK)
        print("\n--- not checked (and not a pass) ---")
        print("  - whether a specific room actually wants this (fit is judgement, read the room)")
        print("  - the room's current self-promo rule - it changes; read it live before you post")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "words": words, "promo": total, "hits": hits}


def _exit_code(verdict):
    return 1 if verdict == "READS AS A PITCH" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print("community: give a content page or file", file=sys.stderr)
        return 2
    target = pos[0]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, log=None)
        return _emit.emit("community", rep, _exit_code(rep["verdict"]))
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
