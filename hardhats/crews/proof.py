"""
hardHats crew: the Proof crew (keyword `proof`). A formal-methods engineer's gate on a Metamath
database. It does not "review" a proof - it RUNS the kernel. A proof is verified or it is not, and
no prose changes that. Deterministic; it DELEGATES to a trusted Metamath verifier (the vendored
mmverify.py, or the metamath C tool). 🛑 It never ships its own kernel and never prints VERIFIED
unless a real verifier returned success - an unchecked "looks right" is exactly the lie this avoids.

Structural pre-checks (counting assertions, catching an incomplete `?` proof) run with or without a
kernel. Whether a theorem is INTERESTING, or the axioms are the right ones, is a mathematician's
call (`counsel` for the maths, or your axiom-hygiene work), not this gate's.

    python -m hardhats.crews.proof <database.mm> [--verifier <mmverify.py|metamath>] [--timeout 180]

Exit 1 if the verifier rejects the database (or, with no kernel, a proof is incomplete).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

KNOWN = [
    r"C:\Users\Admin\Desktop\claude\repos\setmm-choice\vendor\mmverify.py",
    r"C:\Users\Admin\Desktop\claude\repos\setmm-choice\src\mmforge\_vendor\mmverify.py",
]


def find_verifier(explicit=None):
    if explicit:
        if os.path.isfile(explicit):
            return ("metamath" if explicit.lower().endswith((".exe", "metamath")) else "mmverify", explicit)
        return (None, None)
    for p in KNOWN:
        if os.path.isfile(p):
            return ("mmverify", p)
    mm = shutil.which("metamath")
    return ("metamath", mm) if mm else (None, None)


def structural(text):
    provable = len(re.findall(r"\$p\b", text))
    axioms = len(re.findall(r"\$a\b", text))
    incomplete = 0
    for m in re.finditer(r"\$=(.*?)\$\.", text, re.S):
        if "?" in m.group(1).split():
            incomplete += 1
    return provable, axioms, incomplete


def _run(cmd, stdin=None, timeout=180):
    try:
        r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return None, "__timeout__"
    except OSError as e:
        return -1, "could not launch verifier: %s" % e


def review(mm_file, explicit=None, timeout=180, log=print):
    text = open(mm_file, encoding="utf-8", errors="replace").read()
    provable, axioms, incomplete = structural(text)
    kind, path = find_verifier(explicit)

    rc, out = None, ""
    if kind == "mmverify":
        rc, out = _run([sys.executable, path, mm_file], timeout=timeout)
    elif kind == "metamath":
        script = 'read "%s"\nverify proof *\nexit\n' % mm_file
        rc, out = _run([path], stdin=script, timeout=timeout)
        if rc == 0 and re.search(r"\?Error", out):
            rc = 1

    if kind is None:
        verdict = "NOT VERIFIED - no Metamath kernel found"
    elif out == "__timeout__":
        verdict = "DID NOT FINISH - verification timed out at %ds" % timeout
    elif rc == 0:
        verdict = "VERIFIED"
    else:
        verdict = "PROOF REJECTED"

    if log:
        print("THE PROOF CREW - runs a Metamath kernel, never its own (zero model calls)")
        print("Database: %s" % mm_file)
        print("kernel: %s\n" % (("%s (%s)" % (kind, os.path.basename(path))) if kind else "NONE FOUND"))
        print("--- structural (runs with or without a kernel) ---")
        print("  assertions: %d provable ($p), %d axiomatic ($a)" % (provable, axioms))
        print("  %s" % ("[flag] %d proof(s) are INCOMPLETE (a '?' step)" % incomplete if incomplete
                        else "[ok]   no incomplete (`?`) proofs"))
        print("\n--- kernel verdict ---")
        if kind is None:
            print("  [FAIL] no verifier found. Pass --verifier <mmverify.py|metamath>, or install metamath.")
            print("         🛑 structure can look fine and the proof still be wrong - this is NOT a pass.")
        elif out == "__timeout__":
            print("  [....] timed out - a 50 MB database needs the compiled metamath C tool, not this")
        elif rc == 0:
            print("  [PASS] the kernel accepted every proof in the database")
        else:
            print("  [FAIL] the kernel REJECTED the database:")
            tail = [ln for ln in out.splitlines() if ln.strip()][-12:]
            for ln in tail:
                print("         " + ln[:150])
        print("\n--- not checked (and not a pass) ---")
        print("  - whether a theorem is INTERESTING or non-trivial (a mathematician)")
        print("  - whether the AXIOMS are sound / the right ones (your axiom-hygiene work)")
        print("  - definitional soundness conventions beyond what the kernel enforces")
        print("\n== VERDICT: %s ==" % verdict)
        print("   The kernel's word, not mine. VERIFIED means a real verifier returned success.")
    return {"verdict": verdict, "provable": provable, "axioms": axioms,
            "incomplete": incomplete, "kernel": kind, "returncode": rc}


def main():
    args = sys.argv[1:]
    explicit = args[args.index("--verifier") + 1] if "--verifier" in args else None
    timeout = int(args[args.index("--timeout") + 1]) if "--timeout" in args else 180
    skip = {explicit, str(timeout)}
    pos = [a for a in args if not a.startswith("--") and a not in skip]
    if not pos or not os.path.isfile(pos[0]):
        print("proof: need a path to a Metamath .mm database", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(pos[0], explicit, timeout, log=None)
        v = rep["verdict"]
        if v == "VERIFIED":
            code = 0
        elif v == "PROOF REJECTED":
            code = 1
        elif rep["kernel"] is None and rep["incomplete"]:
            code = 1
        else:
            code = 2
        return _emit.emit("proof", rep, code)
    rep = review(pos[0], explicit, timeout)
    if rep["verdict"] == "VERIFIED":
        return 0
    if rep["verdict"] == "PROOF REJECTED":
        return 1
    if rep["kernel"] is None and rep["incomplete"]:
        return 1
    return 0 if rep["verdict"] == "VERIFIED" else (1 if rep["verdict"].startswith("PROOF") else 2)


if __name__ == "__main__":
    sys.exit(main())
