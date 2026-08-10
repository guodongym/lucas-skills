import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "code-change-review"


def load_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"missing YAML frontmatter: {path}")
    return yaml.safe_load(match.group(1)), text[match.end() :]


class CodeChangeReviewSkillTests(unittest.TestCase):
    def test_minimal_layout(self):
        required = {
            "SKILL.md",
            "agents/openai.yaml",
            "references/review-rubric.md",
            "references/output-template.md",
        }
        for relative in required:
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)

        forbidden = {"scripts", "assets", "README.md", "feedback", "cases"}
        self.assertFalse(
            forbidden.intersection({path.name for path in SKILL_ROOT.iterdir()})
        )

    def test_metadata_encodes_positive_and_negative_routing(self):
        frontmatter, _ = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertEqual(frontmatter["name"], "code-change-review")
        description = frontmatter["description"].lower()
        for phrase in (
            "working tree",
            "staged diff",
            "commit range",
            "branch",
            "pull request",
            "merge readiness",
        ):
            self.assertIn(phrase, description)
        for excluded in (
            "proposal",
            "reviewer comments",
            "debugging",
            "whole-repository",
            "implementation or fixes",
        ):
            self.assertIn(excluded, description)

        metadata = yaml.safe_load(
            (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        )["interface"]
        self.assertIn("$code-change-review", metadata["default_prompt"])
        self.assertGreaterEqual(len(metadata["short_description"]), 25)
        self.assertLessEqual(len(metadata["short_description"]), 64)

    def test_workflow_contains_scope_readonly_and_reasoning_contracts(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        for phrase in (
            "Input precedence",
            "Deterministic snapshots",
            "Read-only safety gate",
            "First principles",
            "Adversarial review",
            "Evidence gate",
            "Merge readiness",
        ):
            self.assertIn(phrase, body)
        self.assertIn("references/review-rubric.md", body)
        self.assertIn("references/output-template.md", body)

    def test_output_contract_separates_findings_questions_and_readiness(self):
        template = (SKILL_ROOT / "references" / "output-template.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Confirmed findings",
            "P0-01",
            "P1-01",
            "P2-01",
            "Questions",
            "Q-01",
            "blocking",
            "non-blocking",
            "Unable to determine",
            "Ready with non-blocking follow-ups",
            "未发现有代码证据支持的缺陷",
        ):
            self.assertIn(phrase, template)

    def test_eval_manifest_has_fixed_case_matrix_and_valid_fixtures(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["skill_name"], "code-change-review")
        evals = manifest["evals"]
        self.assertEqual(len(evals), 24)
        self.assertEqual(len({case["id"] for case in evals}), 24)

        required = {
            "id",
            "kind",
            "prompt",
            "expected_output",
            "files",
            "assertions",
        }
        for case in evals:
            self.assertTrue(required.issubset(case), case["id"])
            self.assertIn(case["kind"], {"trigger", "behavior"})
            self.assertTrue(case["assertions"], case["id"])
            for relative in case["files"]:
                fixture = (SKILL_ROOT / relative).resolve()
                self.assertTrue(
                    fixture.is_relative_to(SKILL_ROOT.resolve()), case["id"]
                )
                self.assertTrue(fixture.is_file(), f"{case['id']}: {relative}")

        triggers = [case for case in evals if case["kind"] == "trigger"]
        behavior = [case for case in evals if case["kind"] == "behavior"]
        self.assertEqual(len(triggers), 12)
        self.assertEqual(len(behavior), 12)
        self.assertEqual(
            {case["route"] for case in triggers},
            {"code-change-review", "other-skill", "mixed"},
        )
        self.assertEqual(
            [case["route"] for case in triggers].count("code-change-review"), 5
        )
        self.assertEqual(
            [case["route"] for case in triggers].count("other-skill"), 5
        )
        self.assertEqual([case["route"] for case in triggers].count("mixed"), 2)

        categories = [case["category"] for case in behavior]
        self.assertEqual(categories.count("bug"), 4)
        self.assertEqual(categories.count("safe"), 4)
        self.assertEqual(categories.count("control"), 4)
        bug_ids = {case["id"] for case in behavior if case["category"] == "bug"}
        safe_controls = {
            case["control_for"]
            for case in behavior
            if case["category"] == "safe"
        }
        self.assertEqual(safe_controls, bug_ids)

    def test_compatibility_bug_assertion_points_to_changed_field(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        case = next(
            item
            for item in manifest["evals"]
            if item["id"] == "behavior-compatibility-bug"
        )
        self.assertIn(
            (
                "Locates the changed user_id to actor_id producer field "
                "(events/user_event.py line 14 in target-file coordinates; "
                "the corresponding fixture diff line is acceptable)."
            ),
            case["assertions"],
        )


if __name__ == "__main__":
    unittest.main()
