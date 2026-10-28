# hardHats crews — the bench

**An expert for every call, but only where "expert" means a standard, not a vibe.**

Each crew here is a world-class professional seat you summon by keyword. A seat earns its
place by one rule: it must answer to a real external **standard** (WCAG, OpenAPI, the FDA
label rules, a Metamath kernel, CIEDE2000), and that standard is its **gate**, the thing it
cannot fake and you can hold it to. The persona is just the handle; the gate is the job.
"THE SWEAT" (frame data) earns a seat; "MICDROP AFICIONADO" does not, because nothing checks it.

The bench is indexed by **condition** (what recurs across the work), not by domain (which is
infinite). Every seat is deterministic unless noted, prints what it **did not** check, and
routes the judgement a rule cannot make to a human.

## Summon

```
python -m hardhats.crews                 # list every seat
python -m hardhats.crews <keyword> ...   # run one; args pass straight through
python -m hardhats.crews geom "2*pi/sqrt(27) < 1.2092"
python -m hardhats.crews resilient ./src
python -m hardhats.crews schema ./app.sql --json   # machine-readable, for coldHat / hardHats
```

The dispatcher discovers seats automatically: any module whose docstring carries a
`` (keyword `x`) `` tag registers itself, so the bench grows without editing the dispatcher.

Add `--json` to any seat and it prints one envelope instead of the human report, so coldHat /
hardHats can **call** a seat and read the result rather than scrape a CLI:

```json
{"seat": "schema", "verdict": "SCHEMA RISK - table(s) with no primary key", "exit": 1, "ok": false,
 "detail": {"tables": ["logs", "users"], "no_pk": ["logs"], "unindexed_fk": [["logs", "user_id"]]}}
```

`exit` is the same code the seat returns from the shell — `0` clears, `1` caught the defect, `2` a
usage or read error — and `ok` is `exit == 0`. The verdict logic stays in the seat; the shared
emitter only serialises it.

## The bench

Everything below runs as `python -m hardhats.crews <keyword> <args>`.

### Code & release
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `resilient` | Reliability / Failure-Mode Engineer — "THE PARANOID MECHANIC" | never-swallow-an-error, SRE resilience | `<dir-or-file>` |
| `sec` | Application-Security Engineer | OWASP Secure Headers | `<url>` |
| `crypteng` | Cryptography Engineer | hardcoded secrets + broken crypto (values redacted) | `<dir>` |
| `inject` | Application-Security Engineer | arbitrary-execution / injection: eval, pickle, unsafe yaml, shell (CWE-94/95/502/78) | `<dir>` |
| `ghactions` | CI-Security Engineer | GitHub Actions hardening: run: injection, pwn-request, mutable-branch / unpinned `uses:` | `<repo-or-workflows-dir>` |
| `deps` | Release Engineer | pinned-vs-floating deps + lockfile | `<dir>` |
| `tests` | SDET | static counts + mutation testing (on a temp copy) | `<dir> [--mutate f.py]` |
| `api` | API Architect | OpenAPI 3.x (ids, responses, versioning) | `<openapi.json\|.yaml>` |
| `schema` | Database Architect | primary keys, indexed FKs, normalisation | `<schema.sql>` |
| `i18n` | Localization Engineer | locale key parity + ICU placeholders | `<locale-dir>` |

### Web, infra & SEO
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `links` | Link-Integrity Checker | local href + `#anchor` liveness (offline; external listed) | `<site-dir>` |
| `richdata` | Structured-Data Analyst | schema.org JSON-LD + Google Rich Results required fields | `<page.html\|dir>` |
| `env` | Cloudflare Platform Engineer | wrangler-binding parity (every `env.X` declared) | `<worker-dir>` |
| `perf` | Web-Performance Engineer | Core Web Vitals (LCP / INP / CLS) via Lighthouse | `<url>` or `--report run.json` |
| `pwa` | PWA / Install Engineer | W3C Web App Manifest + baseline installability (manifest, 192+512 icons, service worker) | `<site-dir>` |
| `og` | Social / SEO Engineer | Open Graph protocol + Twitter Cards (does the link unfurl into a card) | `<page.html\|dir>` |
| `gameperf` | Game-Performance Engineer | frame budget (60 fps = 16.7 ms/frame) from a frame-time trace | `--trace frames.json` |

