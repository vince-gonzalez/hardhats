"""
The bench's own gate suite: every keyword seat re-proven on BOTH a known-good
input (it must clear) and a known-bad input (it must catch the defect). This is
verify-the-verifier - the harness asserts each seat's own verdict against a
ground truth the harness owns, through a different mechanism than built the gate.

    python -m unittest discover -s tests          # run the whole suite
    python -m hardhats.crews.<name> ...           # see any one seat by hand

Two seats reach the network in production: `cite` resolves DOIs and `sec` reads a
URL. Here their single network call is replaced with a known oracle, so the
classifier is proven deterministically and offline; the live fetch is exercised
by hand. `proof` delegates to a Metamath kernel: the honesty property (it NEVER
reports VERIFIED without a real kernel) is proven everywhere, and when a kernel is
discoverable the VERIFIED / REJECTED pair is proven too.
"""
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fx(*parts):
    return os.path.join(FIX, *parts)


def text(*parts):
    with open(fx(*parts), encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def load(*parts):
    with open(fx(*parts), encoding="utf-8-sig", errors="replace") as fh:
        return json.load(fh)


from hardhats.crews import (api, archive, attribution, balance, cipher, cite, crypteng,
                            deliverability, deps, env, food, gameperf, geom, ghactions, i18n,
                            inject, licensing, links, method, og, ops, perf, privacy, proof,
                            pwa, repro, resilient, richdata, schema, sec, seizure, seo, spec,
                            traffic, vision)
from hardhats.crews import testing as testing_seat
from hardhats.crews import community, floor, loop, reckoning, relay
from hardhats import new

try:
    import opticquiz_cvd  # noqa: F401 - the vision seat delegates to it when present
    HAVE_CVD = True
except ImportError:
    HAVE_CVD = False

try:
    import certivl  # noqa: F401 - the geom seat delegates to it when present
    HAVE_CERTIVL = True
except ImportError:
    HAVE_CERTIVL = False

try:
    from authorecon import reference_check  # noqa: F401 - the cite seat delegates to it
    HAVE_AUTHORECON = True
except ImportError:
    HAVE_AUTHORECON = False


class CodeAndRelease(unittest.TestCase):
    def test_resilient(self):
        self.assertEqual(resilient.review(fx("resilient", "fragile"), log=None)["verdict"], "FRAGILE")
        self.assertTrue(resilient.review(fx("resilient", "clean"), log=None)["verdict"].startswith("HARDENED"))

    def test_crypteng(self):
        self.assertEqual(crypteng.review(fx("crypteng", "exposed"), log=None)["verdict"], "EXPOSED")
        self.assertTrue(crypteng.review(fx("crypteng", "clean"), log=None)["verdict"].startswith("CLEAN"))

    def test_deps(self):
        self.assertTrue(deps.review(fx("deps", "loose"), log=None)["verdict"].startswith("LOOSE"))
        self.assertEqual(deps.review(fx("deps", "pinned"), log=None)["verdict"], "PINNED")

    def test_api(self):
        self.assertEqual(api.review(fx("api", "broken.json"), log=None)["verdict"], "INVALID SPEC")
        self.assertTrue(api.review(fx("api", "clean.json"), log=None)["verdict"].startswith("VALID"))

    def test_schema(self):
        self.assertTrue(schema.review(text("schema", "bad.sql"), log=None)["verdict"].startswith("SCHEMA RISK"))
        self.assertTrue(schema.review(text("schema", "good.sql"), log=None)["verdict"].startswith("SOUND"))

    def test_i18n(self):
        self.assertEqual(i18n.review(fx("i18n", "gaps"), log=None)["verdict"], "GAPS")
        self.assertEqual(i18n.review(fx("i18n", "parity"), log=None)["verdict"], "PARITY")

    def test_tests_static(self):
        self.assertEqual(testing_seat.review(fx("testing", "none"), log=None)["verdict"], "NO TESTS")
        self.assertTrue(testing_seat.review(fx("testing", "theater"), log=None)["verdict"].startswith("THEATER"))

    def test_tests_mutation(self):
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "*_test.py"]
        rep = testing_seat.review(fx("testing", "proj_real"), source="calc.py", cmd=cmd, log=None)
        self.assertEqual(rep["verdict"], "REAL (caught every planted break)")


