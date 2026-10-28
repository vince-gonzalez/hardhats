"""
hardHats crew: THE POSTMAN (keyword `deliverability`). Will your outreach land, or get spam-filtered
and rejected at the door? It judges a domain's email-authentication records - the three a receiving
server checks before it trusts a From: address. Deterministic against the record rules.

  - SPF   (a TXT on the domain): `v=spf1 ... -all` (hardfail) or `~all` (softfail). `+all` means anyone
          may send as you; no SPF means nothing vouches for your senders.
  - DMARC (a TXT at _dmarc.<domain>): `v=DMARC1; p=quarantine` or `p=reject`. `p=none` only watches.
  - DKIM  needs a selector to look up, so it is reported, not graded, unless you pass the record.

    python -m hardhats.crews.deliverability <domain>              # live TXT lookup via the system resolver
    python -m hardhats.crews.deliverability --records recs.json   # judge records you supply

🛑 It judges the RECORDS; it does not send a message or read inbox placement (content, IP reputation and
list hygiene also decide the inbox). No resolver and no --records -> NO ENGINE. Exit 1 when the domain
is not email-authenticated (no SPF, or no DMARC, or SPF +all).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys


def _nslookup_txt(name, timeout=15):
    try:
        r = subprocess.run(["nslookup", "-type=TXT", name], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return re.findall(r'"([^"]*)"', r.stdout or "")


def _lookup(domain):
    root = _nslookup_txt(domain)
    dmarc = _nslookup_txt("_dmarc." + domain)
    if root is None and dmarc is None:
        return None
    spf = next((t for t in (root or []) if t.lower().startswith("v=spf1")), "")
    dmc = next((t for t in (dmarc or []) if t.lower().startswith("v=dmarc1")), "")
    return {"spf": spf, "dmarc": dmc, "dkim": ""}


def review(domain=None, records=None, log=print):
    if records is None:
        if not domain:
            if log:
                print("THE POSTMAN - email authentication (SPF / DMARC / DKIM)")
                print("\n  [FAIL] give a <domain> (needs a resolver) or --records recs.json")
                print("\n== VERDICT: NO ENGINE ==")
            return {"verdict": "NO ENGINE"}
        records = _lookup(domain)
        if records is None:
            if log:
                print("THE POSTMAN - email authentication")
                print("\n  [FAIL] no system resolver answered (nslookup). pass --records recs.json instead")
                print("\n== VERDICT: NO ENGINE ==")
            return {"verdict": "NO ENGINE"}

    spf = (records.get("spf") or "").strip()
    dmarc = (records.get("dmarc") or "").strip()
    dkim = (records.get("dkim") or "").strip()
    hard, flags, notes = [], [], []

    if "v=spf1" not in spf.lower():
        hard.append("no SPF record - nothing vouches for who may send as this domain")
    elif re.search(r"\+all\b", spf.lower()):
        hard.append("SPF uses +all - anyone on earth may send as you")
    elif "~all" in spf.lower():
        flags.append("SPF softfail (~all) - a forgery is marked, not rejected; -all is stronger")

    if "v=dmarc1" not in dmarc.lower():
        hard.append("no DMARC record at _dmarc - receivers have no policy to apply")
    else:
        pol = re.search(r"\bp\s*=\s*(none|quarantine|reject)\b", dmarc, re.I)
        p = pol.group(1).lower() if pol else ""
        if p == "none":
            flags.append("DMARC p=none - it only monitors; move to quarantine or reject to enforce")
        elif not p:
            flags.append("DMARC present but no valid p= policy")

    if "v=dkim1" in dkim.lower():
        notes.append("DKIM record supplied and looks well-formed")
    elif dkim:
        flags.append("DKIM record supplied but no v=DKIM1")
    else:
        notes.append("DKIM not checked - pass the selector's record to grade it")

    verdict = ("NOT EMAIL-AUTHENTICATED" if hard else
               "REVIEW - weak email policy" if flags else
               "EMAIL AUTHENTICATED")
    if log:
        print("THE POSTMAN - email authentication (SPF / DMARC / DKIM record rules)")
        print("Domain: %s\n" % (domain or "(from --records)"))
        print("--- will a receiver trust your From:? (a hard miss = spam/rejected) ---")
        if hard:
            for h in hard:
                print("  [FAIL] %s" % h)
        else:
            print("  [ok]   SPF present (not +all) and a DMARC policy exists")
        if flags:
            print("\n--- weak policy (land, but fragile) ---")
            for fl in flags:
                print("  [flag] %s" % fl)
        for nt in notes:
            print("  [note] %s" % nt)
        print("\n--- not checked (and not a pass) ---")
        print("  - inbox PLACEMENT: content spamminess, sending-IP reputation, list hygiene, warmup")
        print("  - DKIM signature validity on a real message (records only)")
        print("\n== VERDICT: %s ==" % verdict)
    return {"verdict": verdict, "hard": hard, "flags": flags,
            "spf": bool(spf), "dmarc": bool(dmarc)}


def _exit_code(verdict):
    if verdict == "NO ENGINE":
        return 2
    return 1 if verdict == "NOT EMAIL-AUTHENTICATED" else 0


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    rec_path = args[args.index("--records") + 1] if "--records" in args else None
    pos = [a for a in args if not a.startswith("--") and a not in (md_out, rec_path)]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    records = None
    if rec_path:
        try:
            with open(rec_path, encoding="utf-8-sig") as fh:
                records = json.load(fh)
        except (OSError, ValueError) as e:
            print("deliverability: cannot read records %s: %s" % (rec_path, e), file=sys.stderr)
            return 2
    domain = pos[0] if pos else None
    if records is None and not domain:
        print("deliverability: give a <domain> or --records recs.json", file=sys.stderr)
        return 2
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(domain=domain, records=records, log=None)
        return _emit.emit("deliverability", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(domain=domain, records=records, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(domain=domain, records=records)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
