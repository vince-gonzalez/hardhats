"""Deterministic gates for the tester crew: what a rule can decide about a
site, a page or a browser game, without asking a model anything.

THE RULE THIS FILE OBEYS. Every function returns findings AND a list of
what it did not look at. A checker that reports only what it found reads
as a clean bill of health for the things it never opened, which is how a
site gets an accessibility badge it has not earned. So "not checked" is
part of the output here, not a footnote.

Severity is three values and they mean different things:
  BLOCK  a person is shut out, or the law is not met. Do not ship.
  WARN   it works, and it is costing you something measurable.
  NOTE   worth knowing. Not a defect on its own.

Nothing here needs a key or a paid service. requests and beautifulsoup4
are the only imports outside the standard library, and both are already
present wherever hardhats runs.
"""
from __future__ import annotations

import io
import os
import re
import urllib.parse
from collections import Counter

try:
    import requests
except ImportError:                                          # pragma: no cover
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:                                          # pragma: no cover
    BeautifulSoup = None

UA = {"user-agent": "Mozilla/5.0 (compatible; hardhats-tester/0.1)"}
TIMEOUT = 30

BLOCK, WARN, NOTE = "BLOCK", "WARN", "NOTE"


# --------------------------------------------------------------- model
class Finding:
    __slots__ = ("level", "what", "where", "fix")

    def __init__(self, level, what, where="", fix=""):
        self.level, self.what, self.where, self.fix = level, what, where, fix

    def __repr__(self):
        return "%-5s %s%s" % (self.level, self.what,
                              (" [%s]" % self.where) if self.where else "")


class Result:
    """One dimension's answer: what was found, and what was not looked at.

    `ran` is the difference between "looked and found nothing" and "did
    not look". Both produce an empty findings list, and reporting the
    second as PASS is precisely the lie this whole file is built to
    avoid - the summary table said PASS for accessibility on a run where
    the checker did not exist. A dimension that did not run says so.
    """

    def __init__(self, name, findings=None, unchecked=None, facts=None,
                 ran=True):
        self.name = name
        self.findings = findings or []
        self.unchecked = unchecked or []
        self.facts = facts or {}
        self.ran = ran

    @property
    def blocks(self):
        return [f for f in self.findings if f.level == BLOCK]

    @property
    def warns(self):
        return [f for f in self.findings if f.level == WARN]

    @property
    def verdict(self):
        if not self.ran:
            return "NOT RUN"
        if self.blocks:
            return "BLOCK"
        return "WARN" if self.warns else "PASS"


# --------------------------------------------------------------- input
class Target:
    """A URL or a local path, loaded once and shared by every gate."""

    def __init__(self, ref):
        self.ref = ref
        self.is_url = ref.startswith(("http://", "https://"))
        self.pages = []          # (name, html)
        self.headers = {}
        self.status = None
        self.base = ""
        self.errors = []
        self._load()

    def _load(self):
        if self.is_url:
            if requests is None:
                self.errors.append("requests is not installed")
                return
            try:
                r = requests.get(self.ref, headers=UA, timeout=TIMEOUT)
                self.status = r.status_code
                self.headers = {k.lower(): v for k, v in r.headers.items()}
                self.pages = [(self.ref, r.text)]
                p = urllib.parse.urlparse(r.url)
                self.base = "%s://%s" % (p.scheme, p.netloc)
            except Exception as e:                           # noqa: BLE001
                self.errors.append("%s: %s" % (type(e).__name__, e))
            return

        if os.path.isdir(self.ref):
            for root, dirs, files in os.walk(self.ref):
                dirs[:] = [d for d in dirs if d not in
                           (".git", "node_modules", "__pycache__", ".wrangler",
                            "dist", "retired")]
                for fn in files:
                    if fn.endswith((".html", ".htm")):
                        p = os.path.join(root, fn)
                        self.pages.append(
                            (os.path.relpath(p, self.ref).replace("\\", "/"),
                             io.open(p, encoding="utf-8",
                                     errors="replace").read()))
        elif os.path.isfile(self.ref):
            self.pages = [(os.path.basename(self.ref),
                           io.open(self.ref, encoding="utf-8",
                                   errors="replace").read())]
        else:
            self.errors.append("no such URL, file or directory")

    def soup(self, html):
        if BeautifulSoup is None:
            return None
        try:
            return BeautifulSoup(html, "html.parser")
        except Exception:                                    # noqa: BLE001
            return None