class ResearchAndStandards(unittest.TestCase):
    def test_spec(self):
        good = ("The server MUST reject an expired token. The client SHALL present its "
                "credentials exactly once. These key words are to be interpreted as "
                "described in RFC 2119.")
        bad = ("The server MUST validate the input. The client should be robust and may "
               "provide retries where possible.")
        self.assertEqual(spec.review(good, log=None)["verdict"], "NORMATIVE AND CONSISTENT")
        self.assertEqual(spec.review(bad, log=None)["verdict"], "AMBIGUOUS")

    def test_method(self):
        self.assertEqual(method.review(text("method", "bad.txt"), log=None)["verdict"], "GAPS")
        self.assertEqual(method.review(text("method", "good.txt"), log=None)["verdict"], "METHODS DOCUMENTED")

    def test_archive(self):
        self.assertTrue(archive.review(fx("archive", "gaps"), log=None)["verdict"].startswith("GAPS"))
        self.assertTrue(archive.review(fx("archive", "preservable"), log=None)["verdict"].startswith("PRESERVABLE"))

    def test_repro(self):
        self.assertTrue(repro.review(fx("repro", "gap"), log=None)["verdict"].startswith("GAPS"))
        self.assertTrue(repro.review(fx("repro", "ok"), log=None)["verdict"].startswith("RE-RUNNABLE"))

    def test_cipher(self):
        self.assertTrue(cipher.review(text("cipher", "short.txt"), log=None)["verdict"].startswith("SHORT"))
        self.assertTrue(cipher.review(text("cipher", "english.txt"), log=None)["verdict"].startswith("LANGUAGE-LIKE"))
        self.assertTrue(cipher.review(text("cipher", "random.txt"), log=None)["verdict"].startswith("FLAT"))

    @unittest.skipUnless(HAVE_CERTIVL, "certivl not importable")
    def test_geom(self):
        self.assertEqual(geom.review(["2*pi/sqrt(27) < 1.2092"], log=None)["verdict"], "ALL CERTIFIED")
        self.assertEqual(geom.review(["sqrt(2) < 1.41421"], log=None)["verdict"], "REFUTED")

    @unittest.skipUnless(HAVE_AUTHORECON, "authorecon not importable")
    def test_cite_delegates(self):
        # Stub authorecon's network resolver and assert cite maps its states to a verdict.
        R = cite._rc
        original = R.run
        try:
            R.run = lambda text, log=None: [{"state": R.CONFIRMED, "ref": "a"},
                                            {"state": R.LOCATED, "ref": "b"}]
            self.assertEqual(cite.review(fx("cite", "two_dois.md"), log=None)["verdict"], "VERIFIED")
            R.run = lambda text, log=None: [{"state": R.RETRACTED, "ref": "a"}]
            self.assertEqual(cite.review(fx("cite", "two_dois.md"), log=None)["verdict"], "RETRACTION PRESENT")
            R.run = lambda text, log=None: [{"state": R.UNLOCATABLE, "ref": "a"}]
            self.assertEqual(cite.review(fx("cite", "two_dois.md"), log=None)["verdict"],
                             "UNLOCATABLE OR WRONG-WORK CITATIONS")
            R.run = lambda text, log=None: []
            self.assertEqual(cite.review(fx("cite", "two_dois.md"), log=None)["verdict"], "NO REFERENCES FOUND")
        finally:
            R.run = original


