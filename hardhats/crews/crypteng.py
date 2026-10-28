"""
hardHats crew: the Crypteng crew (keyword `crypteng`). A security engineer's scan for the
two things that sink a codebase: a secret committed in the clear, and crypto that is broken
by design. Deterministic (zero model calls).

🛑 It REDACTS. It reports the TYPE and the file:line of a secret, never the secret itself.
It does not read git history, judge entropy, or know whether a key is still live - say what
it found, let a human rotate. Rotation and real crypto review route to a human / `counsel`.

    python -m hardhats.crews.crypteng <project-dir> [--md out.md]

Exit 1 if a hardcoded secret is found.
"""
from __future__ import annotations

import os
import re
import sys

SECRETS = [
    ("Stripe live key", re.compile(r"sk_live_[0-9A-Za-z]{10,}")),
    ("Stripe test key", re.compile(r"sk_test_[0-9A-Za-z]{10,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"\b(gh[pousr]_[0-9A-Za-z]{20,}|github_pat_[0-9A-Za-z_]{20,})")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z\-_]{30,}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("secret assignment", re.compile(r"(?i)(api[_-]?key|secret|token|passwd|password|access[_-]?key)"
                                     r"\s*[:=]\s*[\"'][^\"'\s]{12,}[\"']")),
]
WEAK = [
    ("MD5 (broken hash)", re.compile(r"(?i)\bmd5\s*\(|hashlib\.md5|MD5\.new")),
    ("SHA-1 (broken hash)", re.compile(r"(?i)\bsha1\s*\(|hashlib\.sha1")),
    ("DES / 3DES (broken cipher)", re.compile(r"\b(DES|TripleDES|3DES)\b")),
    ("ECB mode (leaks structure)", re.compile(r"MODE_ECB|\bECB\b")),
    ("insecure RNG for a secret", re.compile(r"(?i)\brandom\.(random|randint|choice|getrandbits)\b"
                                             r"[^\n]{0,40}(token|secret|key|password|nonce|salt|otp)")),
    ("TLS verification disabled", re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false|"
                                             r"CERT_NONE|_create_unverified_context")),
]
TEXT_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".jsx", ".tsx",
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".sh", ".ps1",
            ".rb", ".go", ".java", ".php", ".html", ".txt", ".md", ".properties", ".xml")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}


def _redact(s):
    s = s.strip().strip("\"'")
    return (s[:4] + "..redacted(%d)" % len(s)) if len(s) > 6 else "..redacted"


def review(root, log=print):
    secrets, weak = [], []
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in files:
            if not f.lower().endswith(TEXT_EXT):
                continue
            if f.endswith((".example", ".sample", ".dist")) or f in ("package-lock.json", "yarn.lock"):
                continue
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > 2_000_000:
                    continue
                lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
            except OSError:
                continue
            rel = os.path.relpath(p, root)
            for i, line in enumerate(lines, 1):
                if "re.compile(" in line or re.search(r"\br['\"]", line):
                    continue   # skip rule/regex definition lines: a scanner must not flag its own patterns
                for name, rx in SECRETS:
                    m = rx.search(line)
                    if m:
                        secrets.append((name, "%s:%d" % (rel, i), _redact(m.group(0))))
                for name, rx in WEAK:
                    if rx.search(line):
                        weak.append((name, "%s:%d" % (rel, i)))
    verdict = "EXPOSED" if secrets else ("WEAK CRYPTO" if weak else "CLEAN (automated)")
    if log:
        print("THE CRYPTENG CREW - secrets + broken-crypto scan (zero model calls; values REDACTED)")
        print("Project: %s\n" % root)
        print("--- hardcoded secrets ---")
        if secrets:
            for name, loc, red in secrets[:40]:
                print("  [FAIL] %s at %s  (%s)" % (name, loc, red))
            print("  🛑 rotate anything real IMMEDIATELY - a committed secret is compromised, "
                  "even after you delete it (git history keeps it).")
        else:
            print("  [ok]   no hardcoded secret pattern found")
        print("\n--- broken / misused crypto ---")
        if weak:
            for name, loc in weak[:40]:
                print("  [flag] %s at %s" % (name, loc))
        else:
            print("  [ok]   no broken-crypto pattern found")
        print("\n--- not checked (and not a pass) ---")
        print("  - git HISTORY (a secret removed from HEAD is still in the log, still compromised)")
        print("  - entropy-based detection of secrets that match no known prefix")
        print("  - whether a flagged key is live, and whether it was ever rotated")
        print("  - whether the crypto is correct beyond these known-bad patterns")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Patterns only. Rotation and a real crypto review are a human's; route to `counsel`.")
    return {"verdict": verdict, "secrets": secrets, "weak": weak}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("crypteng: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("crypteng", rep, 1 if rep["verdict"] == "EXPOSED" else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return 1 if rep["verdict"] == "EXPOSED" else 0


if __name__ == "__main__":
    sys.exit(main())
