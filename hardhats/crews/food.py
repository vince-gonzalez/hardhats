"""
hardHats crew: the Food crew (keyword `food`). A food-regulatory specialist's first pass
over food copy - a recipe page, a product blurb, a shelf. Deterministic (zero model calls):
a prohibited disease claim, the word "FDA approved" on a food, a regulated claim term, and
an allergen in the ingredients are all patterns, not opinions.

🛑 It FLAGS patterns for a human to decide; it does not render a regulatory verdict and it is
not legal advice. FDA labeling, FALCPA allergen law and health-claim rules are a professional's
call - this routes judgement to the `counsel` seat. It also prints what it did NOT check, so a
clean scan never reads as a clearance.

    python -m hardhats.crews.food <url|path> [--md out.md]
    cat page.html | python -m hardhats.crews.food -

Exit 1 if a disease/drug claim or "FDA approved" misbranding is present.
"""
from __future__ import annotations

import re
import sys
import urllib.request

UA = "Mozilla/5.0 (compatible; hardhats-food/0.1)"
MAX = 5_000_000

# Disease / drug claims: a food (not a drug) may not claim to treat a condition. These are
# the ones that get a letter from the FDA. Verb + a health target, or an explicit phrase.
DISEASE = [
    r"(?i)\b(cures?|treats?|prevents?|heals?|reverses?|diagnoses?)\b[^.<]{0,45}\b("
    r"disease|diabetes|cancer|arthritis|inflammation|blood pressure|cholesterol|covid|flu|"
    r"infection|illness|ailment|condition|symptoms?|anxiety|depression|alzheimer\w*)\b",
    r"(?i)\b(anti[-\s]?inflammatory|immune[-\s]?boost\w*|boosts?\s+(your\s+)?immun\w+|"
    r"detox\w*|cleanse\w*|lowers?\s+(your\s+)?(cholesterol|blood pressure|blood sugar)|"
    r"clinically proven|fda[-\s]?(approved|registered))\b",
]
# Regulated claim terms: allowed only if the product meets the FDA definition/threshold.
REGULATED = (r"(?i)\b(healthy|all[-\s]?natural|100%\s*natural|low[-\s](fat|sodium|calorie|carb)|"
             r"fat[-\s]?free|sugar[-\s]?free|calorie[-\s]?free|no sugar added|high in|"
             r"good source of|excellent source|reduced\s+\w+|\blight\b|\blite\b|lean\b|"
             r"gluten[-\s]?free|keto\b|superfood|antioxidant|probiotic|heart[-\s]healthy)\b")

# Allergen keyword -> the FALCPA major allergen it signals (9 since sesame, Jan 2023).
ALLERGENS = {
    "milk": r"(?i)\b(milk|butter(?!nut)|cheese|cream(?!\s+of\s+tartar)|yogurt|whey|casein|ghee|custard)\b",
    "egg": r"(?i)\b(egg|eggs|albumen|mayonnaise|meringue)\b",
    "fish": r"(?i)\b(fish|anchov\w+|salmon|tuna|cod|tilapia|fish sauce|worcestershire)\b",
    "shellfish": r"(?i)\b(shrimp|prawn|crab|lobster|crawfish|crayfish|scallop|clam|mussel|oyster)\b",
    "tree nut": r"(?i)\b(almond|walnut|pecan|cashew|pistachio|hazelnut|macadamia|brazil nut|pine nut)\b",
    "peanut": r"(?i)\b(peanut|groundnut)\b",
    "wheat": r"(?i)\b(wheat|all[-\s]?purpose flour|bread flour|semolina|farro|spelt|durum|couscous)\b",
    "soy": r"(?i)\b(soy|soybean|tofu|edamame|soy sauce|tempeh|miso)\b",
    "sesame": r"(?i)\b(sesame|tahini)\b",
}
HAS_CONTAINS = r"(?i)\b(contains|allergens?|allergy|may contain)\b.{0,60}\b(milk|egg|fish|shellfish|nut|peanut|wheat|soy|sesame|gluten)\b"


def _load(src):
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"user-agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read(MAX).decode("utf-8", "replace")
    if src == "-":
        return sys.stdin.read(MAX)
    with open(src, encoding="utf-8", errors="replace") as fh:
        return fh.read(MAX)


