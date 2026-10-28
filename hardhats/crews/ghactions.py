"""
hardHats crew: the GitHub Actions crew (keyword `ghactions`). CI-workflow security - the ways a
.github/workflows file can hand an attacker your token, graded against GitHub's own hardening guide.

Deterministic (zero model calls). It reads <repo>/.github/workflows/*.yml (or the files in a dir
you point it at) and catches the public incident classes:

  - script injection: an untrusted ${{ github.event.* }} / ${{ github.head_ref }} value
    interpolated straight into a `run:` shell step  (arbitrary command execution)       [FAIL]
  - pwn-request: a `pull_request_target` workflow that checks out the PR's own head
    (untrusted code run with the repo's write token + secrets)                          [FAIL]
  - a `uses:` pinned to a MUTABLE branch (@main / @master / @HEAD)                      [FAIL]
  - a third-party `uses:` pinned to a tag, not a 40-char commit SHA  (supply chain)     [flag]
  - no top-level `permissions:` block  (least privilege not set)                        [flag]
  - ${{ secrets.* }} interpolated inside a `run:` line  (may land in a log)             [flag]

🛑 It flags the PATTERN and the file:line; it does not prove a given event is actually reachable
by an outside attacker, and a SHA pins an action's ref without vetting its code - both are the
reviewer's call.

    python -m hardhats.crews.ghactions <repo-or-workflows-dir> [--json] [--md out.md]

Exit 1 if a run: injection, a pull_request_target checkout of the PR head, or a mutable-branch
pin is found.
"""
from __future__ import annotations

import os
import re
import sys

SHA40 = re.compile(r"^[0-9a-f]{40}$")
FIRST_PARTY = {"actions", "github"}            # GitHub-owned; tags on these are accepted, not flagged
BRANCHY = {"main", "master", "head", "develop", "dev", "trunk", "latest"}

# ${{ ... }} expressions GitHub documents as attacker-controlled (script-injection sources).
UNTRUSTED = re.compile(
    r"github\.event\.(issue\.(title|body)"
    r"|pull_request\.(title|body)"
    r"|pull_request\.head\.(ref|label)"
    r"|pull_request\.head\.repo\.(default_branch|description|homepage)"
    r"|comment\.body|review\.body|review_comment\.body"
    r"|commits\b[^}]*?\.(message|author\.(email|name))"
    r"|head_commit\.(message|author\.(email|name))"
    r"|pages\b[^}]*?\.page_name"
    r"|discussion\.(title|body)|discussion_comment\.body)"
    r"|github\.head_ref")

EXPR = re.compile(r"\$\{\{(.*?)\}\}")
USES = re.compile(r"""(?:-\s+)?uses:\s*([^\s@'"]+)@([^\s#'"]+)""")
CHECKOUT_UNTRUSTED = re.compile(
    r"ref:\s*.*(github\.event\.pull_request\.head|github\.head_ref"
    r"|github\.event\.pull_request\.number)")


def _trim(s, n=58):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n] + "..."


def _runs(lines):
    """Yield (lineno, text) for every line that is part of a `run:` step body - the inline value,
    or, for a `run: |` / `run: >` block scalar, the more-indented body lines beneath it."""
    i, n = 0, len(lines)
    while i < n:
        m = re.match(r"(\s*)(?:-\s+)?run:\s*(.*)$", lines[i])
        if m:
            indent, rest = len(m.group(1)), m.group(2)
            if rest.startswith(("|", ">")):
                j = i + 1
                while j < n:
                    body = lines[j]
                    if body.strip() == "":
                        j += 1
                        continue
                    if len(body) - len(body.lstrip()) <= indent:
                        break
                    yield (j + 1, body)
                    j += 1
                i = j
                continue
            if rest:
                yield (i + 1, rest)
        i += 1