class ComplianceAndDomain(unittest.TestCase):
    def test_licensing(self):
        self.assertEqual(licensing.review(fx("licensing", "none"), log=None)["verdict"], "UNLICENSED")
        self.assertEqual(licensing.review(fx("licensing", "declared"), log=None)["verdict"], "DECLARED")

    def test_privacy(self):
        self.assertTrue(privacy.review(fx("privacy", "risk"), log=None)["verdict"].startswith("PRIVACY RISK"))
        self.assertFalse(privacy.review(fx("privacy", "ok"), log=None)["verdict"].startswith("PRIVACY RISK"))

    def test_food(self):
        self.assertEqual(food.review(fx("food", "misbrand.html"), log=None)["verdict"], "POSSIBLE MISBRANDING")
        self.assertTrue(food.review(fx("food", "clean.html"), log=None)["verdict"].startswith("CLEAN"))

    @unittest.skipUnless(HAVE_CVD, "opticquiz-cvd not importable")
    def test_vision(self):
        hold = [{"fg": "#000000", "bg": "#ffffff", "claim": "distinct"}]
        contra = [{"fg": "#808080", "bg": "#828282", "claim": "distinct"}]
        cvd_collapse = [{"fg": "#d7191c", "bg": "#1a9641", "claim": "distinct"}]
        self.assertEqual(vision.review(hold, log=None)["verdict"], "CLAIMS HOLD")
        self.assertEqual(vision.review(contra, log=None)["verdict"], "CONTRADICTION")
        # distinct to normal vision but collapses under a CVD sim - opticquiz-cvd catches it,
        # the branch the old in-house vision seat punted on.
        self.assertEqual(vision.review(cvd_collapse, log=None)["verdict"], "CONTRADICTION")

    def test_ops(self):
        self.assertEqual(ops.review(fx("ops", "invalid.json"), log=None)["verdict"], "INVALID PLAN")
        self.assertTrue(ops.review(fx("ops", "feasible.json"), log=None)["verdict"].startswith("FEASIBLE"))

    def test_sec_classifier(self):
        original = sec._fetch
        hardened = {
            "strict-transport-security": "max-age=63072000",
            "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
            "x-frame-options": "DENY",
            "permissions-policy": "geolocation=()",
            "cross-origin-opener-policy": "same-origin",
            "cross-origin-resource-policy": "same-origin",
        }
        try:
            sec._fetch = lambda url: ("https://example/", dict(hardened), [])
            self.assertEqual(sec.review("https://example/", log=None)["verdict"], "HARDENED")
            sec._fetch = lambda url: ("https://example/", {}, [])
            self.assertEqual(sec.review("https://example/", log=None)["verdict"], "GAPS")
        finally:
            sec._fetch = original


class ProofKernel(unittest.TestCase):
    def test_never_fakes_verified(self):
        rep = proof.review(fx("proof", "valid.mm"), explicit="__no_such_kernel__", log=None)
        self.assertEqual(rep["verdict"], "NOT VERIFIED - no Metamath kernel found")
        self.assertNotEqual(rep["verdict"], "VERIFIED")

    def test_structural(self):
        prov, ax, inc = proof.structural(text("proof", "valid.mm"))
        self.assertEqual(prov, 1)
        self.assertEqual(ax, 10)
        self.assertEqual(inc, 0)

    def test_kernel_verdicts(self):
        kind, path = proof.find_verifier()
        if not kind:
            self.skipTest("no Metamath kernel discoverable on this machine")
        self.assertEqual(proof.review(fx("proof", "valid.mm"), log=None)["verdict"], "VERIFIED")
        self.assertEqual(proof.review(fx("proof", "tampered.mm"), log=None)["verdict"], "PROOF REJECTED")