def strip_html(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html)).strip()


def _hits(text, patterns):
    out = []
    for p in (patterns if isinstance(patterns, list) else [patterns]):
        for m in re.finditer(p, text):
            out.append(" ".join(m.group(0).split())[:70])
    seen, uniq = set(), []
    for h in out:
        k = h.lower()
        if k not in seen:
            uniq.append(h); seen.add(k)
    return uniq


def review(src, log=print):
    raw = _load(src)
    text = strip_html(raw) if "<" in raw[:2000] else raw
    disease = _hits(text, DISEASE)
    regulated = _hits(text, REGULATED)
    allergens = [a for a, pat in ALLERGENS.items() if re.search(pat, text)]
    has_contains = bool(re.search(HAS_CONTAINS, text))

    verdict = ("POSSIBLE MISBRANDING" if disease else
               "REVIEW" if (regulated or allergens) else
               "CLEAN (automated)")
    if log:
        print("THE FOOD CREW - food-regulatory first pass; flags patterns, renders no verdict (zero model calls)")
        print("Source: %s\n" % src)
        print("--- disease / drug claims (FDA prohibits these on a food) ---")
        if disease:
            for h in disease:
                print("  [FLAG] reads as a disease/drug claim: %r" % h)
        else:
            print("  [ok]   no disease/drug claim pattern found")
        print("\n--- allergens (FALCPA: 9 majors) ---")
        if allergens:
            print("  allergen-bearing ingredients detected: %s" % ", ".join(sorted(allergens)))
            if has_contains:
                print("  [ok]   a 'Contains' / allergen statement is present - confirm it lists all of the above")
            else:
                print("  [FLAG] no 'Contains' allergen statement found. For a packaged product FALCPA "
                      "requires one; for a recipe, declaring them is the courtesy that prevents harm")
        else:
            print("  [ok]   no major-allergen ingredient keyword detected (keyword scan, conservative)")
        print("\n--- regulated claim terms (allowed only if the FDA definition is met) ---")
        if regulated:
            print("  [flag] substantiate or meet the definition: %s" % ", ".join(regulated))
        else:
            print("  [ok]   no regulated claim term found")
        print("\n--- not checked (and not a pass) ---")
        print("  - the actual nutrient values behind any claim, and whether a claim is substantiated")
        print("  - the full label panel, net weight, ingredient order, country of origin")
        print("  - USDA (meat/poultry/egg) and TTB (alcohol) rules, and any state rules")
        print("  - whether an allergen hides in a compound ingredient the keyword scan missed")
        print("\n== VERDICT: %s ==" % verdict)
        print("   Flags only. FDA / FALCPA / health-claim calls are a professional's; route to `counsel`.")
    return {"verdict": verdict, "disease": disease, "regulated": regulated,
            "allergens": allergens, "has_contains": has_contains}


def main():
    args = sys.argv[1:]
    md_out = args[args.index("--md") + 1] if "--md" in args else None
    pos = [a for a in args if not a.startswith("--") and a != md_out]
    if not pos:
        print(__doc__.strip())
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--json" in args:
        from hardhats.crews import _emit
        try:
            rep = review(pos[0], log=None)
        except Exception as e:  # noqa: BLE001
            print("food: could not read %s (%s)" % (pos[0], e), file=sys.stderr)
            return 2
        return _emit.emit("food", rep, 1 if rep["verdict"] == "POSSIBLE MISBRANDING" else 0)
    try:
        if md_out:
            import io
            buf = io.StringIO()
            rep = review(pos[0], log=lambda *a: print(*a, file=buf))
            with open(md_out, "wb") as fh:
                fh.write(buf.getvalue().encode("utf-8"))
            print("wrote %s (verdict: %s)" % (md_out, rep["verdict"]))
        else:
            rep = review(pos[0])
    except Exception as e:  # noqa: BLE001 - one line, not a traceback
        print("food: could not read %s (%s)" % (pos[0], e), file=sys.stderr)
        return 2
    return 1 if rep["verdict"] == "POSSIBLE MISBRANDING" else 0


if __name__ == "__main__":
    sys.exit(main())
