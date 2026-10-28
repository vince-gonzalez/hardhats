"""
hardHats crew: the Deps crew (keyword `deps`). A release engineer's read on dependency
hygiene - how many direct dependencies, how many float instead of pinning, and whether a
lockfile makes the build reproducible. Deterministic (zero model calls); semver / SLSA
grounded.

It reports facts and flags the reproducibility risk. It does NOT resolve CVEs, walk the
transitive tree, or judge dependency licenses (that is `license`) - and says so.

    python -m hardhats.crews.deps <project-dir> [--md out.md]

Exit 1 if direct dependencies float with no lockfile to pin them (builds are not reproducible).
"""
from __future__ import annotations

import json
import os
import re
import sys

LOCKS = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
         "Pipfile.lock", "uv.lock", "Cargo.lock")


def _npm(path):
    d = json.loads(open(path, encoding="utf-8", errors="replace").read() or "{}")
    out = []
    for sect in ("dependencies", "devDependencies", "optionalDependencies"):
        for n, v in (d.get(sect) or {}).items():
            v = str(v)
            floating = (v in ("", "*", "latest") or bool(re.match(r"[\^~>]|x", v)) or
                        "||" in v or " - " in v)
            out.append((n, v, floating))
    return out


def _pip(path):
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[=<>!~ \[;]", line)[0]
        floating = "==" not in line and "@" not in line
        out.append((name, line, floating))
    return out


def _pyproject(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = []
    m = re.search(r"(?s)\bdependencies\s*=\s*\[(.*?)\]", txt)
    if m:
        for item in re.findall(r"[\"']([^\"']+)[\"']", m.group(1)):
            name = re.split(r"[=<>!~ \[;]", item)[0]
            floating = "==" not in item and "@" not in item
            out.append((name, item, floating))
    return out


def _gather(root):
    deps, sources = [], []
    pj = os.path.join(root, "package.json")
    if os.path.isfile(pj):
        deps += _npm(pj); sources.append("package.json")
    py = os.path.join(root, "pyproject.toml")
    if os.path.isfile(py):
        got = _pyproject(py)
        if got:
            deps += got; sources.append("pyproject.toml")
    rq = os.path.join(root, "requirements.txt")
    if os.path.isfile(rq):
        deps += _pip(rq); sources.append("requirements.txt")
    return deps, sources


def review(root, log=print):
    deps, sources = _gather(root)
    locks = [f for f in LOCKS if os.path.isfile(os.path.join(root, f))]
    floating = [(n, v) for n, v, f in deps if f]
    no_manifest = not sources
    verdict = ("NO MANIFEST (nothing to check)" if no_manifest else
               "LOOSE (floating deps, no lockfile -> not reproducible)"
               if (floating and not locks) else
               "FLOATING (ranges present, but a lockfile pins them)" if floating else
               "PINNED")
    if log:
        print("THE DEPS CREW - dependency hygiene / reproducibility (zero model calls)")
        print("Project: %s\n" % root)
        print("--- facts ---")
        if no_manifest:
            print("  [info] no package.json / pyproject / requirements.txt found")
        else:
            print("  manifests: %s   direct dependencies: %d" % (", ".join(sources), len(deps)))
            print("  lockfile: %s" % (", ".join(locks) if locks else "NONE"))
        print("\n--- pinning ---")
        if floating:
            tag = "flag" if locks else "FAIL"
            print("  [%s] %d dependency(ies) float (no exact version):" % (tag, len(floating)))
            for n, v in floating[:15]:
                print("     - %s %s" % (n, v))
            if not locks:
                print("  [FAIL] and there is NO lockfile, so a fresh install is not reproducible")
            else:
                print("  [ok]   a lockfile is present, so the floats are pinned for a reproducible install")
        elif not no_manifest:
            print("  [ok]   every direct dependency is pinned to an exact version")
        print("\n--- not checked (and not a pass) ---")
        print("  - known vulnerabilities / CVEs (needs a vuln database and the resolved tree)")
        print("  - the full transitive dependency graph")
        print("  - dependency LICENSES and copyleft obligations (that is the `license` seat)")
        print("  - whether a floating range is intentional (a published library may float on purpose)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Facts and reproducibility only. CVE and license calls route elsewhere (`sec`, `license`).")
    return {"verdict": verdict, "deps": len(deps), "floating": floating, "locks": locks,
            "sources": sources}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("deps: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("deps", rep, 1 if rep["verdict"].startswith("LOOSE") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return 1 if rep["verdict"].startswith("LOOSE") else 0


if __name__ == "__main__":
    sys.exit(main())