def _text(html):
    t = re.sub(r"<(script|style|svg|noscript).*?</\1>", " ", html,
               flags=re.S | re.I)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ------------------------------------------------------------ 1. reach
def gate_reach(t: Target) -> Result:
    """Does it load, and does every internal link go somewhere real?"""
    f, un = [], []
    if t.errors:
        for e in t.errors:
            f.append(Finding(BLOCK, "the target could not be loaded: " + e,
                             t.ref, "check the address, or the path"))
        return Result("Reachability", f, un)

    if t.is_url and t.status != 200:
        f.append(Finding(BLOCK, "the page returned HTTP %s" % t.status, t.ref))

    if t.is_url:
        un.append("links on OTHER pages of this site, since one URL was given")
        un.append("whether external links still resolve, which needs a request "
                  "to somebody else's server")
        return Result("Reachability", f, un,
                      {"pages loaded": len(t.pages), "status": t.status})

    # local tree: resolve every internal href against the filesystem
    known = {n.lower() for n, _ in t.pages}
    checked = broken = 0
    for name, html in t.pages:
        for m in re.finditer(r'href="(/[^"#?]*)', html):
            href = m.group(1)
            checked += 1
            cand = href.lstrip("/")
            opts = [cand, cand + "index.html", cand.rstrip("/") + "/index.html",
                    cand.rstrip("/") + ".html"]
            root = t.ref if os.path.isdir(t.ref) else os.path.dirname(t.ref)
            if any(os.path.exists(os.path.join(root, o)) for o in opts) or \
                    any(o.lower() in known for o in opts):
                continue
            broken += 1
            if broken <= 25:
                f.append(Finding(BLOCK, "internal link goes nowhere: " + href,
                                 name, "fix the href or restore the page"))
    un.append("external links, which need a request to somebody else's server")
    un.append("anchors (#fragments) and query strings")
    return Result("Reachability", f, un,
                  {"pages": len(t.pages), "internal links checked": checked,
                   "broken": broken})


# ------------------------------------------------------------- 2. legal
# A site that takes money, or collects a name, has obligations. These are
# presence checks: whether the page EXISTS and is reachable, never whether
# its contents are adequate, which is a lawyer's job and is reported as
# not checked rather than guessed at.
LEGAL_WANTED = [
    ("privacy policy", r"privacy", True),
    ("terms or an agreement", r"\bterms\b|terms of service|agreement|\beula\b", False),
    ("a way to contact a human", r"contact|support|mailto:", True),
    ("who the operator is", r"\bllc\b|\bltd\b|\binc\b|limited liability|"
                            r"registered|company number|document number", False),
    ("a copyright or licence line", r"&copy;|©|\bcopyright\b|\blicen[cs]e\b", False),
    ("an accessibility statement", r"accessibility", False),
]


