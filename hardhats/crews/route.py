"""
hardHats crew: the Router (keyword `route`). The meta-seat that dispatches BY WHAT THE
ARTIFACT IS, not by keyword. Point it at a file, a directory, or a URL; it classifies the
input, runs the seat(s) that apply, and reports each verdict. 🛑 It never guesses: an input
it cannot classify with confidence is reported as such - with the seats you could try - not
routed to one on a hunch.

    python -m hardhats.crews route <path|dir|url> [--json]
    python -m hardhats.crews ./app.sql            # the dispatcher auto-routes a bare path/url

Routing (deterministic):
  .mm                     -> proof
  .sql / .ddl             -> schema
  .json/.yaml openapi     -> api       (an openapi/swagger key is present)
  .json load plan         -> ops       (container + items)
  .json move table        -> balance   (moves / fps)
  <bcp47>.json locale     -> i18n       (run on its directory)
  .html / .htm            -> richdata   (and links across a directory of them)
  http(s) url             -> sec
  a dir with a manifest   -> pwa       (manifest.json / *.webmanifest present)
  a .github/workflows dir -> ghactions
  a directory             -> the dir-level seats whose signal is present
                             (deps, env, i18n, license, crypteng, resilient, tests,
                              archive, repro, richdata, links)

Each routed seat runs through the real dispatcher with --json, so the Router reuses the seat's
own I/O and verdict - it decides WHICH seat, it never re-implements one. Accessibility
(a11yhat / vpat) lives in its own repo; free text with no rule to match is reported, not routed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BCP47 = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?(-[A-Za-z]{2}|-\d{3})?$")

MANIFESTS_DEPS = ("requirements.txt", "pyproject.toml", "package.json", "setup.cfg",
                  "cargo.toml", "go.mod", "pipfile", "poetry.lock", "package-lock.json")
MANIFESTS_LIC = ("pyproject.toml", "package.json", "setup.cfg", "cargo.toml")
LICENSE_FILES = ("license", "license.txt", "license.md", "licence", "copying")
SRC_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".php")
DATA_EXT = (".csv", ".parquet", ".jsonl")
FIXITY = ("sha256sums", "checksums.txt", "manifest-sha256.txt", "datapackage.json", "md5sums")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
TESTY = (re.compile(r"^test_.*\.py$"), re.compile(r"_test\.py$"), re.compile(r"\.(test|spec)\.[jt]sx?$"))


def _sniff_json(path):
    try:
        head = open(path, encoding="utf-8-sig", errors="replace").read(4000).lower()
    except OSError:
        return None
    if "openapi" in head or "swagger" in head:
        return ("api", [path])
    if '"container"' in head and '"items"' in head:
        return ("ops", [path])
    if '"moves"' in head or '"fps"' in head:
        return ("balance", [path])
    base = os.path.basename(path)[:-5]
    if BCP47.match(base):
        return ("i18n", [os.path.dirname(path) or "."])
    return None


def classify_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".mm":
        return [("proof", [path])]
    if ext in (".sql", ".ddl"):
        return [("schema", [path])]
    if ext in (".json", ".yaml", ".yml"):
        r = _sniff_json(path)
        return [r] if r else []
    if ext in (".html", ".htm"):
        return [("richdata", [path])]
    return []


def _walk_has(root, pred, cap=6000):
    n = 0
    for dp, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIR]
        for f in files:
            n += 1
            if n > cap:
                return False
            if pred(f):
                return True
    return False


def classify_dir(path):
    try:
        names = {f.lower() for f in os.listdir(path)}
    except OSError:
        names = set()
    routes = []
    if os.path.isdir(os.path.join(path, ".github", "workflows")):
        routes.append(("ghactions", [path]))
    if names & {"wrangler.toml", "wrangler.jsonc", "wrangler.json"}:
        routes.append(("env", [path]))
    if names & set(MANIFESTS_DEPS):
        routes.append(("deps", [path]))
    locales = [f for f in names if f.endswith(".json") and BCP47.match(f[:-5])]
    if locales or os.path.isdir(os.path.join(path, "locales")):
        routes.append(("i18n", [path]))
    if (names & set(LICENSE_FILES)) or (names & set(MANIFESTS_LIC)):
        routes.append(("license", [path]))
    if _walk_has(path, lambda f: f.lower().endswith(SRC_EXT)):
        routes.append(("crypteng", [path]))
        routes.append(("resilient", [path]))
        routes.append(("inject", [path]))
    if _walk_has(path, lambda f: any(rx.search(f) for rx in TESTY)):
        routes.append(("tests", [path]))
    if _walk_has(path, lambda f: f.lower().endswith((".html", ".htm"))):
        routes.append(("richdata", [path]))
        routes.append(("links", [path]))
    if "manifest.json" in names or _walk_has(path, lambda f: f.lower().endswith(".webmanifest")):
        routes.append(("pwa", [path]))
    if (names & set(FIXITY)) or _walk_has(path, lambda f: f.lower().endswith(DATA_EXT)):
        routes.append(("archive", [path]))
        routes.append(("repro", [path]))
    seen, out = set(), []
    for kw, a in routes:
        if kw not in seen:
            seen.add(kw)
            out.append((kw, a))
    return out


def classify(target):
    if re.match(r"^https?://", target, re.I):
        return [("sec", [target])], "url"
    if os.path.isdir(target):
        return classify_dir(target), "dir"
    if os.path.isfile(target):
        return classify_file(target), "file"
    return [], "missing"


def run_seat(kw, args):
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-m", "hardhats.crews", kw, *args, "--json"],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if lines:
        try:
            return json.loads(lines[-1])
        except json.JSONDecodeError:
            pass
    return {"seat": kw, "verdict": None, "exit": proc.returncode, "ok": False,
            "detail": {"error": "no JSON envelope", "stderr": proc.stderr.strip()[-200:]}}


def _overall(envelopes):
    if not envelopes:
        return 2
    if any(e.get("exit") == 1 for e in envelopes):
        return 1
    if any(e.get("exit") == 2 for e in envelopes):
        return 2
    return 0


def _hint(target, kind):
    ext = os.path.splitext(target)[1].lower()
    if ext in (".html", ".htm"):
        return ("an .html page: accessibility -> a11yhat (python -m a11yhat <path>); "
                "link-liveness and structured-data are bench gaps; food copy -> `food`")
    if ext in (".md", ".txt", ".rst"):
        return "free text: try `spec` (RFC 2119), `method` (study methods), or `cite` (DOIs)"
    if kind == "file":
        return "no rule matches this file type; run a seat by keyword if you know the one"
    return "nothing in this package classifies it"


def main():
    args = sys.argv[1:]
    want_json = "--json" in args
    pos = [a for a in args if not a.startswith("--")]
    if not pos:
        print(__doc__.strip())
        return 2
    target = pos[0]
    routes, kind = classify(target)
    if kind == "missing":
        print("route: no such path or url: %s" % target, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    envelopes = [run_seat(kw, a) for kw, a in routes]
    code = _overall(envelopes)

    if want_json:
        print(json.dumps({"seat": "route", "input": target, "kind": kind,
                          "routed": [e.get("seat") for e in envelopes], "exit": code,
                          "ok": code == 0, "routes": envelopes}, ensure_ascii=False))
        return code

    print("THE ROUTER - dispatch by artifact type (zero model calls)")
    print("Input: %s   (%s)\n" % (target, kind))
    if not envelopes:
        print("  [????] nothing to route - %s" % _hint(target, kind))
        print("\n== VERDICT: NOTHING TO ROUTE ==")
        return code
    print("routed to %d seat(s):" % len(envelopes))
    for e in envelopes:
        tag = "[FAIL]" if e.get("exit") == 1 else ("[ok]  " if e.get("exit") == 0 else "[????]")
        print("  %s %-10s -> %s" % (tag, e.get("seat"), e.get("verdict")))
    print("\n--- not routed here (by design) ---")
    print("  - accessibility (WCAG) is a11yhat / `vpat`, a separate repo")
    print("  - the Router decides WHICH seat; each verdict is the seat's own, run with --json")
    print("\n== VERDICT: ROUTED (%d seat%s) ==" % (len(envelopes), "" if len(envelopes) == 1 else "s"))
    return code


if __name__ == "__main__":
    sys.exit(main())
