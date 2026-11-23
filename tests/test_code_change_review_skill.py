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
            "references/pr-comments.md",
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

    def test_entry_keeps_core_review_and_reporting_rules(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        for concept in (
            "read-only", "pre-change", "nine surfaces", "user-visible ui",
            "reachable path", "special attention", "ui coverage", "merge readiness",
            "结论：未发现有代码证据支持的缺陷。",
        ):
            self.assertIn(concept, body.lower())
        for rule in (
            r"UI coverage[^\n]*rules/reuse[^\n]*walkthrough",
            r"Not ready[^.\n]*P0/P1[^.\n]*C",
            r"Unable to determine[^.\n]*blocking Q",
            r"Ready with non-blocking follow-ups[^.\n]*P2",
            r"P0[^.\n]*severe[^.\n]*containment",
            r"P1[^.\n]*material[^.\n]*before merge",
            r"P2[^.\n]*narrow[^.\n]*reversible",
        ):
            self.assertRegex(body, rule)

    def test_entry_routes_existing_local_references_by_condition(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertRegex(body.lower(), r"matching reference[^\n]*entry alone")
        routes = {
            link: condition.lower()
            for condition, link in re.findall(
                r"^\|([^|\n]+)\|[^|\n]*\]\((references/[^)\s]+\.md)\)",
                body,
                re.MULTILINE,
            )
        }
        for filename, trigger in {
            "output-template.md": r"c/p/q|report",
            "pr-comments.md": r"comment|publication",
            "rereview.md": r"findings|repairs|delta",
            "review-rubric.md": r"risk|concurrency",
            "review-scope.md": r"baseline|working tree|pr",
            "ui-review.md": r"ui|renderer",
            "validation-safety.md": r"executing|reproducer",
        }.items():
            relative = f"references/{filename}"
            with self.subTest(reference=relative):
                self.assertIn(relative, routes)
                self.assertRegex(routes[relative], trigger)
        for relative in re.findall(r"\]\((references/[^)\s]+\.md)\)", body):
            reference = (SKILL_ROOT / relative).resolve()
            self.assertTrue(reference.is_relative_to(SKILL_ROOT.resolve()), relative)
            self.assertTrue(reference.is_file(), relative)

    def test_output_template_preserves_distinct_evidence_entries(self):
        template = (SKILL_ROOT / "references" / "output-template.md").read_text(
            encoding="utf-8"
        )
        for phrase in ("C-01", "P0-01", "P1-01", "P2-01", "Q-01", "non-blocking"):
            self.assertIn(phrase, template)

    def test_ui_reference_preserves_checks_and_walkthrough_boundary(self):
        guidance = (SKILL_ROOT / "references" / "ui-review.md").read_text(
            encoding="utf-8"
        ).lower()
        for check in (
            "permission-denied", "enum", "destructive", "cancel/submit", "overflow",
            "reuse", "runtime walkthrough", "unverified",
        ):
            self.assertIn(check, guidance)
        self.assertRegex(guidance, r"copy-only[^\n]*walkthrough[^\n]*(only if|unless)")

    def test_eval_manifest_has_fixed_case_matrix_and_valid_fixtures(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["skill_name"], "code-change-review")
        evals = manifest["evals"]
        self.assertEqual(len(evals), 58)
        self.assertEqual(len({case["id"] for case in evals}), 58)

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
        self.assertEqual(len(triggers), 13)
        self.assertEqual(len(behavior), 45)
        self.assertEqual(
            {case["route"] for case in triggers},
            {"code-change-review", "other-skill", "mixed"},
        )
        self.assertEqual(
            [case["route"] for case in triggers].count("code-change-review"), 6
        )
        self.assertEqual(
            [case["route"] for case in triggers].count("other-skill"), 5
        )
        self.assertEqual([case["route"] for case in triggers].count("mixed"), 2)

        categories = [case["category"] for case in behavior]
        self.assertEqual(categories.count("bug"), 4)
        self.assertEqual(categories.count("safe"), 9)
        self.assertEqual(categories.count("control"), 27)
        self.assertEqual(categories.count("constraint"), 5)
        bug_ids = {
            case["id"] for case in behavior
            if case["category"] in {"bug", "constraint"}
        }
        safe_controls = {
            case["control_for"]
            for case in behavior
            if case["category"] == "safe"
        }
        self.assertEqual(safe_controls, bug_ids)


if __name__ == "__main__":
    unittest.main()
