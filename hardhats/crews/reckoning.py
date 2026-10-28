"""
hardHats panel: THE RECKONING (run: `python -m hardhats.crews.reckoning`). The judging tier of the
distribution crew - where a reach claim gets reckoned with. The epistemology heart: a number is not a
result until it survives three skeptics.
  THE SOURCE    - from WHERE? provenance and attribution, or is it "direct / unknown"?
  THE HEADCOUNT - how many HUMANS? net of bots, duplicates, bounces, your own team.
  THE REPEAT    - REPEATABLE, or luck / a one-off spike / someone else's audience?

This is NOT a gated seat (no `(keyword ...)` tag): judgement has no deterministic standard, so it cannot
fake a pass/fail. It is a PANEL - three skeptics on DECORRELATED backends - and a full run calls those
models, so it is run on purpose:

    python -m hardhats.crews.reckoning "<reach claim>" [--log access.log] [--links links.txt] [--run]

Hand it the evidence and the gates run first (zero model calls): `--log` runs THE BOUNCER (the real
bot share), `--links` runs THE LEDGER (the real attribution), so the skeptics argue from measured facts,
not vibes. THE HEADCOUNT will apply a measured bot share to the claimed number out loud.

🛑 THE RECKONING is advisory - it hands you the questions a reach claim must answer, not a verdict to
merge on. Its job is to make a vanity number expensive to keep believing.
"""
from __future__ import annotations

import os
import sys

from hardhats import Crew, Hat
from hardhats.crews import attribution, traffic

SOURCE = (
    "You are THE SOURCE. You do not accept a reach number until you know where it came from. For this "
    "claim, list the exact provenance questions it must answer before the number means anything: which "
    "specific channel, attributed how, and what share is 'direct / unknown'. If the attribution facts "
    "above show untagged or drifting links, that is your opening - say so. Name the one check that would "
    "settle it. Do not flatter the number.")
HEADCOUNT = (
    "You are THE HEADCOUNT. You only count humans. Strip the claim down: of the raw number, how much is "
    "bots, duplicates, bounces, and the team's own traffic? If the traffic facts above give a bot share, "
    "apply it to the claimed number OUT LOUD and state the human-adjusted figure. Name the single "
    "measurement that turns this from a vanity number into a real one. Give no benefit of the doubt.")
REPEAT = (
    "You are THE REPEAT. A number you cannot reproduce is an anecdote. Ask of this claim: was it caused by "
    "a repeatable action, or by luck, a one-off spike, or someone else's audience? Could you run it again "
    "next week and land within range? Name the one thing that would have to be true for this to be a "
    "CHANNEL and not a story. Be blunt about survivorship.")

# Decorrelated on purpose: three vendors, so no one model's credulity carries the room.
SKEPTICS = [
    ("the-source", "THE SOURCE", "gemini", "gemini-flash-lite-latest", SOURCE),
    ("the-headcount", "THE HEADCOUNT", "groq", "openai/gpt-oss-120b", HEADCOUNT),
    ("the-repeat", "THE REPEAT", "openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free", REPEAT),
]


def _fact(seat_name, fn, target):
    def gate(_payload):
        try:
            return "%s -> %s" % (seat_name, fn(target, log=None)["verdict"])
        except Exception as e:  # noqa: BLE001 - a floor fact must never crash the panel
            return "%s -> (could not run: %s)" % (seat_name, type(e).__name__)
    return gate


def build_crew(claim, log_path=None, links_path=None):
    """THE RECKONING for one reach claim. Evidence grounds it: a traffic log runs THE BOUNCER, a links
    file runs THE LEDGER, and those verdicts are the facts the skeptics argue from."""
    hats = []
    if log_path and os.path.isfile(log_path):
        hats.append(Hat("facts-traffic", gate=_fact("traffic", traffic.review, log_path)))
    if links_path and os.path.isfile(links_path):
        hats.append(Hat("facts-attribution", gate=_fact("attribution", attribution.review, links_path)))
    for key, _handle, backend, model, instruction in SKEPTICS:
        hats.append(Hat(key, model=(backend, model), instruction=instruction,
                        temperature=0.4, max_tokens=550))
    return Crew("reckoning", hats)


def main():
    args = sys.argv[1:]
    run = "--run" in args
    log_path = args[args.index("--log") + 1] if "--log" in args else None
    links_path = args[args.index("--links") + 1] if "--links" in args else None
    pos = [a for a in args if not a.startswith("--") and a not in (log_path, links_path)]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if not pos:
        print(__doc__.strip())
        return 2
    claim = pos[0]
    crew = build_crew(claim, log_path=log_path, links_path=links_path)

    print("THE RECKONING - the reach-skeptic panel (advisory; NOT a gate)")
    print("Claim: %s\n" % claim)
    facts = [h for h in crew.hats if h.kind == "gate"]
    if facts:
        print("--- the evidence on the table (gated seats, zero model calls) ---")
        for h in facts:
            print("  " + h.wear(""))
        print("")
    else:
        print("  (no evidence attached - pass --log access.log and/or --links links.txt to ground it)\n")
    print("--- the skeptics (decorrelated backends) ---")
    for _key, handle, backend, model, _ in SKEPTICS:
        print("  %-16s %s / %s" % (handle, backend, model))

    if not run:
        print("\n  add --run to convene the reckoning (it calls the models above).")
        print("== THE RECKONING: ROSTER ONLY (no models called) ==")
        return 0

    print("\n--- the reckoning (each skeptic sees the evidence and every prior one) ---\n")
    outputs = crew.run("Stress-test this reach claim. Be a skeptic; argue from the evidence above.")
    for key, handle, _, _, _ in SKEPTICS:
        print("### %s\n%s\n" % (handle, outputs.get(key, "(no output)")))
    print("== THE RECKONING: QUESTIONS, NOT A VERDICT - answer them before you believe the number ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
