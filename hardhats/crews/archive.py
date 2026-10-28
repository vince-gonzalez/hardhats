"""
hardHats crew: the Archive crew (keyword `archive`). A digital-preservation read on an
artifact: can its integrity be verified (fixity), is it in formats that will still open in
ten years, and does it carry the metadata and license a repository needs. Deterministic
(zero model calls); OAIS / FAIR grounded.

It reports what preservation needs and what is missing. It does not deposit anything, and
it does not judge whether the content is worth keeping - that is the author's call. Pairs
with the `deposit` crew (which checks citation-readiness).

    python -m hardhats.crews.archive <dir> [--md out.md]

Exit 1 if integrity cannot be verified (no fixity) or at-risk proprietary formats dominate.
"""
from __future__ import annotations

import json
import os
import re
import sys

FIXITY = ("sha256sums", "sha256sum.txt", "checksums.txt", "manifest-sha256.txt",
          "md5sums", "sha1sums")
META = ("datapackage.json", "codemeta.json", "CITATION.cff", "metadata.json",
        "ro-crate-metadata.json", "README", "README.md")
LICENSES = ("license", "license.txt", "license.md", "licence", "copying")
OPEN_EXT = {".csv", ".json", ".txt", ".md", ".xml", ".pdf", ".png", ".tif", ".tiff",
            ".wav", ".flac", ".html", ".svg", ".yaml", ".yml", ".jsonl", ".parquet"}
ATRISK_EXT = {".doc", ".xls", ".ppt", ".psd", ".ai", ".dwg", ".rar", ".sketch",
              ".indd", ".cdr", ".wpd"}


def _find(root, names):
    try:
        low = {f.lower(): f for f in os.listdir(root)}
    except OSError:
        return []
    return [low[n] for n in names if n in low]


def _has_datapackage_hashes(root):
    p = os.path.join(root, "datapackage.json")
    if os.path.isfile(p):
        try:
            d = json.loads(open(p, encoding="utf-8", errors="replace").read())
        except json.JSONDecodeError:
            return False
        return any(("hash" in (r or {})) for r in (d.get("resources") or []))
    return False


def review(root, log=print):
    fixity = _find(root, FIXITY) + ([".sha256 file(s)"] if any(
        f.endswith(".sha256") for f in os.listdir(root)) else [])
    if _has_datapackage_hashes(root):
        fixity.append("datapackage.json (per-resource hash)")
    meta = _find(root, [m.lower() for m in META])
    license_ = _find(root, LICENSES)

    open_n = atrisk_n = other_n = 0
    atrisk = []
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in OPEN_EXT:
                open_n += 1
            elif ext in ATRISK_EXT:
                atrisk_n += 1
                atrisk.append(f)
            else:
                other_n += 1

    no_fixity = not fixity
    atrisk_dominant = atrisk_n > open_n and atrisk_n > 0
    verdict = ("GAPS - integrity cannot be verified (no fixity)" if no_fixity else
               "GAPS - at-risk formats dominate" if atrisk_dominant else
               "PRESERVABLE, with gaps" if (not meta or not license_) else
               "PRESERVABLE")
    if log:
        print("THE ARCHIVE CREW - digital-preservation read (OAIS / FAIR; zero model calls)")
        print("Artifact: %s\n" % root)
        print("--- fixity (can integrity be checked?) ---")
        if fixity:
            print("  [ok]   %s" % ", ".join(fixity))
        else:
            print("  [FAIL] no checksum manifest - a reader cannot tell if a file was corrupted or altered")
        print("\n--- formats (will it still open in ten years?) ---")
        print("  open/archival: %d   at-risk/proprietary: %d   other: %d" % (open_n, atrisk_n, other_n))
        if atrisk:
            print("  [flag] at-risk formats present: %s" % ", ".join(sorted(set(atrisk))[:8]))
        print("\n--- metadata & rights ---")
        print("  %s descriptive metadata%s" % ("[ok]  " if meta else "[flag]",
              " (%s)" % ", ".join(meta[:3]) if meta else " - no datapackage / codemeta / CITATION / README"))
        print("  %s license%s" % ("[ok]  " if license_ else "[flag]",
              " (%s)" % license_[0] if license_ else " - absent (reuse rights undefined)"))
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the checksums actually MATCH the files (this checks presence, not integrity)")
        print("  - whether a proprietary format has an open equivalent already beside it")
        print("  - fixity of files inside archives (zip/tar), and external links rotting")
        print("  - Zenodo / submission-readiness is a deposit-level check, not local OAIS:")
        print("    authorecon's `zenodo-precheck` and `deposit-lint`")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Preservation-readiness only. What is worth keeping is the author's call; pairs with `deposit`.")
    return {"verdict": verdict, "fixity": fixity, "meta": meta, "license": license_,
            "open": open_n, "atrisk": atrisk_n}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("archive: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("archive", rep, 1 if rep["verdict"].startswith("GAPS") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return 1 if rep["verdict"].startswith("GAPS") else 0


if __name__ == "__main__":
    sys.exit(main())
