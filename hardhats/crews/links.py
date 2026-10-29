"""
hardHats crew: the Links crew (keyword `links`). A link-integrity check across a site or a document
set: does every LOCAL link resolve - the file it points at exists, and the #fragment it names is a
real anchor on that page. Deterministic and OFFLINE (zero model calls): a relative link either lands
on a file in the corpus or it does not, and an anchor is present or it is not.

🛑 It does NOT fetch external http(s) links - that needs the network and belongs to a crawler (and
to your `sec` seat for one URL). External links are listed, not judged. A root-absolute "/path"
is resolved against the corpus root, which is a guess about where the site is served from, so those
are flagged rather than failed.

    python -m hardhats.crews.links <site-dir|doc> [--json] [--md out.md]

Scans .html/.htm and .md. Exit 1 if a local link points at a missing file or a dead anchor.
"""
from __future__ import annotations

import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urldefrag

MD_LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
MD_HEAD = re.compile(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)  # http:, mailto:, tel:, data:, //host


class _Html(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        for k in ("id", "name"):
            if a.get(k):
                self.ids.add(a[k])


def _slug(text):
    t = re.sub(r"<[^>]+>", "", text).strip().lower()
    t = re.sub(r"[^\w\- ]+", "", t)
    return re.sub(r"\s+", "-", t)


def _scan_file(path):
    """-> (list of hrefs, set of anchor ids) for a supported file."""
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return [], set()
    if path.lower().endswith((".html", ".htm")):
        p = _Html()
        try:
            p.feed(text)
        except (ValueError, AssertionError):  # a parser error on malformed HTML still yields what parsed
            pass
        return p.hrefs, p.ids
    if path.lower().endswith((".md", ".markdown")):
        return MD_LINK.findall(text), {_slug(h) for h in MD_HEAD.findall(text)}
    return [], set()


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def review(root, log=print):
    root = root if os.path.isdir(root) else os.path.dirname(root) or "."
    files = []
    for dp, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for f in fs:
            if f.lower().endswith((".html", ".htm", ".md", ".markdown")):
                files.append(os.path.join(dp, f))
    anchors = {}
    hrefs_by = {}
    for p in files:
        h, ids = _scan_file(p)
        rp = _rel(root, p)
        anchors[rp] = ids
        hrefs_by[rp] = h

    broken, dead_anchor, external, abs_flag, checked = [], [], 0, [], 0
    for rp, hrefs in hrefs_by.items():
        base_dir = os.path.dirname(rp)
        for href in hrefs:
            href = href.strip()
            if not href or href.startswith("#"):
                if href.startswith("#"):
                    checked += 1
                    frag = unquote(href[1:])
                    if frag and frag not in anchors.get(rp, set()):
                        dead_anchor.append((rp, href, "same page"))
                continue
            if EXTERNAL.match(href):
                external += 1
                continue
            path_part, frag = urldefrag(href)
            path_part = unquote(path_part)
            if path_part.startswith("/"):
                target = path_part.lstrip("/")          # root-absolute: assume corpus root
                abs_flag.append((rp, href))
            else:
                target = os.path.normpath(os.path.join(base_dir, path_part)).replace(os.sep, "/")
            checked += 1
            disk = os.path.join(root, target)
            if os.path.isdir(disk):
                disk = os.path.join(disk, "index.html")
                target = target + "/index.html"
            if not os.path.isfile(disk):
                broken.append((rp, href, target))
                continue
            if frag:
                tgt_rel = target
                if tgt_rel in anchors:
                    if _slug(unquote(frag)) not in anchors[tgt_rel] and unquote(frag) not in anchors[tgt_rel]:
                        dead_anchor.append((rp, href, target))

    verdict = ("NO LINKS" if checked == 0 and external == 0 else
               "BROKEN LINKS" if (broken or dead_anchor) else
               "ALL LOCAL LINKS RESOLVE")
    if log:
        print("THE LINKS CREW - local link + anchor integrity, offline (zero model calls)")
        print("Root: %s   files: %d\n" % (root, len(files)))
        print("--- local links ---")
        print("  checked: %d local target(s)/anchor(s)   external (not fetched): %d" % (checked, external))
        for rp, href, target in broken:
            print("  [FAIL] %s -> %s  (no file at %s)" % (rp, href, target))
        for rp, href, where in dead_anchor:
            print("  [FAIL] %s -> %s  (no such anchor on %s)" % (rp, href, where))
        if not broken and not dead_anchor and checked:
            print("  [ok]   every local link lands on a file, every fragment on a real anchor")
        if abs_flag:
            print("  [flag] %d root-absolute link(s) resolved against the corpus root (verify the real site root)"
                  % len(abs_flag))
        print("\n--- not checked (and not a pass) ---")
        print("  - external http(s) links (needs the network; that is a crawler / the `sec` seat per URL)")
        print("  - whether a present page is the RIGHT page, and redirects that will later rot")
        print("  - links built by JavaScript at runtime (this reads the static markup)")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Local integrity only. External liveness and content correctness are a crawler's / human's.")
    return {"verdict": verdict, "files": len(files), "checked": checked, "external": external,
            "broken": broken, "dead_anchor": dead_anchor, "abs": abs_flag}


def _exit_code(verdict):
    return 1 if verdict == "BROKEN LINKS" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos or not os.path.exists(pos[0]):
        print("links: need a path to a site directory or a document", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(pos[0], log=None)
        return _emit.emit("links", rep, _exit_code(rep["verdict"]))
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
