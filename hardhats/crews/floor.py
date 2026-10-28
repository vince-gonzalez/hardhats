"""
hardHats panel: THE FLOOR (run: `python -m hardhats.crews.floor`). The taste layer that turns a build
into a product - the three it has to survive on the floor:
  THE STRANGER   - a cold player, thirty seconds in: can they tell what to do and whether they're winning?
  THE SCREENSHOT - is there one moment in this worth posting, unprompted?
  THE WORD       - who drags a friend to it, what do they say, and where does that crowd already gather?

This is NOT a gated seat (no `(keyword ...)` tag, so not a quick-summon): nothing deterministic checks
taste, so it cannot fake a pass/fail. That is exactly why it is a PANEL - three models on DECORRELATED
backends arguing it out - instead of one seat pretending to a verdict. A full run calls those models,
so it is put on the floor on purpose:

    python -m hardhats.crews.floor <game-dir-or-file>          # the floor + who's on it
    python -m hardhats.crews.floor <game-dir-or-file> --run    # put it on the floor (calls the models)

Before anyone speaks, the gated seats (`seizure`, `og`, `pwa`) run - zero model calls - and their
verdicts are the first facts on the floor. THE SCREENSHOT can't call it shareable when `og` says the
card is missing; THE STRANGER can't call it safe when `seizure` found a flash hazard. The gates settle
the facts; the floor judges only what no rule can.

🛑 THE FLOOR is advisory. Its output is a read, not a gate - take it to a human, do not merge on it.
"""
from __future__ import annotations

import os
import sys

from hardhats import Crew, Hat
from hardhats.crews import og, pwa, seizure

STRANGER = (
    "You are THE STRANGER. You walked up to this game thirty seconds ago and nobody told you anything. "
    "Say plainly whether you can tell what to do, what is happening, and whether you are winning - and "
    "name the exact moment you got lost. One moment, one fix. Do not praise, do not invent features, do "
    "not soften it. Never contradict a gate verdict in the facts above.")
SCREENSHOT = (
    "You are THE SCREENSHOT. You decide whether there is one frame, one sound, one moment in this worth "
    "posting without being asked. Name it, or say there isn't one yet - then name the cheapest change "
    "that would create one. No mood-board words, no flattery, no new scope. Stay inside the facts above.")
WORD = (
    "You are THE WORD - word of mouth. Name the smallest, most specific crowd that would drag a friend to "
    "this, the exact sentence they would say to do it, and the one place that crowd already gathers. If "
    "the share-card or install facts above are weak, that is the first fix. No 'go viral', no growth-"
    "hacking - a real crowd, a real sentence, a first move.")

# Decorrelated on purpose: three vendors (Google / OpenAI-oss / Nvidia), so no one model's blind spot
# or flattery carries the floor. (key, handle, backend, model, instruction).
HATS = [
    ("the-stranger", "THE STRANGER", "gemini", "gemini-flash-lite-latest", STRANGER),
    ("the-screenshot", "THE SCREENSHOT", "groq", "openai/gpt-oss-120b", SCREENSHOT),
    ("the-word", "THE WORD", "openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", WORD),
]


def _fact(seat_name, fn, target):
    def gate(_payload):
        try:
            return "%s -> %s" % (seat_name, fn(target, log=None)["verdict"])
        except Exception as e:  # noqa: BLE001 - a floor fact must never crash the panel
            return "%s -> (could not run: %s)" % (seat_name, type(e).__name__)
    return gate


def build_crew(target):
    """THE FLOOR for one game: the gate floor first (deterministic), then the three taste hats."""
    hats = [
        Hat("facts-seizure", gate=_fact("seizure", seizure.review, target)),
        Hat("facts-og", gate=_fact("og", og.review, target)),
        Hat("facts-pwa", gate=_fact("pwa", pwa.review, target)),
    ]
    for key, _handle, backend, model, instruction in HATS:
        hats.append(Hat(key, model=(backend, model), instruction=instruction,
                        temperature=0.5, max_tokens=500))
    return Crew("floor", hats)


def main():
    args = sys.argv[1:]
    run = "--run" in args
    pos = [a for a in args if not a.startswith("--")]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if not pos:
        print(__doc__.strip())
        return 2
    target = pos[0]
    if not os.path.exists(target):
        print("floor: no such path: %s" % target, file=sys.stderr)
        return 2
    crew = build_crew(target)

    print("THE FLOOR - the taste panel (advisory; NOT a gate)")
    print("Game: %s\n" % target)
    print("--- the facts on the floor (gated seats, zero model calls) ---")
    for hat in crew.hats:
        if hat.kind == "gate":
            print("  " + hat.wear(""))
    print("\n--- who's on the floor (decorrelated backends) ---")
    for _key, handle, backend, model, _ in HATS:
        print("  %-16s %s / %s" % (handle, backend, model))

    if not run:
        print("\n  add --run to put it on the floor (it calls the models above).")
        print("== THE FLOOR: ROSTER ONLY (no models called) ==")
        return 0

    print("\n--- on the floor (one pass; each sees the facts and every prior read) ---\n")
    outputs = crew.run("Judge this game as a product about to ship. Be specific and blunt.")
    for key, handle, _, _, _ in HATS:
        print("### %s\n%s\n" % (handle, outputs.get(key, "(no output)")))
    print("== THE FLOOR: ADVISORY - take it to a human, do not merge on it ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