def gate_legal(t: Target) -> Result:
    f, un = [], []
    blob = " ".join(h for _n, h in t.pages).lower()
    present = {}
    for label, pat, required in LEGAL_WANTED:
        hit = bool(re.search(pat, blob, re.I))
        present[label] = hit
        if not hit:
            f.append(Finding(BLOCK if required else WARN,
                             "no sign of %s" % label, "",
                             "add a page, and link it from every page"))

    # Collecting personal data raises the floor from "nice" to "required".
    collects = re.search(r"<input[^>]*type=[\"']?(email|tel|text)|<textarea",
                         blob, re.I)
    pays = re.search(r"stripe|paypal|checkout|\bbuy\b|\badd to cart\b|"
                     r"\$[0-9]", blob, re.I)
    if collects and not present["privacy policy"]:
        f.append(Finding(BLOCK, "the site collects personal data and has no "
                                "privacy policy", "",
                         "a privacy notice is required before the first field"))
    if pays and not present["terms or an agreement"]:
        f.append(Finding(WARN, "the site takes money and states no terms", "",
                         "say what is sold, refunds, and who is liable"))
    if collects:
        forms = re.findall(r"<form[^>]*>", blob, re.I)
        for tag in forms:
            act = re.search(r'action="([^"]*)"', tag, re.I)
            if act and act.group(1).startswith("http://"):
                f.append(Finding(BLOCK, "a form posts over plain http",
                                 act.group(1), "use https"))

    un += ["whether the privacy policy is ACCURATE about what the site does",
           "whether the terms are enforceable, or fit for the jurisdiction",
           "GDPR, CCPA and ADA applicability, which depend on who you serve",
           "cookie consent law, which depends on what the cookies are for",
           "this is a presence check, not legal advice, and no part of it "
           "replaces a lawyer"]
    return Result("Legal and policy", f, un,
                  {k: ("yes" if v else "NO") for k, v in present.items()})


# ----------------------------------------------------------- 3. privacy
TRACKERS = [
    ("Google Analytics", r"google-analytics\.com|gtag/js|googletagmanager"),
    ("Google Ads", r"googlesyndication|doubleclick|adservice\.google"),
    ("Meta pixel", r"connect\.facebook\.net|fbevents\.js"),
    ("TikTok pixel", r"analytics\.tiktok\.com"),
    ("Hotjar", r"static\.hotjar\.com"),
    ("Segment", r"cdn\.segment\.com"),
    ("Mixpanel", r"cdn\.mxpnl\.com"),
    ("Sentry", r"browser\.sentry-cdn|sentry\.io"),
    ("Google Fonts", r"fonts\.googleapis\.com|fonts\.gstatic\.com"),
    ("Cloudflare Insights", r"static\.cloudflareinsights\.com"),
]


def gate_privacy(t: Target) -> Result:
    f, un = [], []
    blob = " ".join(h for _n, h in t.pages)
    found = [name for name, pat in TRACKERS if re.search(pat, blob, re.I)]
    for name in found:
        lvl = NOTE if name in ("Sentry", "Cloudflare Insights") else WARN
        f.append(Finding(lvl, "third party loaded: %s" % name, "",
                         "each one is a disclosure you owe the visitor"))

    origins = Counter()
    for m in re.finditer(r'(?:src|href)="https?://([^/"]+)', blob, re.I):
        origins[m.group(1).lower()] += 1
    own = urllib.parse.urlparse(t.ref).netloc.lower() if t.is_url else ""
    third = {o: n for o, n in origins.items() if own not in o and o not in own}
    if third:
        f.append(Finding(NOTE, "%d third-party origin(s) referenced"
                         % len(third), ", ".join(sorted(third)[:8])))

    if t.is_url and t.headers:
        sc = t.headers.get("set-cookie", "")
        if sc:
            f.append(Finding(WARN, "the page sets a cookie on first visit", "",
                             "if it is not strictly necessary, ask first"))

    un += ["cookies and storage written by JavaScript after load",
           "what any third party does with the request once it has it",
           "requests made only after a click"]
    return Result("Privacy and third parties", f, un,
                  {"third-party origins": len(third),
                   "known trackers": ", ".join(found) or "none"})


# ----------------------------------------------------------- 4. headers
WANT_HEADERS = [
    ("content-security-policy", WARN,
     "controls what the page is allowed to load"),
    ("x-content-type-options", WARN, "stops MIME sniffing"),
    ("referrer-policy", WARN, "stops the full URL leaking to other sites"),
    ("strict-transport-security", WARN, "forces https on later visits"),
    ("permissions-policy", NOTE, "turns off camera, mic and geolocation"),
]


