import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "review-and-release-pr"


def load_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"missing YAML frontmatter: {path}")
    return yaml.safe_load(match.group(1)), text[match.end() :]


class ReviewAndReleasePrSkillTests(unittest.TestCase):
    def test_minimal_layout(self):
        self.assertEqual(
            {path.name for path in SKILL_ROOT.iterdir()},
            {"SKILL.md", "agents", "evals"},
        )
        self.assertEqual(
            {path.name for path in (SKILL_ROOT / "agents").iterdir()},
            {"openai.yaml"},
        )

    def test_metadata_routes_only_end_to_end_pr_requests(self):
        frontmatter, _ = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertEqual(set(frontmatter), {"name", "description"})
        self.assertEqual(frontmatter["name"], "review-and-release-pr")
        description = frontmatter["description"]
        self.assertTrue(description.startswith("Use when "))
        lowered = description.lower()
        for trigger in (
            "codex",
            "pull request",
            "requirement",
            "existing review",
            "independent review",
            "merge or release",
        ):
            self.assertIn(trigger, lowered)
        for excluded in (
            "isolated code review",
            "proposal-only",
            "comment-only",
            "bugfix-only",
            "release-only",
            "cleanup-only",
        ):
            self.assertIn(excluded, lowered)

    def test_openai_metadata_is_minimal_and_invocable(self):
        document = yaml.safe_load(
            (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(set(document), {"interface"})
        interface = document["interface"]
        self.assertEqual(
            set(interface),
            {"display_name", "short_description", "default_prompt"},
        )
        self.assertGreaterEqual(len(interface["short_description"]), 25)
        self.assertLessEqual(len(interface["short_description"]), 64)
        self.assertIn("$review-and-release-pr", interface["default_prompt"])

    def test_behavior_cases_are_independently_runnable(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["skill_name"], "review-and-release-pr")
        cases = manifest["evals"]
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertTrue(cases)
        for case in cases:
            self.assertEqual(case["kind"], "behavior")
            self.assertTrue(case["prompt"])
            self.assertTrue(case["expected_output"])
            self.assertTrue(case["assertions"])
            for relative in case["files"]:
                fixture = (SKILL_ROOT / relative).resolve()
                self.assertTrue(fixture.is_relative_to(SKILL_ROOT.resolve()))
                self.assertTrue(fixture.is_file())


if __name__ == "__main__":
    unittest.main()
