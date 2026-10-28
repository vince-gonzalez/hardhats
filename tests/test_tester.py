"""The tester crew has to be able to FAIL, per dimension.

A gate that has only ever returned PASS is untested. So this builds two
samples - one deliberately broken in a named way per dimension, one
clean - and asserts that each gate fires on the first and stays quiet on
the second. If a check here starts passing on the broken sample, the
check has stopped working, which is the failure mode that survives
review because nothing looks wrong.

Run: python -m pytest tests/test_tester.py -q
 or: python tests/test_tester.py
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardhats.gates.webtest import (          # noqa: E402
    Target, gate_game, gate_legal, gate_meta, gate_mobile, gate_privacy,
    gate_reach, gate_ux, gate_weight, BLOCK, WARN)

BROKEN = """<!doctype html><html><head>
<title>Bad</title>
<meta name="viewport" content="width=device-width, user-scalable=no">
<script src="https://www.googletagmanager.com/gtag/js"></script>
<script src="/app.js"></script>
</head><body>
<h1>Bad</h1>
<audio autoplay src="/loop.mp3"></audio>
<canvas id="stage" width="800" height="600"></canvas>
<form action="http://example.com/post" method="post">
  <input type="email" name="e">
</form>
<a href="/nowhere-at-all.html">gone</a>
<script>
  document.addEventListener('keydown', function (e) { move(e); });
  requestAnimationFrame(function tick(){ requestAnimationFrame(tick); });