def gate_headers(t: Target) -> Result:
    f, un = [], []
    if not t.is_url:
        return Result("Transport and headers", [],
                      ["everything: headers only exist for a served URL, and "
                       "a local path was given"], ran=False)
    if not t.ref.startswith("https://"):
        f.append(Finding(BLOCK, "served over plain http", t.ref, "use https"))
    for name, lvl, why in WANT_HEADERS:
        if name not in t.headers:
            f.append(Finding(lvl, "no %s header" % name, "", why))
    xfo = t.headers.get("x-frame-options", "")
    csp = t.headers.get("content-security-policy", "")
    if not xfo and "frame-ancestors" not in csp:
        f.append(Finding(WARN, "nothing stops the page being framed", "",
                         "set frame-ancestors, or X-Frame-Options"))
    un += ["headers on other pages and on the API, if there is one",
           "whether the CSP is actually tight, as opposed to present",
           "TLS version and certificate chain"]
    return Result("Transport and headers", f, un,
                  {"https": t.ref.startswith("https://"),
                   "headers seen": len(t.headers)})


# -------------------------------------------------------------- 5. meta
def gate_meta(t: Target) -> Result:
    """Metadata, MINUS anything the accessibility dimension owns.

    The page title, the lang attribute and heading structure are WCAG
    criteria and belong to that checker. Re-deciding them here would mean
    two gates with two opinions about one fact, and the weaker one
    eventually contradicts the stronger one in front of a client. So this
    sticks to what accessibility has no view on: how the page describes
    itself to a search engine and to whatever renders a shared link.
    """
    f, un = [], []
    for name, html in t.pages[:400]:
        ttl = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        if ttl and len(_text(ttl.group(1))) > 70:
            f.append(Finding(NOTE, "title is long and will be cut", name))
        if not re.search(r'<meta[^>]*name=["\']description', html, re.I):
            f.append(Finding(WARN, "no meta description", name))
        if not re.search(r'rel=["\']canonical', html, re.I):
            f.append(Finding(NOTE, "no canonical link", name))
        if not re.search(r'property=["\']og:', html, re.I):
            f.append(Finding(NOTE, "no Open Graph tags, so shares look bare",
                             name))
    un += ["the page title, the lang attribute and heading structure, which "
           "are WCAG criteria and belong to the accessibility dimension",
           "whether the description actually describes the page",
           "robots.txt and the sitemap, which live beside the page not in it",
           "whether search engines have indexed any of it"]
    return Result("Titles, metadata and sharing", f, un,
                  {"pages read": min(len(t.pages), 400)})


# ------------------------------------------------------------ 6. weight
def gate_weight(t: Target) -> Result:
    f, un = [], []
    for name, html in t.pages[:400]:
        kb = len(html.encode("utf-8")) / 1024.0
        if kb > 500:
            f.append(Finding(WARN, "the HTML alone is %.0f KB" % kb, name,
                             "over a slow connection this is the whole wait"))
        scripts = len(re.findall(r"<script\b", html, re.I))
        if scripts > 15:
            f.append(Finding(NOTE, "%d script tags" % scripts, name))
        blocking = len(re.findall(
            r'<script(?![^>]*\b(?:async|defer|type="module"))[^>]*\bsrc=',
            html, re.I))
        if blocking:
            f.append(Finding(WARN, "%d render-blocking script(s)" % blocking,
                             name, "add defer, or move it to the end"))
        imgs = re.findall(r"<img\b[^>]*>", html, re.I)
        lazy = sum(1 for i in imgs if re.search(r'loading=["\']lazy', i, re.I))
        if len(imgs) > 6 and lazy < len(imgs) // 2:
            f.append(Finding(NOTE, "%d images, %d lazy" % (len(imgs), lazy),
                             name, 'loading="lazy" below the fold'))
    un += ["the size of images, scripts and fonts, which needs fetching them",
           "how long it actually takes on a phone on a bad connection",
           "Core Web Vitals, which need a real browser and a real visitor"]
    return Result("Weight and loading", f, un,
                  {"pages read": min(len(t.pages), 400)})


