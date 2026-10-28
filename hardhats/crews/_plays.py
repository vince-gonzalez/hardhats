"""
Shared pieces for the distribution 'do' seats - THE REGULAR (`community`), THE LOOP (`loop`),
THE RELAY (`relay`). Each of those is a gated seat: a deterministic readiness CHECK plus a concrete
PLAYBOOK that both print with ZERO model calls. This module holds the small content parsers they
share and the OPTIONAL `--run` tailor, which asks one model to fit the standing playbook to the
specific content - the only thing here that ever calls a model, and only on --run.
"""
from __future__ import annotations

import os
import re

_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z:_-]+)\s*=\s*"([^"]*)"|([a-zA-Z:_-]+)\s*=\s*'([^']*)'""")
_TITLE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.I | re.S)
_IMG = re.compile(r"<img\b", re.I)
_CANON = re.compile(r"""<link\b[^>]*\brel\s*=\s*["']?\s*canonical""", re.I)


def load_text(target):
    """Read the target (a dir resolves to its index.html). Returns the raw bytes-as-text."""
    path = target
    if target and os.path.isdir(target):
        for n in ("index.html", "index.htm"):
            if os.path.isfile(os.path.join(target, n)):
                path = os.path.join(target, n)
                break
    try:
        return open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def visible_text(raw):
    """Strip script/style and tags down to the visible words."""
    s = _SCRIPT.sub(" ", raw)
    s = _TAG.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def metas(raw):
    out = {}
    for tag in _META.findall(raw):
        a = {}
        for m in _ATTR.finditer(tag):
            k = (m.group(1) or m.group(3) or "").lower()
            v = m.group(2) if m.group(2) is not None else m.group(4)
            a[k] = v
        key = a.get("property") or a.get("name")
        if key:
            out[key.lower()] = a.get("content", "")
    return out


def page_title(raw):
    m = _TITLE.search(raw)
    return m.group(1).strip() if m else ""


def has_img(raw):
    return bool(_IMG.search(raw))


def has_canonical(raw):
    return bool(_CANON.search(raw))


def tailor(instruction, playbook, content, log):
    """Optional --run pass: one model tailors the standing playbook to this content. Never called
    unless the seat was run with --run; degrades to a note if no backend is keyed."""
    from hardhats.backends import BACKENDS, chat, read_key
    be = next((n for n, s in BACKENDS.items() if not s["key_env"] or read_key(s["key_env"])), None)
    if not be:
        log("\n  (no backend keyed - the playbook above stands; set a key to tailor it)")
        return
    prompt = ("%s\n\nStanding playbook:\n%s\n\nThe specific content:\n%s\n\nTailor the playbook to THIS "
              "content as a few concrete, numbered steps. Flag any step that depends on a live UI you "
              "must verify today." % (instruction, playbook, content[:2000]))
    try:
        out = chat(be, prompt, temperature=0.5, max_tokens=500)
    except Exception as e:  # noqa: BLE001 - a flaky backend must not crash a deterministic seat
        log("\n  (tailor unavailable: %s - the playbook above stands)" % type(e).__name__)
        return
    log("\n--- tailored to your content (%s; verify every click live) ---\n%s" % (be, out.strip()))