class JsonMode(unittest.TestCase):
    """`--json` makes a seat callable: coldHat / hardHats run it and read one
    envelope ({seat, verdict, exit, ok, detail}) instead of scraping a CLI. Driven
    through the real dispatcher (`python -m hardhats.crews <kw> ... --json`), one per
    input shape: path, dir, text, claims, pairs, and proof's honesty path."""

    def _probe(self, *argv):
        proc = subprocess.run([sys.executable, "-m", "hardhats.crews", *argv, "--json"],
                              cwd=ROOT, capture_output=True, text=True)
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        self.assertTrue(lines, "no JSON on stdout for %r (stderr tail: %s)"
                        % (argv, proc.stderr[-300:]))
        env = json.loads(lines[-1])
        self.assertEqual(env["exit"], proc.returncode)
        self.assertEqual(env["ok"], proc.returncode == 0)
        self.assertIn("verdict", env["detail"])
        return env, proc.returncode

    def test_path_seat_api(self):
        env, code = self._probe("api", fx("api", "clean.json"))
        self.assertEqual(env["seat"], "api")
        self.assertTrue(env["verdict"].startswith("VALID"))
        self.assertEqual(code, 0)

    def test_dir_seat_crypteng(self):
        env, code = self._probe("crypteng", fx("crypteng", "exposed"))
        self.assertEqual(env["verdict"], "EXPOSED")
        self.assertEqual(code, 1)

    def test_text_seat_schema(self):
        env, code = self._probe("schema", fx("schema", "bad.sql"))
        self.assertTrue(env["verdict"].startswith("SCHEMA RISK"))
        self.assertEqual(code, 1)

    @unittest.skipUnless(HAVE_CERTIVL, "certivl not importable")
    def test_claims_seat_geom(self):
        env, code = self._probe("geom", "sqrt(2) < 1.41421")
        self.assertEqual(env["verdict"], "REFUTED")
        self.assertEqual(code, 1)

    @unittest.skipUnless(HAVE_CVD, "opticquiz-cvd not importable")
    def test_pairs_seat_vision(self):
        env, code = self._probe("vision", "--pairs", fx("vision", "pairs.json"))
        self.assertEqual(env["verdict"], "CONTRADICTION")
        self.assertEqual(code, 1)

    def test_dir_seat_deps_clean(self):
        env, code = self._probe("deps", fx("deps", "pinned"))
        self.assertEqual(env["verdict"], "PINNED")
        self.assertEqual(code, 0)

    def test_proof_honesty_via_cli(self):
        env, code = self._probe("proof", fx("proof", "valid.mm"), "--verifier", "__no_such_kernel__")
        self.assertEqual(env["verdict"], "NOT VERIFIED - no Metamath kernel found")
        self.assertEqual(code, 2)


