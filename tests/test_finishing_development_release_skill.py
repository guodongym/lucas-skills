import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "finishing-a-development-release"


def load_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"missing YAML frontmatter: {path}")
    return yaml.safe_load(match.group(1)), text[match.end() :]


class FinishingDevelopmentReleaseSkillTests(unittest.TestCase):
    def test_layout_allows_only_expected_entries(self):
        entries = {path.name for path in SKILL_ROOT.iterdir()}
        self.assertEqual(entries, {"SKILL.md", "agents", "references", "evals"})
        self.assertFalse({"scripts", "assets", "README.md"}.intersection(entries))
        self.assertEqual(
            {path.name for path in (SKILL_ROOT / "agents").iterdir()},
            {"openai.yaml"},
        )
        self.assertTrue((SKILL_ROOT / "references" / "deployment-package.md").is_file())

    def test_deployment_package_reference_covers_core_contracts(self):
        ref_path = SKILL_ROOT / "references" / "deployment-package.md"
        self.assertTrue(ref_path.is_file(), "references/deployment-package.md must exist")
        text = ref_path.read_text(encoding="utf-8")

        for required_phrase in (
            "deploy/releases/<version>/",
            "DEPLOY.md",
            "完整文件树",
            "空库初始化",
            "存量增量升级",
            "回滚",
            "测试",
            "自建",
            "已判定用于存量升级",
            "无法从项目入口",
            "pre-migration",
            "post-migration",
            "重复执行",
            "起始版本",
            "sha256",
            "内容完全一致",
            "set -euo pipefail",
            "bash -n",
            "绝不自动删除",
            "明文密钥",
            "路径与变更状态",
            "键名",
            "工具输出",
            "A/M/D/R",
            "已发布",
            "历史兼容性",
            "其他升级起点",
            "任一起点",
        ):
            with self.subTest(phrase=required_phrase):
                self.assertIn(required_phrase, text)

    def test_eval_manifest_is_complete_and_fixtures_exist(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["skill_name"], "finishing-a-development-release")
        cases = manifest["evals"]
        self.assertEqual(len(cases), 19)
        ids = [case["id"] for case in cases]
        self.assertEqual(len(set(ids)), 19)

        required_pairs = {
            "bootstrap-and-incremental-sql",
            "managed-bootstrap-ok",
            "managed-bypass-ddl-blocked",
            "managed-custom-chain-and-skipped-prod",
            "managed-legitimate-dba-sql-hybrid",
            "sql-unclassified-purpose-blocked",
            "repo-rule-with-ops-changes",
            "repo-rule-no-ops-changes",
            "initial-release-full-tree",
            "post-tag-immutable-digest-boundary",
            "same-version-dir-reuse-vs-conflict",
            "local-main-blocked-preserves-workspace",
            "protected-release-pr-merge-sha-and-custom-exec",
            "ezone-atomic-and-portable-auth-split",
            "fast-path-tool-repo-skip",
            "explicit-skip-overrides-repo-rule",
            "sensitive-config-diff-redaction",
            "managed-history-migration-mutated-blocked",
            "managed-rc-migration-mutated-blocked",
        }
        self.assertEqual(set(ids), required_pairs)

        fixture_count = 0
        for case in cases:
            for field in (
                "id",
                "kind",
                "category",
                "prompt",
                "expected_output",
                "files",
                "assertions",
            ):
                self.assertIn(field, case, case["id"])
            self.assertIn(case["kind"], {"behavior", "trigger"})
            self.assertTrue(case["assertions"], case["id"])
            for relative in case["files"]:
                fixture_count += 1
                fixture = (SKILL_ROOT / relative).resolve()
                self.assertTrue(fixture.is_relative_to(SKILL_ROOT.resolve()), relative)
                self.assertTrue(fixture.is_file(), f"{case['id']}: {relative}")
        self.assertEqual(fixture_count, 17)

    def test_metadata_and_openai_yaml_are_valid(self):
        frontmatter, _ = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertEqual(set(frontmatter), {"name", "description"})
        self.assertEqual(frontmatter["name"], "finishing-a-development-release")
        description = frontmatter["description"]
        self.assertTrue(description.startswith("Use when "))
        lowered = description.lower()
        for trigger in ("发布收尾", "部署文档", "部署脚本", "github", "ezone"):
            self.assertIn(trigger, lowered)

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
        self.assertIn("$finishing-a-development-release", interface["default_prompt"])

    def test_entry_routes_deployment_reference_conditionally(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        routes = {
            link: condition
            for condition, link in re.findall(
                r"^\|([^|\n]+)\|[^|\n]*\]\((references/[^)\s]+\.md)\)",
                body,
                re.MULTILINE,
            )
        }
        self.assertIn("references/deployment-package.md", routes)
        condition = routes["references/deployment-package.md"]
        self.assertRegex(condition, r"部署|每版|信号")
        for self_contained_clue in (
            "容器",
            "迁移",
            "配置模板",
            "纯文档",
            "弱信号",
        ):
            with self.subTest(clue=self_contained_clue):
                self.assertIn(self_contained_clue, condition)
        self.assertRegex(body, r"未命中.*仅用本入口|仅在命中.*读取")
        for relative in re.findall(r"\]\((references/[^)\s]+\.md)\)", body):
            ref = (SKILL_ROOT / relative).resolve()
            self.assertTrue(ref.is_relative_to(SKILL_ROOT.resolve()), relative)
            self.assertTrue(ref.is_file(), relative)

    def test_entry_encodes_orchestration_paths_ezone_and_gates(self):
        _, body = load_frontmatter(SKILL_ROOT / "SKILL.md")
        for subskill in (
            "neat-freak",
            "git-history-rewrite",
            "finishing-a-development-branch",
            "verification-before-completion",
            "ezone",
        ):
            with self.subTest(subskill=subskill):
                self.assertIn(subskill, body)

        for phrase in (
            "REQUIRED SUB-SKILL",
            "REUSED CONTRACT",
            "每版",
            "独立临时 worktree",
            "release PR awaiting review/merge",
            "实际合并 SHA",
            "按文件用途",
            "--no-notify",
            "git ls-remote",
            "skipped (not authorized)",
            "unavailable",
            "Deployment package",
            "skipped",
            "reused",
            "generated",
            "blocked",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)


if __name__ == "__main__":
    unittest.main()
