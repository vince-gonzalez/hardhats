"""
hardHats crew: the Privacy crew (keyword `privacy`). An ed-tech privacy engineer's first pass:
what personal data does this collect, does it touch children or students (COPPA / FERPA), and is
there any notice or consent anywhere to cover it? Deterministic (zero model calls); name-based.

🛑 This is a SIGNAL scanner, not legal advice and not a data-flow proof. It finds field names and
keywords - "student_email", "date_of_birth", "consent" - and tells you where collecting a child's
data meets no visible policy. Whether a given flow is lawful, and whether a policy is sufficient,
is a privacy attorney's call: route to `counsel` / real counsel.

    python -m hardhats.crews.privacy <dir-or-file> [--md out.md]

Exit 1 if child/student PII signals are present with NO visible privacy policy or consent.
"""
from __future__ import annotations

import os
import re
import sys

TEXT_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json", ".sql",
            ".html", ".htm", ".yaml", ".yml", ".toml", ".env", ".md", ".txt", ".csv")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}

PII = [
    ("email", re.compile(r"\be[- ]?mail\b", re.I)),
    ("name", re.compile(r"\b(?:first[_ ]?name|last[_ ]?name|full[_ ]?name|surname|given[_ ]?name)\b", re.I)),
    ("date of birth / age", re.compile(r"\b(?:date[_ ]?of[_ ]?birth|birth[_ ]?date|birthday|\bdob\b|\bage\b)\b", re.I)),
    ("phone", re.compile(r"\b(?:phone|telephone|mobile[_ ]?number|cell[_ ]?phone)\b", re.I)),
    ("postal address", re.compile(r"\b(?:street[_ ]?address|postal[_ ]?code|zip[_ ]?code|zipcode|mailing[_ ]?address)\b", re.I)),
    ("government id", re.compile(r"\b(?:\bssn\b|social[_ ]?security|passport[_ ]?(?:no|number)|national[_ ]?id|driver'?s?[_ ]?licen[sc]e)\b", re.I)),
    ("precise location", re.compile(r"\b(?:geolocation|gps[_ ]?coord|lat(?:itude)?[_ ]?long|coordinates)\b", re.I)),
    ("ip address", re.compile(r"\b(?:ip[_ ]?address|ipaddr|remote[_ ]?addr)\b", re.I)),
]
MINOR_EDU = re.compile(
    r"\b(?:student|pupil|parent|guardian|minor|child(?:ren)?|kindergarten|k-?12|classroom|"
    r"teacher|transcript|school|grade[_ ]?level|education[_ ]?record|under[_ ]?13)\b", re.I)
INFRA = re.compile(
    r"\b(?:consent|opt[- ]?in|parental[_ ]?consent|privacy[_ ]?policy|data[_ ]?retention|"
    r"right[_ ]?to[_ ]?be[_ ]?forgotten|erasure|\bgdpr\b|\bcoppa\b|\bferpa\b|age[_ ]?gate|"
    r"data[_ ]?deletion|verifiable[_ ]?parental)\b", re.I)
RULEDEF = re.compile(r"re\.compile\(|\br['\"]")


def review(root, log=print):
    is_file = os.path.isfile(root)
    targets, policy_files = [], []
    if is_file:
        targets = [root]
    else:
        for dp, dirs, fs in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIR]
            for f in fs:
                if "privacy" in f.lower():
                    policy_files.append(os.path.relpath(os.path.join(dp, f), root))
                if f.lower().endswith(TEXT_EXT):
                    targets.append(os.path.join(dp, f))

    pii_hits = {}          # category -> first "file:line"
    minor_hit = infra_hit = None
    files = 0
    base = root if not is_file else os.path.dirname(root)
    for p in targets:
        files += 1
        try:
            lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        rel = os.path.relpath(p, base)
        for i, line in enumerate(lines, 1):
            if RULEDEF.search(line):
                continue
            # field names are usually snake_case; treat '_' as a word break so
            # student_email / home_address / user_phone are seen, not missed.
            scan = line.replace("_", " ")
            for cat, rx in PII:
                if cat not in pii_hits and rx.search(scan):
                    pii_hits[cat] = "%s:%d" % (rel, i)
            if minor_hit is None and MINOR_EDU.search(scan):
                minor_hit = "%s:%d" % (rel, i)
            if infra_hit is None and INFRA.search(scan):
                infra_hit = "%s:%d" % (rel, i)

    has_infra = bool(policy_files) or infra_hit is not None
    verdict = ("PRIVACY RISK - child/student data with no visible policy or consent"
               if (minor_hit and pii_hits and not has_infra) else
               "REVIEW - personal data present" if pii_hits else
               "NO PII SIGNALS")
    if log:
        print("THE PRIVACY CREW - COPPA / FERPA signal scan (zero model calls; NOT legal advice)")
        print("files: %d\n" % files)
        print("--- personal data collected (by field name) ---")
        if pii_hits:
            for cat, loc in pii_hits.items():
                print("  [data] %-20s first seen %s" % (cat, loc))
        else:
            print("  [ok]   no personal-data field names found")
        print("\n--- children / students in scope (COPPA / FERPA trigger) ---")
        print("  %s" % ("[FLAG] child/student/school signal at %s" % minor_hit if minor_hit
                        else "[ok]   no child/student/school signal"))
        print("\n--- notice & consent present anywhere? ---")
        if policy_files:
            print("  [ok]   privacy policy file(s): %s" % ", ".join(policy_files[:5]))
        if infra_hit:
            print("  [ok]   consent / policy / deletion keyword at %s" % infra_hit)
        if not has_infra:
            print("  [FAIL] no privacy policy file, no consent / retention / deletion keyword anywhere")
        print("\n--- not checked (and NOT a pass) ---")
        print("  - whether data is ACTUALLY collected, stored, or shared (names, not data flows)")
        print("  - whether a policy that exists is SUFFICIENT or truthful (a privacy attorney)")
        print("  - verifiable parental consent mechanics, data-processing agreements, breach duties")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Signals only. Lawfulness is counsel's call; route to `counsel` / a privacy attorney.")
    return {"verdict": verdict, "pii": pii_hits, "minor": minor_hit,
            "infra": infra_hit, "policy_files": policy_files}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.exists(root):
        print("privacy: no such path: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("privacy", rep, 1 if rep["verdict"].startswith("PRIVACY RISK") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return 1 if rep["verdict"].startswith("PRIVACY RISK") else 0


if __name__ == "__main__":
    sys.exit(main())
