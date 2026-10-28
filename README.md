# hardHats

**A verdict a chatbot can't fake.**

Point hardHats at a file, a folder, or a URL and it returns PASS or FAIL with the finding —
because a real check produced it, not an opinion. A chatbot can write a paragraph that *looks*
like a security review; it cannot hand you the file and line of the committed secret. hardHats
hands you the line.

## 30 seconds

```
pip install hardhats
python -m hardhats.crews                    # list the seats
python -m hardhats.crews crypteng ./src     # e.g. scan a tree for committed secrets
python -m hardhats.crews sec https://your.site
```

Add `--json` to any seat for a machine-readable verdict a script or another agent can read.
The exit code *is* the verdict: `0` clears, `1` caught the defect.

## Why it holds

A seat is a crew of **hats**, and a hat is one of two things:

- a **gate hat** — a deterministic function: a real check, a measurement, a linter;
- an **LLM hat** — a model wearing an instruction.

The gate hats settle the facts. The LLM hats do only the judgement a rule can't, and they are
handed the facts *after* they exist — they cannot overrule a gate and are never asked whether
something passed. That is the moat: the output is a finding with a location, not a vibe. Every
seat also prints what it did **not** check, so a clean result never reads as a blank cheque.

## The bench — an expert for the call

40 seats, summoned by keyword, each gated on a real external standard it cannot fake:

| keyword | what it catches |
|---|---|
| `crypteng` | a secret committed in the clear, or crypto broken by design (values redacted) |
| `tests` | a test suite that only *looks* real — mutation testing, not a green checkmark |
| `sec` | missing OWASP secure headers on a live URL |
| `schema` | SQL without primary keys or indexed foreign keys |
| `resilient` | errors swallowed where a failure should surface |

…and 35 more — `inject` (RCE / injection patterns), `ghactions` (CI-workflow security), `seizure` (photosensitive-flash safety), `pwa` (installable), `og` (shareable), `gameperf` (60 fps hold), `traffic` (human-vs-bot reach), `attribution` (UTM integrity), `seo` (indexability floor), `deliverability` (email auth), `community` / `loop` / `relay` (the distribution plays), `api`, `cite`, `proof`, `vision`, `geom`, `i18n`, `perf`, `links`, `env`, `richdata`, `spec`, `method`, `archive`, `repro`, `deps`, `food`, `ops`, `balance`, `cipher`, `privacy`, `license`, `route`.

Don't know which seat? Point the router at the thing and it picks:

```
python -m hardhats.crews route ./my-project
python -m hardhats.crews ./openapi.json        # a bare path routes too
```

Full catalog, with the standard behind each gate: [`hardhats/crews/README.md`](hardhats/crews/README.md).

## Gate your repo (CI / pre-commit)

The exit code *is* the verdict, so any seat drops into a pipeline as a gate — `1` fails the step.

```yaml
# .github/workflows/gate.yml
name: gate
on: [push, pull_request]
jobs:
  hardhats:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install hardhats
      - run: python -m hardhats.crews crypteng .     # a committed secret fails the build
      - run: python -m hardhats.crews resilient .    # a swallowed error fails the build
```

Catch it before it ever leaves your machine, with pre-commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: hardhats-crypteng
        name: hardhats crypteng
        entry: python -m hardhats.crews crypteng
        language: system
        pass_filenames: false
        args: ["."]
```

Want a report rather than a gate? Add `--json` and read the envelope — `exit`, `verdict`, `detail`.

## Build your own crew

The seats are built on a tiny engine, and a crew is config, not code:

```python
from hardhats import Hat, Crew

crew = Crew("review", [
    Hat("reader", model=("groq", "<model-id>"), instruction="List what a Statement of Need must establish."),
    Hat("check", gate=slopgate),          # a deterministic gate hat
])
outputs = crew.run("Draft a Statement of Need for an accessibility tool.")
```

`hardhats.backends` speaks one `chat()` across many free model backends, each read from the
environment — keys are never printed. Add a key, gain a perspective. Each hat sees the task and
every prior hat's output, down the line.

## Proven on every change

`python -m unittest discover -s tests` runs the bench's own gate suite: every seat against a
known-good input it must clear **and** a known-bad input it must catch. A GitHub Action runs it
on every push, across Python 3.11–3.13.

## License

MIT. Copyright Vincent Gonzalez / F-Keys Creative LLC.
