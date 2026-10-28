"""
hardHats crew: the API crew (keyword `api`). An API architect's read on an OpenAPI description:
is it a valid 3.x document, does every operation carry a unique id and a documented error, and is
it versioned. Deterministic (zero model calls); OpenAPI 3.x / RFC 9110 conventions.

A spec is a contract. The failures here are the ones an integrator hits on day one: an operation
with no error response documented, two operations sharing an id, a path parameter never declared.
It validates the DOCUMENT, not the running service - whether the API behaves as written is a job
for contract tests, not a reader.

    python -m hardhats.crews.api <openapi.json|.yaml> [--md out.md]

Exit 1 if the document is not a valid OpenAPI 3.x spec (unparseable, no paths, duplicate ids,
or an operation with no responses).
"""
from __future__ import annotations

import json
import os
import sys

METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _load(path):
    raw = open(path, encoding="utf-8-sig", errors="replace").read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            return None, "YAML spec but PyYAML is not installed - give me the JSON form"
        try:
            return yaml.safe_load(raw), None
        except yaml.YAMLError as e:
            return None, "YAML parse error: %s" % e
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, "JSON parse error: %s" % e


def review(path, log=print):
    doc, err = _load(path)
    hard, flags, ops_n = [], [], 0
    if doc is None or not isinstance(doc, dict):
        hard.append(err or "top level is not an object")
    else:
        ver = doc.get("openapi") or ""
        if doc.get("swagger"):
            flags.append("this is Swagger 2.0 (`swagger: %s`), not OpenAPI 3.x - consider upgrading"
                         % doc.get("swagger"))
        elif not str(ver).startswith("3."):
            hard.append("no `openapi: 3.x` version field (got %r)" % (ver or None))
        info = doc.get("info") or {}
        if not info.get("title"):
            flags.append("info.title is missing")
        if not info.get("version"):
            flags.append("info.version is missing (API has no stated version)")
        if not doc.get("servers"):
            flags.append("no servers[] (no base URL / versioning anchor)")
        paths = doc.get("paths") or {}
        if not paths:
            hard.append("no paths - the document describes no operations")
        seen_ids = {}
        for p, item in paths.items():
            if not isinstance(item, dict):
                continue
            for method, op in item.items():
                if method.lower() not in METHODS or not isinstance(op, dict):
                    continue
                ops_n += 1
                label = "%s %s" % (method.upper(), p)
                oid = op.get("operationId")
                if not oid:
                    flags.append("%s: no operationId (clients cannot name it)" % label)
                else:
                    seen_ids.setdefault(oid, []).append(label)
                responses = op.get("responses")
                if not responses:
                    hard.append("%s: no responses documented" % label)
                else:
                    codes = [str(c) for c in responses]
                    if not any(c.startswith("2") or c == "default" for c in codes):
                        flags.append("%s: no 2xx success response" % label)
                    if not any(c.startswith(("4", "5")) or c == "default" for c in codes):
                        flags.append("%s: no 4xx/5xx error response documented" % label)
                # path params must be declared
                params = [x.get("name") for x in (op.get("parameters") or [])
                          if x.get("in") == "path"]
                import re as _re
                for tok in _re.findall(r"\{([^}]+)\}", p):
                    if tok not in params and tok not in [
                            x.get("name") for x in (item.get("parameters") or [])
                            if x.get("in") == "path"]:
                        flags.append("%s: path param {%s} is not declared" % (label, tok))
        for oid, where in seen_ids.items():
            if len(where) > 1:
                hard.append("duplicate operationId %r on: %s" % (oid, ", ".join(where)))

    verdict = ("INVALID SPEC" if hard else "VALID, with gaps" if flags else "VALID & COMPLETE")
    if log:
        print("THE API CREW - OpenAPI 3.x document check (zero model calls)")
        print("Spec: %s   operations: %d\n" % (path, ops_n))
        print("--- must hold (a broken contract) ---")
        if hard:
            for h in hard[:40]:
                print("  [FAIL] %s" % h)
        else:
            print("  [ok]   parses, is OpenAPI 3.x, has paths, ids are unique, every op has responses")
        print("\n--- gaps (an integrator will trip on these) ---")
        if flags:
            for f in flags[:40]:
                print("  [flag] %s" % f)
        else:
            print("  [ok]   ids, error responses, versioning and path params all present")
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the DEPLOYED service still matches this document - that is DRIFT, a")
        print("    different check: the `openapi-drift` package, not this static read")
        print("  - security-scheme correctness and auth flows")
        print("  - schema semantics, examples validity, and breaking-change diffs between versions")
        print("\n== VERDICT: %s ==" % verdict)
        print("   The document only. Whether the service honours it is a contract test's job.")
    return {"verdict": verdict, "hard": hard, "flags": flags, "operations": ops_n}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos or not os.path.isfile(pos[0]):
        print("api: need a path to an OpenAPI spec (.json/.yaml)", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(pos[0], log=None)
        return _emit.emit("api", rep, 1 if rep["verdict"] == "INVALID SPEC" else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(pos[0], log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(pos[0])
    return 1 if rep["verdict"] == "INVALID SPEC" else 0


if __name__ == "__main__":
    sys.exit(main())
