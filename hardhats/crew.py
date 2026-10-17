"""
hardHats - the crew engine. A crew is config, not code: an ordered list of hats.
A hat is either an LLM hat (a model wearing an instruction) or a gate hat (a
deterministic function - a real check, a linter, a measurement). The same engine
runs both, so a crew can mix an LLM drafter with a deterministic verifier.

  from hardhats import Hat, Crew

  crew = Crew("grant", [
      Hat("researcher", model=("groq", "openai/gpt-oss-20b"),
          instruction="List what a Statement of Need must establish."),
      Hat("writer", model=("groq", "openai/gpt-oss-120b"),
          instruction="Draft it in a cold, plain register. No AI-tell words."),
      Hat("critic", gate=my_slopgate_function),   # deterministic hat
  ])
  outputs = crew.run("Write a Statement of Need for ...")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .backends import chat


@dataclass
class Hat:
    """A role in the crew. LLM hat: set model + instruction. Gate hat: set gate."""
    name: str
    instruction: str = ""
    model: tuple | None = None          # (backend, model)
    gate: object = None                 # callable(payload: str) -> str
    temperature: float = 0.4
    max_tokens: int = 700

    @property
    def kind(self) -> str:
        return "gate" if self.gate else "llm"

    def wear(self, payload: str) -> str:
        if self.gate:
            return str(self.gate(payload))
        if not self.model:
            raise ValueError(f"hat '{self.name}' has neither a model nor a gate")
        prompt = f"{self.instruction}\n\n---\n{payload}" if self.instruction else payload
        return chat(self.model[0], prompt, model=self.model[1],
                    temperature=self.temperature, max_tokens=self.max_tokens)


class Crew:
    """An ordered pipeline of hats. Each hat sees the task and every prior output."""

    def __init__(self, name: str, hats: list[Hat]):
        self.name = name
        self.hats = hats

    def preflight(self, conflicts: list | None = None):
        """Check the crew's LLM hats for conflicting instructions before they run.
        `conflicts` is a list of (text_a, text_b, reason); supply the atom conflict
        graph (dataset/prompt-conflicts.json) to use the measured one."""
        if not conflicts:
            return []
        hats = [h for h in self.hats if h.kind == "llm"]

        def present(atom, text):
            words = {w for w in re.findall(r"[a-z]{4,}", atom.lower())
                     if w not in ("output", "section", "list", "only", "nothing", "your", "with")}
            if not words:
                return False
            return sum(1 for w in words if w in text.lower()) >= max(1, len(words) // 2)

        found = []
        for a, b, reason in conflicts:
            for i, ha in enumerate(hats):
                for hb in hats[i + 1:]:
                    if present(a, ha.instruction) and present(b, hb.instruction):
                        found.append((ha.name, hb.name, reason))
        return found

    def run(self, task: str, log=print) -> dict:
        context = f"Task: {task}"
        outputs: dict[str, str] = {}
        for hat in self.hats:
            if log:
                log(f"[{hat.name}] ({hat.kind}) ...")
            out = hat.wear(context).strip()
            outputs[hat.name] = out
            context += f"\n\n{hat.name} produced:\n{out}"
        return outputs
