"""
hardHats crew: the Ops crew (keyword `ops`). An industrial / operations-research analyst's
read on a load or packing plan - the problem LOCK IN turns into a game. Deterministic (zero
model calls): fill factor, the container lower bound, overweight, and whether placed items
overlap or spill out are arithmetic, not opinion.

It reports the OR facts and VALIDATES a placement when one is given. It does NOT invent the
optimal pack (3D bin-packing is NP-hard) and it prints what it did not check - stacking,
fragility, orientation, axle law, unload order - because fitting by VOLUME is not fitting by
SHAPE, and neither is real-world shippability.

    python -m hardhats.crews.ops <loadplan.json> [--md out.md]

Load plan JSON:
  {"container": {"length": L, "width": W, "height": H, "max_weight": optional},
   "unit": "in",
   "items": [{"id": "pallet-1", "length": l, "width": w, "height": h,
              "weight": optional, "qty": optional,
              "x": optional, "y": optional, "z": optional}]}
Give x/y/z (the near bottom-left corner) to validate a placement; omit them for a sizing pass.

Exit 1 if the plan is INVALID (overlap, overflow, or overweight).
"""
from __future__ import annotations

import json
import math
import os
import sys


def _vol(d):
    return d["length"] * d["width"] * d["height"]


def _expand(items):
    out = []
    for it in items:
        out.extend([it] * int(it.get("qty", 1)))
    return out


def _overlap(a, b):
    def seg(a0, al, b0, bl):
        return not (a0 + al <= b0 or b0 + bl <= a0)
    return (seg(a["x"], a["length"], b["x"], b["length"]) and
            seg(a["y"], a["width"], b["y"], b["width"]) and
            seg(a["z"], a["height"], b["z"], b["height"]))


def _ffd_bins(vols, cap):
    """First-fit-decreasing by volume (1D) - a legitimate baseline, not a geometric pack."""
    bins = []
    for v in sorted(vols, reverse=True):
        for i, used in enumerate(bins):
            if used + v <= cap + 1e-9:
                bins[i] += v
                break
        else:
            bins.append(v)
    return len(bins)


def review(path, log=print):
    plan = json.loads(open(path, encoding="utf-8").read())
    c = plan["container"]
    unit = plan.get("unit", "units")
    items = _expand(plan.get("items", []))
    cvol = _vol(c)
    tvol = sum(_vol(it) for it in items)
    weights = [it["weight"] for it in items if it.get("weight") is not None]
    tweight = sum(weights) if weights else None
    maxw = c.get("max_weight")
    placed = [it for it in items if all(k in it for k in ("x", "y", "z"))]

    overflow, overlaps = [], []
    for it in placed:
        if (it["x"] < 0 or it["y"] < 0 or it["z"] < 0 or
                it["x"] + it["length"] > c["length"] + 1e-9 or
                it["y"] + it["width"] > c["width"] + 1e-9 or
                it["z"] + it["height"] > c["height"] + 1e-9):
            overflow.append(str(it.get("id", "?")))
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            if _overlap(placed[i], placed[j]):
                overlaps.append((str(placed[i].get("id", "?")), str(placed[j].get("id", "?"))))

    fill = 100.0 * tvol / cvol if cvol else 0.0
    vol_lb = math.ceil(tvol / cvol) if cvol else 0
    wt_lb = math.ceil(tweight / maxw) if (tweight and maxw) else None
    overweight = bool(tweight and maxw and vol_lb <= 1 and tweight > maxw)
    ffd = _ffd_bins([_vol(it) for it in items], cvol) if cvol else 0

    invalid = bool(overflow or overlaps or overweight)
    verdict = "INVALID PLAN" if invalid else "FEASIBLE (by volume and weight)"
    if log:
        print("THE OPS CREW - industrial / OR read on a load plan (zero model calls)")
        print("Plan: %s   container %sx%sx%s %s%s\n" % (
            path, c["length"], c["width"], c["height"], unit,
            ", max %s" % maxw if maxw else ""))
        print("--- size (facts) ---")
        print("  items: %d   total item volume: %.0f   container volume: %.0f" % (len(items), tvol, cvol))
        print("  fill factor: %.1f%% of one container" % fill)
        print("  volume lower bound: %d container(s) - nobody packs it in fewer by volume alone" % vol_lb)
        if wt_lb is not None:
            print("  weight: %.0f total, max %s -> weight lower bound: %d container(s)" % (tweight, maxw, wt_lb))
        print("  first-fit-decreasing baseline (volume only, 1D): %d container(s)" % ffd)
        print("\n--- placement validity ---")
        if not placed:
            print("  [info] no x/y/z placements given - a sizing pass only, nothing to validate")
        else:
            if overflow:
                print("  [FAIL] %d item(s) spill outside the container: %s" % (len(overflow), ", ".join(overflow)))
            if overlaps:
                print("  [FAIL] %d overlapping pair(s): %s" % (len(overlaps), "; ".join("%s/%s" % p for p in overlaps)))
            if not overflow and not overlaps:
                print("  [ok]   all %d placed item(s) fit inside the container with no overlap" % len(placed))
        if overweight:
            print("  [FAIL] single container is overweight: %.0f > %s" % (tweight, maxw))
        print("\n--- not checked (and not a pass) ---")
        print("  - 3D geometric packability: fitting by VOLUME is not fitting by SHAPE (NP-hard)")
        print("  - stacking limits, fragility, orientation, and whether an item may be turned")
        print("  - axle weight distribution and DOT / bridge-formula weight law")
        print("  - load and unload SEQUENCE (last on, first off) and dock constraints")
        print("\n== VERDICT: %s ==" % verdict)
        print("   OR facts and placement validity only. Real-world shippability is the operator's call.")
    return {"verdict": verdict, "fill": fill, "vol_lb": vol_lb, "wt_lb": wt_lb,
            "ffd": ffd, "overflow": overflow, "overlaps": overlaps, "overweight": overweight}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print(__doc__.strip())
        return 2
    if not os.path.isfile(pos[0]):
        print("ops: no such file: %s" % pos[0], file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        try:
            rep = review(pos[0], log=None)
        except (json.JSONDecodeError, KeyError, TypeError, ZeroDivisionError) as e:
            print("ops: bad load plan (%s)" % e, file=sys.stderr)
            return 2
        return _emit.emit("ops", rep, 1 if rep["verdict"] == "INVALID PLAN" else 0)
    try:
        if md_out:
            import io
            buf = io.StringIO()
            rep = review(pos[0], log=lambda *a: print(*a, file=buf))
            with open(md_out, "wb") as fh:
                fh.write(buf.getvalue().encode("utf-8"))
            print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
        else:
            rep = review(pos[0])
    except (json.JSONDecodeError, KeyError, TypeError, ZeroDivisionError) as e:
        print("ops: bad load plan (%s)" % e, file=sys.stderr)
        return 2
    return 1 if rep["verdict"] == "INVALID PLAN" else 0


if __name__ == "__main__":
    sys.exit(main())
