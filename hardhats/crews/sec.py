"""
hardHats crew: the Sec crew (keyword `sec`). An application-security engineer's read on a
URL's HTTP response - the OWASP Secure Headers set, cookie flags, transport, and version
leakage. Deterministic (zero model calls): a header is present or it is not.

It reports what is missing or weak and the quick wins. It does NOT test the app itself -
auth, injection, the TIGHTNESS of a CSP, TLS config - and it says so; those need a real
pentest. Deeper work routes to a human / `counsel`.

    python -m hardhats.crews.sec <url> [--md out.md]

Exit 1 if a required security header is missing.
"""
from __future__ import annotations

import sys
import urllib.request

UA = "Mozilla/5.0 (compatible; hardhats-sec/0.1)"

REQUIRED = [
    ("strict-transport-security", "HSTS - forces HTTPS on return visits"),
    ("content-security-policy", "CSP - controls what the page may load (the main XSS defense)"),
    ("x-content-type-options", "stops MIME sniffing (value must be 'nosniff')"),
    ("referrer-policy", "stops the full URL leaking to other sites"),
]
ADVISED = [
    ("permissions-policy", "turns off camera, mic, geolocation unless needed"),
    ("cross-origin-opener-policy", "isolates the browsing context (Spectre-class)"),
    ("cross-origin-resource-policy", "controls who may embed your resources"),
]


def _fetch(url):
    req = urllib.request.Request(url, headers={"user-agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.url, {k.lower(): v for k, v in r.headers.items()}, r.headers.get_all("set-cookie") or []


def review(url, log=print):
    final, h, cookies = _fetch(url)
    missing, weak, notes = [], [], []

    for key, why in REQUIRED:
        if key not in h:
            missing.append((key, why))
        elif key == "x-content-type-options" and "nosniff" not in h[key].lower():
            weak.append(("x-content-type-options", "present but not 'nosniff': %r" % h[key]))

    # clickjacking: X-Frame-Options OR a CSP frame-ancestors directive
    xfo = h.get("x-frame-options")
    csp = h.get("content-security-policy", "")
    if not xfo and "frame-ancestors" not in csp.lower():
        missing.append(("x-frame-options / frame-ancestors", "nothing stops the page being framed (clickjacking)"))

    advised_missing = [(k, w) for k, w in ADVISED if k not in h]

    # version / stack leakage
    for key in ("server", "x-powered-by", "x-aspnet-version"):
        if key in h and any(ch.isdigit() for ch in h[key]):
            notes.append("leaks stack/version in %s: %r" % (key, h[key]))

    # cookie flags
    for c in cookies:
        cl = c.lower()
        name = c.split("=", 1)[0].strip()
        gaps = [flag for flag, tok in (("Secure", "secure"), ("HttpOnly", "httponly"),
                                       ("SameSite", "samesite")) if tok not in cl]
        if gaps:
            weak.append(("cookie %s" % name, "missing " + ", ".join(gaps)))

    if not final.startswith("https://"):
        missing.append(("https", "the response is not served over HTTPS"))

    verdict = "GAPS" if missing else ("REVIEW" if (weak or advised_missing) else "HARDENED")
    if log:
        print("THE SEC CREW - OWASP secure-headers read on a URL (zero model calls)")
        print("URL: %s\n" % final)
        print("--- required (missing = a real gap) ---")
        if missing:
            for k, why in missing:
                print("  [FAIL] no %s - %s" % (k, why))
        else:
            print("  [ok]   all required security headers present")
        if weak:
            print("\n--- present but weak ---")
            for k, why in weak:
                print("  [flag] %s: %s" % (k, why))
        print("\n--- advised (hardening, not blocking) ---")
        if advised_missing:
            for k, why in advised_missing:
                print("  [note] no %s - %s" % (k, why))
        else:
            print("  [ok]   advised headers present")
        if notes:
            print("\n--- information leakage ---")
            for n in notes:
                print("  [flag] " + n)
        print("\n--- not checked (and not a pass) ---")
        print("  - whether the CSP is actually TIGHT (present is not the same as strict)")
        print("  - TLS version, cipher suite and certificate chain")
        print("  - authentication, authorization, injection, and the app's own logic")
        print("  - headers on other routes and on the API")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Header facts only. A real pentest and CSP review are a human's job; route to `counsel`.")
    return {"verdict": verdict, "missing": missing, "weak": weak,
            "advised_missing": advised_missing, "notes": notes}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print(__doc__.strip())
        return 2
    url = pos[0]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        try:
            rep = review(url, log=None)
        except Exception as e:  # noqa: BLE001
            print("sec: could not reach %s (%s)" % (url, e), file=sys.stderr)
            return 2
        return _emit.emit("sec", rep, 1 if rep["verdict"] == "GAPS" else 0)
    try:
        if md_out:
            import io
            buf = io.StringIO()
            rep = review(url, log=lambda *a: print(*a, file=buf))
            with open(md_out, "wb") as fh:
                fh.write(buf.getvalue().encode("utf-8"))
            print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
        else:
            rep = review(url)
    except Exception as e:  # noqa: BLE001 - one line, not a traceback
        print("sec: could not reach %s (%s)" % (url, e), file=sys.stderr)
        return 2
    return 1 if rep["verdict"] == "GAPS" else 0


if __name__ == "__main__":
    sys.exit(main())
