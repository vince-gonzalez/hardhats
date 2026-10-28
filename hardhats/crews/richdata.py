"""
hardHats crew: the Richdata crew (keyword `richdata`). A structured-data check on a page: is its
JSON-LD valid, and does each rich-result type carry the fields Google REQUIRES to be eligible.
Deterministic (zero model calls), grounded in schema.org + the Google Rich Results required-property
tables. A page can be beautiful and still be invisible to rich results because one required field is
missing; that is a fact a parser settles.

🛑 It checks PRESENCE and JSON-LD validity, not truth: that an `image` URL resolves, that a price is
current, or that the markup matches the visible page is out of scope (Google's own test renders the
page; this reads the markup). It reads `<script type="application/ld+json">` blocks; Microdata/RDFa
are not covered.

    python -m hardhats.crews.richdata <page.html|dir> [--json] [--md out.md]

Exit 1 if any JSON-LD block is invalid or a declared rich-result type is missing a required field.
"""
from __future__ import annotations

import json
import os
import re
import sys

LD = re.compile(r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
                re.S | re.I)

# Google Rich Results required properties. Each entry is a list of requirement GROUPS; a group is
# satisfied if the node has ANY key in it (so Product needs name AND one of offers/review/rating).
REQUIRED = {
    "Recipe": [["name"], ["image"]],
    "Product": [["name"], ["offers", "review", "aggregateRating"]],
    "Article": [["headline"]],
    "NewsArticle": [["headline"]],
    "BlogPosting": [["headline"]],
    "Event": [["name"], ["startDate"], ["location"]],
    "FAQPage": [["mainEntity"]],
    "QAPage": [["mainEntity"]],
    "BreadcrumbList": [["itemListElement"]],
    "JobPosting": [["title"], ["description"], ["datePosted"], ["hiringOrganization"], ["jobLocation"]],
    "LocalBusiness": [["name"], ["address"]],
    "Organization": [["name"]],
    "VideoObject": [["name"], ["thumbnailUrl"], ["uploadDate"]],
    "Review": [["reviewRating"], ["author"], ["itemReviewed"]],
}
RECOMMENDED = {
    "Recipe": ["recipeIngredient", "recipeInstructions", "author", "datePublished"],
    "Product": ["brand", "description", "image"],
    "Article": ["image", "datePublished", "author"],
    "NewsArticle": ["image", "datePublished", "author"],
    "BlogPosting": ["image", "datePublished", "author"],
    "Event": ["endDate", "image", "offers"],
    "JobPosting": ["baseSalary", "employmentType", "validThrough"],
}


def _types(node):
    t = node.get("@type")
    return [t] if isinstance(t, str) else list(t) if isinstance(t, list) else []


def _nodes(doc):
    """Flatten a parsed JSON-LD value into individual typed nodes, following @graph."""
    out = []
    items = doc if isinstance(doc, list) else [doc]
    for it in items:
        if not isinstance(it, dict):
            continue
        if isinstance(it.get("@graph"), list):
            out.extend(n for n in it["@graph"] if isinstance(n, dict))
        else:
            out.append(it)
    return out


def review(src, log=print):
    blocks = []
    if os.path.isdir(src):
        for dp, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
            for f in files:
                if f.lower().endswith((".html", ".htm")):
                    p = os.path.join(dp, f)
                    blocks += [(os.path.relpath(p, src), b) for b in
                               LD.findall(open(p, encoding="utf-8", errors="replace").read())]
    else:
        blocks = [(os.path.basename(src), b) for b in
                  LD.findall(open(src, encoding="utf-8", errors="replace").read())]

    invalid, missing, flags, typed = [], [], [], 0
    for where, raw in blocks:
        try:
            doc = json.loads(raw.strip())
        except json.JSONDecodeError as e:
            invalid.append((where, "invalid JSON-LD: %s" % e))
            continue
        for node in _nodes(doc):
            for t in _types(node):
                base = t.split("/")[-1]
                if base in REQUIRED:
                    typed += 1
                    for group in REQUIRED[base]:
                        if not any(k in node and node[k] not in (None, "", []) for k in group):
                            missing.append((where, base, " / ".join(group)))
                    for rec in RECOMMENDED.get(base, []):
                        if rec not in node:
                            flags.append((where, base, rec))

    verdict = ("NO STRUCTURED DATA" if not blocks else
               "INVALID JSON-LD" if invalid else
               "MISSING REQUIRED FIELDS" if missing else
               "RICH RESULTS VALID, with gaps" if flags else
               "RICH RESULTS VALID")
    if log:
        print("THE RICHDATA CREW - schema.org JSON-LD + Google Rich Results required fields (zero model calls)")
        print("Source: %s\n" % src)
        print("--- JSON-LD blocks: %d   typed rich-result nodes: %d ---" % (len(blocks), typed))
        if invalid:
            for where, why in invalid:
                print("  [FAIL] %s: %s" % (where, why))
        if missing:
            for where, base, group in missing:
                print("  [FAIL] %s: %s is missing a required field (%s)" % (where, base, group))
        if not invalid and not missing and blocks:
            print("  [ok]   every rich-result node carries its required fields")
        if flags:
            for where, base, rec in flags[:20]:
                print("  [flag] %s: %s - recommended field %r absent" % (where, base, rec))
        print("\n--- not checked (and not a pass) ---")
        print("  - whether an image/URL resolves, a price is current, or markup matches the visible page")
        print("  - Microdata / RDFa (this reads JSON-LD only), and Google's own render-time eligibility")
        print("  - types outside the Rich Results set (valid schema.org, but no rich treatment)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Presence and validity only. Eligibility is Google's call; run the Rich Results Test too.")
    return {"verdict": verdict, "blocks": len(blocks), "typed": typed,
            "invalid": invalid, "missing": missing, "flags": flags}


def _exit_code(verdict):
    return 1 if verdict in ("INVALID JSON-LD", "MISSING REQUIRED FIELDS") else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos or not os.path.exists(pos[0]):
        print("richdata: need a path to an .html file or a directory", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(pos[0], log=None)
        return _emit.emit("richdata", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(pos[0], log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(pos[0])
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