class NetNewGates(unittest.TestCase):
    """B: gates with no existing F-Keys package behind them - stdlib only, so no skip guard."""

    def test_env(self):
        self.assertEqual(env.review(fx("env", "undeclared"), log=None)["verdict"], "UNDECLARED BINDINGS")
        self.assertEqual(env.review(fx("env", "clean"), log=None)["verdict"], "ALL BINDINGS DECLARED")

    def test_richdata(self):
        self.assertEqual(richdata.review(fx("richdata", "missing.html"), log=None)["verdict"],
                         "MISSING REQUIRED FIELDS")
        self.assertEqual(richdata.review(fx("richdata", "valid.html"), log=None)["verdict"],
                         "RICH RESULTS VALID")

    def test_links(self):
        self.assertEqual(links.review(fx("links", "broken"), log=None)["verdict"], "BROKEN LINKS")
        self.assertEqual(links.review(fx("links", "clean"), log=None)["verdict"], "ALL LOCAL LINKS RESOLVE")

    def test_inject(self):
        self.assertEqual(inject.review(fx("inject", "risk"), log=None)["verdict"], "INJECTION RISK")
        self.assertEqual(inject.review(fx("inject", "clean"), log=None)["verdict"], "NO DANGEROUS EXECUTION")

    def test_ghactions(self):
        self.assertEqual(ghactions.review(fx("ghactions", "risk"), log=None)["verdict"],
                         "WORKFLOW INJECTION RISK")
        self.assertEqual(ghactions.review(fx("ghactions", "clean"), log=None)["verdict"],
                         "WORKFLOWS HARDENED")

    def test_seizure(self):
        with open(fx("seizure", "hazard.json"), encoding="utf-8") as fh:
            hazard = json.load(fh)
        with open(fx("seizure", "safe.json"), encoding="utf-8") as fh:
            safe = json.load(fh)
        self.assertEqual(seizure.review(None, trace=hazard, log=None)["verdict"], "FLASH HAZARD")
        self.assertEqual(seizure.review(None, trace=safe, log=None)["verdict"], "WITHIN FLASH LIMITS")
        self.assertEqual(seizure.review(fx("seizure", "flashing"), log=None)["verdict"],
                         "REVIEW - potential flash sources present")
        self.assertEqual(seizure.review(fx("seizure", "clean"), log=None)["verdict"],
                         "NO FLASH SOURCES FOUND")

    def test_pwa(self):
        self.assertEqual(pwa.review(fx("pwa", "installable"), log=None)["verdict"], "INSTALLABLE PWA")
        self.assertEqual(pwa.review(fx("pwa", "bare"), log=None)["verdict"], "NOT INSTALLABLE")

    def test_og(self):
        self.assertEqual(og.review(fx("og", "shareable"), log=None)["verdict"], "SHARE-READY")
        self.assertEqual(og.review(fx("og", "gaps"), log=None)["verdict"], "REVIEW - share gaps present")
        self.assertEqual(og.review(fx("og", "bare"), log=None)["verdict"], "NOT SHAREABLE")

    def test_gameperf(self):
        with open(fx("gameperf", "smooth.json"), encoding="utf-8") as fh:
            smooth = json.load(fh)
        with open(fx("gameperf", "janky.json"), encoding="utf-8") as fh:
            janky = json.load(fh)
        self.assertEqual(gameperf.review(trace=smooth, log=None)["verdict"], "HOLDS TARGET FRAMERATE")
        self.assertEqual(gameperf.review(trace=janky, log=None)["verdict"], "DROPS FRAMES")
        self.assertEqual(gameperf.review(trace=None, log=None)["verdict"], "NO ENGINE")

    def test_traffic(self):
        self.assertEqual(traffic.review(fx("traffic", "bots", "access.log"), log=None)["verdict"],
                         "TRAFFIC IS MOSTLY BOTS")
        self.assertEqual(traffic.review(fx("traffic", "human", "access.log"), log=None)["verdict"],
                         "TRAFFIC LOOKS HUMAN")

    def test_attribution(self):
        self.assertEqual(attribution.review(fx("attribution", "messy.txt"), log=None)["verdict"],
                         "UNATTRIBUTABLE LINKS")
        self.assertEqual(attribution.review(fx("attribution", "clean.txt"), log=None)["verdict"],
                         "ATTRIBUTION CLEAN")

    def test_seo(self):
        self.assertEqual(seo.review(fx("seo", "blocked"), log=None)["verdict"], "BLOCKED FROM SEARCH")
        self.assertEqual(seo.review(fx("seo", "indexed"), log=None)["verdict"], "SEO FLOOR MET")

    def test_deliverability(self):
        self.assertEqual(deliverability.review(
            records={"spf": "v=spf1 -all", "dmarc": "v=DMARC1; p=reject;"}, log=None)["verdict"],
            "EMAIL AUTHENTICATED")
        self.assertEqual(deliverability.review(
            records={"spf": "", "dmarc": ""}, log=None)["verdict"], "NOT EMAIL-AUTHENTICATED")
        self.assertEqual(deliverability.review(
            records={"spf": "v=spf1 ~all", "dmarc": "v=DMARC1; p=none;"}, log=None)["verdict"],
            "REVIEW - weak email policy")

    def test_perf(self):
        # The classifier is proven on a Lighthouse report (no browser); NO ENGINE is proven by
        # forcing no runner. perf delegates measurement to Lighthouse and only judges the numbers.
        with open(fx("perf", "good.json"), encoding="utf-8") as fh:
            good = json.load(fh)
        with open(fx("perf", "bad.json"), encoding="utf-8") as fh:
            bad = json.load(fh)
        self.assertEqual(perf.review(None, report=good, log=None)["verdict"], "WITHIN CORE WEB VITALS BUDGETS")
        self.assertEqual(perf.review(None, report=bad, log=None)["verdict"], "FAILS CORE WEB VITALS")
        self.assertEqual(perf.review("https://x", report=None, explicit="__no_runner__", log=None)["verdict"],
                         "NO ENGINE")