### Distribution & reach — the distribution-epistemology crew
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `traffic` | THE BOUNCER | access-log human-vs-bot share (declared-bot UA + rendered-nothing tell) | `<access.log>` |
| `attribution` | THE LEDGER | UTM tagging: source / medium / campaign present + consistent, no PII | `<links-file>` |
| `seo` | THE INDEX | on-page indexability floor: title, canonical, no noindex, robots / sitemap | `<page.html\|site-dir>` |
| `deliverability` | THE POSTMAN | email auth: SPF + DMARC policy (DKIM needs a selector) | `<domain>` or `--records recs.json` |

Those four **catch** - "is the reach real, attributable, findable, deliverable". These three are the
**do** - each a readiness gate plus a concrete playbook (the click-by-click), deterministic, with an
optional `--run` that asks one model to tailor the playbook to your content:

| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `community` | THE REGULAR | is the content value-first, not a pitch a community will remove? | `<page-or-file> [--run]` |
| `loop` | THE LOOP | is there a forwardable hook + a travelable asset (og) to carry a share? | `<page-or-file> [--run]` |
| `relay` | THE RELAY | does it carry what a syndication submit needs: title, description, image? | `<page-or-file> [--run]` |

(The **judge** tier is **THE RECKONING**, a panel, below. A backlink-reality gate is deliberately not
here: offline you cannot verify a link's authority or traffic, only its `rel` attribute and whether it
resolves, so a "backlink reality" gate would claim more than it can check.)

### Accessibility & craft
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `seizure` | Photosensitivity Analyst | WCAG 2.3.1 flash threshold (the Harding general-flash rule) | `<game-dir>` or `--trace trace.json` |
| `vpat` | 508 / ADA Conformance Specialist | VPAT 2.x (ITI) — **lives in the a11yhat repo** | `python -m a11yhat.vpat <url\|path>` |

(The full WCAG 2.2 machine is **a11yhat** itself; `vpat` renders its findings as a conformance doc.)

### Writing & standards
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `spec` | Standards Editor | RFC 2119 / 8174 normative keywords | `<doc.md\|->` |

### Research & scholarship
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `cite` | Reference Editor | DOI resolution (Crossref **and** DataCite) + retraction | `<doc>` |
| `repro` | Research Software Engineer | re-run checklist: steps, pinned env, citation, licence | `<dir>` |
| `method` | Methodologist / Biostatistician | CONSORT + OSF pre-registration | `<methods.txt\|.md\|.html>` |
| `archive` | Digital-Preservation Archivist | OAIS / FAIR — fixity, open formats, metadata | `<dir>` |
| `proof` | Proof / Formal-Methods Engineer | **runs a Metamath kernel** (mmverify), never its own | `<database.mm>` |
| `geom` | Discrete-Geometry Referee | certified interval arithmetic (outward rounding) | `"<inequality>"` |
| `cipher` | Classical Cryptanalyst | index of coincidence, entropy, Kasiski | `<text-file>` |

### Compliance, legal & money
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `license` | FOSS Licensing Counsel | SPDX / OSI — surfaces options, **never picks** | `<dir>` |
| `privacy` | EdTech Privacy Counsel | COPPA / FERPA signals — **not legal advice** | `<dir>` |
| `food` | Food Regulatory Specialist | FDA labeling + FALCPA allergens | `<url\|path>` |

### Domain & product
| keyword | seat | gate (the standard) | args |
|---|---|---|---|
| `vision` | Vision-Science Methodologist | CIEDE2000 (ΔE00) colour difference | `"#rrggbb" "#rrggbb"` or `--pairs f.json` |
| `ops` | Industrial / OR Analyst | bin-packing / load-plan feasibility | `<loadplan.json>` |
| `balance` | Competitive Balance Analyst — "THE SWEAT" | fighting-game frame data (true combos, infinites) | `<moves.json>` |

