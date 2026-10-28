"""
hardHats crew: the Licensing crew (keyword `license`). A FOSS licensing counsel's first
pass over a project: is a license declared, what is it (SPDX), does the declaration agree
with itself, and do any dependencies carry a copyleft obligation. Deterministic - zero
model calls - because an SPDX id, a present file and a dependency's license field are
facts, not opinions.

🛑 It REPORTS and SURFACES. It never PICKS a license, and it is not legal advice. Choosing
a license, and resolving any conflict, is the author's call and their counsel's. Anything
needing judgement routes to the `counsel` seat. This mirrors the deposit crew,
which reports the license and never chooses one.

    python -m hardhats.crews.licensing <project-dir> [--md out.md]

Exit 1 if the project is UNLICENSED or the declaration is INCONSISTENT.
"""
from __future__ import annotations

import json
import os
import re
import sys

# --- SPDX knowledge (small, explicit; not the whole registry) -------------------
STRONG_COPYLEFT = {"GPL-2.0", "GPL-3.0", "AGPL-3.0"}      # derivatives inherit the licence
WEAK_COPYLEFT = {"LGPL-2.1", "LGPL-3.0", "MPL-2.0", "EPL-2.0", "CDDL-1.0"}  # file/library level
PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Zlib"}
PUBLIC_DOMAIN = {"Unlicense", "CC0-1.0"}

# LICENSE-text fingerprints -> SPDX id. First match wins; order matters (AGPL before GPL).
FINGERPRINTS = [
    ("AGPL-3.0", "GNU AFFERO GENERAL PUBLIC LICENSE"),
    ("LGPL-3.0", "GNU LESSER GENERAL PUBLIC LICENSE"),
    ("GPL-3.0", "GNU GENERAL PUBLIC LICENSE"),          # version pinned below
    ("Apache-2.0", "Apache License"),
    ("MPL-2.0", "Mozilla Public License Version 2.0"),
    ("MIT", "Permission is hereby granted, free of charge"),
    ("BSD-3-Clause", "Neither the name of"),
    ("BSD-2-Clause", "Redistribution and use in source and binary forms"),
    ("ISC", "Permission to use, copy, modify, and/or distribute this software"),
    ("Unlicense", "released into the public domain"),
    ("CC0-1.0", "CC0 1.0 Universal"),
]

# OSI-approved options surfaced when NOTHING is declared. One line each, no recommendation.
OPTIONS = [
    ("MIT", "permissive; keep the copyright and notice, do almost anything else"),
    ("Apache-2.0", "permissive with an explicit patent grant; ships a NOTICE file"),
    ("BSD-3-Clause", "permissive; adds a no-endorsement clause"),
    ("MPL-2.0", "weak copyleft at the file level; mixes with closed code"),
    ("GPL-3.0", "strong copyleft; distributed derivatives must also be GPL"),
    ("AGPL-3.0", "strong copyleft that reaches network use (hosted apps too)"),
    ("Unlicense / CC0-1.0", "public-domain dedication; you keep no rights"),
]

LIC_FILES = ("license", "license.txt", "license.md", "licence", "licence.txt",
             "copying", "copying.txt", "unlicense")


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def detect_spdx(text):
    t = text.strip()
    if not t:
        return None
    m = re.search(r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+ ]+)", t)
    if m:
        return m.group(1).strip().split()[0]
    up = t.upper()
    for spdx, sig in FINGERPRINTS:
        if sig.upper() in up:
            if spdx == "GPL-3.0" and "VERSION 2" in up and "VERSION 3" not in up:
                return "GPL-2.0"
            return spdx
    return None


def license_files(root):
    out = []
    try:
        for name in os.listdir(root):
            if name.lower() in LIC_FILES or name.lower().startswith("license") \
                    or name.lower().startswith("licence") or name.lower().startswith("copying"):
                p = os.path.join(root, name)
                if os.path.isfile(p):
                    out.append(p)
    except OSError:
        pass
    return out


def declared_in_metadata(root):
    """License as the package manifests declare it. Returns list of (source, value)."""
    found = []
    pj = os.path.join(root, "package.json")
    if os.path.isfile(pj):
        try:
            data = json.loads(_read(pj) or "{}")
            lic = data.get("license") or data.get("licenses")
            if isinstance(lic, list):
                lic = ", ".join(x.get("type", str(x)) if isinstance(x, dict) else str(x) for x in lic)
            if lic:
                found.append(("package.json", str(lic)))
        except json.JSONDecodeError:
            found.append(("package.json", "(unparseable)"))
    py = os.path.join(root, "pyproject.toml")
    if os.path.isfile(py):
        txt = _read(py)
        m = re.search(r'(?mi)^\s*license\s*=\s*["\']?([^"\'\n{]+)', txt)
        if m:
            found.append(("pyproject.toml", m.group(1).strip()))
        for m in re.finditer(r'License\s*::\s*OSI Approved\s*::\s*([^"\']+)', txt):
            found.append(("pyproject classifier", m.group(1).strip()))
    for fn in ("setup.cfg", "Cargo.toml"):
        p = os.path.join(root, fn)
        if os.path.isfile(p):
            m = re.search(r'(?mi)^\s*license\s*=\s*["\']?([^"\'\n]+)', _read(p))
            if m:
                found.append((fn, m.group(1).strip()))
    return found