class Router(unittest.TestCase):
    """`route` dispatches by what the artifact IS, reusing each seat's own --json.
    Driven through the real dispatcher, one case per classification path."""

    def _route(self, target):
        proc = subprocess.run([sys.executable, "-m", "hardhats.crews", "route", target, "--json"],
                              cwd=ROOT, capture_output=True, text=True)
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        self.assertTrue(lines, "no JSON from route %r (stderr tail: %s)" % (target, proc.stderr[-300:]))
        env = json.loads(lines[-1])
        self.assertEqual(env["exit"], proc.returncode)
        return env, proc.returncode

    def test_file_routes_by_extension(self):
        env, code = self._route(fx("schema", "bad.sql"))
        self.assertEqual(env["kind"], "file")
        self.assertEqual(env["routed"], ["schema"])
        self.assertTrue(env["routes"][0]["verdict"].startswith("SCHEMA RISK"))
        self.assertEqual(code, 1)

    def test_json_content_sniff(self):
        self.assertEqual(self._route(fx("api", "clean.json"))[0]["routed"], ["api"])
        self.assertEqual(self._route(fx("ops", "invalid.json"))[0]["routed"], ["ops"])

    def test_locale_routes_to_i18n_dir(self):
        env, _ = self._route(fx("i18n", "gaps", "en.json"))
        self.assertEqual(env["routed"], ["i18n"])
        self.assertEqual(env["routes"][0]["verdict"], "GAPS")

    def test_dir_routes_multiple(self):
        env, code = self._route(fx("crypteng", "exposed"))
        self.assertEqual(env["kind"], "dir")
        self.assertIn("crypteng", env["routed"])
        self.assertIn("resilient", env["routed"])
        self.assertEqual(code, 1)

    def test_bare_path_fallback(self):
        proc = subprocess.run([sys.executable, "-m", "hardhats.crews", fx("schema", "bad.sql"), "--json"],
                              cwd=ROOT, capture_output=True, text=True)
        env = json.loads([ln for ln in proc.stdout.splitlines() if ln.strip()][-1])
        self.assertEqual(env["seat"], "route")
        self.assertEqual(env["routed"], ["schema"])


class FloorPanel(unittest.TestCase):
    """THE FLOOR is a PANEL, not a gated seat: this proves its composition and that the gate
    floor runs, with ZERO model calls (the taste hats are never worn here)."""

    def test_composition_and_floor(self):
        crew = floor.build_crew(fx("seizure", "flashing"))
        gate = [h for h in crew.hats if h.kind == "gate"]
        llm = [h for h in crew.hats if h.kind == "llm"]
        self.assertEqual(len(gate), 3)
        self.assertEqual(len(llm), 3)
        # decorrelated: every taste hat sits on a distinct backend
        self.assertEqual(len({h.model[0] for h in llm}), 3)
        # the floor runs deterministically and carries the real seat verdicts into the context
        facts = [h.wear("") for h in gate]
        self.assertTrue(any("HAZARD" in f or "REVIEW" in f for f in facts))
        self.assertTrue(any(f.startswith("og ->") for f in facts))


class DistributionPlays(unittest.TestCase):
    """The 'do' tier: THE REGULAR / THE LOOP / THE RELAY are gated seats now - a deterministic
    readiness check plus a playbook, zero model calls. Proven on a ready and a not-ready input."""

    def test_community(self):
        self.assertEqual(community.review(fx("plays", "community", "pitch.html"), log=None)["verdict"],
                         "READS AS A PITCH")
        self.assertEqual(community.review(fx("plays", "community", "value.html"), log=None)["verdict"],
                         "VALUE-FIRST")

    def test_loop(self):
        self.assertEqual(loop.review(fx("plays", "loop", "forwardable.html"), log=None)["verdict"],
                         "FORWARDABLE")
        self.assertEqual(loop.review(fx("plays", "loop", "flat.html"), log=None)["verdict"],
                         "NOTHING TO FORWARD")

    def test_relay(self):
        self.assertEqual(relay.review(fx("plays", "relay", "submittable.html"), log=None)["verdict"],
                         "SUBMITTABLE")
        self.assertEqual(relay.review(fx("plays", "relay", "thin.html"), log=None)["verdict"],
                         "NOT SUBMITTABLE")


