"""
hardHats crew: the Photosensitivity crew (keyword `seizure`). Does the game flash in a way that
can trigger a seizure? Graded against WCAG 2.3.1 (three flashes or below threshold) and the
general-flash rule behind the Harding test - the same bar console cert holds a game to.

Two modes, like a real flash analyser:
  - with a luminance TRACE (per-frame relative luminance of the flashing region, 0..1), it runs
    the flash-rate math: a flash is a >=10% opposing luminance change with the darker level below
    0.80; more than 3 flashes in any one-second window is a FAIL.                         [gate]
  - with no trace, it SCANS the source for constructs that can flash - a sub-0.4s CSS animation,
    a setInterval faster than 3 Hz, an animated GIF - and tells you to capture a trace. A clean
    scan is NOT a safety certificate; only a trace measures the real rate and area.

    python -m hardhats.crews.seizure <game-dir-or-file> [--trace trace.json] [--json] [--md out.md]

🛑 The source scan flags the PATTERN, not the measured rate or the flashing AREA; the area
threshold (a ~10-degree field) and the saturated-red-flash integral are the analyser's call.
Exit 1 only when a trace exceeds the flash limit.
"""
from __future__ import annotations

import json
import os
import re
import sys

FLASH_DELTA = 0.10      # a transition counts at >= 10% of max relative luminance
DARK_BELOW = 0.80       # ...only when the darker of the two levels is below 0.80 (WCAG general flash)
LIMIT_PER_SEC = 3       # more than 3 flashes in any 1-second window fails

TEXT_EXT = (".html", ".htm", ".css", ".js", ".mjs", ".cjs")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
DUR = re.compile(r"(\d*\.?\d+)\s*(ms|s)\b", re.I)
ANIM = re.compile(r"animation(?:-duration)?\s*:\s*([^;}]+)", re.I)
INTERVAL = re.compile(r"setInterval\s*\([^,]*,\s*(\d+)")
GIF = re.compile(r"[\w./-]+\.gif\b", re.I)


# --- trace mode: the real gate -------------------------------------------------------------

def _transitions(series):
    """Indices where the signal has moved >= FLASH_DELTA from the last committed level, with the
    darker of the two levels below DARK_BELOW. Each entry is one luminance transition."""
    if not series:
        return []
    ref = series[0]
    idx = []
    for i in range(1, len(series)):
        if abs(series[i] - ref) >= FLASH_DELTA and min(series[i], ref) < DARK_BELOW:
            idx.append(i)
            ref = series[i]
    return idx


def _max_flash_rate(series, fps):
    """Worst-case flashes per second. A flash is a pair of opposing transitions, so the flash
    count in a window is its transition count / 2; we slide a 1-second window and take the max."""
    idx = _transitions(series)
    if len(idx) < 2:
        return 0.0
    times = [i / float(fps) for i in idx]
    best = 0.0
    for a in range(len(times)):
        c = 0
        for b in range(a, len(times)):
            if times[b] - times[a] <= 1.0:
                c += 1
            else:
                break
        best = max(best, c / 2.0)
    return best


def _review_trace(trace, log):
    fps = float(trace.get("fps") or 60)
    lum = [float(x) for x in trace.get("luminance", [])]
    red = [float(x) for x in trace.get("red", [])]
    general = _max_flash_rate(lum, fps)
    red_rate = _max_flash_rate(red, fps) if red else 0.0
    hazard = general > LIMIT_PER_SEC or red_rate > LIMIT_PER_SEC
    verdict = "FLASH HAZARD" if hazard else "WITHIN FLASH LIMITS"
    rep = {"verdict": verdict, "mode": "trace", "fps": fps, "frames": len(lum),
           "general_flashes_per_sec": round(general, 2), "red_flashes_per_sec": round(red_rate, 2),
           "limit_per_sec": LIMIT_PER_SEC}
    if log:
        print("THE SEIZURE CREW - photosensitive-flash analysis (WCAG 2.3.1 / general-flash rule)")
        print("Trace: %d frames @ %.3g fps\n" % (len(lum), fps))
        print("--- flash rate in the worst 1-second window (limit: %d/s) ---" % LIMIT_PER_SEC)
        g = "[FAIL]" if general > LIMIT_PER_SEC else "[ok]  "
        print("  %s general luminance flashes:  %.2f /s" % (g, general))
        if red:
            r = "[FAIL]" if red_rate > LIMIT_PER_SEC else "[ok]  "
            print("  %s saturated-red flashes:      %.2f /s" % (r, red_rate))
        else:
            print("  [--]   no red channel in the trace (saturated-red flash not measured)")
        print("\n--- not checked (and not a pass) ---")
        print("  - the flashing AREA (WCAG exempts a flash smaller than a ~10-degree field)")
        print("  - whether the trace region is the brightest-flashing part of the screen")
        print("\n== VERDICT: %s ==" % verdict)
    return rep


