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

    def test_entry_sets_zero_trust_stance_with_evidence_gated_verdicts(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertIn("## Stance", body)
        self.assertLess(body.index("## Stance"), body.index("## Anchor the review"))
        stance = body.split("## Stance", 1)[1].split("\n## ", 1)[0]
        for rule in (
            r"zero trust",
            r"requirement[^\n]*design[^\n]*green test",
            r"unproved",
            r"unnecessary until",
            r"polite filler",
            r"block[^\n]*P0[^\n]*P1[^\n]*C[^\n]*Q",
            r"advisory reviewer judgment",
        ):
            self.assertRegex(stance.lower(), rule.lower())

    def test_report_deduplicates_sections_while_keeping_briefing_detailed(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        report = body.split("## Report and verdict", 1)[1]
        self.assertRegex(report, r"Explain each fact or issue once[^\n]*reference[^\n]*ID")
        template = (SKILL_ROOT / "references" / "output-template.md").read_text(
            encoding="utf-8"
        )
        for rule in (
            r"detailed and self-contained",
            r"one line per item",
            r"2–3 sentences",
            r"C/P/Q IDs",
            r"Do not repeat",
        ):
            self.assertRegex(template, rule)

    def test_entry_briefs_the_change_before_judgment(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertLess(
            body.index("## Anchor the review"), body.index("## Brief the change")
        )
        self.assertLess(
            body.index("## Brief the change"), body.index("## Screen the change")
        )
        briefing = body.split("## Brief the change", 1)[1].split("\n## ", 1)[0]
        for rule in (
            r"[Bb]usiness problem",
            r"`claimed`[^\n]*`inferred`[^\n]*`not stated`",
            r"[Nn]ever invent",
            r"3–5 steps",
            r"before/after",
            r"[Cc]hange groups[^\n]*hand-written lines",
            r"single-group[^\n]*three lines",
            r"[Dd]iagram only when",
        ):
            self.assertRegex(briefing, rule)

    def test_entry_judges_pr_fit_by_independent_units(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        section = body.split("## Does the whole change need to go together?", 1)[1]
        section = section.split("\n## ", 1)[0]
        for rule in (
            r"\*\*PR fit\*\*",
            r"Can it ship alone\?",
            r"Should it\?",
            r"Would separating hurt\?",
            r"[Rr]ecommend a split only when",
            r"[Aa]uthor effort, elapsed time and smallness are never reasons",
            r"size alone",
            r"[Rr]epository splitting rules prevail[^\n]*mandatory one is C",
            r"advisory",
        ):
            self.assertRegex(section, rule)

    def test_report_opens_with_verdict_line_then_briefing(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertRegex(
            body, r"one-line verdict[^\n]*change briefing[^\n]*\*\*Special attention\*\*"
        )
        self.assertRegex(body, r"five questions[^\n]*citing the briefing")

    def test_output_template_defines_briefing_and_diagram_limits(self):
        template = (SKILL_ROOT / "references" / "output-template.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Change briefing", template)
        self.assertRegex(template, r"新概念[^\n]*角色/权限[^\n]*界面用词[^\n]*\| 类别 \|")
        for rule in (
            r"verdict line[^\n]*briefing[^\n]*attention",
            r"[Vv]erified facts",
            r"dashed[^\n]*unverified",
            r"new, modified or removed",
            r"12 nodes",
            r"at most two",
            r"Mermaid[^\n]*text arrows",
        ):
            self.assertRegex(template, rule)

    def test_entry_challenges_each_new_concept(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        briefing = body.split("## Brief the change", 1)[1].split("\n## ", 1)[0]
        self.assertRegex(
            briefing,
            r"[Nn]ew concepts[^\n]*states?[^\n]*mechanisms?[^\n]*roles?[^\n]*"
            r"flow steps?[^\n]*(user-facing|visible) terms[^\n]*shared dependenc",
        )
        section = body.split("## Does the whole change need to go together?", 1)[1]
        section = section.split("\n## ", 1)[0]
        for rule in (
            r"\*\*Challenge new concepts\*\*",
            r"every touched category",
            r"per action",
            r"[Ww]here does it come from\?",
            r"[Ww]hat user task fails without it\?",
            r"[Ii]s there a simpler way\?",
            r"[Dd]ocuments the change (adds|brings)[^\n]*(claims|cannot justify)",
            r"[Cc]onfirmed source[^\n]*C",
            r"reviewer judgment",
            r"simplify or remove[^\n]*advisory",
        ):
            self.assertRegex(section, rule)

    def test_pr_comment_template_carries_verdict_and_briefing(self):
        comments = (SKILL_ROOT / "references" / "pr-comments.md").read_text(
            encoding="utf-8"
        )
        self.assertRegex(comments, r"结论：[^\n]*\n改动导读：[^\n]*PR fit[^\n]*\n特别提醒：")
        self.assertRegex(comments, r"改动导读：[^\n]*text arrows")

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
        for relative, anchor in re.findall(
            r"\]\((references/[^)#\s]+\.md)(?:#([^)\s]+))?\)", body
        ):
            reference = (SKILL_ROOT / relative).resolve()
            self.assertTrue(reference.is_relative_to(SKILL_ROOT.resolve()), relative)
            self.assertTrue(reference.is_file(), relative)
            if anchor:
                headings = {
                    re.sub(r"[^a-z0-9\- ]", "", h.lower()).strip().replace(" ", "-")
                    for h in re.findall(
                        r"^#+\s+(.+)$", reference.read_text(encoding="utf-8"), re.MULTILINE
                    )
                }
                self.assertIn(anchor, headings, f"{relative}#{anchor}")

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
        self.assertEqual(len(evals), 67)
        self.assertEqual(len({case["id"] for case in evals}), 67)

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
        self.assertEqual(len(behavior), 54)
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
        self.assertEqual(categories.count("control"), 36)
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

        briefing_ids = {
            "behavior-briefing-small-change",
            "behavior-briefing-mixed-noise",
            "behavior-briefing-atomic-large",
            "behavior-briefing-repo-split-rule",
            "behavior-briefing-description-mismatch",
            "behavior-briefing-async-flow",
            "behavior-briefing-comment-diagram-fallback",
            "behavior-briefing-unconfirmed-concepts",
            "behavior-briefing-justified-concepts",
        }
        self.assertTrue(briefing_ids.issubset({case["id"] for case in behavior}))


if __name__ == "__main__":
    unittest.main()
