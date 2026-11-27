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
            "写总结",
            "调研总结",
            "进展汇报",
            "变更总结",
            "写报告",
            "整理成文档",
            "写成文档给人看",
            "agent 完成一段工作后",
            "正式专业文档",
            "内部沟通/会议材料",
            "从零撰写技术方案",
            "主要交付物",
            "不得用本 Skill 取代",
            "继续",
            "按原流程",
        ):
            self.assertIn(phrase, description)
        for phrase in (
            "设计、开发或治理流程",
            "spec",
            "plan",
            "design doc",
            "technical-proposal-review",
        ):
            self.assertIn(phrase, description)

    def test_guardrail_body_is_self_contained_lean_and_splits_reader_contexts(self):
        body = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        lines = body.splitlines()
        self.assertLessEqual(len(lines), 25)
        self.assertFalse((SKILL_ROOT / "references").exists())
        for required in (
            "内部复盘与会议稿每条问题直接就地给出对应建议",
            "不解释行业常识词",
            "冷门项目缩写",
            "防御性括号标签",
            "不给模糊空话脑补职责",
            "教程关键状态不断链",
        ):
            self.assertIn(required, body)
        for retired in (
            "0 mismatch",
            "正向事实槽",
            "反向主张槽",
            "可见顺序缩写槽",
            "类型专项槽",
            "stable ID",
            "source bound",
            "references/",
        ):
            self.assertNotIn(retired, body)

    def test_content_evals_manifest_covers_seven_scenarios_with_existing_fixtures(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["skill_name"], "professional-writing")
        evals = manifest["evals"]
        self.assertEqual(len(evals), 7)
        self.assertEqual([case["id"] for case in evals], [1, 2, 3, 4, 5, 6, 7])
        names = {case["name"] for case in evals}
        self.assertIn("internal-retro-meeting-doc", names)
        for case in evals:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expectations"])
            for rel_file in case["files"]:
                self.assertTrue(
                    (SKILL_ROOT / rel_file).is_file(),
                    f"Missing eval fixture: {rel_file}",
                )

    def test_trigger_eval_matrix_covers_positive_negative_and_mixed_routes(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "trigger-evals.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["skill_name"], "professional-writing")
        evals = manifest["evals"]
        self.assertEqual(len(evals), 24)
        self.assertEqual(len({case["id"] for case in evals}), 24)
        self.assertEqual(sum(case["should_trigger"] for case in evals), 14)
        self.assertEqual(
            {case["route"] for case in evals},
            {"professional-writing", "other-skill", "mixed"},
        )
        self.assertEqual(
            sum(case["route"] == "professional-writing" for case in evals), 12
        )
        self.assertEqual(sum(case["route"] == "mixed" for case in evals), 2)
        self.assertEqual(
            sum(case["route"] == "other-skill" for case in evals), 10
        )
        required = {"id", "query", "should_trigger", "route", "reason"}
        for case in evals:
            self.assertEqual(set(case), required)
            self.assertTrue(case["query"].strip())
            self.assertTrue(case["reason"].strip())

        routes_by_id = {
            case["id"]: (case["should_trigger"], case["route"])
            for case in evals
        }
        self.assertEqual(
            routes_by_id["positive-standalone-technical-proposal"],
            (True, "professional-writing"),
        )
        for case_id in (
            "positive-agent-autonomous-postmortem",
            "positive-progress-report",
            "positive-change-summary",
            "positive-internal-retro-meeting",
        ):
            self.assertEqual(routes_by_id[case_id], (True, "professional-writing"))
        self.assertEqual(
            routes_by_id["negative-active-superpowers-design-doc"],
            (False, "other-skill"),
        )
        self.assertEqual(
            routes_by_id["mixed-superpowers-draft-professional-writing-verify"],
            (True, "mixed"),
        )
        self.assertEqual(
            routes_by_id["mixed-design-judgment-then-authoring"],
            (True, "mixed"),
        )

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
