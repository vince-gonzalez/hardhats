"""
hardHats crew: the Geom crew (keyword `geom`). A discrete-geometry referee's gate: a covering or
packing bound is only trustworthy if the arithmetic behind it is CERTIFIED. This seat parses an
inequality and hands the numbers to a real certified-arithmetic engine - it does NOT roll its own.

It DELEGATES to `certivl` (exact rational + certified interval arithmetic: every quantity is an
exact-endpoint enclosure, every operation rounds outward, so a computed inequality becomes a
proof). This seat owns only the parser; certivl owns the numbers. Without certivl it reports
NO ENGINE and refuses to answer - an unchecked bound is exactly the lie this avoids.

    python -m hardhats.crews.geom "<claim>" ["<claim>" ...] [--file claims.txt] [--md out.md]

A claim is an inequality over `+ - * / ^ sqrt() pi`, e.g. "2*pi/sqrt(27) < 1.2092". It returns
CERTIFIED (holds for the whole enclosure), REFUTED (fails for the whole enclosure), or UNDECIDED
(the enclosure straddles the boundary - widen precision). Exit 1 if any claim is not CERTIFIED,
2 if certivl is absent.
"""
from __future__ import annotations

import re
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction

try:
    import certivl
    _HAVE = True
except ImportError:
    certivl = None
    _HAVE = False

TOKEN = re.compile(r"\s*(\d+\.?\d*(?:[eE][+-]?\d+)?|sqrt|pi|<=|>=|[()+\-*/^<>])")


def tokenize(s):
    toks, i = [], 0
    while i < len(s):
        m = TOKEN.match(s, i)
        if not m:
            if s[i:].strip() == "":
                break
            raise ValueError("unexpected %r" % s[i:])
        toks.append(m.group(1))
        i = m.end()
    return toks


def _num(tok):
    # Exact rational from the decimal literal (Decimal handles 1.2092 and 1e-3 exactly);
    # no binary float ever touches the proof path.
    try:
        return certivl.Ivl.exact(Fraction(Decimal(tok)))
    except (InvalidOperation, ValueError):
        raise ValueError("bad number %r" % tok)


class P:
    """Recursive-descent parser. The grammar is the seat's; every value it builds is a
    certivl.Ivl, so all arithmetic is the engine's certified, outward-rounded kind."""

    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def eat(self, x=None):
        tok = self.t[self.i]
        if x and tok != x:
            raise ValueError("expected %r got %r" % (x, tok))
        self.i += 1
        return tok

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            op = self.eat()
            v = v + self.term() if op == "+" else v - self.term()
        return v

    def term(self):
        v = self.factor()
        while self.peek() in ("*", "/"):
            op = self.eat()
            v = v * self.factor() if op == "*" else v / self.factor()
        return v

    def factor(self):
        v = self.base()
        if self.peek() == "^":
            self.eat()
            e = self.base()
            if e.lo != e.hi or e.lo < 0 or e.lo.denominator != 1:
                raise ValueError("exponent must be a non-negative integer literal")
            v = v ** int(e.lo)
        return v

    def base(self):
        tok = self.peek()
        if tok == "-":
            self.eat()
            return -self.base()
        if tok == "(":
            self.eat("(")
            v = self.expr()
            self.eat(")")
            return v
        if tok == "sqrt":
            self.eat("sqrt")
            self.eat("(")
            v = certivl.sqrt_ivl(self.expr())
            self.eat(")")
            return v
        if tok == "pi":
            self.eat("pi")
            return certivl.pi_ivl()
        self.eat()
        return _num(tok)


