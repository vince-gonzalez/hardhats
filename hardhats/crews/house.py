"""
hardHats crew: the house gate.

coldHat is for play; hardHats are for work. This is the work crew every
F-Keys artifact passes before it ships: the house gates, each worn as a
deterministic gate hat, with an optional LLM foreman on the end that reads
the findings and says in plain words what failed.

The gate hats do the facts. The foreman does the judgement. Nobody trusts a
model for a thing a rule can decide - which is the whole point of hardHats.

    python -m hardhats.crews.house <path> [--summary] [--backend groq] [--tools DIR]

Exit 1 if any gate fails, else 0 - so it drops into a pre-commit hook or CI
exactly where the raw scripts sat.
"""
from __future__ import annotations

import os
import subprocess
import sys

from ..crew import Crew, Hat

# The house gates live beside his live pre-publish hook. Point HARDHATS_TOOLS
# at another checkout to run a different copy.
DEFAULT_TOOLS = os.environ.get("HARDHATS_TOOLS", r"C:\tmp\f-keys\tools")

# (script, hat name, what it decides). Each gate exits non-zero on a finding;
# the exit code IS the verdict, so the crew wraps whatever ships without
# reaching inside it.
GATES = [
    ("slopgate.py",      "slopgate",  "does the prose read as machine-written"),
    ("a11y.py",          "a11y",      "WCAG 2.2 A/AA decidable from static HTML"),
    ("contrast.py",      "contrast",  "WCAG contrast ratios, inline styles too"),
    ("typefloor.py",     "typefloor", "body text at or above the size floor"),
    ("deadname_gate.py", "deadname",  "no retired name anywhere in the bytes"),
    ("version_gate.py",  "version",   "version strings agree across the repo"),
    ("brand-gate.py",    "brand",     "no retired brand name"),
]


def run_gate(script: str, target: str, tools: str) -> str:
    """Run one house gate on the target and turn its exit code into a verdict."""
    path = os.path.join(tools, script)
    if not os.path.isfile(path):
        return f"SKIP   {script} not found in {tools}"
    try:
        p = subprocess.run([sys.executable, path, target],
                           capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return "ERROR  gate timed out"
    verdict = "PASS" if p.returncode == 0 else "FAIL"
    lines = (p.stdout or p.stderr or "").strip().splitlines()
    tail = "\n       ".join(ln.rstrip() for ln in lines[-8:] if ln.strip())
    return f"{verdict}\n       {tail}" if tail else verdict


def _gate_hat(script: str, name: str, target: str, tools: str) -> Hat:
    # A gate hat measures a file, so it ignores the pipeline payload and closes
    # over the target. Default-arg capture keeps each lambda bound to its own gate.
    return Hat(name, gate=lambda _payload, s=script, t=target, tl=tools: run_gate(s, t, tl))


FOREMAN = (
    "You are the gate foreman. Below are the house gates' verdicts on one file. "
    "In five lines or fewer, plainly, name what failed and what the writer must "
    "change. If every gate passed, say so in one line. Add no praise, no caveats, "
    "nothing that is not in the findings."
)


def house_crew(target: str, tools: str = DEFAULT_TOOLS,
               foreman: tuple | None = None) -> Crew:
    """A crew of the house gates present in `tools`, plus an optional LLM foreman.

    `foreman` is (backend, model) to add the summarising hat; None keeps the
    crew all-gates, which runs with zero model calls."""
    hats = [_gate_hat(script, name, target, tools)
            for script, name, _ in GATES
            if os.path.isfile(os.path.join(tools, script))]
    if foreman:
        hats.append(Hat("foreman", model=foreman, instruction=FOREMAN,
                        temperature=0.0, max_tokens=400))
    return Crew("house", hats)


def main() -> int:
    args = sys.argv[1:]
    tools = DEFAULT_TOOLS
    if "--tools" in args:
        tools = args[args.index("--tools") + 1]
    backend = "mistral"   # a clean instruction-follower; override with --backend
    if "--backend" in args:
        backend = args[args.index("--backend") + 1]
    foreman = None
    if "--summary" in args:
        from ..backends import BACKENDS
        foreman = (backend, BACKENDS[backend]["models"][0])
    positional = [a for a in args if not a.startswith("--")]
    # drop values that followed a flag
    for flag in ("--tools", "--backend"):
        if flag in args:
            val = args[args.index(flag) + 1]
            if val in positional:
                positional.remove(val)
    if not positional:
        print("usage: python -m hardhats.crews.house <path> [--summary] "
              "[--backend groq] [--tools DIR]")
        return 2
    target = positional[0]

    crew = house_crew(target, tools, foreman)
    gate_names = [h.name for h in crew.hats if h.kind == "gate"]
    if not gate_names:
        print(f"no house gates found in {tools} (set HARDHATS_TOOLS)")
        return 2

    print(f"hardHats house crew on {target}")
    print(f"  {len(gate_names)} gate hats" + (" + foreman" if foreman else "")
          + f"  (gates from {tools})\n")

    outputs = crew.run(f"Pre-publish gate on {target}",
                       log=lambda m: print("  ..", m))
    print()

    failed = []
    for h in crew.hats:
        out = outputs.get(h.name, "")
        if h.kind == "gate":
            head = out.splitlines()[0] if out else "?"
            print(f"  [{head:5}] {h.name}")
            body = "\n".join(out.splitlines()[1:])
            if body.strip():
                print(body)
            if head.startswith("FAIL") or head.startswith("ERROR"):
                failed.append(h.name)
        else:
            print(f"\n  foreman ({h.model[0]}):\n{out}\n")

    print()
    if failed:
        print(f"  NO SHIP - {len(failed)} gate(s) failed: {', '.join(failed)}")
        return 1
    print("  SHIP - every house gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
