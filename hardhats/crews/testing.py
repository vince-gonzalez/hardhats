"""
hardHats crew: the Tests crew (keyword `tests`). An SDET's read on whether a test suite is
REAL - not "are there tests" but "does a test actually fail when the code breaks." The static
pass counts tests and assertions and flags assertion-free theater; the headline pass is
MUTATION testing: break the source one operator at a time and see whether the suite catches
it. A suite that stays green after `==` becomes `!=` is not protecting anything.

🛑 Mutation runs on a TEMP COPY of the project. Your real files are never written to. The crew
reports the mutation score and the survivors (the regressions the suite would miss); fixing
them is yours.

    python -m hardhats.crews.testing <project-dir>                 # static pass
    python -m hardhats.crews.testing <project-dir> --mutate hardhats/crew.py
    python -m hardhats.crews.testing <project-dir> --mutate a11yhat/color.py --cmd "python -m unittest discover -s tests -q"

Exit 1 if there are NO tests, assertion-free tests, or surviving mutants.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

CAP = 12  # mutants to try; one suite run each, so keep it bounded
IGNORE = shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".venv", "venv",
                                "dist", "build", "*.egg-info", ".pytest_cache", ".mypy_cache")
FLIP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.Gt: ast.LtE,
        ast.LtE: ast.Gt, ast.GtE: ast.Lt, ast.And: ast.Or, ast.Or: ast.And,
        ast.Add: ast.Sub, ast.Sub: ast.Add}


class Mutator(ast.NodeTransformer):
    """Flip exactly the k-th mutatable site; record a one-line description."""

    def __init__(self, k):
        self.k, self.i, self.desc = k, -1, None

    def _hit(self):
        self.i += 1
        return self.i == self.k

    def visit_Compare(self, node):
        self.generic_visit(node)
        for idx, op in enumerate(node.ops):
            if type(op) in FLIP and self._hit():
                new = FLIP[type(op)]
                node.ops[idx] = new()
                self.desc = "line %s: %s -> %s" % (node.lineno, type(op).__name__, new.__name__)
        return node

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if type(node.op) in FLIP and self._hit():
            new = FLIP[type(node.op)]
            self.desc = "line %s: %s -> %s" % (node.lineno, type(node.op).__name__, new.__name__)
            node.op = new()
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if type(node.op) in FLIP and self._hit():
            new = FLIP[type(node.op)]
            self.desc = "line %s: %s -> %s" % (node.lineno, type(node.op).__name__, new.__name__)
            node.op = new()
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._hit():
            self.desc = "line %s: removed 'not'" % node.lineno
            return node.operand
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool) and self._hit():
            self.desc = "line %s: %s -> %s" % (node.lineno, node.value, not node.value)
            return ast.copy_location(ast.Constant(value=not node.value), node)
        return node


def _count_sites(src):
    m = Mutator(-1)
    m.visit(ast.parse(src))
    return m.i + 1


def _test_files(root):
    out = []
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build")]
        for f in files:
            if (re.match(r"test_.*\.py$", f) or re.search(r"_test\.py$", f) or
                    re.search(r"\.(test|spec)\.[jt]sx?$", f) or
                    (os.path.basename(dp) == "tests" and f.endswith(".py") and f != "__init__.py")):
                out.append(os.path.join(dp, f))
    return out


def _static(root, log):
    tfiles = _test_files(root)
    tests = asserts = theater = 0
    for p in tfiles:
        txt = open(p, encoding="utf-8", errors="replace").read()
        fns = re.findall(r"(?m)^\s*(?:def\s+test\w*|it\(|test\()", txt)
        a = len(re.findall(r"\b(assert|self\.assert\w+|expect\(|assert\.\w+)", txt))
        tests += len(fns)
        asserts += a
        if fns and a == 0:
            theater += 1
    if log:
        print("--- static (facts) ---")
        print("  test files: %d   test functions: ~%d   assertions: ~%d" % (len(tfiles), tests, asserts))
        if not tfiles:
            print("  [FAIL] no test files found - the suite does not exist")
        elif theater:
            print("  [FAIL] %d test file(s) have test functions but ZERO assertions (they run, they check nothing)" % theater)
        elif tests and asserts < tests:
            print("  [flag] fewer assertions than test functions - some tests may not assert")
        else:
            print("  [ok]   tests carry assertions")
    return {"files": len(tfiles), "tests": tests, "asserts": asserts, "theater": theater}


def _run(root, cmd, timeout=180):
    env = dict(os.environ)
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    try:
        p = subprocess.run(cmd, cwd=root, env=env, capture_output=True, timeout=timeout,
                           shell=isinstance(cmd, str))
        return p.returncode
    except subprocess.TimeoutExpired:
        return 124


def _mutate(root, source, cmd, log):
    tmp = tempfile.mkdtemp(prefix="hh_tests_")
    dest = os.path.join(tmp, "proj")
    result = {"ran": False}
    try:
        shutil.copytree(root, dest, ignore=IGNORE)
        src_abs = os.path.join(dest, source)
        if not os.path.isfile(src_abs):
            if log:
                print("\n--- mutation ---\n  [skip] source not found in project: %s" % source)
            return result
        if log:
            print("\n--- mutation (on a temp copy; your files are untouched) ---")
            print("  baseline: running the suite green before breaking anything...")
        if _run(dest, cmd) != 0:
            if log:
                print("  [skip] the suite is not green at baseline (or could not run) with: %s" %
                      (cmd if isinstance(cmd, str) else " ".join(cmd)))
            return result
        orig = open(src_abs, encoding="utf-8").read()
        try:
            n = _count_sites(orig)
        except SyntaxError:
            if log:
                print("  [skip] could not parse %s" % source)
            return result
        killed = survived = 0
        survivors = []
        for k in range(min(n, CAP)):
            m = Mutator(k)
            tree = m.visit(ast.parse(orig))
            if m.desc is None:
                continue
            ast.fix_missing_locations(tree)
            try:
                mutant = ast.unparse(tree)
            except Exception:  # noqa: BLE001
                continue
            with open(src_abs, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(mutant)
            rc = _run(dest, cmd)
            with open(src_abs, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(orig)                      # restore the temp copy immediately
            if rc != 0:
                killed += 1
            else:
                survived += 1
                survivors.append(m.desc)
        total = killed + survived
        score = (100 * killed / total) if total else 0
        result = {"ran": True, "killed": killed, "survived": survived, "score": score,
                  "survivors": survivors, "source": source}
        if log:
            print("  mutants planted in %s: %d   killed: %d   survived: %d   score: %.0f%%"
                  % (source, total, killed, survived, score))
            if survivors:
                print("  [FAIL] the suite did NOT catch these breaks (regressions it would miss):")
                for s in survivors:
                    print("     - %s" % s)
            elif total:
                print("  [ok]   the suite caught every planted break")
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def review(root, source=None, cmd=None, log=print):
    cmd = cmd or [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]
    if log:
        print("THE TESTS CREW - is the suite real? static + mutation (your files are never written)")
        print("Project: %s\n" % root)
    st = _static(root, log)
    mut = _mutate(root, source, cmd, log) if source else {"ran": False}
    if log:
        print("\n--- not checked (and not a pass) ---")
        print("  - real line/branch COVERAGE (needs a coverage run), and untested files")
        print("  - integration / end-to-end behaviour and flaky or order-dependent tests")
        print("  - non-Python suites (the mutation pass is Python only)")
        print("  - whether a killed mutant was killed for the RIGHT reason")
    no_tests = st["files"] == 0
    bad = no_tests or st["theater"] > 0 or (mut.get("ran") and mut.get("survived"))
    verdict = ("NO TESTS" if no_tests else
               "THEATER - tests without assertions" if st["theater"] else
               "GAPS - suite misses %d planted regression(s)" % mut["survived"]
               if (mut.get("ran") and mut.get("survived")) else
               "REAL (caught every planted break)" if mut.get("ran") else
               "STATIC ONLY - run --mutate to test regression-catching")
    if log:
        print("\n== VERDICT: %s ==" % verdict)
        print("   SDET read. A green suite proves nothing a mutation did not try to break.")
    return {"verdict": verdict, "static": st, "mutation": mut, "bad": bad}


def main():
    args = sys.argv[1:]

    def opt(flag):
        return args[args.index(flag) + 1] if flag in args else None

    source, cmd_s, md_out = opt("--mutate"), opt("--cmd"), opt("--md")
    taken = {source, cmd_s, md_out, "--mutate", "--cmd", "--md"}
    pos = [a for a in args if a not in taken and not a.startswith("--")]
    if not pos:
        print(__doc__.strip())
        return 2
    root = pos[0]
    if not os.path.isdir(root):
        print("tests: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    cmd = cmd_s if cmd_s else None
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, source, cmd, log=None)
        return _emit.emit("tests", rep, 1 if rep["bad"] else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, source, cmd, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root, source, cmd)
    return 1 if rep["bad"] else 0


if __name__ == "__main__":
    sys.exit(main())
