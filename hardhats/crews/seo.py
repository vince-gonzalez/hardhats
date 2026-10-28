"""
hardHats crew: THE INDEX (keyword `seo`). Can a search crawler find and index this page, or does it
quietly block itself? The on-page indexability FLOOR - not ranking tricks, the things that decide
whether you are in the index at all. Deterministic, zero model calls.

Hard (the page blocks its own search presence): a `noindex` robots meta, a site robots.txt that
disallows everything, or no `<title>`. Floor gaps (flagged): no meta description, no canonical, not
exactly one `<h1>`, no `<html lang>`, and for a site dir, no sitemap.

    python -m hardhats.crews.seo <page.html-or-site-dir> [--json] [--md out.md]

🛑 This is findability, not ranking - it does not judge content quality, links, or Core Web Vitals
(that is `perf`), or the share card (that is `og`). Exit 1 when the page blocks its own indexing.
"""
from __future__ import annotations

import os
import re
import sys

META = re.compile(r"<meta\b[^>]*>", re.I)
ATTR = re.compile(r"""([a-zA-Z:_-]+)\s*=\s*"([^"]*)"|([a-zA-Z:_-]+)\s*=\s*'([^']*)'""")
TITLE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.I | re.S)
H1 = re.compile(r"<h1\b", re.I)
CANON = re.compile(r"""<link\b[^>]*\brel\s*=\s*["']?\s*canonical\s*["']?""", re.I)
HTML_LANG = re.compile(r"""<html\b[^>]*\blang\s*=\s*["']?[a-z]""", re.I)
DISALLOW_ALL = re.compile(r"^\s*Disallow:\s*/\s*$", re.I | re.M)


def _metas(html):
    out = {}
    for tag in META.findall(html):
        attrs = {}
        for m in ATTR.finditer(tag):
            k = (m.group(1) or m.group(3) or "").lower()
            v = m.group(2) if m.group(2) is not None else m.group(4)
            attrs[k] = v
        key = attrs.get("name")
        if key:
            out[key.lower()] = attrs.get("content", "")
    return out


def _find_html(target):
    if os.path.isfile(target):
        return target
    for name in ("index.html", "index.htm"):
        p = os.path.join(target, name)
        if os.path.isfile(p):
            return p
    for f in sorted(os.listdir(target)):
        if f.lower().endswith((".html", ".htm")):
            return os.path.join(target, f)
    return None


def review(target, log=print):
    hard, flags = [], []
    html_path = _find_html(target) if target else None
    is_dir = bool(target) and os.path.isdir(target)
    if not html_path:
        hard.append("no HTML page found")
    else:
        html = open(html_path, encoding="utf-8", errors="replace").read()
        metas = _metas(html)
        title = TITLE.search(html)
        if not (title and title.group(1).strip()):
            hard.append("no <title> (the first thing a crawler indexes)")
        robots = metas.get("robots", "").lower()
        if "noindex" in robots:
            hard.append("<meta name=robots> says noindex - the page tells search engines to skip it")
        if not metas.get("description", "").strip():
            flags.append("no meta description (the search snippet is then auto-generated)")
        if not CANON.search(html):
            flags.append("no <link rel=canonical> (duplicate URLs can split ranking signals)")
        h1s = len(H1.findall(html))
        if h1s != 1:
            flags.append("%d <h1> on the page (exactly one is the floor)" % h1s)
        if not HTML_LANG.search(html):
            flags.append("no <html lang> (hurts language targeting and accessibility)")

    if is_dir:
        robots_path = os.path.join(target, "robots.txt")
        if os.path.isfile(robots_path):
            rtxt = open(robots_path, encoding="utf-8", errors="replace").read()
            if DISALLOW_ALL.search(rtxt):
                hard.append("robots.txt has 'Disallow: /' - it blocks the whole site from crawling")
            has_sitemap = "sitemap:" in rtxt.lower() or os.path.isfile(os.path.join(target, "sitemap.xml"))
        else:
            has_sitemap = os.path.isfile(os.path.join(target, "sitemap.xml"))
        if not has_sitemap:
            flags.append("no sitemap.xml and none referenced in robots.txt")

    verdict = ("BLOCKED FROM SEARCH" if hard else
               "REVIEW - SEO floor gaps" if flags else
               "SEO FLOOR MET")
    if log:
        print("THE INDEX - on-page indexability floor (findability, not ranking; zero model calls)")
        print("Target: %s\n" % (html_path or target))
        print("--- can a crawler index it? (a hard miss blocks search presence) ---")
        if hard:
            for h in hard:
                print("  [FAIL] %s" % h)
        else:
            print("  [ok]   has a title, not noindex, not disallowed site-wide")
        if flags:
            print("\n--- floor gaps (fix to compete) ---")
            for fl in flags:
                print("  [flag] %s" % fl)
        print("\n--- not checked (and not a pass) ---")
        print("  - content quality, keywords, inbound links - findability is not ranking")
        print("  - the share card (`og`), structured data (`richdata`), speed (`perf`)")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "hard": hard, "flags": flags}


def _exit_code(verdict):
    return 1 if verdict == "BLOCKED FROM SEARCH" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    target = pos[0] if pos else "."
    if not os.path.exists(target):
        print("seo: no such path: %s" % target, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, log=None)
        return _emit.emit("seo", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(target, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(target)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
