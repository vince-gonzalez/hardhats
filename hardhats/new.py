"""
hardHats seat scaffolder - mint a new bench seat that already obeys the contract.

    python -m hardhats.new <keyword> [--title "THE X CREW"] [--standard "CWE-123"]
                                     [--summary "one line of what it catches"]
                                     [--force] [--no-fixtures] [--stdout]

One command writes hardhats/crews/<keyword>.py (and a clean/marker fixture pair under
tests/fixtures/<keyword>/), so the seat registers in the dispatcher, runs, and passes the
bench suite the moment it is minted. The body is a working skeleton - it flags a leftover
marker (TODO/FIXME/XXX) in any text file - marked with TODO(author) everywhere the real
rule and the external standard go. Replace the rule; keep the shape.

The shape every seat shares (this is the contract the bench's SeatContract test enforces):
  - a module docstring carrying a (keyword `<kw>`) tag, so discovery registers it;
  - review(target, log=print) -> a dict whose "verdict" is the finding;
  - main() -> an int exit code (0 clears, 1 caught the defect, 2 a usage/read error),
    with --json (one envelope) and --md (a report file) wired the house way.
"""
from __future__ import annotations

import os
import re
import sys
from string import Template

CREWS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crews")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A public seat must never take a name git is told to ignore, or the new file would be silently
# ignored and never ship. Those names already live in ONE public place - .gitignore - so they
# are read from there (see _reserved) rather than copied here, where a second list could drift.
_VALID = re.compile(r"^[a-z][a-z0-9]{1,15}$")
_RESERVED_RE = re.compile(r"^hardhats/crews/([A-Za-z0-9_]+)\.py\s*$")


def _reserved():
    """Seat names .gitignore tells git to skip - the one public source of the names a public
    seat must not take. Read from the file so this never drifts from it; empty if it is absent."""
    names = set()
    try:
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = _RESERVED_RE.match(line.strip())
                if m:
                    names.add(m.group(1))
    except OSError:
        pass
    return names


def is_reserved(keyword):
    return (keyword or "").strip() in _reserved()

TEMPLATE = Template('''"""
hardHats crew: $TITLE (keyword `$KEYWORD`). $SUMMARY Deterministic (zero model calls), grounded in $STANDARD.

    python -m hardhats.crews $KEYWORD <path-or-dir> [--json] [--md out.md]

Exit 1 if the gate catches its defect.
"""
from __future__ import annotations

import os
import sys

# TODO(author): replace this marker rule with the real check your standard defines.
#   The skeleton flags a leftover marker so the seat runs and is testable the moment it is
#   minted. Swap it for the check that answers to $STANDARD, and keep the shape: read the
#   target, collect (finding, location) tuples, let a hard finding decide the verdict.
MARKERS = ("TODO", "FIXME", "XXX")
TEXT_EXT = (".py", ".js", ".ts", ".md", ".txt", ".html", ".css", ".yml", ".yaml")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def _scan_file(path, rel):
    found = []
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return found
    for i, line in enumerate(lines, 1):
        for mark in MARKERS:
            if mark in line:
                found.append((mark, "%s:%d" % (rel, i)))
    return found


def review(target, log=print):
    """Read the target, collect findings, return a dict. The "verdict" key is the contract."""
    findings, files = [], 0
    if os.path.isdir(target):
        for dp, dirs, fs in os.walk(target):
            dirs[:] = [d for d in dirs if d not in SKIP_DIR]
            for f in fs:
                if f.lower().endswith(TEXT_EXT):
                    files += 1
                    full = os.path.join(dp, f)
                    findings += _scan_file(full, os.path.relpath(full, target))
    elif os.path.isfile(target):
        files = 1
        findings += _scan_file(target, os.path.basename(target))
    # TODO(author): name the two states your standard draws the line between.
    verdict = "MARKERS PRESENT" if findings else "CLEAN"
    if log:
        print("$TITLE - $SUMMARY (zero model calls)")
        print("Target: %s   files read: %d\\n" % (target, files))
        if findings:
            for mark, loc in findings:
                print("  [FAIL] %-8s %s" % (mark, loc))
        else:
            print("  [ok]   no markers found")
        print("\\n--- not checked (and not a pass) ---")
        print("  - TODO(author): list what this gate does NOT prove, so a clear result is not a blank cheque")
        print("\\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "findings": findings, "files": files}


def _exit_code(verdict):
    # TODO(author): 1 only for the defect state; every other verdict clears.
    return 1 if verdict == "MARKERS PRESENT" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print("$KEYWORD: give a file or directory to gate", file=sys.stderr)
        return 2
    target = pos[0]
    if not os.path.exists(target):
        print("$KEYWORD: no such path: %s" % target, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, log=None)
        return _emit.emit("$KEYWORD", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(target, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(target)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
''')


