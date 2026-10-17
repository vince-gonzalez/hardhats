# hardHats

**coldHat is for play; hardHats are for work.** hardHats is the framework — the
factory that makes crews. A crew is a line-up of agents, each **wearing a hat**,
run across a federation of free model backends.

A **hat** is one of two things:
- an **LLM hat** — a model wearing an instruction (a role, a method, an output rule), or
- a **gate hat** — a deterministic function: a real check, a linter, a measurement.

The same engine runs both, so a crew can put an LLM drafter and a deterministic
verifier on the same line. That is the point: the LLM hats do the judgement, the
gate hats do the facts, and nobody has to trust a model for something a rule can decide.

## A crew is config, not code
```python
from hardhats import Hat, Crew

crew = Crew("grant", [
    Hat("researcher", model=("groq", "openai/gpt-oss-20b"),
        instruction="List what a Statement of Need must establish."),
    Hat("writer", model=("github", "openai/gpt-4o"),
        instruction="Draft it in a cold, plain register. No AI-tell words."),
    Hat("critic", gate=slopgate),          # a deterministic gate hat
])

# pre-flight the crew against a conflict graph before it runs
conflicts = crew.preflight(load("dataset/prompt-conflicts.json"))

outputs = crew.run("Write a Statement of Need for an accessibility tool.")
```
Each hat sees the task and every prior hat's output, down the line.

## The federation
`hardhats.backends` speaks to one `chat()` over many OpenAI-compatible (and Gemini)
backends — Gemini, Groq, OpenRouter, Ollama, plus GitHub Models, Cloudflare Workers
AI, Cerebras, Mistral, NVIDIA NIM, SambaNova and Cohere — each read from the
environment, keys never printed. Add a key, gain a perspective.

## Crews in the family
- **a11yhat** — the WCAG accessibility machine, four crew leads as deterministic gate hats.
- a grant crew, a compliance crew, a prompt-check crew — each a few lines of config.

## Tests
`python -m unittest discover -s tests` — the engine (pipeline + pre-flight) is
verified with gate hats only, so it proves out with zero model calls.

## License
Not chosen yet — the owner's call before publishing.
