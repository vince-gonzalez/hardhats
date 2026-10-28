"""
Shared --json output for the bench seats, so coldHat / hardHats can CALL a seat and
read a machine-readable verdict instead of scraping a human CLI. One envelope for
every seat:

    {"seat": <keyword>, "verdict": <str>, "exit": <int>, "ok": <bool>, "detail": <report>}

`exit` is the exact code the seat would return from the shell (0 clears, 1 caught the
defect, 2 a usage/read error); `ok` is `exit == 0`; `detail` is the seat's full report
dict. A seat adds `--json` by calling emit() with its report and its own exit code, so
the verdict logic stays in one place - the seat - and is never duplicated here.
"""
from __future__ import annotations

import json
import sys


def _default(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def emit(seat, rep, code):
    """Print one JSON envelope to stdout and return the process exit code unchanged."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    envelope = {"seat": seat, "verdict": rep.get("verdict"), "exit": code,
                "ok": code == 0, "detail": rep}
    print(json.dumps(envelope, default=_default, ensure_ascii=False))
    return code