class ReckoningPanel(unittest.TestCase):
    """THE RECKONING is a PANEL, not a gated seat: this proves composition and that attached evidence
    runs through the gates, with ZERO model calls (the skeptic hats are never worn here)."""

    def test_evidence_grounds_the_skeptics(self):
        crew = reckoning.build_crew("we got 10k views from launch",
                                    log_path=fx("traffic", "bots", "access.log"))
        gate = [h for h in crew.hats if h.kind == "gate"]
        llm = [h for h in crew.hats if h.kind == "llm"]
        self.assertEqual(len(llm), 3)
        self.assertEqual(len(gate), 1)                            # only --log was attached
        self.assertEqual(len({h.model[0] for h in llm}), 3)       # decorrelated backends
        self.assertTrue(any("BOTS" in h.wear("") for h in gate))  # the real bot share is on the table

    def test_no_evidence_no_gate_floor(self):
        crew = reckoning.build_crew("we got 10k views")
        self.assertEqual([h for h in crew.hats if h.kind == "gate"], [])
        self.assertEqual(len([h for h in crew.hats if h.kind == "llm"]), 3)


class SeatContract(unittest.TestCase):
    """The factory contract: every discovered seat obeys ONE shape, so a seat minted by
    `python -m hardhats.new` drops into the bench with no special-casing. This is what makes
    the bench a production line and not a pile - a seat that breaks the shape fails here."""

    def setUp(self):
        from hardhats.crews.__main__ import discover
        self.reg = discover()

    def test_known_set_is_still_registered(self):
        # the bench may grow, but it must never silently drop one of the known seats
        known = {"api", "archive", "balance", "cipher", "cite", "crypteng", "deps", "food",
                 "geom", "i18n", "license", "method", "ops", "privacy", "proof", "repro",
                 "resilient", "schema", "sec", "spec", "tests", "vision", "route", "env",
                 "links", "richdata", "perf", "inject", "ghactions", "seizure", "pwa", "og",
                 "gameperf", "traffic", "attribution", "seo", "deliverability", "community",
                 "loop", "relay",
                 "claims", "security", "contract", "reproducible", "reach", "safety"}
        self.assertTrue(known <= set(self.reg), "dropped seats: %s" % (known - set(self.reg)))

    def test_every_seat_has_main_and_a_matching_tag(self):
        import importlib
        tag = re.compile(r"keyword `([^`]+)`")
        for kw, (mod, _summary) in sorted(self.reg.items()):
            module = importlib.import_module("hardhats.crews." + mod)
            self.assertTrue(callable(getattr(module, "main", None)),
                            "seat %r (%s.py) has no callable main()" % (kw, mod))
            self.assertTrue(module.__doc__, "seat %r (%s.py) has no module docstring" % (kw, mod))
            m = tag.search(module.__doc__)
            self.assertTrue(m, "seat %r (%s.py) docstring has no (keyword `..`) tag" % (kw, mod))
            self.assertEqual(m.group(1), kw,
                             "seat %r is tagged %r - tag and registry disagree" % (kw, m.group(1)))

    def test_keywords_are_unique(self):
        # discover() is a dict, so a duplicate tag would silently win; re-scan to catch it.
        from hardhats.crews import __main__ as dispatch
        crews_dir = os.path.dirname(dispatch.__file__)
        tag = re.compile(r"keyword `([^`]+)`")
        claimed = {}
        for fn in sorted(os.listdir(crews_dir)):
            if not fn.endswith(".py") or fn.startswith("_") or fn in dispatch._SKIP:
                continue
            with open(os.path.join(crews_dir, fn), encoding="utf-8", errors="replace") as fh:
                src = fh.read()
            doc = re.search(r'"""(.*?)"""', src, re.S)
            m = tag.search(doc.group(1)) if doc else None
            if not m:
                continue
            self.assertNotIn(m.group(1), claimed,
                             "keyword %r claimed by both %s and %s"
                             % (m.group(1), claimed.get(m.group(1)), fn))
            claimed[m.group(1)] = fn


