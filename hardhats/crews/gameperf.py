"""
hardHats crew: the Frame-Budget crew (keyword `gameperf`). Does the game hold its framerate, or does
it drop frames? A game's performance is its render loop, not its page load - so this judges a trace of
per-frame times, not Core Web Vitals (that is `perf`). The standard is the frame budget: 60 fps means
every frame must finish inside 16.7 ms; a frame over budget is a dropped frame, and a frame over
100 ms is a visible hitch.

It does NOT measure - it DELEGATES. Capture a trace in the game (wrap the requestAnimationFrame loop,
record `performance.now()` deltas, dump them as JSON: {"frames_ms": [16.6, 16.7, ...]}), then:

    python -m hardhats.crews.gameperf --trace frames.json            # 60 fps budget
    python -m hardhats.crews.gameperf --trace frames.json --target 30   # 30 fps budget

🛑 With no trace it says NO ENGINE and refuses - a smoothness claim with nothing measured is the lie
this avoids. The trace is only as honest as the scene it was captured on (capture the worst one).
Exit 1 when the trace drops frames; 2 when there is no trace.
"""
from __future__ import annotations

import json
import os
import sys

STALL_MS = 100.0        # a frame this long is a visible hitch
LONG_MS = 50.0          # a frame this long is a clear stutter


def _pct(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def review(trace=None, budget=1000.0 / 60.0, log=print):
    if trace is None:
        if log:
            print("THE GAMEPERF CREW - frame-budget gate (60 fps = 16.7 ms/frame)")
            print("\n  [FAIL] no --trace given. capture per-frame times from the rAF loop first:")
            print("         {\"frames_ms\": [16.6, 16.7, 20.1, ...]}  (performance.now() deltas)")
            print("  \U0001f6d1 a smoothness claim with nothing measured is not a pass.")
            print("\n== VERDICT: NO ENGINE ==")
        return {"verdict": "NO ENGINE", "metrics": {}}
    frames = [float(x) for x in trace.get("frames_ms", []) if isinstance(x, (int, float))]
    if not frames:
        if log:
            print("THE GAMEPERF CREW - frame-budget gate")
            print("\n  [FAIL] the trace has no frames_ms samples")
            print("\n== VERDICT: NO FRAMES IN TRACE ==")
        return {"verdict": "NO FRAMES IN TRACE", "metrics": {}}
    s = sorted(frames)
    n = len(s)
    p50, p95, p99, worst = _pct(s, 0.50), _pct(s, 0.95), _pct(s, 0.99), s[-1]
    over = sum(1 for f in s if f > budget)
    longf = sum(1 for f in s if f > LONG_MS)
    stalls = sum(1 for f in s if f > STALL_MS)
    over_frac = over / n
    hazard = p95 > budget * 1.2 or over_frac > 0.10 or stalls > 0
    verdict = "DROPS FRAMES" if hazard else "HOLDS TARGET FRAMERATE"
    metrics = {"frames": n, "budget_ms": round(budget, 2), "p50_ms": round(p50, 2),
               "p95_ms": round(p95, 2), "p99_ms": round(p99, 2), "worst_ms": round(worst, 2),
               "over_budget_pct": round(100 * over_frac, 1), "long_frames": longf, "stalls": stalls,
               "target_fps": round(1000.0 / budget, 1)}
    if log:
        print("THE GAMEPERF CREW - frame-budget gate (budget %.1f ms = %.0f fps; zero model calls)"
              % (budget, 1000.0 / budget))
        print("Trace: %d frames\n" % n)
        print("--- frame times vs the %.1f ms budget ---" % budget)
        print("  %s p95 frame time:   %.2f ms   (budget x1.2 = %.2f ms)"
              % ("[FAIL]" if p95 > budget * 1.2 else "[ok]  ", p95, budget * 1.2))
        print("  %s over budget:      %.1f%% of frames   (limit 10%%)"
              % ("[FAIL]" if over_frac > 0.10 else "[ok]  ", 100 * over_frac))
        print("  %s hitches >100 ms:  %d" % ("[FAIL]" if stalls else "[ok]  ", stalls))
        print("  [info] p50 %.2f ms   p99 %.2f ms   worst %.2f ms   stutters >50ms %d"
              % (p50, p99, worst, longf))
        print("\n--- not checked (and not a pass) ---")
        print("  - the SCENE the trace came from - a smooth menu proves nothing; capture the worst")
        print("  - GPU vs CPU time, memory growth over a long session, and load/first-frame time")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "metrics": metrics}


def _exit_code(verdict):
    if verdict in ("NO ENGINE", "NO FRAMES IN TRACE"):
        return 2
    return 1 if verdict == "DROPS FRAMES" else 0


def main():
    args = sys.argv[1:]
    trace_path = args[args.index("--trace") + 1] if "--trace" in args else None
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    target = args[args.index("--target") + 1] if "--target" in args else None
    budget = 1000.0 / 60.0
    if target:
        try:
            budget = 1000.0 / float(target)
        except (ValueError, ZeroDivisionError):
            print("gameperf: --target must be a framerate, e.g. 60 or 30", file=sys.stderr)
            return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    trace = None
    if trace_path:
        try:
            with open(trace_path, encoding="utf-8-sig") as fh:
                trace = json.load(fh)
        except (OSError, ValueError) as e:
            print("gameperf: cannot read trace %s: %s" % (trace_path, e), file=sys.stderr)
            return 2
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(trace=trace, budget=budget, log=None)
        return _emit.emit("gameperf", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(trace=trace, budget=budget, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(trace=trace, budget=budget)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
