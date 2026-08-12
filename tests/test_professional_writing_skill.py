import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "professional-writing"


def load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class ProfessionalWritingSkillTests(unittest.TestCase):
    def test_description_preserves_authoring_and_excludes_incidental_artifacts(self):
        frontmatter = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertEqual(set(frontmatter), {"name", "description"})
        self.assertEqual(frontmatter["name"], "professional-writing")
        description = frontmatter["description"]
        self.assertTrue(description.startswith("Use when "))
        self.assertLessEqual(len(description), 1024)
        for phrase in (
            "首要目标",
            "正式专业文档",
            "从零撰写技术方案",
            "主要交付物",
        ):
            self.assertIn(phrase, description)
        for phrase in (
            "不得仅因",
            "设计、开发或治理流程",
            "spec",
            "plan",
            "design doc",
            "technical-proposal-review",
        ):
            self.assertIn(phrase, description)

    def test_trigger_eval_matrix_covers_positive_negative_and_mixed_routes(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "trigger-evals.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["skill_name"], "professional-writing")
        evals = manifest["evals"]
        self.assertEqual(len(evals), 20)
        self.assertEqual(len({case["id"] for case in evals}), 20)
        self.assertEqual(sum(case["should_trigger"] for case in evals), 10)
        self.assertEqual(
            {case["route"] for case in evals},
            {"professional-writing", "other-skill", "mixed"},
        )
        required = {"id", "query", "should_trigger", "route", "reason"}
        for case in evals:
            self.assertEqual(set(case), required)
            self.assertTrue(case["query"].strip())
            self.assertTrue(case["reason"].strip())

        positive = " ".join(
            case["query"] for case in evals if case["should_trigger"]
        )
        negative = " ".join(
            case["query"] for case in evals if not case["should_trigger"]
        )
        for phrase in ("技术方案", "设计文档", "design doc"):
            self.assertIn(phrase, positive)
            self.assertIn(phrase, negative)


if __name__ == "__main__":
    unittest.main()
