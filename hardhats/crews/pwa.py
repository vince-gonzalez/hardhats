"""
hardHats crew: the PWA crew (keyword `pwa`). Does the game INSTALL - does a browser treat it as an
app, not a page? Deterministic, graded against the W3C Web App Manifest spec and the baseline
installability criteria: a linked manifest with a name, a start_url and an app display mode; a 192px
and a 512px icon whose files exist; a registered service worker. The same checks behind Lighthouse's
installability audit.

    python -m hardhats.crews.pwa <site-dir-or-index.html> [--json] [--md out.md]

🛑 It confirms the manifest and the registration are present and well-formed and that each declared
icon file exists; it does not fetch the page, execute the service worker, or open the icon bytes to
confirm their real pixel size. Exit 1 when a baseline installability requirement is missing.
"""
from __future__ import annotations

import json
import os
import re
import sys

APP_DISPLAY = {"standalone", "fullscreen", "minimal-ui"}
MANIFEST_LINK = re.compile(r"""<link\b[^>]*\brel\s*=\s*["']?\s*manifest\s*["']?[^>]*>""", re.I)
HREF = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)
SW_REG = re.compile(r"serviceWorker\s*\.\s*register\s*\(")


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
    manifest = None
    icon_sizes = set()
    if not html_path:
        hard.append("no HTML entry point found (index.html)")
    else:
        base = os.path.dirname(os.path.abspath(html_path))
        html = open(html_path, encoding="utf-8", errors="replace").read()
        link = MANIFEST_LINK.search(html)
        href = HREF.search(link.group(0)) if link else None
        if not href:
            hard.append("no <link rel=\"manifest\"> in the page")
        else:
            mpath = os.path.normpath(os.path.join(base, href.group(1).lstrip("/")))
            if not os.path.isfile(mpath):
                hard.append("manifest link points to a missing file: %s" % href.group(1))
            else:
                try:
                    manifest = json.loads(open(mpath, encoding="utf-8-sig").read())
                except (OSError, ValueError) as e:
                    hard.append("manifest is not valid JSON (%s)" % e)
                else:
                    mdir = os.path.dirname(mpath)
                    if not (manifest.get("name") or manifest.get("short_name")):
                        hard.append("manifest has no name / short_name")
                    if not manifest.get("start_url"):
                        hard.append("manifest has no start_url")
                    disp = (manifest.get("display") or "").lower()
                    if disp not in APP_DISPLAY:
                        hard.append("display is %r, not an app mode (standalone / fullscreen / minimal-ui)"
                                    % (disp or "unset"))
                    for ic in manifest.get("icons", []):
                        for tok in str(ic.get("sizes", "")).lower().split():
                            icon_sizes.add(tok)
                        src = ic.get("src")
                        if src and not os.path.isfile(os.path.normpath(os.path.join(mdir, src.lstrip("/")))):
                            hard.append("icon file is missing: %s" % src)
                    if "192x192" not in icon_sizes:
                        hard.append("no 192x192 icon declared")
                    if "512x512" not in icon_sizes:
                        hard.append("no 512x512 icon declared")
                    if not manifest.get("theme_color"):
                        flags.append("no theme_color (the install UI falls back to a default)")
                    if not manifest.get("background_color"):
                        flags.append("no background_color (the splash screen falls back to a default)")
        js = html
        for f in os.listdir(base):
            if f.lower().endswith((".js", ".mjs")):
                js += "\n" + open(os.path.join(base, f), encoding="utf-8", errors="replace").read()
        if not SW_REG.search(js):
            hard.append("no service-worker registration (navigator.serviceWorker.register)")

    verdict = ("NOT INSTALLABLE" if hard else
               "REVIEW - install gaps present" if flags else
               "INSTALLABLE PWA")
    if log:
        print("THE PWA CREW - installability gate (W3C Web App Manifest + baseline criteria)")
        print("Entry: %s\n" % (html_path or target))
        print("--- installability requirements (a hard miss means it will not install) ---")
        if hard:
            for h in hard:
                print("  [FAIL] %s" % h)
        else:
            print("  [ok]   linked manifest, name, start_url, app display, 192+512 icons, service worker")
        if flags:
            print("\n--- recommended (confirm) ---")
            for fl in flags:
                print("  [flag] %s" % fl)
        print("\n--- not checked (and not a pass) ---")
        print("  - the icon bytes' REAL pixel size, and whether the service worker actually caches")
        print("  - that start_url responds offline - run the page and read the Application panel")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "hard": hard, "flags": flags,
            "manifest": bool(manifest), "icon_sizes": sorted(icon_sizes)}


def _exit_code(verdict):
    return 1 if verdict == "NOT INSTALLABLE" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    target = pos[0] if pos else "."
    if not os.path.exists(target):
        print("pwa: no such path: %s" % target, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(target, log=None)
        return _emit.emit("pwa", rep, _exit_code(rep["verdict"]))
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