# --- source mode: a pre-filter, never a certificate ----------------------------------------

def _scan_file(path, rel):
    flags = []
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return flags
    for i, line in enumerate(lines, 1):
        loc = "%s:%d" % (rel, i)
        m = ANIM.search(line)
        if m:
            dm = DUR.search(m.group(1))
            if dm:
                secs = float(dm.group(1)) / (1000.0 if dm.group(2).lower() == "ms" else 1.0)
                if 0 < secs < 0.4:
                    flags.append(("rapid CSS animation (%.3gs) - can exceed 3 Hz" % secs, loc))
        m = INTERVAL.search(line)
        if m and int(m.group(1)) < 167:
            flags.append(("setInterval every %sms (>3 Hz) - confirm it does not toggle brightness"
                          % m.group(1), loc))
        if GIF.search(line):
            flags.append(("animated-GIF reference - confirm it does not flash >3 Hz", loc))
    return flags


def _review_source(target, log):
    files, flags = 0, []
    paths = []
    if target and os.path.isdir(target):
        for dp, dirs, fs in os.walk(target):
            dirs[:] = [d for d in dirs if d not in SKIP_DIR]
            for f in fs:
                if f.lower().endswith(TEXT_EXT):
                    paths.append(os.path.join(dp, f))
    elif target and os.path.isfile(target):
        paths = [target]
    base = target if (target and os.path.isdir(target)) else os.path.dirname(target or ".") or "."
    for p in paths:
        files += 1
        flags += _scan_file(p, os.path.relpath(p, base))
    verdict = "REVIEW - potential flash sources present" if flags else "NO FLASH SOURCES FOUND"
    if log:
        print("THE SEIZURE CREW - static flash-source scan (no trace; not a safety certificate)")
        print("Target: %s   files read: %d\n" % (target, files))
        print("--- constructs that CAN flash (capture a luminance trace to measure the rate) ---")
        if flags:
            for label, loc in flags:
                print("  [flag] %-62s %s" % (label, loc))
        else:
            print("  [ok]   no sub-0.4s animation, no >3 Hz setInterval, no animated GIF")
        print("\n--- not measured (a clean scan does NOT certify the game is safe) ---")
        print("  - the actual flash RATE and AREA on screen - run with --trace trace.json")
        print("  - canvas / WebGL draw loops, shader strobes, and video content")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "mode": "source", "files": files, "flags": flags}


def review(target, trace=None, log=print):
    if trace is not None:
        return _review_trace(trace, log)
    return _review_source(target, log)


def _exit_code(verdict):
    return 1 if verdict == "FLASH HAZARD" else 0


def main():
    args = sys.argv[1:]
    trace_path = args[args.index("--trace") + 1] if "--trace" in args else None
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a not in (trace_path, md_out)]
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
            print("seizure: cannot read trace %s: %s" % (trace_path, e), file=sys.stderr)
            return 2
    elif not pos:
        print("seizure: give a game dir/file to scan, or --trace trace.json", file=sys.stderr)
        return 2
    target = pos[0] if pos else None

    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, trace=trace, log=None)
        return _emit.emit("seizure", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(target, trace=trace, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(target, trace=trace)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
