"""
hardHats crew: the Inject crew (keyword `inject`). A security engineer's scan for the arbitrary-
execution class - the calls that turn data into code. Deterministic (zero model calls), grounded in
CWE-94/95 (code injection / eval), CWE-502 (unsafe deserialization), and CWE-78 (OS command
injection) - the same calls Bandit flags B102/B301-403/B506/B602-605.

🛑 It flags the PATTERN and the file:line; it does not prove the input is attacker-controlled - that
is the reviewer's call. A deliberate `eval` on a trusted literal is a FLAG, not a hard fail. It reads
.py/.js/.ts and skips its own rule lines. Real exploitability review routes to a human / `counsel`.

    python -m hardhats.crews.inject <project-dir> [--json] [--md out.md]

Exit 1 if an arbitrary-execution or unsafe-deserialization call is found.
"""
from __future__ import annotations

import os
import re
import sys

TEXT_EXT = (".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".jsx", ".tsx")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}
INTERP = re.compile(r"""f["']|%[sd]|%\s*\(|\.format\s*\(|\+\s*\w|`""")  # string built from parts

# (label, CWE, regex, hard?). "hard" unless a later check downgrades it to a flag.
RULES = [
    ("unsafe deserialization (pickle)", "CWE-502", re.compile(r"\b_?[cC]?pickle\.loads?\s*\("), True),
    ("unsafe deserialization (marshal)", "CWE-502", re.compile(r"\bmarshal\.loads?\s*\("), True),
    ("unsafe deserialization (shelve)", "CWE-502", re.compile(r"\bshelve\.open\s*\("), False),
    ("code execution (eval)", "CWE-95", re.compile(r"(?<![\w.])eval\s*\(\s*(?![\"')\s])"), True),
    ("code execution (exec)", "CWE-95", re.compile(r"(?<![\w.])exec\s*\(\s*(?![\"')\s])"), True),
    ("code execution (Function/vm)", "CWE-95", re.compile(r"\bnew\s+Function\s*\(|\bvm\.runIn"), True),
    ("dynamic import of a non-literal", "CWE-95", re.compile(r"\b__import__\s*\(\s*(?![\"')\s])"), False),
]
YAML_LOAD = re.compile(r"\byaml\.load\s*\(([^)]*)\)")
OS_SYSTEM = re.compile(r"\bos\.system\s*\(([^)]*)")
SHELL_TRUE = re.compile(r"shell\s*=\s*True")
RULEDEF = re.compile(r're\.compile|RULES\s*=|"""|CWE-')  # this file's own rule lines


def scan_file(path, rel):
    hard, flags = [], []
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return hard, flags
    own = os.path.basename(path) == "inject.py"
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith(("#", "//", "*")):
            continue
        if own and RULEDEF.search(line):
            continue
        loc = "%s:%d" % (rel, i)
        for label, cwe, rx, is_hard in RULES:
            if rx.search(line):
                (hard if is_hard else flags).append((label, cwe, loc))
        m = YAML_LOAD.search(line)
        if m and "SafeLoader" not in m.group(1) and "Loader=" not in m.group(1).replace(" ", ""):
            hard.append(("yaml.load without SafeLoader", "CWE-502", loc))
        m = OS_SYSTEM.search(line)
        if m:
            (hard if INTERP.search(m.group(1)) else flags).append(
                ("OS command" + (" built from input" if INTERP.search(m.group(1)) else " (literal)"),
                 "CWE-78", loc))
        if SHELL_TRUE.search(line):
            (hard if INTERP.search(line) else flags).append(
                ("shell=True" + (" with an interpolated command" if INTERP.search(line) else ""),
                 "CWE-78", loc))
    return hard, flags


def review(root, log=print):
    hard, flags, files = [], [], 0
    for dp, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in fs:
            if f.lower().endswith(TEXT_EXT):
                files += 1
                h, fl = scan_file(os.path.join(dp, f), os.path.relpath(os.path.join(dp, f), root))
                hard += h
                flags += fl
    verdict = ("INJECTION RISK" if hard else
               "REVIEW - execution patterns present" if flags else
               "NO DANGEROUS EXECUTION")
    if log:
        print("THE INJECT CREW - arbitrary-execution / injection scan (zero model calls)")
        print("Project: %s   files read: %d\n" % (root, files))
        print("--- data-turned-into-code (a hard finding) ---")
        if hard:
            for label, cwe, loc in hard:
                print("  [FAIL] %-40s %-8s %s" % (label, cwe, loc))
        else:
            print("  [ok]   no eval/exec on input, no pickle/marshal/unsafe-yaml, no injected shell")
        if flags:
            print("\n--- present, confirm the input is trusted ---")
            for label, cwe, loc in flags:
                print("  [flag] %-40s %-8s %s" % (label, cwe, loc))
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the argument is actually ATTACKER-controlled (taint is the reviewer's call)")
        print("  - SQL built by string concatenation inside an ORM, and template/SSTI injection")
        print("  - the full Bandit/semgrep rule set - this is the high-severity execution class only")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Pattern and location only. Exploitability is a human's call; route to `counsel`.")
    return {"verdict": verdict, "hard": hard, "flags": flags, "files": files}


def _exit_code(verdict):
    return 1 if verdict == "INJECTION RISK" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("inject: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("inject", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
