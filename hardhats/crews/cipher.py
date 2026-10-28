"""
hardHats crew: the Cipher crew (keyword `cipher`). A classical cryptanalyst's measurements on a
symbol stream: index of coincidence, Shannon entropy per symbol (h1), conditional entropy given
the previous symbol (h2), and a Kasiski-lite scan for repeated runs. Deterministic (zero model
calls). The one seat that answers to the Voynich program - and the one that must stay honest about
what it cannot do.

🛑 It MEASURES. It does NOT decrypt, it does NOT translate, and it does NOT adjudicate whether a
text is meaningful, a cipher, or a hoax - that is a century-old open question and no statistic
settles it. It reports numbers next to natural-language and uniform-random baselines, and says
plainly what remains open.

    python -m hardhats.crews.cipher <text-file> [--alpha abcdefghijklmnopqrstuvwxyz] [--md out.md]

Exit 1 only when the sample is too short for the statistics to mean anything (a real guard:
a number computed on 50 symbols is not a measurement).
"""
from __future__ import annotations

import math
import os
import re
import sys
from collections import Counter

MIN_N = 200   # below this, IoC / entropy are noise

# natural-language monographic baselines (lowercase letters), for context only
EN_IOC = 0.0667
EN_H1 = 4.14
EN_H2 = 3.40


def _ioc(counts, n):
    if n < 2:
        return 0.0
    return sum(f * (f - 1) for f in counts.values()) / (n * (n - 1))


def _h1(counts, n):
    return -sum((f / n) * math.log2(f / n) for f in counts.values()) if n else 0.0


def _h2(stream):
    """Conditional entropy H(X_i | X_{i-1}) in bits, over adjacent symbols."""
    if len(stream) < 2:
        return 0.0
    bi = Counter((stream[i - 1], stream[i]) for i in range(1, len(stream)))
    uni = Counter(stream[:-1])
    total = sum(bi.values())
    h = 0.0
    for (a, b), fab in bi.items():
        p_ab = fab / total
        p_b_given_a = fab / uni[a]
        h -= p_ab * math.log2(p_b_given_a)
    return h


def _kasiski(stream, k=3, top=6):
    pos = {}
    for i in range(len(stream) - k + 1):
        pos.setdefault(stream[i:i + k], []).append(i)
    spac = Counter()
    for gram, ps in pos.items():
        if len(ps) > 1:
            for j in range(1, len(ps)):
                spac[ps[j] - ps[j - 1]] += 1
    # candidate key lengths = small common divisors of frequent spacings
    cand = Counter()
    for d, c in spac.items():
        for f in range(2, 16):
            if d % f == 0:
                cand[f] += c
    return cand.most_common(top), sum(1 for ps in pos.values() if len(ps) > 1)


def review(text, alpha=None, log=print):
    low = text.lower()
    if alpha:
        keep = set(alpha.lower())
        stream = "".join(c for c in low if c in keep)
    else:
        stream = "".join(re.findall(r"[a-z]", low))
    n = len(stream)
    counts = Counter(stream)
    distinct = len(counts)
    ioc = _ioc(counts, n)
    h1 = _h1(counts, n)
    h2 = _h2(stream)
    hmax = math.log2(distinct) if distinct > 1 else 0.0
    unif_ioc = 1.0 / distinct if distinct else 0.0
    kas, nrep = _kasiski(stream)

    short = n < MIN_N
    if short:
        verdict = "SHORT SAMPLE - statistics unreliable (n < %d)" % MIN_N
    elif ioc >= 0.055:
        verdict = "LANGUAGE-LIKE frequencies (monoalphabetic substitution or plaintext)"
    elif ioc <= unif_ioc * 1.3:
        verdict = "FLAT frequencies (polyalphabetic cipher, compression, or constructed/random)"
    else:
        verdict = "INTERMEDIATE frequencies"
    rigid = (not short) and h1 > 0 and (h2 / h1) < 0.70

    if log:
        print("THE CIPHER CREW - classical measurements on a symbol stream (zero model calls)")
        print("symbols kept: %d   distinct: %d\n" % (n, distinct))
        print("  index of coincidence   %.5f   (English ~%.4f, uniform ~%.4f)"
              % (ioc, EN_IOC, unif_ioc))
        print("  entropy h1 (bits/sym)  %.3f     (English ~%.2f, max here %.2f)" % (h1, EN_H1, hmax))
        print("  cond. entropy h2       %.3f     (English ~%.2f) -> h2/h1 = %.2f"
              % (h2, EN_H2, (h2 / h1) if h1 else 0))
        if rigid:
            print("     ^ h2 is LOW relative to h1: each symbol strongly predicts the next")
            print("       (rigid local structure - the Voynich signature; not a verdict on meaning)")
        print("\n  repeated trigrams: %d   candidate key-lengths (Kasiski-lite): %s"
              % (nrep, ", ".join("%d(%d)" % (k, c) for k, c in kas) or "(none)"))
        print("\n--- not checked, and NOT inferable from these numbers ---")
        print("  - the plaintext: this does NOT decrypt or translate anything")
        print("  - whether the text is meaningful, a cipher, or a hoax (a century-old OPEN question)")
        print("  - the transliteration's fidelity (EVA vs glyphs) - garbage in, garbage out")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Measurements only. What the text MEANS is unsettled scholarship, not this tool's call.")
    return {"verdict": verdict, "n": n, "distinct": distinct, "ioc": ioc,
            "h1": h1, "h2": h2, "rigid": rigid, "kasiski": kas}


def main():
    args = sys.argv[1:]
    alpha = args[args.index("--alpha") + 1] if "--alpha" in args else None
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a not in (alpha, md_out)]
    if not pos or not os.path.isfile(pos[0]):
        print("cipher: need a path to a text file", file=sys.stderr)
        return 2
    text = open(pos[0], encoding="utf-8-sig", errors="replace").read()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(text, alpha, log=None)
        return _emit.emit("cipher", rep, 1 if rep["verdict"].startswith("SHORT") else 0)
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(text, alpha, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(text, alpha)
    return 1 if rep["verdict"].startswith("SHORT") else 0


if __name__ == "__main__":
    sys.exit(main())