# ------------------------------------------------------------ 7. mobile
def gate_mobile(t: Target) -> Result:
    f, un = [], []
    for name, html in t.pages[:400]:
        vp = re.search(r'<meta[^>]*name=["\']viewport["\'][^>]*>', html, re.I)
        if not vp:
            f.append(Finding(BLOCK, "no viewport meta", name,
                             "without it a phone renders a desktop page shrunk"))
        else:
            v = vp.group(0).lower()
            if "user-scalable=no" in v or re.search(r"maximum-scale=1(\.0)?\b", v):
                f.append(Finding(BLOCK, "the page blocks pinch zoom", name,
                                 "remove user-scalable=no and maximum-scale"))
        # BARE width only. max-width and min-width are how a responsive
        # container is built - "max-width:1100px" caps the layout on a
        # desktop and shrinks on a phone, which is correct and common.
        # The first version matched any *width property and reported a
        # fixed width on two well-built sites in a row, which is the kind
        # of false positive that teaches somebody to stop reading the
        # report. Anything ending in -width is skipped.
        for m in re.finditer(r"(?<![\w-])width\s*:\s*(\d{4,})px", html, re.I):
            f.append(Finding(WARN, "a fixed width of %spx will overflow a phone"
                             % m.group(1), name,
                             "use max-width so it can shrink"))
            break
        for m in re.finditer(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", html, re.I):
            if float(m.group(1)) < 12:
                f.append(Finding(WARN, "text at %spx is below the readable "
                                 "floor" % m.group(1), name))
                break
    un += ["tap target SIZE, which needs the page laid out in a real browser",
           "whether anything overflows sideways at 320px",
           "how it behaves in landscape, or with a keyboard open"]
    return Result("Phones and small screens", f, un,
                  {"pages read": min(len(t.pages), 400)})


# -------------------------------------------------------------- 8. game
def gate_game(t: Target) -> Result:
    """What a rule can decide about a browser game.

    Games fail accessibility in ways a document never does: sound that
    starts itself, a control scheme with no alternative, colour as the
    only signal, and flashing. The last one is the dangerous one, and it
    is the one a static read cannot settle, so it is reported as a thing
    to test rather than a thing that passed.
    """
    f, un = [], []
    blob = " ".join(h for _n, h in t.pages)
    low = blob.lower()

    for m in re.finditer(r"<(audio|video)\b[^>]*>", blob, re.I):
        tag = m.group(0).lower()
        if "autoplay" in tag and "muted" not in tag:
            f.append(Finding(BLOCK, "media autoplays with sound", "",
                             "WCAG 1.4.2: let the player stop it, or start "
                             "muted"))
    if re.search(r"<canvas\b", blob, re.I):
        for m in re.finditer(r"<canvas\b([^>]*)>(.*?)</canvas>", blob,
                             re.S | re.I):
            attrs, inner = m.group(1), _text(m.group(2))
            if not re.search(r"aria-label|aria-labelledby|role=", attrs, re.I) \
                    and len(inner) < 20:
                f.append(Finding(BLOCK, "a canvas has no text alternative", "",
                                 "name it, and say what it shows"))
                break
    if re.search(r"new\s+AudioContext|webkitAudioContext|<audio", blob, re.I):
        if not re.search(r"\bmute\b|\bvolume\b|sound.?(on|off)|audio.?(on|off)",
                         low):
            f.append(Finding(WARN, "the game makes sound and no mute control "
                                   "was found", "",
                             "a visible mute is the single cheapest fix here"))
    if re.search(r"addEventListener\(\s*['\"]key(down|up|press)", blob):
        has_pointer = re.search(
            r"addEventListener\(\s*['\"](pointerdown|touchstart|click)", blob)
        if not has_pointer:
            f.append(Finding(WARN, "keyboard input only, no pointer or touch "
                             "handler found", "",
                             "a phone and a switch user cannot play this"))
    elif re.search(r"addEventListener\(\s*['\"](pointerdown|touchstart)", blob):
        f.append(Finding(WARN, "pointer input only, no keyboard handler found",
                         "", "WCAG 2.1.1: everything must work from a keyboard"))
    if not re.search(r"\bpause\b|\bresume\b", low):
        f.append(Finding(NOTE, "no sign of a pause", "",
                         "WCAG 2.2.2 if anything moves or times out"))
    if re.search(r"requestAnimationFrame|setInterval", blob) and \
            not re.search(r"prefers-reduced-motion", blob, re.I):
        f.append(Finding(WARN, "animation runs and prefers-reduced-motion is "
                         "not honoured", "",
                         "@media (prefers-reduced-motion: reduce)"))
    for word in ("red", "green"):
        if re.search(r"(colou?r|style)[^;{}]{0,40}%s\b" % word, low) and \
                not re.search(r"aria-label|title=|<span class=\"sr", low):
            break

    un += ["FLASHING. Three flashes a second can cause a seizure, and no "
           "static read can settle it. Record thirty seconds of play and "
           "measure it, every time.",
           "whether the game is actually completable using only a keyboard",
           "whether colour is the ONLY way a state is signalled",
           "difficulty, timing and whether anything cannot be turned off",
           "controller and assistive-switch support"]
    return Result("Game specifics", f, un,
                  {"canvas": bool(re.search(r"<canvas", blob, re.I)),
                   "audio or video": bool(re.search(r"<audio|<video|AudioContext",
                                                    blob, re.I))})


# ---------------------------------------------------------------- 9. ux
def gate_ux(t: Target) -> Result:
    """Usability signals a rule can decide, MINUS anything accessibility owns.

    The first version of this checked form labels, tables and link text,
    and it reported forty-seven correctly labelled controls on one page as
    unlabelled, because its idea of "labelled" could not see a control
    wrapped in its own <label>. The accessibility checker had already
    solved that exact problem. Two gates deciding one fact means the
    weaker one eventually contradicts the stronger one in front of a
    client, so those three checks are gone from here and the
    accessibility dimension owns them.

    What is left is what accessibility has no opinion about: whether
    there is enough on the page to read, whether a visitor can get to a
    person, and whether a dead link lands anywhere useful.
    """
    f, un = [], []
    thin = 0
    for name, html in t.pages[:400]:
        if len(_text(html)) < 200:
            thin += 1
            if thin <= 10:
                f.append(Finding(WARN, "almost no text on the page", name,
                                 "a visitor and a search engine both read text"))
    blob = " ".join(h for _n, h in t.pages).lower()
    if not re.search(r"mailto:|/contact|contact\.html|\bphone\b|\btel:", blob):
        f.append(Finding(BLOCK, "no route to a human anywhere in the pages "
                                "read", "",
                         "an email address is the minimum"))
    if not t.is_url and len(t.pages) > 3 and \
            not any(re.search(r"404|not.?found", n, re.I) for n, _h in t.pages):
        f.append(Finding(NOTE, "no 404 page found in the tree", "",
                         "a dead link should land somewhere useful"))
    un += ["form labels, tables and link text, which are WCAG criteria and "
           "belong to the accessibility dimension",
           "whether the wording is clear, which the foreman judges",
           "whether a first-time visitor can tell what to do next",
           "whether the navigation matches how people think about the thing",
           "anything that needs a person to sit down and try it"]
    return Result("Usability signals", f, un,
                  {"pages read": min(len(t.pages), 400),
                   "pages with almost no text": thin})


GATES = [
    ("reach", gate_reach), ("legal", gate_legal), ("privacy", gate_privacy),
    ("headers", gate_headers), ("meta", gate_meta), ("weight", gate_weight),
    ("mobile", gate_mobile), ("ux", gate_ux),
]
GAME_GATES = GATES + [("game", gate_game)]
