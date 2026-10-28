"""
hardHats crew: THE BOUNCER (keyword `traffic`). The first seat of the distribution-epistemology crew -
the one at the door that asks of every visitor: are you a real person? It audits a server access log
(combined/NCSA format) and reports the human-vs-bot share, so a reach number can be held to the only
question that matters: how much of it was a human. Deterministic, zero model calls.

Signals (a declared bot is the hard one; the rest are tells):
  - DECLARED BOT - the user-agent self-identifies (contains bot / crawler / spider / headless /
    python-requests / curl / wget / ...), or is empty. The robots convention; no brand names needed.  [hard]
  - NO ASSETS - a visitor that pulled the page but never one css/js/image. A real browser renders;
    a trailer-load does not. (A single self-contained page with no external assets looks like this too.) [tell]

    python -m hardhats.crews.traffic <access.log> [--json] [--md out.md]

🛑 This is a FLOOR, not forensics: it does not resolve IPs to datacenter ASNs, run a JS challenge, or
fingerprint - a bot wearing a real browser UA and pulling assets passes here. A low bot share is not
proof of real humans; a high one is proof you are counting machines. Exit 1 when most visitors are bots.
"""
from __future__ import annotations

import os
import re
import sys

# combined log: ip - - [when] "METHOD path PROTO" status size "referer" "user-agent"
LOG = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) (\S+) "([^"]*)" "([^"]*)"')
# generic, self-declared bot tokens only - NO brand/company names (grep-clean by design).
BOT_TOKENS = ("bot", "crawl", "spider", "slurp", "headless", "preview", "scrap", "monitor",
              "uptime", "fetch", "python-requests", "python-urllib", "curl", "wget",
              "go-http-client", "libwww", "okhttp", "httpclient", "java/", "apache-http",
              "phantomjs", "puppeteer", "playwright", "selenium", "axios", "node-fetch", "+http")
ASSET_EXT = (".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif",
             ".woff", ".woff2", ".ttf", ".ico", ".mp3", ".mp4", ".webm", ".map")


def _is_bot_ua(ua):
    u = ua.strip().lower()
    if not u or u == "-":
        return True
    return any(tok in u for tok in BOT_TOKENS)


def _is_asset(path):
    p = path.split("?", 1)[0].lower()
    return p.endswith(ASSET_EXT)


def review(path, log=print):
    visitors = {}
    lines = parsed = 0
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError as e:
        return {"verdict": "COULD NOT READ LOG", "error": str(e)}
    with fh:
        for line in fh:
            lines += 1
            m = LOG.match(line)
            if not m:
                continue
            parsed += 1
            ip, _method, p, _status, _size, _ref, ua = m.groups()
            v = visitors.setdefault(ip, {"reqs": 0, "asset": False, "bot": False})
            v["reqs"] += 1
            if _is_asset(p):
                v["asset"] = True
            if _is_bot_ua(ua):
                v["bot"] = True

    n = len(visitors)
    bots = sum(1 for v in visitors.values() if v["bot"])
    noasset = sum(1 for v in visitors.values() if not v["bot"] and not v["asset"])
    humans = n - bots - noasset
    bot_share = bots / n if n else 0.0
    susp_share = (bots + noasset) / n if n else 0.0

    verdict = ("NO PARSED REQUESTS" if not n else
               "TRAFFIC IS MOSTLY BOTS" if bot_share > 0.50 else
               "REVIEW - heavy non-human share" if susp_share > 0.25 else
               "TRAFFIC LOOKS HUMAN")
    if log:
        print("THE BOUNCER - who at the door is a real person? (access-log audit, zero model calls)")
        print("Log: %s   lines: %d   parsed: %d   visitors (unique IPs): %d\n"
              % (path, lines, parsed, n))
        print("--- the headcount ---")
        print("  declared bots (UA self-identifies or is empty): %d  (%.0f%%)" % (bots, 100 * bot_share))
        print("  no assets pulled (rendered nothing - a tell):   %d  (%.0f%%)"
              % (noasset, 100 * (noasset / n if n else 0)))
        print("  looks human (browser UA + pulled an asset):     %d  (%.0f%%)"
              % (humans, 100 * (humans / n if n else 0)))
        print("\n--- not checked (and not a pass) ---")
        print("  - datacenter / proxy IP ranges (no ASN lookup), JS-challenge, fingerprinting")
        print("  - a bot wearing a real browser UA and pulling assets passes here")
        print("  - a single self-contained page (no external assets) reads as 'no assets' for humans too")
        print("\n== VERDICT: %s ==" % verdict)
        print("   A high bot share is proof you are counting machines; a low one is not proof of humans.")
    return {"verdict": verdict, "visitors": n, "bots": bots, "no_assets": noasset,
            "humans": humans, "bot_share": round(bot_share, 3), "parsed": parsed}


def _exit_code(verdict):
    if verdict in ("NO PARSED REQUESTS", "COULD NOT READ LOG"):
        return 2
    return 1 if verdict == "TRAFFIC IS MOSTLY BOTS" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print("traffic: give an access log (combined/NCSA format)", file=sys.stderr)
        return 2
    path = pos[0]
    if not os.path.isfile(path):
        print("traffic: not a file: %s" % path, file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(path, log=None)
        return _emit.emit("traffic", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(path, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(path)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
