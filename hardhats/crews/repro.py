"""
hardHats crew: the Repro crew (keyword `repro`). A research software engineer's check: could
someone else re-run this artifact. Deterministic (zero model calls); ACM artifact-review /
FORCE11 grounded. It looks for run instructions, a pinned environment, a way to cite, a
license, and a determinism signal, and reports what is missing.

It does NOT execute the artifact, so it cannot promise it actually runs - only that the
things a re-runner needs are present. That, and data access, are the human's to confirm.

    python -m hardhats.crews.repro <dir> [--md out.md]

Exit 1 if it is not re-runnable as given (no run instructions).
"""
from __future__ import annotations

import os
import re
import sys

READMES = ("readme", "readme.md", "readme.txt", "readme.rst")
PINNED_ENV = ("requirements.txt", "poetry.lock", "Pipfile.lock", "package-lock.json",
              "yarn.lock", "environment.yml", "environment.yaml", "Dockerfile", "uv.lock",
              "Cargo.lock", "renv.lock")
CITATION = ("CITATION.cff", "codemeta.json", "CITATION", "CITATION.bib")
LICENSES = ("license", "license.txt", "license.md", "licence", "copying")


def _find(root, names):
    try:
        low = {f.lower(): f for f in os.listdir(root)}
    except OSError:
        return []
    return [low[n] for n in names if n in low]


def _readme_has_runsteps(root, readmes):
    for r in readmes:
        txt = open(os.path.join(root, r), encoding="utf-8", errors="replace").read().lower()
        if re.search(r"\b(usage|install|getting started|how to run|quick ?start|run it|"
                     r"```|pip install|npm install|python -m|\./)\b", txt):
            return True
    return False


def _has_pinned(root):
    found = _find(root, [p.lower() for p in PINNED_ENV])
    if found:
        return found
    rq = os.path.join(root, "requirements.txt")   # requirements only counts if it pins
    if os.path.isfile(rq) and "==" in open(rq, encoding="utf-8", errors="replace").read():
        return ["requirements.txt"]
    return []


def _seed_signal(root):
    hits = []
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for f in files:
            if f.endswith((".py", ".js", ".ipynb", ".R", ".r")):
                try:
                    t = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                if re.search(r"(random_state|seed\(|set\.seed|PYTHONHASHSEED|np\.random\.seed)", t):
                    hits.append(os.path.relpath(os.path.join(dp, f), root))
        if len(hits) > 3:
            break
    return hits


def review(root, log=print):
    readmes = _find(root, READMES)
    runsteps = bool(readmes) and _readme_has_runsteps(root, readmes)
    pinned = _has_pinned(root)
    citation = _find(root, [c.lower() for c in CITATION])
    license_ = _find(root, LICENSES)
    seeds = _seed_signal(root)

    missing = []
    if not runsteps:
        missing.append("run instructions (a README that says how to install and run it)")
    if not pinned:
        missing.append("a pinned environment (a lockfile, pinned requirements, or a Dockerfile)")
    if not license_:
        missing.append("a LICENSE (so a re-user may legally run and build on it)")
    if not citation:
        missing.append("a CITATION (CITATION.cff or codemeta.json)")

    blocking = not runsteps  # only run steps truly block; a zero-dep project needs no lockfile
    verdict = ("RE-RUNNABLE (the essentials are present)" if not missing else
               "GAPS - not re-runnable as given" if blocking else
               "RE-RUNNABLE, with gaps (citation/license)")
    if log:
        print("THE REPRO CREW - can someone else re-run this? (zero model calls)")
        print("Artifact: %s\n" % root)
        print("--- the re-runner's checklist ---")
        print("  %s run instructions%s" % ("[ok]  " if runsteps else "[FAIL]",
              "" if runsteps else " - none found"))
        print("  %s pinned environment%s" % ("[ok]  " if pinned else "[flag]",
              " (%s)" % ", ".join(pinned) if pinned else " - nothing pins the versions (fine if it has no dependencies)"))
        print("  %s license%s" % ("[ok]  " if license_ else "[flag]",
              " (%s)" % license_[0] if license_ else " - absent"))
        print("  %s citation%s" % ("[ok]  " if citation else "[flag]",
              " (%s)" % citation[0] if citation else " - no CITATION.cff / codemeta.json"))
        print("  %s determinism signal%s" % ("[ok]  " if seeds else "[note]",
              " (seed set in %s)" % seeds[0] if seeds else " - no explicit seed found (may not need one)"))
        print("\n--- not checked (and not a pass) ---")
        print("  - whether it ACTUALLY runs (this crew does not execute the artifact)")
        print("  - data availability and access, and any hardware or OS requirement")
        print("  - whether the pinned versions still install today")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Presence of the essentials only. A real re-run is the reviewer's job.")
    return {"verdict": verdict, "runsteps": runsteps, "pinned": pinned,
            "license": license_, "citation": citation, "seeds": seeds, "missing": missing}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("repro: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("repro", rep, 1 if rep["verdict"].startswith("GAPS") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return 1 if rep["verdict"].startswith("GAPS") else 0


if __name__ == "__main__":
    sys.exit(main())
