"""
hardHats crews - the keyword dispatcher. One door to the whole bench.

    python -m hardhats.crews                 # list every summonable seat
    python -m hardhats.crews <keyword> ...   # summon that seat (args pass straight through)
    python -m hardhats.crews geom "2*pi/sqrt(27) < 1.2092"
    python -m hardhats.crews <keyword> ... --json   # one machine-readable verdict envelope

Add --json to any seat and it prints a single envelope - {"seat", "verdict", "exit", "ok",
"detail"} - instead of the human report, so coldHat / hardHats can CALL a seat and read the
result. "exit" is the same code the seat returns from the shell (0 clears, 1 caught the defect,
2 a usage/read error); "detail" is the seat's full report.

Each seat is a self-contained crew: a world-class professional role whose verdict answers to a
real external STANDARD (its gate), not to opinion. Discovery is automatic - any module in this
package whose docstring declares a (keyword `x`) tag registers itself here, so the bench grows
without editing this file. Modules with no keyword tag (the multi-model panels and the older
workflow crews) are run on their own, not via quick summon - a panel convenes several models
and is a deliberate call.
"""
from __future__ import annotations

import importlib
import os
import re
import sys

_DIR = os.path.dirname(__file__)
_KW = re.compile(r"keyword `([^`]+)`")
_SKIP = {"__main__.py", "__init__.py"}


def discover():
    """keyword -> (module_name, one-line summary), parsed from each sibling's docstring."""
    reg = {}
    for fn in sorted(os.listdir(_DIR)):
        if not fn.endswith(".py") or fn.startswith("_") or fn in _SKIP:
            continue
        try:
            src = open(os.path.join(_DIR, fn), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        doc = re.search(r'"""(.*?)"""', src, re.S)
        if not doc:
            continue
        m = _KW.search(doc.group(1))
        if not m:
            continue
        after = doc.group(1)[m.end():]           # skip past the "(keyword `x`[, "ALIAS"])" close
        close = after.find(")")
        tail = (after[close + 1:] if close != -1 else after).lstrip(".  \t\r\n")
        summary = re.sub(r"\s+", " ", tail.split(". ")[0]).strip()
        reg[m.group(1)] = (fn[:-3], summary)
    return reg


def _list(reg):
    print("hardHats crews - %d summonable seats (keyword -> what it gates)\n" % len(reg))
    for kw in sorted(reg):
        mod, summary = reg[kw]
        if len(summary) > 96:
            summary = summary[:93] + "..."
        print("  %-10s %s" % (kw, summary))
    print("\n  summon:  python -m hardhats.crews <keyword> [args...]")
    print("  add --json to any seat for a machine-readable verdict envelope {seat, verdict, exit, ok, detail}.")
    print("  (multi-model panels and the older workflow crews are run on their own.)")


def main():
    reg = discover()
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "list", "--list"):
        _list(reg)
        return 0
    kw = argv[0]
    if kw not in reg and (os.path.exists(kw) or re.match(r"^https?://", kw, re.I)):
        kw = "route"                       # a bare path or url dispatches by artifact type
        argv = ["route"] + argv
    if kw not in reg:
        print("unknown seat %r.\nknown: %s" % (kw, ", ".join(sorted(reg))), file=sys.stderr)
        return 2
    mod, _ = reg[kw]
    module = importlib.import_module("hardhats.crews." + mod)
    if not hasattr(module, "main"):
        print("seat %r (module %s) has no main()" % (kw, mod), file=sys.stderr)
        return 2
    sys.argv = ["python -m hardhats.crews " + kw] + argv[1:]
    return module.main()


if __name__ == "__main__":
    sys.exit(main())
