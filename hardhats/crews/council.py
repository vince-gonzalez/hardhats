"""
hardHats: the panel engine shared by the verdict benches - The Devs, the Academic
Jury, Apex Six, the Numerical Operators, the Hex Codex.

A panel fans one subject out to independent members. Each member is an LLM hat on
its OWN backend (round-robin across the roster) so the room is genuinely
decorrelated - independent models, not one model doing every voice. Each member
returns a verdict; the board's own protocol aggregates them.

Pipelines - The Seven Notes (A..G compose) and The Three Voices (re-key) - are
sequential handoffs, so they use the base Crew class instead of this.

One primitive, every bench: `ask()` calls one member and rolls to the next backend
on failure or a non-answer; `convene()` runs a whole panel with each member on its
own primary; `tag()` reads a machine verdict line.
"""
from __future__ import annotations

from ..backends import BACKENDS, chat

# Clean instruction-followers lead; groq's reasoning model (which dumps its
# scratchpad instead of a verdict) sits last, as a fallback only.
ROSTER = ["gemini", "cohere", "mistral", "openrouter", "cloudflare", "groq"]

EXCERPT_NOTE = ("The material below may be an excerpt; if it ends mid-tag or "
                "mid-sentence that is the excerpt boundary, not a defect.")


def rotate(i: int, roster: list | None = None) -> list:
    r = roster or ROSTER
    n = len(r)
    return r[i % n:] + r[:i % n]


def tag(verdict: str) -> str:
    """Read a machine verdict line out of a member's answer."""
    v = verdict.upper()
    if "BLOCK" in v and "VERDICT: PASS" not in v:
        return "BLOCK"
    if "UNAVAILABLE" in v or v.startswith("ERROR"):
        return "UNAVAILABLE"
    if "VERDICT: FAIL" in v or v.startswith("FAIL"):
        return "FAIL"
    if "VERDICT: PASS" in v:
        return "PASS"
    return "UNCLEAR"


def ask(instruction: str, subject: str, roster: list,
        require_tag: bool = True, temperature: float = 0.2,
        max_tokens: int = 350) -> tuple:
    """Run one member, rolling across `roster` on failure. When require_tag is
    True an answer with no VERDICT/BLOCK line isn't an answer (a reasoning model
    that rambled) and we roll on. Returns (text, backend) or (UNAVAILABLE, None)."""
    prompt = f"{instruction}\n\n{EXCERPT_NOTE}\n\n--- MATERIAL UNDER REVIEW ---\n{subject}"
    for backend in roster:
        model = BACKENDS[backend]["models"][0]
        try:
            out = chat(backend, prompt, model=model, temperature=temperature,
                       max_tokens=max_tokens, attempts=1).strip()
            if not out:
                continue
            if require_tag and tag(out) not in ("PASS", "FAIL", "BLOCK"):
                continue
            return out, backend
        except Exception:  # noqa: BLE001 - roll to the next backend
            continue
    return "UNAVAILABLE - no backend answered", None


def convene(members: list, subject: str, require_tag: bool = True,
            temperature: float = 0.2, max_tokens: int = 350, log=None) -> dict:
    """Run a panel. `members` is a list of (name, instruction). Each member gets
    its own primary backend (round-robin) with the rest as fallback. Returns
    {name: (text, backend)} in member order."""
    results: dict[str, tuple] = {}
    for i, (name, instruction) in enumerate(members):
        text, backend = ask(instruction, subject, rotate(i), require_tag,
                            temperature, max_tokens)
        if log:
            mark = tag(text) if require_tag else ("--" if backend is None else "ok")
            via = f"[{backend}]" if backend else ""
            log(f"  {mark:5} {name:22} {via}")
        results[name] = (text, backend)
    return results


def read_subject(target: str, cap: int = 12000) -> tuple:
    """Read a file (or treat the string as inline text) for review. Returns
    (text, truncated)."""
    import os
    if os.path.isfile(target):
        raw = open(target, encoding="utf-8", errors="replace").read()
    else:
        raw = target
    return raw[:cap], len(raw) > cap