def dependency_licenses(root, cap=4000):
    """Best effort: licenses of INSTALLED deps whose metadata is in the tree."""
    seen = {}
    nm = os.path.join(root, "node_modules")
    if os.path.isdir(nm):
        for dirpath, dirs, files in os.walk(nm):
            if "package.json" in files and dirpath.count(os.sep) - nm.count(os.sep) <= 2:
                try:
                    d = json.loads(_read(os.path.join(dirpath, "package.json")) or "{}")
                    lic = d.get("license")
                    if isinstance(lic, (dict, list)):
                        lic = json.dumps(lic)
                    if d.get("name") and lic:
                        seen[d["name"]] = str(lic)
                except json.JSONDecodeError:
                    pass
            if len(seen) > cap:
                break
    for dirpath, dirs, files in os.walk(root):
        if dirpath.endswith((".dist-info", ".egg-info")):
            meta = _read(os.path.join(dirpath, "METADATA")) or _read(os.path.join(dirpath, "PKG-INFO"))
            m = re.search(r"(?mi)^License:\s*(.+)$", meta)
            nm2 = re.search(r"(?mi)^Name:\s*(.+)$", meta)
            if m and nm2:
                seen[nm2.group(1).strip()] = m.group(1).strip()
        dirs[:] = [x for x in dirs if x not in ("node_modules",)]
    return seen


def _copyleft_hits(dep_licenses):
    hits = []
    for name, lic in dep_licenses.items():
        up = lic.upper()
        for c in sorted(STRONG_COPYLEFT | WEAK_COPYLEFT):
            if c.upper().replace("-", "") in up.replace("-", "") or c.split("-")[0] in up:
                if "AGPL" in up or "GPL" in up or "MPL" in up or "LGPL" in up or "EPL" in up or "CDDL" in up:
                    hits.append((name, lic))
                    break
    # dedupe
    out, seen = [], set()
    for n, l in hits:
        if n not in seen:
            out.append((n, l)); seen.add(n)
    return out


def review(root, log=print):
    files = license_files(root)
    file_spdx = None
    for p in files:
        file_spdx = detect_spdx(_read(p))
        if file_spdx:
            break
    meta = declared_in_metadata(root)
    deps = dependency_licenses(root)
    copyleft = _copyleft_hits(deps)

    # consistency: does the metadata agree with the LICENSE file's detected id?
    meta_ids = [v for _s, v in meta]
    inconsistent = False
    if file_spdx and meta_ids:
        norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        inconsistent = not any(norm(file_spdx) in norm(v) or norm(v) in norm(file_spdx)
                               for v in meta_ids)

    unlicensed = not files and not meta
    verdict = ("UNLICENSED" if unlicensed else
               "INCONSISTENT" if inconsistent else
               "COPYLEFT OBLIGATION PRESENT" if copyleft else
               "DECLARED")

    if log:
        print("THE LICENSING CREW - reports and surfaces; never picks a licence (zero model calls)")
        print("Project: %s\n" % root)
        print("--- declared license (facts) ---")
        if files:
            print("  [ok]   LICENSE file: %s%s" % (os.path.basename(files[0]),
                  "  -> detected %s" % file_spdx if file_spdx else "  -> SPDX not auto-detected"))
        else:
            print("  [FLAG] no LICENSE / COPYING file in the project root")
        if meta:
            for s, v in meta:
                print("  [ok]   %s declares: %s" % (s, v))
        else:
            print("  [info] no license field in package.json / pyproject / setup.cfg / Cargo.toml")
        if inconsistent:
            print("  [FLAG] the LICENSE file (%s) and the manifest (%s) do not agree"
                  % (file_spdx, "; ".join(meta_ids)))
        print("\n--- dependencies (best effort) ---")
        if deps:
            print("  read licenses for %d installed dependency package(s)" % len(deps))
            if copyleft:
                print("  [FLAG] copyleft obligation in dependencies - review with counsel:")
                for n, l in copyleft[:12]:
                    print("     - %s: %s" % (n, l))
            else:
                print("  [ok]   no copyleft license seen among the dependencies read")
        else:
            print("  [info] no installed dependency metadata in this tree - dependency "
                  "licenses NOT evaluated (install deps, or point at a built tree)")
        if unlicensed:
            print("\n--- no license is declared. ALL RIGHTS RESERVED by default ---")
            print("  Nobody may legally copy, use, or build on this until you choose. If")
            print("  you WANT it open you must pick one; if you want it closed, that is the")
            print("  default. 🛑 This tool does not pick. Options, for you and counsel:")
            for spdx, note in OPTIONS:
                print("     - %-18s %s" % (spdx, note))
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the chosen license FITS the author's intent (that is counsel)")
        print("  - dual-licensing, patent and trademark terms, contributor agreements")
        print("  - per-file SPDX headers across the source, and vendored/bundled code")
        print("  - license COMPATIBILITY as a legal conclusion (flagged here, decided by counsel)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Reported, not chosen. Licence selection and any conflict route to `counsel`.")
    return {"verdict": verdict, "file_spdx": file_spdx, "metadata": meta,
            "dependencies": deps, "copyleft": copyleft, "unlicensed": unlicensed,
            "inconsistent": inconsistent}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("licensing: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("license", rep, 1 if rep["verdict"] in ("UNLICENSED", "INCONSISTENT") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return 1 if rep["verdict"] in ("UNLICENSED", "INCONSISTENT") else 0


if __name__ == "__main__":
    sys.exit(main())