def certify(claim):
    if not _HAVE:
        return "NO ENGINE", "certivl is not installed", None, None
    toks = tokenize(claim)
    rel = next((r for r in ("<=", ">=", "<", ">") if r in toks), None)
    if not rel:
        return "ERROR", "no relation (<, <=, >, >=) in the claim", None, None
    k = toks.index(rel)
    try:
        L = P(toks[:k]).expr()
        R = P(toks[k + 1:]).expr()
    except (ValueError, IndexError, ZeroDivisionError) as e:
        return "ERROR", str(e), None, None
    if rel in ("<", "<="):
        if (L.definitely_lt(R) if rel == "<" else L.definitely_le(R)):
            v = "CERTIFIED"
        elif L.definitely_ge(R):
            v = "REFUTED"
        else:
            v = "UNDECIDED"
    else:
        if (L.definitely_gt(R) if rel == ">" else L.definitely_ge(R)):
            v = "CERTIFIED"
        elif L.definitely_le(R):
            v = "REFUTED"
        else:
            v = "UNDECIDED"
    return v, "", L, R


def _fmt(iv):
    if iv is None:
        return "n/a"
    return "[%.12g, %.12g]" % (float(iv.lo), float(iv.hi))


def review(claims, log=print):
    if not _HAVE:
        if log:
            print("THE GEOM CREW - certified interval arithmetic (delegates to certivl)")
            print("\n  [FAIL] certivl is not installed - this seat refuses to certify without it.")
            print("         pip install certivl   (exact rational + certified interval arithmetic)")
            print("  \U0001f6d1 an unchecked bound is not a pass. No engine, no verdict.")
            print("\n== VERDICT: NO ENGINE ==")
        return {"verdict": "NO ENGINE", "rows": [(c, "NO ENGINE") for c in claims]}
    rows = [(c,) + certify(c) for c in claims]
    any_refuted = any(r[1] == "REFUTED" for r in rows)
    all_cert = all(r[1] == "CERTIFIED" for r in rows)
    verdict = "ALL CERTIFIED" if all_cert else ("REFUTED" if any_refuted else "NOT CERTIFIED")
    if log:
        print("THE GEOM CREW - certified interval arithmetic via certivl (zero model calls)")
        print("the seat parses; certivl owns the numbers (exact rationals, outward rounding)\n")
        for claim, v, msg, L, R in rows:
            if v == "ERROR":
                print("  [ERR ] %s   (%s)" % (claim, msg))
            else:
                tag = {"CERTIFIED": "[cert]", "REFUTED": "[FALSE]", "UNDECIDED": "[????]"}[v]
                print("  %s %s" % (tag, claim))
                print("        %s -> LHS=%s RHS=%s" % (v, _fmt(L), _fmt(R)))
        print("\n--- not checked (and not a pass) ---")
        print("  - the GEOMETRY itself - that a construction actually covers/packs is a separate proof")
        print("  - UNDECIDED means certivl's enclosure straddles the boundary here, NOT that it is true")
        print("\n== VERDICT: %s ==" % verdict)
        print("   An enclosure proof from certivl. CERTIFIED means the inequality holds for the whole interval.")
    return {"verdict": verdict, "rows": [(r[0], r[1]) for r in rows]}


def _exit_code(verdict):
    if verdict == "ALL CERTIFIED":
        return 0
    if verdict == "NO ENGINE":
        return 2
    return 1


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    claims = []
    if "--file" in args:
        fp = args[args.index("--file") + 1]
        for ln in open(fp, encoding="utf-8-sig", errors="replace"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                claims.append(ln)
    claims += [a for a in args if not a.startswith("--") and a not in (md_out,)
               and a != (args[args.index("--file") + 1] if "--file" in args else None)]
    if not claims:
        print("geom: give an inequality, e.g. geom \"2*pi/sqrt(27) < 1.2092\"", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        rep = review(claims, log=None)
        return _emit.emit("geom", rep, _exit_code(rep["verdict"]))
    if md_out:
        import io
        buf = io.StringIO()
        rep = review(claims, log=lambda *a: print(*a, file=buf))
        with open(md_out, "wb") as fh:
            fh.write(buf.getvalue().encode("utf-8"))
        print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
    else:
        rep = review(claims)
    return _exit_code(rep["verdict"])


if __name__ == "__main__":
    sys.exit(main())