def validate(keyword):
    """Raise ValueError if the keyword can't be a public seat; return it normalised otherwise."""
    kw = (keyword or "").strip()                       # strict: the keyword IS the seat name
    if not _VALID.match(kw):
        raise ValueError("keyword must be 2-16 chars, lowercase letters/digits, "
                         "starting with a letter: got %r" % keyword)
    if is_reserved(kw):
        raise ValueError("%r is a git-ignored name, so a public seat by that name would never "
                         "ship. Pick another." % kw)
    return kw


def render(keyword, title=None, standard=None, summary=None):
    """Return the source of a contract-passing seat. Pure - writes nothing."""
    kw = validate(keyword)
    summary = (summary or "TODO(author): one line of what this seat catches").strip()
    summary = summary.rstrip(".") + "."          # exactly one period, so the catalog cuts cleanly
    return TEMPLATE.safe_substitute(
        KEYWORD=kw,
        TITLE=title or ("THE %s CREW" % kw.upper()),
        STANDARD=standard or "TODO(author): the external standard this gate answers to",
        SUMMARY=summary,
    )


def _write_bytes(path, text):
    # temp file + os.replace so a half-write never truncates an existing file; bytes with
    # "\n" so minted seats are LF on every OS.
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def write(keyword, title=None, standard=None, summary=None, force=False, fixtures=True):
    """Write the seat (and its fixture pair). Return (seat_path, [fixture_paths])."""
    kw = validate(keyword)
    seat_path = os.path.join(CREWS, kw + ".py")
    if os.path.exists(seat_path) and not force:
        raise FileExistsError("%s already exists (pass --force to overwrite)" % seat_path)
    try:
        from hardhats.crews.__main__ import discover
        if kw in discover() and not force:
            raise FileExistsError("a seat already answers to %r (pass --force to overwrite)" % kw)
    except ImportError:
        pass
    _write_bytes(seat_path, render(kw, title, standard, summary))
    written = []
    fixdir = os.path.join(ROOT, "tests", "fixtures", kw)
    if fixtures and os.path.isdir(os.path.join(ROOT, "tests")):
        for sub, body in (("clean", "nothing to see here\n"),
                          ("markers", "code = 1  # TODO replace this with the real gate\n")):
            d = os.path.join(fixdir, sub)
            os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, "sample.txt")
            _write_bytes(fp, body)
            written.append(fp)
    return seat_path, written


def _usage():
    print(__doc__.strip(), file=sys.stderr)
    return 2


def main():
    args = sys.argv[1:]
    pos = [a for a in args if not a.startswith("--")]
    if not pos:
        return _usage()
    kw_raw = pos[0]

    def opt(name):
        return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None

    try:
        seat_path, fixtures = write(
            kw_raw,
            title=opt("--title"),
            standard=opt("--standard"),
            summary=opt("--summary"),
            force="--force" in args,
            fixtures="--no-fixtures" not in args,
        )
    except (ValueError, FileExistsError) as e:
        print("hardhats.new: %s" % e, file=sys.stderr)
        return 2

    kw = validate(kw_raw)
    if "--stdout" in args:
        print(render(kw, opt("--title"), opt("--standard"), opt("--summary")))
        return 0

    print("minted seat: %s" % seat_path)
    for fp in fixtures:
        print("  fixture:   %s" % fp)
    print("\nsummon it:   python -m hardhats.crews %s <path-or-dir>" % kw)
    print("see it json: python -m hardhats.crews %s <path> --json" % kw)
    print("\nto lock it into the bench suite, in tests/test_bench.py:")
    print("  1. add %r to the big `from hardhats.crews import (...)` line" % kw)
    print("  2. add %r to the Dispatcher expected set" % kw)
    print("  3. paste this test (it is green against the minted fixtures):\n")
    print("    def test_%s(self):" % kw)
    print("        self.assertEqual(%s.review(fx(%r, \"markers\"), log=None)[\"verdict\"], \"MARKERS PRESENT\")" % (kw, kw))
    print("        self.assertEqual(%s.review(fx(%r, \"clean\"), log=None)[\"verdict\"], \"CLEAN\")" % (kw, kw))
    print("\nthen replace the TODO(author) marker rule with your real check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
