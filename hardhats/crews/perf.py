"""
hardHats crew: the Perf crew (keyword `perf`). A web-performance gate on the Core Web Vitals - the
thresholds Google actually ranks on: LCP <= 2.5s, CLS <= 0.1, and responsiveness (INP <= 200ms in
the field; TBT <= 200ms as the lab proxy Lighthouse reports). Deterministic against those cutoffs;
it does NOT measure, it DELEGATES the measurement to a real engine.

It runs `lighthouse` (headless Chrome) against a URL, OR reads a Lighthouse JSON you already produced
(`--report run.json`), and judges the numbers against the CWV budgets. 🛑 Without a lighthouse runner
AND without a report it says NO ENGINE and refuses - a performance claim with nothing measured behind
it is the lie this avoids. Lab metrics are an estimate of field experience, not the field data itself.

    python -m hardhats.crews.perf <url>                 # needs `lighthouse` + Chrome on PATH
    python -m hardhats.crews.perf --report lighthouse.json   # judge a report you already have

Exit 1 if any Core Web Vital is in the POOR band; 2 if there is no engine and no report.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

# (good cutoff, poor cutoff). Between the two is "needs improvement".
LCP = (2500.0, 4000.0)   # ms
CLS = (0.1, 0.25)        # unitless
INP = (200.0, 500.0)     # ms (field)
TBT = (200.0, 600.0)     # ms (lab proxy for responsiveness when INP is absent)


def find_runner(explicit=None):
    if explicit:
        return explicit if (os.path.isfile(explicit) or shutil.which(explicit)) else None
    return shutil.which("lighthouse")


def run_lighthouse(url, runner, timeout=180):
    cmd = [runner, url, "--quiet", "--chrome-flags=--headless=new --no-sandbox",
           "--only-categories=performance", "--output=json", "--output-path=stdout"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (r.stdout or "").strip()
    if not out:
        return None
    try:
        return json.loads(out[out.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return None


def _metric(report, key):
    a = (report.get("audits") or {}).get(key) or {}
    v = a.get("numericValue")
    return float(v) if isinstance(v, (int, float)) else None


def _band(value, good, poor):
    if value is None:
        return None
    return "good" if value <= good else ("poor" if value > poor else "needs-improvement")


def review(url, report=None, runner=None, explicit=None, log=print):
    if report is None:
        runner = runner or find_runner(explicit)
        if not runner:
            if log:
                print("THE PERF CREW - Core Web Vitals via Lighthouse")
                print("\n  [FAIL] no `lighthouse` runner found and no --report given.")
                print("         install lighthouse (needs Chrome), or pass --report run.json")
                print("  \U0001f6d1 a performance claim with nothing measured is not a pass.")
                print("\n== VERDICT: NO ENGINE ==")
            return {"verdict": "NO ENGINE", "metrics": {}}
        report = run_lighthouse(url, runner)
        if report is None:
            if log:
                print("THE PERF CREW - Core Web Vitals via Lighthouse")
                print("\n  [FAIL] lighthouse did not return a usable report (run, Chrome, or the URL failed)")
                print("\n== VERDICT: DID NOT RUN ==")
            return {"verdict": "DID NOT RUN", "metrics": {}}

    lcp = _metric(report, "largest-contentful-paint")
    cls = _metric(report, "cumulative-layout-shift")
    inp = _metric(report, "interaction-to-next-paint") or _metric(report, "experimental-interaction-to-next-paint")
    tbt = _metric(report, "total-blocking-time")
    resp_val, resp_cut, resp_name = (inp, INP, "INP") if inp is not None else (tbt, TBT, "TBT (lab)")

    bands = {"LCP": (lcp, _band(lcp, *LCP)), "CLS": (cls, _band(cls, *CLS)),
             resp_name: (resp_val, _band(resp_val, *resp_cut))}
    measured = {k: v for k, (v, b) in bands.items() if v is not None}
    any_poor = any(b == "poor" for _, b in bands.values())
    any_ni = any(b == "needs-improvement" for _, b in bands.values())
    missing = [k for k, (v, b) in bands.items() if v is None]

    verdict = ("NO METRICS IN REPORT" if not measured else
               "FAILS CORE WEB VITALS" if any_poor else
               "NEEDS IMPROVEMENT" if any_ni else
               "WITHIN CORE WEB VITALS BUDGETS")
    if log:
        print("THE PERF CREW - Core Web Vitals via Lighthouse (lab metrics; zero model calls of our own)")
        print("URL: %s\n" % (report.get("finalUrl") or report.get("requestedUrl") or url or "(from report)"))
        print("--- Core Web Vitals (good / poor cutoffs) ---")
        units = {"LCP": ("ms", LCP), "CLS": ("", CLS), "INP": ("ms", INP), "TBT (lab)": ("ms", TBT)}
        for k, (v, b) in bands.items():
            u, cut = units.get(k, ("", (0, 0)))
            tag = {"good": "[ok]  ", "needs-improvement": "[flag]", "poor": "[FAIL]", None: "[ -- ]"}[b]
            shown = "n/a" if v is None else ("%.3f" % v if k == "CLS" else "%.0f%s" % (v, u))
            print("  %s %-9s %s   (good <= %s, poor > %s)" % (tag, k, shown, cut[0], cut[1]))
        if missing:
            print("  [note] not present in the report: %s" % ", ".join(missing))
        print("\n--- not checked (and not a pass) ---")
        print("  - FIELD data (CrUX / real users); lab metrics estimate it, they are not it")
        print("  - INP needs interaction; a lab run reports TBT as its proxy unless INP is present")
        print("  - everything Lighthouse scores beyond CWV (SEO, best-practices, a11y - that is a11yhat)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   The numbers are Lighthouse's; the budgets are Google's CWV thresholds.")
    return {"verdict": verdict, "metrics": measured, "missing": missing}


def _exit_code(verdict):
    if verdict in ("NO ENGINE", "DID NOT RUN", "NO METRICS IN REPORT"):
        return 2
    return 1 if verdict == "FAILS CORE WEB VITALS" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    report_path = args[args.index("--report") + 1] if "--report" in args else None
    explicit = args[args.index("--runner") + 1] if "--runner" in args else None
    taken = {md_out, report_path, explicit}
    pos = [a for a in args if not a.startswith("--") and a not in taken]
    report = None
    if report_path:
        if not os.path.isfile(report_path):
            print("perf: no such report: %s" % report_path, file=sys.stderr)
            return 2
        try:
            report = json.loads(open(report_path, encoding="utf-8", errors="replace").read())
        except (OSError, json.JSONDecodeError) as e:
            print("perf: cannot read report (%s)" % e, file=sys.stderr)
            return 2
    url = pos[0] if pos else None
    if report is None and not url:
        print("perf: give a <url> (needs lighthouse) or --report lighthouse.json", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(url, report=report, explicit=explicit, log=None)
        return _emit.emit("perf", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(url, report=report, explicit=explicit, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(url, report=report, explicit=explicit)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
