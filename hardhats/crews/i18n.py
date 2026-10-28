"""
hardHats crew: the i18n crew (keyword `i18n`). A localization engineer's read on a set of
JSON locale files: does every locale carry the same keys as the base, do the placeholders
match, and are any values empty. Deterministic (zero model calls). Unicode CLDR / ICU /
BCP 47 grounded.

A missing key is a blank screen in that language; a dropped placeholder is a message that
renders "Hello " with no name. Those are facts a diff can settle. Whether the TRANSLATION
is good is a human's call.

    python -m hardhats.crews.i18n <dir-of-locale-json> [--base en] [--md out.md]

Looks for <code>.json files (en.json, de.json, ...) or locales/<code>/*.json. Exit 1 if a
locale is missing keys or has mismatched placeholders.
"""
from __future__ import annotations

import json
import os
import re
import sys

PLACEHOLDER = re.compile(r"\{\{?\s*[\w.]+\s*\}?\}|%[sd]|%\d*\$[sd]|\{\d+\}")
BCP47 = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?(-[A-Za-z]{2}|-\d{3})?$")


def _flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, prefix + k + "."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, prefix + str(i) + "."))
    else:
        out[prefix.rstrip(".")] = obj
    return out


def _placeholders(s):
    return sorted(set(PLACEHOLDER.findall(str(s)))) if isinstance(s, str) else []


def _find_locales(root):
    found = {}
    for f in os.listdir(root):
        p = os.path.join(root, f)
        if os.path.isfile(p) and f.endswith(".json"):
            code = f[:-5]
            if BCP47.match(code):
                found[code] = p
    loc = os.path.join(root, "locales")
    if os.path.isdir(loc):
        for code in os.listdir(loc):
            d = os.path.join(loc, code)
            if os.path.isdir(d) and BCP47.match(code):
                js = [x for x in os.listdir(d) if x.endswith(".json")]
                if js:
                    found[code] = os.path.join(d, js[0])
    return found


def review(root, base=None, log=print):
    locs = _find_locales(root)
    data = {}
    for code, p in locs.items():
        try:
            data[code] = _flatten(json.loads(open(p, encoding="utf-8-sig", errors="replace").read()))
        except json.JSONDecodeError:
            data[code] = None
    base = base or ("en" if "en" in data else (max(data, key=lambda c: len(data[c] or {})) if data else None))
    findings = {}
    if base and data.get(base):
        bkeys = set(data[base])
        for code, d in data.items():
            if code == base or d is None:
                continue
            missing = sorted(bkeys - set(d))
            extra = sorted(set(d) - bkeys)
            empty = sorted(k for k, v in d.items() if v == "" or v is None)
            ph = [k for k in (bkeys & set(d))
                  if _placeholders(data[base][k]) != _placeholders(d[k])]
            findings[code] = {"missing": missing, "extra": extra, "empty": empty, "ph": ph}
    bad = any(f["missing"] or f["ph"] for f in findings.values())
    unparsable = [c for c, d in data.items() if d is None]
    verdict = ("NO LOCALE FILES" if not locs else
               "UNPARSABLE JSON" if unparsable else
               "NO BASE" if not (base and data.get(base)) else
               "GAPS" if bad else "PARITY")
    if log:
        print("THE i18n CREW - locale key parity + placeholders (zero model calls)")
        print("Dir: %s\n" % root)
        print("locales found: %s   base: %s" % (", ".join(sorted(locs)) or "(none)", base))
        if unparsable:
            print("  [FAIL] unparsable JSON: %s" % ", ".join(unparsable))
        print("")
        for code in sorted(findings):
            f = findings[code]
            if f["missing"] or f["ph"] or f["extra"] or f["empty"]:
                print("  [%s] %s:" % ("FAIL" if (f["missing"] or f["ph"]) else "flag", code))
                if f["missing"]:
                    print("        missing %d key(s): %s" % (len(f["missing"]), ", ".join(f["missing"][:8])))
                if f["ph"]:
                    print("        placeholder mismatch in %d key(s): %s" % (len(f["ph"]), ", ".join(f["ph"][:8])))
                if f["extra"]:
                    print("        %d extra key(s) not in base: %s" % (len(f["extra"]), ", ".join(f["extra"][:6])))
                if f["empty"]:
                    print("        %d empty value(s)" % len(f["empty"]))
            else:
                print("  [ok]   %s: full parity with %s" % (code, base))
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the TRANSLATION is correct or natural (a human / native speaker)")
        print("  - gender, plural and ICU select rules beyond placeholder names")
        print("  - .po / .properties / page-generated i18n (this reads JSON locale files)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Parity facts only. Translation quality is a human's call.")
    return {"verdict": verdict, "locales": sorted(locs), "base": base, "findings": findings}


def main():
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else None
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a not in (base, md_out)]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("i18n: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, base, log=None)
        return _emit.emit("i18n", rep, 1 if rep["verdict"] == "GAPS" else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, base, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root, base)
    return 1 if rep["verdict"] == "GAPS" else 0


if __name__ == "__main__":
    sys.exit(main())