</script>
</body></html>"""

CLEAN = """<!doctype html><html lang="en"><head>
<title>Good</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="A page that behaves.">
<link rel="canonical" href="https://example.com/">
<meta property="og:title" content="Good">
</head><body>
<h1>Good</h1>
<p>This page has enough text on it to be worth reading, a route to a
person, and nothing that shuts anybody out. It exists so the tester has
something to stay quiet about, because a gate that only ever fires is as
useless as one that never does.</p>
<p><a href="mailto:someone@example.com">Email someone</a></p>
<p><a href="/privacy.html">Privacy</a> and <a href="/terms.html">Terms</a>.
Operated by Example LLC, document 12345. &copy; 2026.
<a href="/accessibility.html">Accessibility</a>.</p>
</body></html>"""


def build(tmp, name, html, extras=()):
    d = os.path.join(tmp, name)
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, "index.html"), "w", encoding="utf-8",
                 newline="\n") as fh:
        fh.write(html)
    for fn in extras:
        with io.open(os.path.join(d, fn), "w", encoding="utf-8",
                     newline="\n") as fh:
            fh.write('<!doctype html><html lang=en><title>x</title>'
                     '<meta name="viewport" content="width=device-width,'
                     ' initial-scale=1"><p>x</p>')
    return d


def names(res):
    return " | ".join(f.what for f in res.findings)


def main():
    tmp = tempfile.mkdtemp(prefix="hardhats-test-")
    fails = []

    def want(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    try:
        bad = Target(build(tmp, "bad", BROKEN))
        good = Target(build(tmp, "good", CLEAN,
                            ("privacy.html", "terms.html",
                             "accessibility.html", "404.html")))

        print("\nBROKEN sample - every dimension must fire")
        r = gate_reach(bad)
        want(any(f.level == BLOCK for f in r.findings),
             "reach   catches a link to a page that is not there")

        r = gate_legal(bad)
        want(any("privacy" in f.what for f in r.findings),
             "legal   catches a data-collecting page with no privacy policy")
        want(any("plain http" in f.what for f in r.findings),
             "legal   catches a form posting over http")

        r = gate_privacy(bad)
        want(any("Google Analytics" in f.what for f in r.findings),
             "privacy catches a third-party tracker")

        r = gate_mobile(bad)
        want(any("pinch zoom" in f.what for f in r.findings),
             "mobile  catches a page that blocks zoom")

        r = gate_weight(bad)
        want(any("render-blocking" in f.what for f in r.findings),
             "weight  catches a render-blocking script")

        r = gate_game(bad)
        want(any("autoplays with sound" in f.what for f in r.findings),
             "game    catches audio that starts itself")
        want(any("canvas" in f.what for f in r.findings),
             "game    catches a canvas with no text alternative")
        want(any("prefers-reduced-motion" in f.what for f in r.findings),
             "game    catches animation that ignores reduced motion")
        want(any("keyboard input only" in f.what for f in r.findings),
             "game    catches keyboard-only input")

        r = gate_meta(bad)
        want(any("meta description" in f.what for f in r.findings),
             "meta    catches a missing description")

        r = gate_ux(bad)
        want(any(f.level == BLOCK for f in r.findings),
             "ux      catches a page with no route to a human")

        print("\nCLEAN sample - the same gates must stay quiet")
        for fn, g in (("legal", gate_legal), ("mobile", gate_mobile),
                      ("game", gate_game), ("ux", gate_ux),
                      ("privacy", gate_privacy), ("reach", gate_reach)):
            res = g(good)
            want(not res.blocks,
                 "%-7s no blocking finding on the clean page%s"
                 % (fn, "" if not res.blocks else " -> " + names(res)))

        print("\nEVERY dimension must declare what it did not check")
        for fn, g in (("reach", gate_reach), ("legal", gate_legal),
                      ("privacy", gate_privacy), ("meta", gate_meta),
                      ("weight", gate_weight), ("mobile", gate_mobile),
                      ("ux", gate_ux), ("game", gate_game)):
            res = g(good)
            want(bool(res.unchecked),
                 "%-7s lists what it did not look at" % fn)

        print("")
        print("A dimension that did not run must NOT read PASS")
        from hardhats.gates.webtest import Result as _R, gate_headers as _gh
        want(_R("x", [], ["everything"], ran=False).verdict == "NOT RUN",
             "result  ran=False reports NOT RUN, not PASS")
        want(_R("x", [], []).verdict == "PASS",
             "result  looked-and-found-nothing still reports PASS")
        want(_gh(good).verdict == "NOT RUN",
             "headers on a local path reports NOT RUN, not PASS")

        print("")
        print("max-width is NOT a fixed width")
        mw = build(tmp, "maxw",
                   '<!doctype html><html lang=en><title>MW</title>'
                   '<meta name="viewport" content="width=device-width,'
                   ' initial-scale=1">'
                   '<style>.wrap{max-width:1100px;margin:0 auto}</style>'
                   '<h1>MW</h1><p>A responsive container that caps on a '
                   'desktop and shrinks on a phone, with enough words to '
                   'clear the thin-page check, and a way to reach somebody '
                   'at <a href="mailto:a@b.com">this address</a>.</p>')
        res = gate_mobile(Target(mw))
        want(not any("fixed width" in f.what for f in res.findings),
             "mobile  max-width:1100px is not called a fixed width")
        fw = build(tmp, "fixedw",
                   '<!doctype html><html lang=en><title>FW</title>'
                   '<meta name="viewport" content="width=device-width,'
                   ' initial-scale=1">'
                   '<style>.wrap{width:1100px}</style>'
                   '<h1>FW</h1><p>This one really is pinned to eleven '
                   'hundred pixels and will overflow a phone, and it has a '
                   'way to reach somebody at '
                   '<a href="mailto:a@b.com">this address</a>.</p>')
        res = gate_mobile(Target(fw))
        want(any("fixed width" in f.what for f in res.findings),
             "mobile  a bare width:1100px still IS reported")

        print("\nThe false positive that started this must stay dead")
        wrapped = build(tmp, "wrapped", """<!doctype html><html lang=en>
<title>Wrapped</title><h1>W</h1>
<p>Enough words here to clear the thin-page check, and a way to reach a
person as well, so the only thing left that could fire is the label
check that used to be wrong.</p>
<p><a href="mailto:a@b.com">Email</a></p>
<form><label>Your name <input type="text"></label>
<label><input type="radio" name="p"> Standard</label></form>""")
        res = gate_ux(Target(wrapped))
        want(not any("name them" in f.what for f in res.findings),
             "ux      no longer re-decides form labels at all")

        print()
        if fails:
            print("  %d FAILED" % len(fails))
            return 1
        print("  every check passed")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
