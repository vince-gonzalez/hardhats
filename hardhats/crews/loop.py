"""
hardHats crew: THE LOOP (keyword `loop`). The 'do' tier - design the share so it carries itself. It
GATES one thing, deterministically: is there actually something to forward - a hook and an asset that
travel in someone else's feed without the page? Then it prints the loop playbook, zero model calls.

    python -m hardhats.crews.loop <content-page-or-file> [--run] [--json] [--md out.md]

The forward is the atom of reach: a share is one person sending it to one other person before it is
ever one-to-many. No travelable asset, no loop. `--run` tailors the loop to your content; the gate and
the playbook are deterministic. Exit 1 when there is nothing to forward.
"""
from __future__ import annotations

import sys

from hardhats.crews import _plays

ROLE = ("You are THE LOOP: you design a share so it carries itself - a hook, one asset that travels, "
        "and a built-in reason one person forwards it to one other person.")
PLAYBOOK = """1. THE HOOK: one line stating the single most surprising or useful thing, as a claim or a
   number - "X beats Y by Z", not "my new project". It goes in og:title and the first line on the page.
2. THE TRAVELING ASSET: one image/clip/number that makes the point WITHOUT the page - it has to work as
   a screenshot in a stranger's feed. That is what og:image is for; make it the proof, not a logo.
3. THE FORWARD REASON: give the viewer a reason to send it to ONE specific person ("send this to whoever
   still does X by hand"). One-to-one first.
4. THE LANDING: the forwarded person lands back on the hook and the same asset - and the same one-line
   forward reason is right there - so THEY forward it too. That closes the loop."""


def review(target, log=print):
    raw = _plays.load_text(target)
    m = _plays.metas(raw)
    title = m.get("og:title") or _plays.page_title(raw)
    img = m.get("og:image")
    desc = m.get("og:description") or m.get("description")
    missing = []
    if not img:
        missing.append("og:image - no asset to travel in a feed")
    if not title:
        missing.append("a hook (og:title / <title>)")
    verdict = "NOTHING TO FORWARD" if missing else "FORWARDABLE"
    flags = []
    if not missing and not desc:
        flags.append("no og:description / description - the forward loses its one line")
    if log:
        print("THE LOOP - share-loop readiness (is there anything to forward?; zero model calls)")
        print("Content: %s\n" % target)
        print("--- the gate ---")
        if missing:
            for x in missing:
                print("  [FAIL] %s" % x)
        else:
            print("  [ok]   has a hook and a travelable asset - a forward can carry it")
        for fl in flags:
            print("  [flag] %s" % fl)
        print("\n--- the loop (deterministic; the same every run) ---")
        print(PLAYBOOK)
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the asset is actually compelling (that is taste - THE FLOOR, by hand)")
        print("  - that og:image resolves and is sized for the feed (that is `og`)")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "hook": bool(title), "asset": bool(img), "flags": flags}


def _exit_code(verdict):
    return 1 if verdict == "NOTHING TO FORWARD" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print("loop: give a content page or file", file=sys.stderr)
        return 2
    target = pos[0]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, log=None)
        return _emit.emit("loop", rep, _exit_code(rep["verdict"]))
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
