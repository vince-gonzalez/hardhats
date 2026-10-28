"""
hardHats crew: the Open-Graph crew (keyword `og`). When the game's link is pasted into a chat, a
post, a DM - does it unfurl into a card, and can a crawler tell it is a game? Deterministic, graded
against the Open Graph protocol (ogp.me) and the Twitter/X Card tags.

Hard floor (OGP requires all four on every page): og:title, og:type, og:image, og:url.
Recommended: a Twitter card (twitter:card + title + image), a meta description, and og:image
dimensions at or above the 1200x630 the platforms crop to.

    python -m hardhats.crews.og <page.html-or-site-dir> [--json] [--md out.md]

🛑 It reads the <head> tags; it does not fetch og:image to confirm it loads or measure its real
pixels (declared dimensions only). schema.org / Rich Results is a separate job - that is `richdata`.
Exit 1 when a page is missing an OGP-required tag.
"""
from __future__ import annotations

import os
import re
import sys

OGP_REQUIRED = ("og:title", "og:type", "og:image", "og:url")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
META = re.compile(r"<meta\b[^>]*>", re.I)
ATTR = re.compile(r"""([a-zA-Z:_-]+)\s*=\s*"([^"]*)"|([a-zA-Z:_-]+)\s*=\s*'([^']*)'""")


def _metas(html):
    out = {}
    for tag in META.findall(html):
        attrs = {}
        for m in ATTR.finditer(tag):
            k = (m.group(1) or m.group(3) or "").lower()
            v = m.group(2) if m.group(2) is not None else m.group(4)
            attrs[k] = v
        key = attrs.get("property") or attrs.get("name")
        if key:
            out[key.lower()] = attrs.get("content", "")
    return out


def _scan(html, rel):
    hard, flags = [], []
    m = _metas(html)
    for req in OGP_REQUIRED:
        if not m.get(req):
            hard.append(("missing %s" % req, rel))
    if not (m.get("twitter:card")):
        flags.append(("no twitter:card (X / iMessage fall back to a small card)", rel))
    elif not (m.get("twitter:title") and m.get("twitter:image")):
        flags.append(("twitter:card set but missing twitter:title / twitter:image", rel))
    if not m.get("description"):
        flags.append(("no meta description", rel))
    if not m.get("og:description"):
        flags.append(("no og:description", rel))
    w, h = m.get("og:image:width"), m.get("og:image:height")
    if m.get("og:image"):
        if not (w and h):
            flags.append(("no og:image:width / og:image:height declared (aim for 1200x630)", rel))
        else:
            try:
                if int(w) < 1200 or int(h) < 630:
                    flags.append(("og:image is %sx%s, below the 1200x630 platforms crop to" % (w, h), rel))
            except ValueError:
                flags.append(("og:image dimensions are not numeric", rel))
    return hard, flags


def _html_files(target):
    if os.path.isfile(target):
        return [target], os.path.dirname(os.path.abspath(target)) or "."
    out = []
    for dp, dirs, fs in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in fs:
            if f.lower().endswith((".html", ".htm")):
                out.append(os.path.join(dp, f))
    return sorted(out), target


def review(target, log=print):
    files, base = _html_files(target)
    hard, flags = [], []
    for p in files:
        html = open(p, encoding="utf-8", errors="replace").read()
        h, fl = _scan(html, os.path.relpath(p, base))
        hard += h
        flags += fl
    verdict = ("NO PAGES FOUND" if not files else
               "NOT SHAREABLE" if hard else
               "REVIEW - share gaps present" if flags else
               "SHARE-READY")
    if log:
        print("THE OG CREW - share-card and crawler gate (Open Graph protocol + Twitter Cards)")
        print("Target: %s   pages read: %d\n" % (target, len(files)))
        print("--- OGP-required on every page (a hard miss = no card) ---")
        if hard:
            for label, rel in hard:
                print("  [FAIL] %-48s %s" % (label, rel))
        elif files:
            print("  [ok]   every page has og:title, og:type, og:image, og:url")
        if flags:
            print("\n--- recommended (confirm) ---")
            for label, rel in flags:
                print("  [flag] %-48s %s" % (label, rel))
        print("\n--- not checked (and not a pass) ---")
        print("  - that og:image actually loads, and its REAL pixel size")
        print("  - schema.org / Google Rich Results structured data - that is `richdata`")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "hard": hard, "flags": flags, "pages": len(files)}


def _exit_code(verdict):
    return 1 if verdict == "NOT SHAREABLE" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    target = pos[0] if pos else "."
    if not os.path.exists(target):
        print("og: no such path: %s" % target, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, log=None)
        return _emit.emit("og", rep, _exit_code(rep["verdict"]))
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
