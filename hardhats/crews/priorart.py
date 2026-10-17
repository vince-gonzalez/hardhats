"""
hardHats crew: the Prior-Art / Novelty crew. The board you wished you had before
you got scooped - twice. Its gate is a thing a chatbot cannot fake: LIVE searches
against arXiv and Crossref (public APIs, standard library, no key), pulling the real
closest prior work. Then a novelty panel judges the claim against what actually
exists. Verdict: NOVEL / ADJACENT / SCOOPED, with the closest prior work named.

    python -m hardhats.crews.priorart "<the claim in a sentence>" [--query "search terms"]
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

from .council import ask, convene, rotate

UA_STR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")


def _terms(claim: str) -> str:
    stop = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "on", "is", "are",
            "that", "this", "with", "from", "by", "as", "it", "we", "our", "can", "be"}
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z-]{2,}", claim.lower())
             if w not in stop]
    return " ".join(words[:8])


def search_arxiv(query: str, n: int = 5) -> list:
    # arXiv's all: field is picky - strip punctuation (a hyphen 400s the query).
    safe = re.sub(r"[^a-z0-9 ]", " ", query.lower()).strip()
    safe = " ".join(safe.split()[:6])
    url = ("https://export.arxiv.org/api/query?search_query=all:"
           + urllib.parse.quote(safe) + f"&max_results={n}")
    try:
        req = urllib.request.Request(url, headers={"user-agent": UA_STR})
        with urllib.request.urlopen(req, timeout=25) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return [f"(arXiv unreachable: {type(e).__name__})"]
    titles = re.findall(r"<entry>.*?<title>(.*?)</title>", xml, re.S)
    return [re.sub(r"\s+", " ", t).strip() for t in titles[:n]] or ["(no arXiv hits)"]


def search_crossref(query: str, n: int = 5) -> list:
    url = ("https://api.crossref.org/works?rows=%d&select=title,DOI,author&query="
           % n) + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers={"user-agent": UA_STR})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.load(r)
    except Exception as e:  # noqa: BLE001
        return [f"(Crossref unreachable: {type(e).__name__})"]
    out = []
    for it in data.get("message", {}).get("items", [])[:n]:
        title = (it.get("title") or ["(untitled)"])[0]
        out.append(f"{title[:110]} — {it.get('DOI','')}")
    return out or ["(no Crossref hits)"]


PANELISTS = [
    ("The Lexical Judge", "Compare the claim to the found prior work at the level of wording and terminology. Is the vocabulary already standard in this literature?"),
    ("The Structural Judge", "Compare the SHAPE of the argument/method to the prior work. Has this move - this construction, this pipeline - been made before?"),
    ("The Conceptual Judge", "Compare the underlying CLAIM, not the words. Is the core contribution already established, partially established, or genuinely open?"),
]

PANEL_RULE = ("You are given a claim and the real closest prior work found by live "
              "search. Judge ONLY your dimension. Name the single closest item and "
              "whether it pre-empts the claim. 2-3 lines. End with one line: "
              "`DIMENSION: NOVEL` / `ADJACENT` / `SCOOPED`.")


def review(claim, query=None, log=print):
    q = query or _terms(claim)
    if log:
        print(f"  search terms: {q!r}")
    arxiv = search_arxiv(q)
    crossref = search_crossref(q)
    if log:
        print("  arXiv:")
        for t in arxiv:
            print("    - " + t[:110])
        print("  Crossref:")
        for t in crossref:
            print("    - " + t[:110])
    priorwork = "arXiv:\n" + "\n".join(arxiv) + "\n\nCrossref:\n" + "\n".join(crossref)
    subject = f"CLAIM:\n{claim}\n\nCLOSEST PRIOR WORK (live search):\n{priorwork}"
    members = [(name, f"You are {name} on the novelty panel. {role}\n\n{PANEL_RULE}")
               for name, role in PANELISTS]
    if log:
        print("\n  novelty panel:")
    results = convene(members, subject, require_tag=False, temperature=0.2,
                      max_tokens=240, log=log)
    panel = "\n".join(f"{n}: {t}" for n, (t, _b) in results.items())
    synth = ("You are the chair of the novelty panel. Below are the three judges and "
             "the live prior-art hits. Render the verdict: `VERDICT: NOVEL`, `VERDICT: "
             "ADJACENT - <how to position against the nearest work>`, or `VERDICT: "
             "SCOOPED - <the work that pre-empts it>`. Name the single closest prior "
             "work. Terse.")
    verdict, vb = ask(synth, subject + "\n\n--- PANEL ---\n" + panel, rotate(0),
                      require_tag=False, temperature=0.1, max_tokens=300)
    return {"claim": claim, "arxiv": arxiv, "crossref": crossref,
            "results": results, "verdict": verdict}


def main():
    args = sys.argv[1:]
    query = None
    if "--query" in args:
        query = args[args.index("--query") + 1]
    pos = [a for a in args if not a.startswith("--") and a != query]
    if not pos:
        print('usage: python -m hardhats.crews.priorart "<claim>" [--query "terms"]')
        return 2
    claim = " ".join(pos)
    print("THE PRIOR-ART / NOVELTY CREW - live arXiv + Crossref, then a novelty panel")
    print("Chip count: 2 live searches (free) + 3 judges + the chair = ~4 model calls.\n")
    rep = review(claim, query)
    print("\n--- VERDICT ---")
    print(rep["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