That is **40 gated seats**: the 39 crews in this package plus `vpat` in the a11yhat repo. A
non-gated **meta-seat**, `route`, dispatches to them by artifact type (below).

## The Router — dispatch by what it is

`route` is the one door that picks the seat FOR you, by what the artifact *is* rather than by a
keyword you remember:

```
python -m hardhats.crews route <path|dir|url>     # classify, then run the seat(s) that apply
python -m hardhats.crews ./app.sql                # a bare path or url auto-routes, no "route" needed
python -m hardhats.crews route ./project --json   # one envelope with each routed seat's verdict
```

| the artifact | routes to |
|---|---|
| `.mm` | `proof` |
| `.sql` / `.ddl` | `schema` |
| `.json` / `.yaml` with an openapi/swagger key | `api` |
| `.json` load plan (container + items) | `ops` |
| `.json` move table (moves / fps) | `balance` |
| `<bcp47>.json` locale (e.g. `en.json`) | `i18n`, on its directory |
| an `http(s)` url | `sec` |
| a `.github/workflows` directory | `ghactions` |
| a directory with a `manifest.json` / `*.webmanifest` | `pwa` |
| a directory | the dir-level seats whose signal is present — `deps`, `i18n`, `license`, `crypteng`, `resilient`, `tests`, `archive`, `repro` |

The Router runs each routed seat through the dispatcher with `--json`, so it reuses the seat's own
I/O and verdict — it decides *which* seat, never re-implements one. 🛑 It does not guess: free text
or anything no rule matches is **reported** (accessibility/WCAG is a11yhat / `vpat`, a separate repo),
not routed on a hunch.

## Proven on every change

Every seat here is backed by [`../../tests/test_bench.py`](../../tests/test_bench.py): each gate is
run against a known-good input it must clear **and** a known-bad input it must catch, so a change
that quietly breaks a gate fails the suite. The two seats that reach the network in production
(`cite`, `sec`) have their single network call replaced with a known oracle, so the classifier is
proven offline and deterministically. `proof` is held to its honesty rule — it never reports
VERIFIED without a real Metamath kernel, and when one is present it is run on a valid database and a
tampered copy.

    python -m unittest discover -s tests

A GitHub Action (`.github/workflows/bench.yml`) runs this same suite on every push and pull
request, on Python 3.11–3.13, so a change that quietly breaks a gate goes red before it merges.

## What is deliberately not here

- **Panels** — multi-model deliberation benches. A full run is a swarm, so they are run on their
  own, on purpose, not fired from a quick summon. The first is **THE FLOOR**
  (`python -m hardhats.crews.floor <game> [--run]`): the three a build has to survive to be a
  product. **THE STRANGER** (can a cold player tell what to do?), **THE SCREENSHOT** (is one moment
  worth posting?), **THE WORD** (who drags a friend, and from where?), as decorrelated-backend hats
  standing on the gated seats' facts (`seizure`, `og`, `pwa` run first, zero model calls). Taste has
  no standard to fake, so it is a panel, not a gate; advisory, a read for a human, never a merge gate.
  The second is **THE RECKONING** (`python -m hardhats.crews.reckoning "<claim>" [--log] [--links] [--run]`),
  the judging tier: it stress-tests a reach claim through **THE SOURCE** (from where?), **THE HEADCOUNT**
  (how many humans?) and **THE REPEAT** (repeatable, or luck?). Attach a log or a links file and the
  gates run first, so THE HEADCOUNT applies a measured bot share to the claimed number. It hands you the
  questions a number must answer, not a verdict.
- **The earlier crews** — a few workflow crews predate the keyword tag and run directly as
  `python -m hardhats.crews.<name>`.
- **Costume seats** — UX, docs, information architecture, brand, go-to-market, pricing, narrative,
  deal terms. No standard checks them, so they are not gated crews. They belong to coldHat as
  prompt-singles, or they need a decorrelated-backend panel to earn a seat.

## Licence

MIT. Copyright Vincent Gonzalez / F-Keys Creative LLC.