def scan_file(path, rel):
    hard, flags = [], []
    try:
        raw = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return hard, flags
    lines = raw.splitlines()

    # 1. script injection + secrets, over run: step bodies only
    for ln, body in _runs(lines):
        loc = "%s:%d" % (rel, ln)
        for expr in EXPR.findall(body):
            if UNTRUSTED.search(expr):
                hard.append(("script injection: untrusted ${{ %s }} in run:" % _trim(expr), loc))
            elif "github.event." in expr:
                flags.append(("other github.event field in a run:  ${{ %s }}" % _trim(expr), loc))
            if re.search(r"\bsecrets\.", expr):
                flags.append(("secret interpolated into a run: line (may land in logs)", loc))

    # 2. uses: pinning
    for i, line in enumerate(lines, 1):
        m = USES.search(line)
        if not m:
            continue
        repo, ref = m.group(1), m.group(2)
        if repo.startswith((".", "docker://")):
            continue
        owner = repo.split("/")[0].lower()
        loc = "%s:%d" % (rel, i)
        if ref.lower() in BRANCHY:
            hard.append(("uses a MUTABLE branch ref: %s@%s" % (repo, ref), loc))
        elif SHA40.match(ref):
            pass
        elif owner not in FIRST_PARTY:
            flags.append(("third-party action pinned to a tag, not a SHA: %s@%s" % (repo, ref), loc))

    # 3. pull_request_target + untrusted checkout (pwn-request)
    if re.search(r"(^|\s)pull_request_target\b", raw):
        if CHECKOUT_UNTRUSTED.search(raw):
            hard.append(("pull_request_target checks out the PR head - untrusted code with the "
                         "write token + secrets", rel))
        elif re.search(r"uses:\s*actions/checkout", raw):
            flags.append(("pull_request_target with a checkout - confirm it is the BASE, not the "
                          "PR head", rel))
        else:
            flags.append(("pull_request_target grants a write token + secrets - confirm least "
                          "privilege", rel))

    # 4. least-privilege permissions
    if not re.search(r"^permissions:", raw, re.M) and not re.search(r"^\s+permissions:", raw, re.M):
        flags.append(("no permissions: block - the workflow runs with the repo default token scope",
                      rel))

    return hard, flags


def _workflow_files(root):
    wf = os.path.join(root, ".github", "workflows")
    base = wf if os.path.isdir(wf) else root
    try:
        names = os.listdir(base)
    except OSError:
        names = []
    return sorted(os.path.join(base, f) for f in names
                  if f.lower().endswith((".yml", ".yaml"))), base


def review(root, log=print):
    files, base = _workflow_files(root)
    hard, flags = [], []
    for p in files:
        h, fl = scan_file(p, os.path.relpath(p, root))
        hard += h
        flags += fl
    verdict = ("NO WORKFLOWS FOUND" if not files else
               "WORKFLOW INJECTION RISK" if hard else
               "REVIEW - hardening gaps present" if flags else
               "WORKFLOWS HARDENED")
    if log:
        print("THE GHACTIONS CREW - CI-workflow security scan (zero model calls)")
        print("Workflows: %s   files read: %d\n" % (base, len(files)))
        if not files:
            print("  no .github/workflows/*.yml (or *.yaml) under this path")
            print("\n== VERDICT: %s ==" % verdict)
            return {"verdict": verdict, "hard": hard, "flags": flags, "files": 0}
        print("--- token-handoff findings (a hard finding fails the build) ---")
        if hard:
            for label, loc in hard:
                print("  [FAIL] %-70s %s" % (label, loc))
        else:
            print("  [ok]   no run: injection, no pull_request_target checkout of PR head, "
                  "no mutable-branch pin")
        if flags:
            print("\n--- harden these (confirm trusted, or set least privilege) ---")
            for label, loc in flags:
                print("  [flag] %-70s %s" % (label, loc))
        print("\n--- not checked (and not a pass) ---")
        print("  - whether a given trigger is actually reachable by an outside attacker")
        print("  - the action's OWN source - a SHA pins the ref, it does not vet the code")
        print("  - OIDC trust policies, self-hosted-runner exposure, reusable-workflow inputs")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Pattern and location only. Reachability and action-source trust are a human's call.")
    return {"verdict": verdict, "hard": hard, "flags": flags, "files": len(files)}


def _exit_code(verdict):
    return 1 if verdict == "WORKFLOW INJECTION RISK" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("ghactions: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("ghactions", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(root, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(root)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
