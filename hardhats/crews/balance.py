"""
hardHats crew: the Balance crew (keyword `balance`, "THE SWEAT"). A competitive player's read
on a move table: what is a GUARANTEED combo, what pressure is physically unreactable, and what
loops forever. Deterministic (zero model calls); fighting-game frame-data conventions.

Frame data is arithmetic, and so is whether a thing is fair at the top level. A move that is
plus-on-block and faster than a human can react to is unreactable BY DEFINITION, not by opinion.
A move that recovers with more hit-advantage than its own start-up is an infinite. Those are the
calls a "it feels balanced" chat cannot make and this settles. It does NOT judge fun, matchup
spread, or whether the numbers fit the game's intended feel - that is a designer's call (`feel`).

    python -m hardhats.crews.balance <moves.json> [--fps 60] [--reaction 15] [--md out.md]

moves.json: {"fps":60, "moves":[{"name","startup","active","recovery","onBlock","onHit","damage"}]}
onBlock / onHit are frame advantage (+/-). Exit 1 if an infinite or unreactable advantage exists.
"""
from __future__ import annotations

import json
import os
import sys


def review(doc, reaction=15, log=print):
    fps = doc.get("fps", 60)
    moves = doc.get("moves", doc if isinstance(doc, list) else [])
    by = {}
    for m in moves:
        by[m.get("name", "?")] = m
    infinites, unreactable, punishable, traps = [], [], [], []
    true_links = []

    for m in moves:
        name = m.get("name", "?")
        su = m.get("startup")
        ob = m.get("onBlock")
        oh = m.get("onHit")
        # Infinite: the move recovers on hit with >= its own start-up, so it re-hits
        # before the opponent can act. (Real games defeat this with pushback/proration,
        # which frame data alone does not carry - see the caveats.)
        if su is not None and oh is not None and oh >= su:
            infinites.append((name, oh, su))
        # Unreactable pressure: plus on block AND starts faster than a human reacts.
        if su is not None and ob is not None and ob >= 1 and su < reaction:
            unreactable.append((name, ob, su))
        # Launch-punishable: very minus on block.
        if ob is not None and ob <= -8:
            punishable.append((name, ob))
        # Frame trap: small positive gap on block (tight but legitimate).
        if ob is not None and 1 <= ob <= 3:
            traps.append((name, ob))
        # True combos: this move's hit advantage covers another move's start-up.
        if oh is not None:
            for n2, m2 in by.items():
                if n2 == name:
                    continue
                su2 = m2.get("startup")
                if su2 is not None and oh >= su2:
                    true_links.append((name, n2, oh, su2))

    bad = bool(infinites) or bool(unreactable)
    verdict = ("BALANCE RISK - infinite loop present" if infinites else
               "BALANCE RISK - unreactable plus-on-block" if unreactable else
               "WITHIN FRAME NORMS")
    if log:
        print("THE BALANCE CREW (\"THE SWEAT\") - frame-data read (zero model calls)")
        print("fps %d; human reaction floor ~%d frames (%.0f ms)\n" % (fps, reaction, reaction / fps * 1000))
        print("--- infinites (onHit >= own startup = guaranteed loop) ---")
        if infinites:
            for n, oh, su in infinites:
                print("  [FAIL] %s: +%d on hit vs %df startup - loops into itself" % (n, oh, su))
        else:
            print("  [ok]   no move loops into itself")
        print("\n--- unreactable pressure (plus on block, faster than reaction) ---")
        if unreactable:
            for n, ob, su in unreactable:
                print("  [FAIL] %s: +%d on block at %df startup - cannot be contested on reaction" % (n, ob, su))
        else:
            print("  [ok]   no unreactable plus-on-block move")
        print("\n--- punishable / frame traps (information, not failures) ---")
        for n, ob in punishable:
            print("  [note] %s: %d on block - launch-punishable on block" % (n, ob))
        for n, ob in traps:
            print("  [note] %s: +%d on block - tight frame trap" % (n, ob))
        print("\n--- guaranteed (true) combo links: %d ---" % len(true_links))
        for a, b, oh, su in true_links[:12]:
            print("  %s -> %s  (+%d on hit covers %df startup)" % (a, b, oh, su))
        if len(true_links) > 12:
            print("  ... and %d more" % (len(true_links) - 12))
        print("\n--- not checked (and not a pass) ---")
        print("  - pushback, damage proration and scaling (which is what actually stops most loops)")
        print("  - whether the numbers are FUN or fit the game's intended feel (`feel` / playtest)")
        print("  - matchup spread, movement, meter, and anything outside the move table")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Frame arithmetic only. Whether it plays well is a designer's call; route to `feel`.")
    return {"verdict": verdict, "infinites": infinites, "unreactable": unreactable,
            "punishable": punishable, "true_links": true_links}


def main():
    args = sys.argv[1:]
    reaction = int(args[args.index("--reaction") + 1]) if "--reaction" in args else 15
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    skip = {str(reaction), md_out}
    pos = [a for a in args if not a.startswith("--") and a not in skip]
    if not pos or not os.path.isfile(pos[0]):
        print("balance: need a path to a moves JSON", file=sys.stderr)
        return 2
    try:
        doc = json.loads(open(pos[0], encoding="utf-8-sig", errors="replace").read())
    except (OSError, json.JSONDecodeError) as e:
        print("balance: cannot read moves: %s" % e, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(doc, reaction, log=None)
        return _emit.emit("balance", rep, 1 if rep["verdict"].startswith("BALANCE RISK") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(doc, reaction, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(doc, reaction)
    return 1 if rep["verdict"].startswith("BALANCE RISK") else 0


if __name__ == "__main__":
    sys.exit(main())
