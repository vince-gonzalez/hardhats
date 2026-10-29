"""
hardHats crew: the Env crew (keyword `env`). A Cloudflare-Workers binding check: every binding the
code READS (env.X / env["X"] / c.env.X) must be DECLARED in the wrangler config (wrangler.toml /
wrangler.jsonc / wrangler.json), and every declared binding should be used. An undeclared binding is
a runtime crash the first time that path runs. Deterministic (zero model calls), grounded in the
Workers runtime binding model.

🛑 It cannot see secrets set out of band (`wrangler secret put`, the dashboard, a .dev.vars that was
not committed), so a read whose name LOOKS like a secret but has no declaration is a FLAG, not a hard
fail. Rotation and real secret hygiene route to a human / `crypteng`.

    python -m hardhats.crews.env <worker-dir> [--json] [--md out.md]

Exit 1 if code reads a binding that no wrangler config declares (and the name is not secret-shaped).
"""
from __future__ import annotations

import json
import os
import re
import sys

CONFIGS = ("wrangler.toml", "wrangler.jsonc", "wrangler.json")
CODE_EXT = (".js", ".mjs", ".cjs", ".ts", ".mts", ".cts", ".jsx", ".tsx")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".wrangler"}
# env.NAME  |  env["NAME"] / env['NAME']  (also matches c.env.NAME via the trailing env)
READ = re.compile(r"\benv\.([A-Za-z_]\w*)|\benv\[\s*[\"']([A-Za-z_]\w*)[\"']\s*\]")
# Names that are usually a `wrangler secret`, i.e. legitimately absent from the config file.
SECRETISH = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD|PASSWD|_PW|API|AUTH|CREDENTIAL|DSN|WEBHOOK|SALT|SIGNING)")
# Reserved runtime-provided names that need no declaration.
RESERVED = {"ASSETS"}


def _strip_jsonc(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|[^:])//[^\n]*", lambda m: m.group(1), text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)  # trailing commas
    return text


def _walk_bindings(obj, out):
    """Collect declared binding names from a parsed wrangler config (toml or json shaped alike).
    `binding` is the usual key; durable-object bindings use `name` alongside `class_name` - the
    worker's own top-level `name` is NOT a binding, so `name` only counts with that sibling."""
    if isinstance(obj, dict):
        if isinstance(obj.get("binding"), str):
            out.add(obj["binding"])
        if "class_name" in obj and isinstance(obj.get("name"), str):
            out.add(obj["name"])
        for k, v in obj.items():
            if k == "vars" and isinstance(v, dict):
                out.update(str(x) for x in v.keys())
            elif k not in ("binding", "name"):
                _walk_bindings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_bindings(v, out)


def _declared(path):
    try:
        raw = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return set(), False
    out = set()
    if path.endswith(".toml"):
        try:
            import tomllib
            _walk_bindings(tomllib.loads(raw), out)
            return out, True
        except (ImportError, ValueError):  # no tomllib (<3.11) or malformed TOML - use the regex read
            pass
        # shallow fallback: binding = "X", name = "X", and [vars] keys
        out.update(re.findall(r'(?m)^\s*(?:binding|name)\s*=\s*"([^"]+)"', raw))
        in_vars = False
        for ln in raw.splitlines():
            s = ln.strip()
            if s.startswith("["):
                in_vars = s.rstrip("]").endswith("vars") or s == "[vars]"
            elif in_vars:
                m = re.match(r'([A-Za-z_]\w*)\s*=', s)
                if m:
                    out.add(m.group(1))
        return out, True
    try:
        _walk_bindings(json.loads(_strip_jsonc(raw)), out)
        return out, True
    except Exception:  # noqa: BLE001
        return out, True


def review(root, log=print):
    configs = [f for f in CONFIGS if os.path.isfile(os.path.join(root, f))]
    declared = set()
    for c in configs:
        d, _ = _declared(os.path.join(root, c))
        declared |= d

    reads = {}
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in files:
            if f.lower().endswith(CODE_EXT):
                p = os.path.join(dp, f)
                try:
                    src = open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for m in READ.finditer(src):
                    name = m.group(1) or m.group(2)
                    reads.setdefault(name, os.path.relpath(p, root))

    undeclared = {n: loc for n, loc in reads.items()
                  if n not in declared and n not in RESERVED}
    hard = {n: loc for n, loc in undeclared.items() if not SECRETISH.search(n)}
    softsecret = {n: loc for n, loc in undeclared.items() if SECRETISH.search(n)}
    unused = sorted(declared - set(reads) - RESERVED)

    verdict = ("NO WRANGLER CONFIG" if not configs else
               "UNDECLARED BINDINGS" if hard else
               "REVIEW - names look like out-of-band secrets" if softsecret else
               "ALL BINDINGS DECLARED")
    if log:
        print("THE ENV CREW - Cloudflare Workers binding parity (zero model calls)")
        print("Project: %s   config: %s\n" % (root, ", ".join(configs) or "NONE"))
        if not configs:
            print("  [info] no wrangler.toml / wrangler.jsonc found - nothing to check against")
        print("--- bindings read vs declared ---")
        print("  declared: %d   read in code: %d" % (len(declared), len(reads)))
        if hard:
            for n, loc in sorted(hard.items()):
                print("  [FAIL] env.%s is read at %s but no wrangler config declares it" % (n, loc))
        if softsecret:
            for n, loc in sorted(softsecret.items()):
                print("  [flag] env.%s (%s) - not in config; may be a `wrangler secret`, confirm" % (n, loc))
        if not undeclared and configs:
            print("  [ok]   every binding read in code is declared")
        if unused:
            print("  [flag] declared but never read: %s" % ", ".join(unused))
        print("\n--- not checked (and not a pass) ---")
        print("  - secrets set with `wrangler secret put` or in the dashboard (not in any file here)")
        print("  - binding TYPE correctness (a KV name declared as a D1, say) and value validity")
        print("  - per-environment [env.NAME] overrides beyond name collection; multi-worker repos")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Declaration parity only. Whether a value is correct or a secret is safe is a human's call.")
    return {"verdict": verdict, "declared": sorted(declared), "reads": sorted(reads),
            "undeclared": sorted(hard), "secretish": sorted(softsecret), "unused": unused}


def _exit_code(verdict):
    return 1 if verdict == "UNDECLARED BINDINGS" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    root = pos[0] if pos else "."
    if not os.path.isdir(root):
        print("env: not a directory: %s" % root, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(root, log=None)
        return _emit.emit("env", rep, _exit_code(rep["verdict"]))
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
