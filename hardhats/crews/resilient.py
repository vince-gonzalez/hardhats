"""
hardHats crew: the Resilient crew (keyword `resilient`, "THE PARANOID MECHANIC"). A reliability
engineer's read on source: what happens when it FAILS? It hunts the failure a green test never
shows - an error swallowed in silence, a network call with no timeout, a result nobody checked.
Deterministic (zero model calls). Grounded in the house law: never swallow an error.

A BARE or broad `except: pass` hides every failure, including the one you needed to see - that is
a hard fail. A NARROW typed swallow (`except (ValueError,): pass`) is usually deliberate, so it is
flagged for a human, not failed. It does not judge whether a caught error is HANDLED well, only
that it is not hidden; deep logic review routes to `codereview`.

    python -m hardhats.crews.resilient <dir-or-file> [--md out.md]

Exit 1 if a bare/broad swallowed error (or an empty catch block) is found.
"""
from __future__ import annotations

import os
import re
import sys

TEXT_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".jsx", ".tsx")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}

EXCEPT = re.compile(r"^(\s*)except\b([^:]*):\s*(#.*)?$")
BROAD = re.compile(r"^\s*(Exception|BaseException)\s*$")        # catches everything
JS_EMPTY_CATCH = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}")
JS_EMPTY_CATCH_OPEN = re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*$")
JS_EMPTY_PROMISE = re.compile(r"\.catch\s*\(\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)?\s*=>\s*\{\s*\}\s*\)")

LINE_FLAGS = [
    ("os.system (exit status ignored)", re.compile(r"\bos\.system\s*\(")),
    ("left-in TODO / FIXME / HACK", re.compile(r"(?i)(?:#|//)\s*(todo|fixme|xxx|hack)\b")),
]
# Calls whose SAFETY keyword can sit AFTER a nested call, e.g. urlopen(Request(...), timeout=25).
# A flat `(?![^)]*timeout)` lookahead stops at the inner ')' and false-flags these, so instead
# pull the balanced-paren argument string and look inside it.
CALLS = [
    ("network call with no timeout",
     re.compile(r"\brequests\.(?:get|post|put|delete|patch|head|request)\s*\("), "timeout"),
    ("urlopen with no timeout", re.compile(r"\burlopen\s*\("), "timeout"),
    ("subprocess without check=", re.compile(r"\bsubprocess\.(?:call|run)\s*\("), "check="),
]
RULEDEF = re.compile(r"re\.compile\(|re\.(?:search|match|findall|finditer)\(|\br['\"]")


def _call_args(text, paren_idx):
    """The substring between the '(' at paren_idx and its matching ')' (balanced)."""
    depth, j = 0, paren_idx
    while j < len(text):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[paren_idx + 1:j]
        j += 1
    return text[paren_idx + 1:]


def _next_code(lines, i):
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    return lines[j] if j < len(lines) else ""


def scan_file(path, rel):
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return [], []
    hard, soft = [], []
    for i, line in enumerate(lines):
        if RULEDEF.search(line):
            continue   # a scanner must not flag its own pattern definitions
        loc = "%s:%d" % (rel, i + 1)
        m = EXCEPT.match(line)
        if m and _next_code(lines, i).strip() == "pass":
            spec = m.group(2).strip()
            if spec == "" or BROAD.match(spec):
                hard.append(("bare/broad `except: pass` - hides every failure", loc))
            else:
                soft.append(("narrow `except (%s): pass` - deliberate? verify" % spec[:30], loc))
        if JS_EMPTY_CATCH.search(line) or JS_EMPTY_PROMISE.search(line):
            hard.append(("empty catch block - the error vanishes", loc))
        elif JS_EMPTY_CATCH_OPEN.search(line) and _next_code(lines, i).strip() == "}":
            hard.append(("empty catch block - the error vanishes", loc))
        for name, rx in LINE_FLAGS:
            if rx.search(line):
                soft.append((name, loc))
    text = "\n".join(lines)
    for name, rx, kw in CALLS:
        for m in rx.finditer(text):
            lineno = text.count("\n", 0, m.start()) + 1
            if RULEDEF.search(lines[lineno - 1]):
                continue
            if kw in _call_args(text, m.end() - 1):
                continue   # the safety keyword is present in the (balanced) argument list
            soft.append((name, "%s:%d" % (rel, lineno)))
    return hard, soft


def review(root, log=print):
    hard, soft = [], []
    files = 0
    targets = [root] if os.path.isfile(root) else None
    if targets is None:
        targets = []
        for dp, dirs, fs in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIR]
            for f in fs:
                if f.lower().endswith(TEXT_EXT):
                    targets.append(os.path.join(dp, f))
    for p in targets:
        if not p.lower().endswith(TEXT_EXT):
            continue
        files += 1
        rel = os.path.relpath(p, root if os.path.isdir(root) else os.path.dirname(root))
        h, s = scan_file(p, rel)
        hard += h
        soft += s
    verdict = "FRAGILE" if hard else ("HARDENED, with flags" if soft else "HARDENED")
    if log:
        print("THE RESILIENT CREW (\"THE PARANOID MECHANIC\") - failure-mode scan (zero model calls)")
        print("files: %d\n" % files)
        print("--- swallowed errors (the house law: never swallow) ---")
        if hard:
            for name, loc in hard[:40]:
                print("  [FAIL] %s  at %s" % (name, loc))
        else:
            print("  [ok]   no bare/broad swallow, no empty catch")
        print("\n--- flags (defensive gaps + deliberate swallows to verify) ---")
        if soft:
            for name, loc in soft[:40]:
                print("  [flag] %s  at %s" % (name, loc))
        else:
            print("  [ok]   no timeout/retry/TODO flags")
        print("\n--- not checked (and not a pass) ---")
        print("  - whether a CAUGHT error is handled correctly (only that it is not hidden) - `codereview`")
        print("  - retries / backoff / idempotency, circuit breakers, and partial-failure paths")
        print("  - a floating promise with no .catch anywhere (needs real control-flow analysis)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Failure-surface only. Whether a handler is correct is a reviewer's call.")
    return {"verdict": verdict, "hard": hard, "soft": soft, "files": files}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.exists(root):
        print("resilient: no such path: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("resilient", rep, 1 if rep["verdict"] == "FRAGILE" else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return 1 if rep["verdict"] == "FRAGILE" else 0


if __name__ == "__main__":
    sys.exit(main())
