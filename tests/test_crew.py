"""
Engine tests for hardHats - gate hats only, so the pipeline and pre-flight are
verified with zero model calls. LLM hats are exercised separately against the
live federation.

  python -m unittest discover -s tests
"""
import unittest

from hardhats import Crew, Hat


class Pipeline(unittest.TestCase):
    def test_gate_hats_pass_outputs_down_the_line(self):
        seen = {}

        def upper(payload):
            seen["upper"] = payload
            return "A, B, C"

        def count(payload):
            seen["count"] = payload          # must contain the first hat's output
            return f"items={payload.count(',') + 1 if ',' in payload else 0}"

        crew = Crew("demo", [
            Hat("lister", gate=upper),
            Hat("counter", gate=count),
        ])
        out = crew.run("make a list", log=None)
        self.assertEqual(out["lister"], "A, B, C")
        self.assertIn("A, B, C", seen["count"], "the counter should see the lister's output")
        self.assertIn("items=", out["counter"])

    def test_hat_kind(self):
        self.assertEqual(Hat("g", gate=lambda p: p).kind, "gate")
        self.assertEqual(Hat("l", model=("groq", "x"), instruction="hi").kind, "llm")

    def test_hat_without_model_or_gate_raises(self):
        with self.assertRaises(ValueError):
            Hat("bad").wear("x")


class Preflight(unittest.TestCase):
    def test_detects_conflicting_instructions_across_hats(self):
        crew = Crew("c", [
            Hat("a", model=("groq", "x"), instruction="Use a bulleted list for the output."),
            Hat("b", model=("groq", "x"), instruction="Use a numbered list for the output."),
        ])
        conflicts = [("Use a bulleted list", "Use a numbered list", "cannot be both")]
        found = crew.preflight(conflicts)
        self.assertTrue(found, "bulleted-vs-numbered hats should be flagged")
        self.assertEqual(found[0][2], "cannot be both")

    def test_clean_crew_has_no_conflicts(self):
        crew = Crew("c", [
            Hat("a", model=("groq", "x"), instruction="Think step by step."),
            Hat("b", model=("groq", "x"), instruction="Write in a plain register."),
        ])
        self.assertEqual(crew.preflight([("Use a bulleted list", "Use a numbered list", "x")]), [])


if __name__ == "__main__":
    unittest.main()
