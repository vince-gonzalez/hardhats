"""
hardHats crew: the Vision crew (keyword `vision`). A vision-science referee on colour choices:
are two colours actually distinguishable, and do they survive colour-vision deficiency. It does
NOT roll its own colour maths - it DELEGATES to `opticquiz-cvd` (the published engine: CIEDE2000
perceptual difference + Machado/Brettel dichromat simulation + the palette conflict check). This
seat owns the claim schema; opticquiz-cvd owns the numbers. Without it the seat reports NO ENGINE
and refuses to bless a pair - an unchecked colour call is exactly the lie this avoids.

A pair is {"fg": "#hex", "bg": "#hex", "claim": "distinct"|"confusable"|""}. "distinct" must hold
for normal vision (ΔE00 >= JND) AND survive a CVD simulation; "confusable" holds if the pair
collapses for normal or CVD vision. No claim = measurement only.

    python -m hardhats.crews.vision "#rrggbb" "#rrggbb"
    python -m hardhats.crews.vision --pairs pairs.json [--md out.md]

Exit 1 on a CONTRADICTION (a claim the colours do not support), 2 if opticquiz-cvd is absent.
"""
from __future__ import annotations

import json
import sys

try:
    import opticquiz_cvd as cvd
    _HAVE = True
except ImportError:
    cvd = None
    _HAVE = False

JND = 2.3  # ~1 just-noticeable difference in ΔE00 for adjacent large fields


def _conflicts(fg, bg):
    """CVD types under which this pair is a conflict, per opticquiz-cvd's own thresholds
    (distinct to normal vision, but its simulated difference collapses)."""
    rep = cvd.check_palette([fg, bg])
    return [t for t in cvd.TYPES if not rep["types"][t]["pass"]]


def review(pairs, log=print):
    if not _HAVE:
        if log:
            print("THE VISION CREW - colour difference + CVD, via opticquiz-cvd")
            print("\n  [FAIL] opticquiz-cvd is not installed - this seat refuses to judge colour without it.")
            print("         pip install opticquiz-cvd   (CIEDE2000 + protan/deutan/tritan simulation)")
            print("  \U0001f6d1 a colour call without the engine is not a pass.")
            print("\n== VERDICT: NO ENGINE ==")
        return {"verdict": "NO ENGINE", "rows": []}
    rows, bad = [], False
    for p in pairs:
        fg, bg = p.get("fg", ""), p.get("bg", "")
        name = p.get("name", "%s/%s" % (fg, bg))
        claim = (p.get("claim") or "").lower()
        try:
            de = cvd.delta_e(fg, bg)
            conflicts = _conflicts(fg, bg)
        except (ValueError, TypeError, IndexError):
            rows.append((name, None, claim, "BAD HEX", False)); bad = True; continue
        if claim == "distinct":
            if de < JND:
                ok, note = False, "FAILS: ΔE00 %.2f is below the JND - not distinct even to normal vision" % de
            elif conflicts:
                ok, note = False, "FAILS: distinct to normal (ΔE00 %.2f) but collapses under %s" % (de, ", ".join(conflicts))
            else:
                ok, note = True, "distinct (ΔE00 %.2f) and holds under protan/deutan/tritan" % de
        elif claim == "confusable":
            if de < JND:
                ok, note = True, "confusable to normal vision (ΔE00 %.2f < JND)" % de
            elif conflicts:
                ok, note = True, "confusable under %s (collapses there)" % ", ".join(conflicts)
            else:
                ok, note = False, "FAILS: ΔE00 %.2f is unmistakable and survives CVD - not confusable" % de
        else:
            ok, note = True, "no claim - measurement only (ΔE00 %.2f%s)" % (
                de, "" if not conflicts else "; collapses under %s" % ", ".join(conflicts))
        bad = bad or not ok
        rows.append((name, de, claim, note, ok))
    if log:
        print("THE VISION CREW - CIEDE2000 + CVD simulation via opticquiz-cvd (zero model calls)")
        print("JND ~%.1f ΔE00; CVD sim: Machado 2009 protan/deutan/tritan\n" % JND)
        for name, de, claim, note, ok in rows:
            de_s = "  n/a " if de is None else "%6.2f" % de
            print("  %s ΔE00=%s  %-11s %s" % ("[ok]  " if ok else "[FAIL]", de_s,
                                              "(%s)" % claim if claim else "", note))
            print("        %s" % name)
        print("\n--- not checked (and not a pass) ---")
        print("  - an individual's actual colour vision; this is a MODEL (Machado dichromat), not a person")
        print("  - display calibration, ambient light, and size / spatial-frequency effects")
        print("  - legal ADA / WCAG CONTRAST is a separate axis - that is a11yhat, not this seat")
        print("\n== VERDICT: %s ==" % ("CONTRADICTION" if bad else "CLAIMS HOLD"))
        print("   ΔE00 and the dichromat simulation are opticquiz-cvd's; the claim schema is the seat's.")
    return {"verdict": "CONTRADICTION" if bad else "CLAIMS HOLD", "rows": rows}


def main():
    args = sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--pairs" in args:
        path = args[args.index("--pairs") + 1]
        md_out = args[args.index("--md") + 1] if "--md" in args else None
        try:
            doc = json.loads(open(path, encoding="utf-8-sig", errors="replace").read())
        except (OSError, json.JSONDecodeError) as e:
            print("vision: cannot read pairs: %s" % e, file=sys.stderr)
            return 2
        pairs = doc.get("pairs", doc if isinstance(doc, list) else [])
        if "--json" in args:
            from hardhats.crews import _emit
            rep = review(pairs, log=None)
            code = 2 if rep["verdict"] == "NO ENGINE" else (1 if rep["verdict"] == "CONTRADICTION" else 0)
            return _emit.emit("vision", rep, code)
        if md_out:
            import io
            buf = io.StringIO()
            rep = review(pairs, log=lambda *a: print(*a, file=buf))
            with open(md_out, "wb") as fh:
                fh.write(buf.getvalue().encode("utf-8"))
            print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
        else:
            rep = review(pairs)
        return 2 if rep["verdict"] == "NO ENGINE" else (1 if rep["verdict"] == "CONTRADICTION" else 0)
    pos = [a for a in args if not a.startswith("--")]
    if len(pos) == 2:
        if not _HAVE:
            print("vision: opticquiz-cvd not installed (pip install opticquiz-cvd)", file=sys.stderr)
            return 2
        try:
            de = cvd.delta_e(pos[0], pos[1])
        except (ValueError, TypeError, IndexError):
            print("vision: need two #rrggbb colours", file=sys.stderr)
            return 2
        print("ΔE00(%s, %s) = %.4f  (%s)" % (pos[0], pos[1], de,
              "below JND - effectively the same colour" if de < JND else "perceptibly different"))
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2