class Scaffolder(unittest.TestCase):
    """The factory proves itself: hardhats.new.render mints a seat that already obeys the
    contract - tagged, importable, a working review()/main() - without touching the package.
    A clean input clears and a planted marker is caught, so a minted seat ships green."""

    def test_minted_seat_obeys_the_contract(self):
        import importlib.util
        import tempfile
        src = new.render("probe", title="THE PROBE CREW",
                         standard="a worked example", summary="flags a leftover marker.")
        self.assertEqual(re.search(r"keyword `([^`]+)`", src).group(1), "probe")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "probe.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)
            spec = importlib.util.spec_from_file_location("hh_probe_seat", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.assertTrue(callable(mod.main) and callable(mod.review))
            clean = os.path.join(d, "clean")
            os.mkdir(clean)
            with open(os.path.join(clean, "a.txt"), "w", encoding="utf-8") as fh:
                fh.write("nothing here\n")
            bad = os.path.join(d, "bad")
            os.mkdir(bad)
            with open(os.path.join(bad, "b.txt"), "w", encoding="utf-8") as fh:
                fh.write("x = 1  # TODO fix\n")
            self.assertEqual(mod.review(clean, log=None)["verdict"], "CLEAN")
            self.assertEqual(mod.review(bad, log=None)["verdict"], "MARKERS PRESENT")

    def test_reserved_names_come_from_gitignore(self):
        # the guard reads the git-ignored names from .gitignore, not a hardcoded list
        reserved = new._reserved()
        self.assertIn("council", reserved)
        self.assertIn("jury", reserved)
        self.assertNotIn("ghactions", reserved)          # a real public seat is never reserved
        self.assertFalse(new.is_reserved("totallynewseat"))
        for name in ("council", "jury", "scout"):
            with self.assertRaises(ValueError):
                new.validate(name)

    def test_refuses_malformed_names(self):
        for name in ("UPPER", "1st", "a", "has-dash", ""):
            with self.assertRaises(ValueError):
                new.validate(name)


class Dispatcher(unittest.TestCase):
    def test_all_seats_register(self):
        from hardhats.crews.__main__ import discover
        reg = discover()
        expected = {"api", "archive", "balance", "cipher", "cite", "crypteng", "deps",
                    "food", "geom", "i18n", "license", "method", "ops", "privacy",
                    "proof", "repro", "resilient", "schema", "sec", "spec", "tests", "vision",
                    "route", "env", "links", "richdata", "perf", "inject", "ghactions",
                    "seizure", "pwa", "og", "gameperf", "traffic", "attribution", "seo",
                    "deliverability", "community", "loop", "relay",
                    "claims", "security", "contract", "reproducible", "reach", "safety"}
        self.assertEqual(set(reg), expected)


class Leads(unittest.TestCase):
    """A lead is a foreman: it runs only the member checks whose signal is present on the target,
    composes ONE verdict, and lists the members it did NOT run - so a clear is never a blank cheque
    and a lead adds no checking logic of its own (every verdict is a member seat's)."""

    def test_security_lead_composes_a_member_defect(self):
        from hardhats.crews import security
        rep = security.review(fx("inject", "risk"), log=None)
        ran = {e.get("seat") for e in rep["ran"]}
        self.assertIn("inject", ran)                       # a source dir gives inject its signal
        self.assertTrue(rep["failed"], "the injection sink must surface as a failed member")
        self.assertTrue(rep["verdict"].startswith("SECURITY DEFECT"))
        self.assertIn("sec", rep["not_run"])               # sec needs a URL - surfaced, not a silent pass

    def test_lead_surfaces_every_member_with_no_signal(self):
        import tempfile
        from hardhats.crews import claims
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "plain.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("just prose, nothing here routes to a claims member\n")
            rep = claims.review(p, log=None)
        self.assertEqual([e.get("seat") for e in rep["ran"]], [])   # a .txt routes to no claims member
        self.assertEqual(set(rep["not_run"]), set(claims.MEMBERS))  # every member surfaced, none hidden
        self.assertTrue(rep["verdict"].startswith("NOTHING APPLIED"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
