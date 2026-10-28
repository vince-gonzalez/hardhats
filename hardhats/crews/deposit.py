"""
hardHats crew: the Deposit crew. Readiness check before a Zenodo (or any immutable)
deposit. All deterministic - it runs with zero model calls, because a hash and a
missing field are facts, not opinions. Zenodo is immutable: a deposit cannot be
edited after publishing, so the check belongs BEFORE the button.

It hashes the bytes that will ship, confirms the citation metadata carries the
fields a record needs, and reports the license field - it REPORTS it, it does not
pick one; the license is the author's call, never the tool's.

    python -m hardhats.crews.deposit <file-to-deposit> [--meta CITATION.cff|metadata.json]

Exit 1 if not ready.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

# A citable record generally needs these. "license" is checked for PRESENCE and its
# value is reported - the crew never recommends which license to use.
REQUIRED = ["title", "authors|creators", "license", "version"]
WANTED = ["orcid", "description|abstract", "doi", "keywords"]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_meta(path: str) -> tuple:
    """Return (text, dict-or-None). .json is parsed; .cff/other scanned as text."""
    text = open(path, encoding="utf-8", errors="replace").read()
    if path.lower().endswith(".json"):
        try:
            return text, json.loads(text)
        except json.JSONDecodeError:
            return text, None
    return text, None


def field_present(key_spec: str, text: str, data) -> bool:
    keys = key_spec.split("|")
    if isinstance(data, dict):
        flat = {k.lower() for k in _keys(data)}
        if any(k in flat for k in keys):
            return True
    low = text.lower()
    return any(re.search(rf"(^|[\s\"']){re.escape(k)}\s*[:=]", low, re.M) for k in keys)


def _keys(d, out=None):
    out = out if out is not None else []
    if isinstance(d, dict):
        for k, v in d.items():
            out.append(k)
            _keys(v, out)
    elif isinstance(d, list):
        for v in d:
            _keys(v, out)
    return out


def license_value(text: str, data) -> str:
    if isinstance(data, dict):
        for k in _keys(data):
            if k.lower() == "license":
                v = data
                break
    m = re.search(r"(?im)^\s*license\s*[:=]\s*[\"']?([A-Za-z0-9.\- ]+)", text)
    return m.group(1).strip() if m else "(present, value not parsed)"


def review(target, meta=None, log=print):
    if not os.path.isfile(target):
        return {"error": f"not a file: {target}"}
    digest = sha256(target)
    size = os.path.getsize(target)
    checks = [("sha256 of the bytes that ship", f"{digest}  ({size} bytes)")]
    ready = True
    if meta and os.path.isfile(meta):
        text, data = load_meta(meta)
        for spec in REQUIRED:
            ok = field_present(spec, text, data)
            checks.append((f"required: {spec}", "PASS" if ok else "MISSING"))
            ready = ready and ok
        for spec in WANTED:
            ok = field_present(spec, text, data)
            checks.append((f"wanted:   {spec}", "ok" if ok else "absent (optional)"))
        lic = license_value(text, data) if field_present("license", text, data) else None
        checks.append(("license (reported, not chosen)",
                       lic if lic else "MISSING - the author must set one; the crew will not pick it"))
    else:
        checks.append(("metadata", "no --meta supplied; cannot check citation fields"))
        ready = False
    if log:
        for name, res in checks:
            flag = "FAIL" if ("MISSING" in res) else ("info" if res and res[0].islower() or "sha256" in name or "license" in name or "no --meta" in name else "PASS")
            print(f"  [{flag:4}] {name}: {res}")
    return {"target": target, "sha256": digest, "checks": checks, "ready": ready,
            "meta": meta}


def main():
    args = sys.argv[1:]
    meta = None
    if "--meta" in args:
        meta = args[args.index("--meta") + 1]
    pos = [a for a in args if not a.startswith("--") and a != meta]
    if not pos:
        print("usage: python -m hardhats.crews.deposit <file> [--meta CITATION.cff|metadata.json]")
        return 2
    target = pos[0]
    print("THE DEPOSIT CREW - readiness before an immutable deposit (zero model calls)")
    print(f"To deposit: {target}\n")
    rep = review(target, meta)
    if "error" in rep:
        print(rep["error"])
        return 2
    print()
    if rep["ready"]:
        print("  READY - bytes hashed, required citation fields present.")
        print("  Reminder: Zenodo is immutable once published; deposit the content, not just a title.")
        return 0
    print("  NOT READY - supply --meta and fill the MISSING required fields above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
