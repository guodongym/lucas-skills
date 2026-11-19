from __future__ import annotations

import io
import importlib
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tools.agent_manager import cli as agent_manager_cli
from tools.agent_manager.cli import main
from tools.agent_manager.instructions import InstructionPlanError
from tools.agent_manager.skills import (
    _enabled_antigravity_plugin_sources,
    _fixed_inventory_sources,
    _enabled_codex_plugin_sources,
    apply_adoption,
    apply_plan,
    BatchResult,
    ChangePlan,
    LinkState,
    OperationResult,
    PathSnapshot,
    PlannedChange,
    build_adapters,
    detect_surfaces,
    plan_adoption,
    plan_set,
    scan_inventory,
    scan_managed_state,
    scan_repository,
)


def write_skill(root: Path, slug: str, name: str, description: str = "test skill") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'fixture'\n",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "# Repository instructions\n\nKeep changes focused.\n",
        encoding="utf-8",
    )
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_dir


def build_test_state(
    repo: Path,
    home: Path,
    *,
    installed_commands: dict[str, str] | None = None,
    installed_apps: set[str] | None = None,
):
    installed_commands = installed_commands or {}
    installed_apps = installed_apps or set()
    applications = home.parent / "Applications"
    for app_name in installed_apps:
        (applications / app_name).mkdir(parents=True, exist_ok=True)
    adapters = build_adapters(home)
    surfaces = detect_surfaces(
        which=lambda command: installed_commands.get(command),
        applications=applications,
    )
    return scan_managed_state(scan_repository(repo), adapters, surfaces)


class PackageLayoutTests(unittest.TestCase):
    def test_default_repo_root_points_to_checkout(self) -> None:
        from tools.agent_manager import cli

        self.assertEqual(cli.DEFAULT_REPO_ROOT, Path(__file__).resolve().parents[1])


class ReadmeTests(unittest.TestCase):
    def test_documents_unified_command_hierarchy_and_service_lifecycle(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        for text in (
            "uv run agent-manager status --json",
            "uv run agent-manager doctor --json",
            "uv run agent-manager skills set docx --tool codex --on --json",
            "uv run agent-manager skills adopt --json",
            "uv run agent-manager instructions status --json",
            "uv run agent-manager instructions adopt --json",
            "uv run agent-manager instructions adopt --replace-existing --json",
            "uv run agent-manager instructions adopt --apply --replace-existing --expect-fingerprint",
            "uv run agent-manager serve --open",
            "uv run upstream-sync check",
            "uv run upstream-sync sync",
            "uv --version",
            "服务不需要后台常驻",
            "Skill 加载位置",
            "Instructions 目标路径",
            "Copilot Desktop",
            "手工",
            "新建会话",
            "必要时重启",
        ):
            self.assertIn(text, readme)
        for path in (
            "pyproject.toml",
            "uv.lock",
            "tools/agent_manager/",
            "tools/upstream_sync/",
            "~/.claude/skills/<skill>",
            "~/.codex/skills/<skill>",
            "~/.copilot/skills/<skill>",
            "~/.gemini/config/skills/<skill>",
            "~/.agents/AGENTS.md",
            "~/.claude/CLAUDE.md",
            "~/.codex/AGENTS.md",
            "~/.copilot/copilot-instructions.md",
            "~/.gemini/GEMINI.md",
        ):
            self.assertIn(path, readme)
        for obsolete in ("pip install pyyaml", "python " "vendor.py"):
            self.assertNotIn(obsolete, readme)

    def test_documents_independent_apply_and_archive_safety_gates(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        manager_docs = readme[
            readme.index("## Agent Manager"):readme.index("## 添加新的上游来源")
        ]
        for text in (
            "文本输出仅提供摘要",
            "完整字段",
            "集成后验收门",
            "preview / cancel / port shutdown",
            "真实 HOME apply",
            "单独取得明确授权",
            "旧状态归档",
            "独立授权",
            "四个工具族、八个检测表面",
            "四个 Skill 根目录",
            "五个 Instructions 文件入口",
            "Cursor/Grok 兼容消费",
            "~/.cursor/skills",
            "~/.grok/skills",
        ):
            self.assertIn(text, manager_docs)
        instructions_start = readme.index("| target | Instructions 目标路径 | 覆盖范围 |")
        instructions_end = readme.index("\n\nCopilot Desktop", instructions_start)
        instructions_rows = [
            line
            for line in readme[instructions_start:instructions_end].splitlines()
            if line.startswith("| `")
        ]
        self.assertEqual(len(instructions_rows), 5)
        self.assertEqual(
            [row.split("|")[1].strip() for row in instructions_rows],
            ["`shared`", "`claude`", "`codex`", "`copilot`", "`antigravity`"],
        )
        self.assertLess(
            readme.index(
                "uv run agent-manager instructions adopt --replace-existing --json"
            ),
            readme.index(
                "uv run agent-manager instructions adopt --apply --replace-existing --expect-fingerprint"
            ),
        )

    def test_documents_fail_closed_scan_and_ds_store_exception(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        spec = Path(
            "docs/superpowers/specs/2026-07-14-global-skill-manager-design.md"
        ).read_text(encoding="utf-8")

        for document in (readme, spec):
            self.assertIn("扫描问题", document)
            self.assertIn("拒绝全部 `set` 和 `adopt`", document)
            self.assertIn("问题代码和路径", document)
        self.assertIn("`.DS_Store`", spec)


class RepositoryScanTests(unittest.TestCase):
    def test_scans_valid_skill_and_allows_name_mismatch_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            temp_home = repo / "home"
            temp_home.mkdir()
            write_skill(repo, "example-skill", "example-trigger-name")

            with patch.dict(os.environ, {"HOME": str(temp_home)}):
                self.assertEqual(Path.home(), temp_home)
                result = scan_repository(repo)

            self.assertEqual([skill.slug for skill in result.skills], ["example-skill"])
            self.assertEqual(result.skills[0].name, "example-trigger-name")
            self.assertEqual(result.skills[0].warnings, ("name-mismatch",))
            self.assertEqual(result.issues, ())

    def test_rejects_missing_frontmatter_and_duplicate_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            temp_home = repo / "home"
            temp_home.mkdir()
            invalid = repo / "skills" / "missing-frontmatter"
            invalid.mkdir(parents=True)
            (invalid / "SKILL.md").write_text("# invalid\n", encoding="utf-8")
            write_skill(repo, "one", "duplicate")
            write_skill(repo, "two", "duplicate")

            with patch.dict(os.environ, {"HOME": str(temp_home)}):
                self.assertEqual(Path.home(), temp_home)
                result = scan_repository(repo)

            self.assertEqual(result.skills, ())
            self.assertEqual(
                sorted(issue.code for issue in result.issues),
                ["duplicate-name", "duplicate-name", "invalid-frontmatter"],
            )


class ManagedStateTests(unittest.TestCase):
    def test_builds_exact_target_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            adapters = {item.key: item for item in build_adapters(home)}
            self.assertEqual(
                set(adapters),
                {
                    "claude-shared",
                    "codex-shared",
                    "copilot-shared",
                    "antigravity-shared",
                },
            )
            self.assertEqual(adapters["claude-shared"].root, home / ".claude/skills")
            self.assertEqual(adapters["codex-shared"].root, home / ".codex/skills")
            self.assertEqual(adapters["copilot-shared"].root, home / ".copilot/skills")
            self.assertEqual(
                adapters["antigravity-shared"].root, home / ".gemini/config/skills"
            )
            self.assertEqual(
                adapters["antigravity-shared"].surfaces,
                ("antigravity-desktop", "antigravity-cli"),
            )

    def test_cli_and_server_allow_lists_match_the_four_tool_contract(self) -> None:
        from tools.agent_manager import server as agent_manager_server

        self.assertEqual(
            agent_manager_cli.TOOLS,
            ("claude", "codex", "copilot", "antigravity"),
        )
        self.assertEqual(
            agent_manager_cli.INSTRUCTION_TARGETS,
            ("shared", "claude", "codex", "copilot", "antigravity"),
        )
        self.assertEqual(agent_manager_server.TOOLS, agent_manager_cli.TOOLS)
        self.assertEqual(
            agent_manager_server.INSTRUCTION_TARGETS,
            agent_manager_cli.INSTRUCTION_TARGETS,
        )

    def test_detects_exact_surfaces_and_codex_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            applications = Path(tmp) / "Applications"
            (applications / "Codex.app").mkdir(parents=True)
            (applications / "Antigravity.app").mkdir(parents=True)
            commands: list[str] = []

            surfaces = detect_surfaces(
                which=lambda command: commands.append(command) or None,
                applications=applications,
            )

            self.assertEqual(
                set(surfaces),
                {
                    "claude-desktop",
                    "codex-desktop",
                    "copilot-desktop",
                    "antigravity-desktop",
                    "claude-cli",
                    "codex-cli",
                    "copilot-cli",
                    "antigravity-cli",
                },
            )
            self.assertTrue(surfaces["codex-desktop"].installed)
            self.assertTrue(surfaces["antigravity-desktop"].installed)
            self.assertFalse(surfaces["antigravity-cli"].installed)
            self.assertEqual(commands, ["claude", "codex", "copilot", "agy"])

    def test_prefers_chatgpt_app_over_codex_app(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            applications = Path(tmp) / "Applications"
            (applications / "ChatGPT.app").mkdir(parents=True)
            (applications / "Codex.app").mkdir(parents=True)
            checked: list[str] = []
            real_exists = Path.exists

            with patch.object(
                Path,
                "exists",
                autospec=True,
                side_effect=lambda path: checked.append(path.name) or real_exists(path),
            ):
                surfaces = detect_surfaces(which=lambda _: None, applications=applications)

            self.assertTrue(surfaces["codex-desktop"].installed)
            self.assertIn("ChatGPT.app", checked)
            self.assertNotIn("Codex.app", checked)

    def test_classifies_direct_legacy_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            home = root / "home"
            skill = write_skill(repo, "docx", "docx")
            scan = scan_repository(repo)
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}

            direct = by_key["claude-shared"].root / "docx"
            direct.parent.mkdir(parents=True)
            direct.symlink_to(skill)

            legacy_root = home / ".cc-switch/skills"
            legacy_root.mkdir(parents=True)
            (legacy_root / "docx").symlink_to(skill)
            legacy = by_key["codex-shared"].root / "docx"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(legacy_root / "docx")

            conflict = by_key["copilot-shared"].root / "docx"
            conflict.mkdir(parents=True)

            installed = {
                "claude": "/bin/claude",
                "codex": "/bin/codex",
                "copilot": "/bin/copilot",
            }
            surfaces = detect_surfaces(
                which=installed.get,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan, adapters, surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(statuses[("claude-shared", "docx")].state, LinkState.ENABLED)
            self.assertEqual(statuses[("codex-shared", "docx")].state, LinkState.LEGACY)
            self.assertEqual(statuses[("copilot-shared", "docx")].state, LinkState.CONFLICT)


class InventoryTests(unittest.TestCase):
    @staticmethod
    def _tree_snapshot(root: Path) -> tuple[tuple[str, str, object], ...]:
        entries: list[tuple[str, str, object]] = []
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(root))
            if path.is_symlink():
                entries.append((relative, "symlink", os.readlink(path)))
            elif path.is_dir():
                entries.append((relative, "directory", None))
            else:
                entries.append((relative, "file", path.read_bytes()))
        return tuple(entries)

    def test_lists_unmanaged_and_duplicate_skills_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(home / "external", "review", "review")
            claude_root = home / ".claude/skills"
            claude_root.mkdir(parents=True)
            (claude_root / "review").symlink_to(home / "external/skills/review")
            review_copy = claude_root / "review-copy"
            review_copy.mkdir()
            (review_copy / "SKILL.md").write_text(
                "---\nname: review\ndescription: local review copy\n---\n",
                encoding="utf-8",
            )
            hidden = claude_root / ".ignored"
            hidden.mkdir()
            (hidden / "SKILL.md").write_text(
                "---\nname: ignored\ndescription: hidden\n---\n",
                encoding="utf-8",
            )
            broken = home / ".copilot/skills/broken"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.symlink_to(home / "missing")
            built_in_root = home / "Library/Application Support/com.github.githubapp/app-skills"
            built_in = built_in_root / "builtin"
            built_in.mkdir(parents=True)
            (built_in / "SKILL.md").write_text(
                "---\nname: builtin\ndescription: built in\n---\n",
                encoding="utf-8",
            )
            enabled_root = home / ".codex/plugins/cache/market/enabled/1.0.0"
            disabled_root = home / ".codex/plugins/cache/market/disabled/1.0.0"
            for plugin_root, slug in (
                (enabled_root, "enabled-skill"),
                (disabled_root, "disabled-skill"),
            ):
                manifest = plugin_root / ".codex-plugin/plugin.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text('{"skills":"skills"}\n', encoding="utf-8")
                write_skill(plugin_root, slug, slug)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                '[plugins]\n"enabled@market" = { enabled = true }\n'
                '"disabled@market" = { enabled = false }\n',
                encoding="utf-8",
            )

            state = build_test_state(
                repo,
                home,
                installed_commands={
                    "claude": "/bin/claude",
                    "copilot": "/bin/copilot",
                },
            )
            before = self._tree_snapshot(home)
            records = scan_inventory(state, home)

            self.assertEqual(self._tree_snapshot(home), before)
            self.assertTrue(
                any(
                    record.slug == "review" and record.source_type == "external-link"
                    for record in records
                )
            )
            self.assertTrue(
                any(
                    record.slug == "review-copy" and record.source_type == "local-copy"
                    for record in records
                )
            )
            self.assertTrue(
                any(
                    record.slug == "broken" and record.source_type == "broken"
                    for record in records
                )
            )
            self.assertTrue(
                any(
                    record.slug == "builtin" and record.source_type == "built-in"
                    for record in records
                )
            )
            self.assertTrue(
                any(
                    record.slug == "enabled-skill" and record.source_type == "plugin"
                    for record in records
                )
            )
            self.assertFalse(any(record.slug == "disabled-skill" for record in records))
            self.assertFalse(any(record.slug == ".ignored" for record in records))
            self.assertTrue(
                all(
                    "duplicate-name" in record.flags
                    for record in records
                    if record.name == "review"
                )
            )
            self.assertTrue(
                any(
                    record.slug == "review"
                    and record.raw_target == home / "external/skills/review"
                    for record in records
                )
            )
            self.assertTrue((claude_root / "review").is_symlink())

    def test_fixed_inventory_sources_are_the_nine_supported_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            sources = _fixed_inventory_sources(home)
            self.assertEqual(
                [source.path for source in sources],
                [
                    home / ".claude/skills",
                    home / ".codex/skills",
                    home / ".codex/skills/.system",
                    home / ".copilot/skills",
                    home / ".agents/skills",
                    home / "Library/Application Support/com.github.githubapp/app-skills",
                    home / ".gemini/config/skills",
                    home / ".gemini/antigravity/builtin/skills",
                    home / ".gemini/antigravity-cli/builtin/skills",
                ],
            )
            by_path = {source.path: source for source in sources}
            self.assertEqual(
                by_path[home / ".gemini/config/skills"].surfaces,
                ("antigravity-desktop", "antigravity-cli"),
            )
            self.assertEqual(
                by_path[home / ".gemini/antigravity/builtin/skills"].surfaces,
                ("antigravity-desktop",),
            )
            self.assertEqual(
                by_path[home / ".gemini/antigravity-cli/builtin/skills"].surfaces,
                ("antigravity-cli",),
            )

    def test_antigravity_plugin_sources_respect_config_override_manifest_disabled_and_jsonc(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            config = home / ".gemini/config/config.json"
            config.parent.mkdir(parents=True)
            config.write_text(
                json.dumps(
                    {
                        "plugins": {
                            "default-enabled": {"installedFrom": {"id": "partner/default"}},
                            "config-disabled": {"enabled": False},
                            "config-reenabled": {"enabled": True},
                            "no-skills-plugin": {"enabled": True},
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            plugins = home / ".gemini/config/plugins"

            # 1. Default-enabled plugin (no explicit enabled key in config.json) with JSONC + URL
            default_enabled = plugins / "default-enabled"
            write_skill(default_enabled, "alpha", "alpha")
            (default_enabled / "plugin.json").write_text(
                "{\n"
                "  // line comment\n"
                '  "name": "default-enabled",\n'
                '  "homepage": "https://antigravity.google/docs/plugins",\n'
                "  /* block comment */\n"
                "}\n",
                encoding="utf-8",
            )

            # 2. Explicitly disabled in config.json (skipped even if manifest is broken)
            config_disabled = plugins / "config-disabled"
            write_skill(config_disabled, "beta", "beta")
            (config_disabled / "plugin.json").write_text("{broken json\n", encoding="utf-8")

            # 3. Ships disabled in manifest, re-enabled in config.json via .antigravity-plugin/plugin.json
            reenabled = plugins / "config-reenabled"
            write_skill(reenabled, "gamma", "gamma")
            (reenabled / ".antigravity-plugin").mkdir(parents=True)
            (reenabled / ".antigravity-plugin/plugin.json").write_text(
                '{"name": "reenabled", "disabled": true}\n',
                encoding="utf-8",
            )

            # 4. Ships disabled in manifest without config override -> skipped
            manifest_disabled = plugins / "manifest-disabled"
            write_skill(manifest_disabled, "delta", "delta")
            (manifest_disabled / "plugin.json").write_text(
                '{"name": "manifest-disabled", "disabled": true}\n',
                encoding="utf-8",
            )

            # 5. Enabled plugin without skills directory -> skipped cleanly without issues
            no_skills = plugins / "no-skills-plugin"
            no_skills.mkdir(parents=True)
            (no_skills / "plugin.json").write_text('{"name": "no-skills"}\n', encoding="utf-8")

            # 6. Directory without any plugin manifest -> ignored
            unmanaged = plugins / "not-a-plugin"
            write_skill(unmanaged, "ignored", "ignored")

            # 7. Enabled plugin using .gemini-plugin/plugin.json
            gemini_manifest = plugins / "gemini-format"
            write_skill(gemini_manifest, "epsilon", "epsilon")
            (gemini_manifest / ".gemini-plugin").mkdir(parents=True)
            (gemini_manifest / ".gemini-plugin/plugin.json").write_text(
                '{"name": "gemini-format"}\n',
                encoding="utf-8",
            )

            sources, issues = _enabled_antigravity_plugin_sources(home)

            self.assertEqual(issues, [])
            self.assertEqual(
                [source.path for source in sources],
                [
                    reenabled / "skills",
                    default_enabled / "skills",
                    gemini_manifest / "skills",
                ],
            )
            self.assertTrue(
                all(
                    source.tools == ("antigravity",)
                    and source.surfaces == ("antigravity-desktop", "antigravity-cli")
                    and source.source_type == "plugin"
                    for source in sources
                )
            )

    def test_antigravity_plugin_failures_become_issues_and_do_not_stop_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            plugins = home / ".gemini/config/plugins"

            bad_json = plugins / "bad-json"
            write_skill(bad_json, "s1", "s1")
            (bad_json / "plugin.json").write_text('{"name": "bad", /* unterminated\n', encoding="utf-8")

            bad_disabled = plugins / "bad-disabled"
            write_skill(bad_disabled, "s2", "s2")
            (bad_disabled / "plugin.json").write_text(
                '{"name": "bad-disabled", "disabled": "yes"}\n',
                encoding="utf-8",
            )

            token_splice = plugins / "token-splice"
            write_skill(token_splice, "s3", "s3")
            (token_splice / "plugin.json").write_text(
                '{"disabled": tru/*comment*/e}\n',
                encoding="utf-8",
            )

            orphan_comma = plugins / "orphan-comma"
            write_skill(orphan_comma, "s4", "s4")
            (orphan_comma / "plugin.json").write_text(
                "{,}\n",
                encoding="utf-8",
            )

            broken_manifest = plugins / "broken-manifest"
            write_skill(broken_manifest, "s5", "s5")
            (broken_manifest / "plugin.json").symlink_to(home / "missing-manifest.json")
            # Ensure broken top-level plugin.json does NOT silently fall through to fallback manifest
            (broken_manifest / ".antigravity-plugin").mkdir(parents=True)
            (broken_manifest / ".antigravity-plugin/plugin.json").write_text(
                '{"name": "fallback"}\n',
                encoding="utf-8",
            )

            outside_manifest = home / "outside-manifest.json"
            outside_manifest.write_text('{"name": "escaped"}\n', encoding="utf-8")
            escaped_manifest = plugins / "escaped-manifest"
            write_skill(escaped_manifest, "s6", "s6")
            (escaped_manifest / "plugin.json").symlink_to(outside_manifest)

            outside_meta_dir = home / "outside-meta"
            outside_meta_dir.mkdir(parents=True)
            (outside_meta_dir / "plugin.json").write_text('{"name": "outside"}\n', encoding="utf-8")
            escaped_meta_plugin = plugins / "escaped-meta-dir"
            write_skill(escaped_meta_plugin, "s7", "s7")
            (escaped_meta_plugin / ".antigravity-plugin").symlink_to(outside_meta_dir)

            escaped_target = write_skill(home / "external", "escaped", "escaped").parent
            escaped_plugin = plugins / "escaped-skills"
            escaped_plugin.mkdir(parents=True)
            (escaped_plugin / "plugin.json").write_text('{"name": "escaped"}\n', encoding="utf-8")
            (escaped_plugin / "skills").symlink_to(escaped_target)

            file_skills_plugin = plugins / "file-skills"
            file_skills_plugin.mkdir(parents=True)
            (file_skills_plugin / "plugin.json").write_text('{"name": "file-skills"}\n', encoding="utf-8")
            (file_skills_plugin / "skills").write_text("not a dir\n", encoding="utf-8")

            broken_skills_plugin = plugins / "broken-skills"
            broken_skills_plugin.mkdir(parents=True)
            (broken_skills_plugin / "plugin.json").write_text('{"name": "broken-skills"}\n', encoding="utf-8")
            (broken_skills_plugin / "skills").symlink_to(broken_skills_plugin / "missing-dir")

            locked_plugin = plugins / "locked-plugin"
            locked_plugin.mkdir(parents=True)

            valid = plugins / "valid-plugin"
            write_skill(valid, "valid-skill", "valid-skill")
            (valid / "plugin.json").write_text(
                '{"name": "valid", "note": "escaped \\"// not comment\\" /* also string */",}\n',
                encoding="utf-8",
            )

            real_lstat = os.lstat

            def controlled_lstat(path, *args, **kwargs):
                if Path(path) == locked_plugin / "plugin.json":
                    raise PermissionError("permission denied")
                return real_lstat(path, *args, **kwargs)

            with patch("tools.agent_manager.skills.os.lstat", side_effect=controlled_lstat):
                sources, issues = _enabled_antigravity_plugin_sources(home)

            self.assertEqual([source.path for source in sources], [valid / "skills"])
            self.assertEqual(
                {(issue.code, issue.path) for issue in issues},
                {
                    ("plugin-manifest-invalid", bad_json / "plugin.json"),
                    ("plugin-manifest-invalid", bad_disabled / "plugin.json"),
                    ("plugin-manifest-invalid", token_splice / "plugin.json"),
                    ("plugin-manifest-invalid", orphan_comma / "plugin.json"),
                    ("plugin-manifest-invalid", broken_manifest / "plugin.json"),
                    ("plugin-manifest-invalid", escaped_manifest / "plugin.json"),
                    (
                        "plugin-manifest-invalid",
                        escaped_meta_plugin / ".antigravity-plugin/plugin.json",
                    ),
                    ("plugin-manifest-invalid", locked_plugin / "plugin.json"),
                    ("plugin-skills-path-invalid", escaped_plugin / "plugin.json"),
                    ("plugin-skills-path-invalid", file_skills_plugin / "plugin.json"),
                    ("plugin-skills-path-invalid", broken_skills_plugin / "plugin.json"),
                },
            )

    def test_antigravity_invalid_config_json_reports_issue(self) -> None:
        cases = (
            ("malformed-json", "{not valid json\n"),
            ("top-level-list", "[]\n"),
            ("plugins-not-object", '{"plugins": []}\n'),
            ("broken-symlink", None),
            ("directory", "DIR"),
        )
        for label, content in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp).resolve() / "home"
                config = home / ".gemini/config/config.json"
                config.parent.mkdir(parents=True)
                if content is None:
                    config.symlink_to(home / "missing-config.json")
                elif content == "DIR":
                    config.mkdir()
                else:
                    config.write_text(content, encoding="utf-8")
                plugin = home / ".gemini/config/plugins/demo"
                write_skill(plugin, "demo-skill", "demo-skill")
                (plugin / "plugin.json").write_text('{"name": "demo"}\n', encoding="utf-8")

                sources, issues = _enabled_antigravity_plugin_sources(home)

                self.assertEqual(sources, [])
                self.assertEqual(len(issues), 1)
                self.assertEqual(issues[0].code, "antigravity-config-invalid")
                self.assertEqual(issues[0].path, config)

    def test_antigravity_config_plugins_null_and_per_plugin_entry_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            config = home / ".gemini/config/config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"plugins": null}\n', encoding="utf-8")
            demo = home / ".gemini/config/plugins/demo"
            write_skill(demo, "demo-skill", "demo-skill")
            (demo / "plugin.json").write_text('{"name": "demo"}\n', encoding="utf-8")

            sources, issues = _enabled_antigravity_plugin_sources(home)
            self.assertEqual(issues, [])
            self.assertEqual([source.path for source in sources], [demo / "skills"])

            # Per-plugin invalid entries report issue without stopping valid plugins
            bad_obj = home / ".gemini/config/plugins/bad-obj"
            write_skill(bad_obj, "s1", "s1")
            (bad_obj / "plugin.json").write_text('{"name": "bad-obj"}\n', encoding="utf-8")
            bad_flag = home / ".gemini/config/plugins/bad-flag"
            write_skill(bad_flag, "s2", "s2")
            (bad_flag / "plugin.json").write_text('{"name": "bad-flag"}\n', encoding="utf-8")
            config.write_text(
                json.dumps(
                    {
                        "plugins": {
                            "bad-obj": "invalid",
                            "bad-flag": {"enabled": "yes"},
                            "demo": {"enabled": True},
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            sources2, issues2 = _enabled_antigravity_plugin_sources(home)
            self.assertEqual([source.path for source in sources2], [demo / "skills"])
            self.assertEqual(len(issues2), 2)
            self.assertEqual(
                {issue.code for issue in issues2},
                {"antigravity-config-invalid"},
            )

    def test_antigravity_shared_adapter_is_available_from_cli_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            state = build_test_state(
                repo,
                home,
                installed_commands={"agy": "/Users/test/.local/bin/agy"},
            )
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}
            self.assertEqual(
                statuses[("antigravity-shared", "docx")].state,
                LinkState.DISABLED,
            )
            plan = plan_set(state, ["docx"], ["antigravity"], True)
            self.assertEqual(
                [(item.adapter_key, item.action) for item in plan.changes],
                [("antigravity-shared", "create")],
            )

    def test_scan_inventory_distinguishes_antigravity_desktop_and_cli_builtins_and_detects_collision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            repo_skill = write_skill(repo, "automation", "automation")
            # Same builtin skill exists in both desktop and cli builtin folders
            desktop_builtin = home / ".gemini/antigravity/builtin/skills/automation"
            desktop_builtin.mkdir(parents=True)
            (desktop_builtin / "SKILL.md").write_text(
                "---\nname: automation\ndescription: desktop builtin\n---\n",
                encoding="utf-8",
            )
            cli_builtin = home / ".gemini/antigravity-cli/builtin/skills/automation"
            cli_builtin.mkdir(parents=True)
            (cli_builtin / "SKILL.md").write_text(
                "---\nname: automation\ndescription: cli builtin\n---\n",
                encoding="utf-8",
            )
            state = build_test_state(
                repo,
                home,
                installed_apps={"Antigravity.app"},
                installed_commands={"agy": "/usr/local/bin/agy"},
            )

            # Without user symlink: desktop builtin and cli builtin do NOT collide with each other
            records_before = scan_inventory(state, home)
            self.assertEqual(len(records_before), 2)
            self.assertTrue(all(record.source_type == "built-in" for record in records_before))
            self.assertTrue(all("duplicate-name" not in record.flags for record in records_before))

            # With user symlink in ~/.gemini/config/skills: collides with both builtins
            user_link = home / ".gemini/config/skills/automation"
            user_link.parent.mkdir(parents=True)
            user_link.symlink_to(repo_skill)
            records_after = scan_inventory(state, home)
            self.assertEqual(len(records_after), 3)
            self.assertTrue(all("duplicate-name" in record.flags for record in records_after))

    def test_codex_plugin_sources_prefer_remote_and_newest_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[plugins]\n"demo@market" = { enabled = true }\n'
                '"missing@market" = { enabled = true }\n',
                encoding="utf-8",
            )
            cache = home / ".codex/plugins/cache"
            regular = cache / "market/demo/1.0.0"
            regular_manifest = regular / ".codex-plugin/plugin.json"
            regular_manifest.parent.mkdir(parents=True)
            regular_manifest.write_text("{}\n", encoding="utf-8")
            write_skill(regular, "regular-skill", "regular-skill")
            remote = cache / "market-remote/demo"
            (remote / ".codex-remote-plugin-install.json").parent.mkdir(parents=True)
            (remote / ".codex-remote-plugin-install.json").write_text(
                "{}\n",
                encoding="utf-8",
            )
            old_manifest = remote / "1.0.0/.claude-plugin/plugin.json"
            old_manifest.parent.mkdir(parents=True)
            old_manifest.write_text("{}\n", encoding="utf-8")
            write_skill(remote / "1.0.0", "old-skill", "old-skill")
            newest = remote / "2.0.0"
            newest_manifest = newest / ".codex-plugin/plugin.json"
            newest_manifest.parent.mkdir(parents=True)
            newest_manifest.write_text(
                '{"skills":"custom-skills"}\n',
                encoding="utf-8",
            )
            write_skill(newest / "custom-skills-root", "newest-skill", "newest-skill")
            (newest / "custom-skills-root/skills").rename(newest / "custom-skills")
            os.utime(old_manifest, ns=(1, 1))
            os.utime(newest_manifest, ns=(2, 2))

            sources, issues = _enabled_codex_plugin_sources(home)

            self.assertEqual(
                [source.path for source in sources],
                [newest / "custom-skills"],
            )
            self.assertEqual([issue.code for issue in issues], ["plugin-manifest-missing"])
            self.assertEqual(issues[0].path, cache / "market/missing")

    def test_codex_manifest_failures_become_issues_and_do_not_stop_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            plugin_names = (
                "bad-stat",
                "bad-read",
                "bad-utf8",
                "bad-json",
                "bad-field",
                "valid",
            )
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "[plugins]\n"
                + "".join(
                    f'"{name}@market" = {{ enabled = true }}\n'
                    for name in plugin_names
                ),
                encoding="utf-8",
            )
            manifests: dict[str, Path] = {}
            for name in plugin_names:
                plugin_root = home / f".codex/plugins/cache/market/{name}/1.0.0"
                manifest = plugin_root / ".codex-plugin/plugin.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text("{}\n", encoding="utf-8")
                manifests[name] = manifest
            manifests["bad-utf8"].write_bytes(b"\xff")
            manifests["bad-json"].write_text("{\n", encoding="utf-8")
            manifests["bad-field"].write_text('{"skills": []}\n', encoding="utf-8")
            valid_skills = manifests["valid"].parent.parent / "skills"
            valid_skill = valid_skills / "valid-skill"
            valid_skill.mkdir(parents=True)
            (valid_skill / "SKILL.md").write_text(
                "---\nname: valid-skill\ndescription: valid\n---\n",
                encoding="utf-8",
            )
            real_stat = Path.stat
            real_read_text = Path.read_text

            def controlled_stat(path: Path, *args, **kwargs):
                if path == manifests["bad-stat"]:
                    raise OSError("stat failed")
                return real_stat(path, *args, **kwargs)

            def controlled_read_text(path: Path, *args, **kwargs):
                if path == manifests["bad-read"]:
                    raise OSError("read failed")
                return real_read_text(path, *args, **kwargs)

            with (
                patch.object(Path, "stat", autospec=True, side_effect=controlled_stat),
                patch.object(
                    Path,
                    "read_text",
                    autospec=True,
                    side_effect=controlled_read_text,
                ),
            ):
                sources, issues = _enabled_codex_plugin_sources(home)

            self.assertEqual([source.path for source in sources], [valid_skills])
            self.assertEqual(len(issues), 5)
            self.assertEqual(
                {issue.code for issue in issues},
                {"plugin-manifest-invalid"},
            )
            self.assertEqual(
                {issue.path for issue in issues},
                {manifests[name] for name in plugin_names if name != "valid"},
            )

    def test_codex_plugin_skills_path_must_stay_inside_version_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            plugin_names = ("absolute", "parent", "symlink", "valid")
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                "[plugins]\n"
                + "".join(
                    f'"{name}@market" = {{ enabled = true }}\n'
                    for name in plugin_names
                ),
                encoding="utf-8",
            )
            version_roots = {
                name: home / f".codex/plugins/cache/market/{name}/1.0.0"
                for name in plugin_names
            }
            external = write_skill(home / "external", "escaped", "escaped").parent
            skills_values = {
                "absolute": str(external),
                "parent": "../outside",
                "symlink": "skills",
                "valid": "skills",
            }
            for name, version_root in version_roots.items():
                manifest = version_root / ".codex-plugin/plugin.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(
                    json.dumps({"skills": skills_values[name]}) + "\n",
                    encoding="utf-8",
                )
            parent_escape = version_roots["parent"].parent / "outside/escaped-parent"
            parent_escape.mkdir(parents=True)
            (parent_escape / "SKILL.md").write_text(
                "---\nname: escaped-parent\ndescription: escaped\n---\n",
                encoding="utf-8",
            )
            (version_roots["symlink"] / "skills").symlink_to(external)
            valid_skill = version_roots["valid"] / "skills/valid-skill"
            valid_skill.mkdir(parents=True)
            (valid_skill / "SKILL.md").write_text(
                "---\nname: valid-skill\ndescription: valid\n---\n",
                encoding="utf-8",
            )

            sources, issues = _enabled_codex_plugin_sources(home)
            records = scan_inventory(build_test_state(repo, home), home)

            self.assertEqual(
                [source.path for source in sources],
                [version_roots["valid"] / "skills"],
            )
            self.assertEqual(len(issues), 3)
            self.assertEqual(
                {issue.code for issue in issues},
                {"plugin-skills-path-invalid"},
            )
            self.assertEqual(
                {record.slug for record in records if record.source_type == "plugin"},
                {"valid-skill"},
            )

    def test_markdown_symlink_is_listed_once_without_false_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            external = home / "external/flat.md"
            external.parent.mkdir(parents=True)
            external.write_text(
                "---\nname: flat\ndescription: linked markdown\n---\n",
                encoding="utf-8",
            )
            linked = home / ".codex/skills/flat.md"
            linked.parent.mkdir(parents=True)
            linked.symlink_to(external)

            records = scan_inventory(build_test_state(repo, home), home)
            flat_records = [record for record in records if record.path == linked]

            self.assertEqual(len(flat_records), 1)
            self.assertNotIn("duplicate-name", flat_records[0].flags)

    def test_symlink_cycles_are_broken_records_instead_of_scan_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            skills_root = home / ".claude/skills"
            skills_root.mkdir(parents=True)
            self_link = skills_root / "self"
            self_link.symlink_to(self_link)
            loop_a = skills_root / "loop-a"
            loop_b = skills_root / "loop-b"
            loop_a.symlink_to(loop_b)
            loop_b.symlink_to(loop_a)

            records = scan_inventory(build_test_state(repo, home), home)
            broken = {
                record.slug: record
                for record in records
                if record.slug in {"self", "loop-a", "loop-b"}
            }

            self.assertEqual(set(broken), {"self", "loop-a", "loop-b"})
            self.assertTrue(
                all(record.source_type == "broken" for record in broken.values())
            )
            self.assertTrue(
                all(record.flags == ("broken-link",) for record in broken.values())
            )
            self.assertTrue(
                all(record.resolved_target is None for record in broken.values())
            )


class ManagedStateFilesystemTests(unittest.TestCase):
    def test_reports_conflict_and_broken_when_surfaces_are_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, applications = root / "repo", root / "home", root / "Applications"
            write_skill(repo, "docx", "docx")
            (applications / "ChatGPT.app").mkdir(parents=True)
            (applications / "Claude.app").mkdir(parents=True)
            (applications / "GitHub Copilot.app").mkdir(parents=True)
            conflict = home / ".copilot/skills/docx"
            conflict.mkdir(parents=True)
            broken = home / ".claude/skills/docx"
            broken.parent.mkdir(parents=True)
            broken.symlink_to(home / "missing/docx")
            adapters = build_adapters(home)
            surfaces = detect_surfaces(which=lambda _: None, applications=applications)

            state = scan_managed_state(scan_repository(repo), adapters, surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(statuses[("copilot-shared", "docx")].state, LinkState.CONFLICT)
            self.assertEqual(statuses[("claude-shared", "docx")].state, LinkState.ERROR)
            self.assertTrue(surfaces["codex-desktop"].installed)

    def test_reports_conflict_when_adapter_root_is_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, applications = root / "repo", root / "home", root / "Applications"
            write_skill(repo, "docx", "docx")
            blocked_root = home / ".claude/skills"
            blocked_root.parent.mkdir(parents=True)
            blocked_root.write_text("not a directory", encoding="utf-8")
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=applications,
            )

            state = scan_managed_state(scan_repository(repo), build_adapters(home), surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(statuses[("claude-shared", "docx")].state, LinkState.CONFLICT)

    def test_reports_error_when_adapter_root_is_a_broken_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, applications = root / "repo", root / "home", root / "Applications"
            write_skill(repo, "docx", "docx")
            broken_root = home / ".codex/skills"
            broken_root.parent.mkdir(parents=True)
            broken_root.symlink_to(home / "missing-skills")
            surfaces = detect_surfaces(
                which=lambda command: "/bin/codex" if command == "codex" else None,
                applications=applications,
            )

            state = scan_managed_state(scan_repository(repo), build_adapters(home), surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(statuses[("codex-shared", "docx")].state, LinkState.ERROR)


class AdoptionTests(unittest.TestCase):
    def test_empty_adoption_apply_succeeds_without_state_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            state = build_test_state(repo, home)
            state_dir = home / ".local/state/lucas-skills-manager"
            plan = plan_adoption(state, state_dir)

            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertTrue(result.ok)
            self.assertEqual(result.results, ())
            self.assertFalse(state_dir.exists())

    def test_unavailable_whole_directory_is_skipped_without_container_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home)

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")

            self.assertEqual(plan.container_changes, ())
            self.assertEqual(
                [(item.adapter_key, item.action) for item in plan.link_changes],
                [("copilot-shared", "unavailable")],
            )
            self.assertTrue(copilot_root.is_symlink())

            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertTrue(result.ok)
            self.assertEqual([item.code for item in result.results], ["unavailable"])
            self.assertFalse((home / ".local/state/lucas-skills-manager").exists())
            self.assertTrue(copilot_root.is_symlink())

    def test_shared_adapter_is_available_from_either_desktop_or_cli_surface(self) -> None:
        for installed_commands, installed_apps in (
            ({}, {"GitHub Copilot.app"}),
            ({"copilot": "/bin/copilot"}, set()),
        ):
            with self.subTest(
                installed_commands=installed_commands,
                installed_apps=installed_apps,
            ), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                repo, home = root / "repo", root / "home"
                write_skill(repo, "docx", "docx")
                copilot_root = home / ".copilot/skills"
                copilot_root.parent.mkdir(parents=True)
                copilot_root.symlink_to(repo / "skills")
                state = build_test_state(
                    repo,
                    home,
                    installed_commands=installed_commands,
                    installed_apps=installed_apps,
                )

                plan = plan_adoption(
                    state,
                    home / ".local/state/lucas-skills-manager",
                )

                self.assertEqual(len(plan.container_changes), 1)
                self.assertEqual(plan.container_changes[0].adapter_key, "copilot-shared")
                self.assertEqual(plan.link_changes, ())

    def test_blocks_copilot_directory_adoption_with_hidden_repository_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (repo / "skills/.private-note").write_text("unknown\n", encoding="utf-8")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertEqual(plan.container_changes, ())
            self.assertEqual([item.action for item in plan.link_changes], ["blocked"])
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "blocked")
            self.assertTrue(copilot_root.is_symlink())
            self.assertFalse((home / ".local/state/lucas-skills-manager").exists())

    def test_copilot_directory_adoption_ignores_ds_store_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (repo / "skills/.DS_Store").write_bytes(b"finder metadata")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(
                repo,
                home,
                installed_commands={"copilot": "/bin/copilot"},
            )

            plan = plan_adoption(
                state,
                home / ".local/state/lucas-skills-manager",
            )
            result = apply_adoption(
                plan,
                {item.key: item for item in state.adapters},
            )

            self.assertEqual(len(plan.container_changes), 1)
            self.assertTrue(result.ok)
            self.assertTrue((copilot_root / "docx").is_symlink())
            self.assertFalse((copilot_root / ".DS_Store").exists())

    def test_apply_rejects_hidden_entry_added_after_container_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            (repo / "skills/.private-note").write_text("late unknown\n", encoding="utf-8")

            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "adoption-failed")
            self.assertTrue(copilot_root.is_symlink())

    def test_blocks_copilot_directory_adoption_with_unmanaged_repository_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (repo / "skills/README.txt").write_text("unmanaged\n", encoding="utf-8")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertEqual(plan.container_changes, ())
            self.assertEqual([item.action for item in plan.link_changes], ["blocked"])
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "blocked")
            self.assertTrue(copilot_root.is_symlink())
            self.assertEqual(copilot_root.resolve(), (repo / "skills").resolve())

    def test_apply_rejects_repository_entry_added_after_container_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            (repo / "skills/README.txt").write_text("late unmanaged\n", encoding="utf-8")

            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "adoption-failed")
            self.assertTrue(copilot_root.is_symlink())
            self.assertEqual(copilot_root.resolve(), (repo / "skills").resolve())

    def test_plan_is_read_only_and_snapshot_contains_original_link_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            cc_skill = home / ".cc-switch/skills/docx"
            cc_skill.parent.mkdir(parents=True)
            cc_skill.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(cc_skill)
            state = build_test_state(repo, home, installed_commands={"claude": "/bin/claude"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")

            self.assertTrue(target.is_symlink())
            self.assertEqual(os.readlink(target), str(cc_skill))
            self.assertFalse(plan.snapshot_path.exists())

            result = apply_adoption(plan, {item.key: item for item in state.adapters})
            payload = json.loads(plan.snapshot_path.read_text(encoding="utf-8"))

            self.assertTrue(result.ok)
            self.assertEqual(
                payload["links"],
                [
                    {
                        "path": str(target),
                        "kind": "symlink",
                        "link_target": str(cc_skill),
                    }
                ],
            )
            self.assertEqual(set(payload), {"links", "containers"})
            self.assertEqual(payload["containers"], [])

    def test_adopts_cc_switch_entry_links_and_writes_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            cc_skill = home / ".cc-switch/skills/docx"
            cc_skill.parent.mkdir(parents=True)
            cc_skill.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(cc_skill)
            state = build_test_state(repo, home, installed_commands={"claude": "/bin/claude"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertTrue(result.ok)
            self.assertEqual(Path(os.readlink(target)), skill.resolve())
            self.assertTrue(cc_skill.is_symlink())
            self.assertTrue(plan.snapshot_path.is_file())
            self.assertIn("links", json.loads(plan.snapshot_path.read_text(encoding="utf-8")))

    def test_converts_copilot_whole_directory_link_to_per_skill_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            result = apply_adoption(plan, {item.key: item for item in state.adapters})
            payload = json.loads(plan.snapshot_path.read_text(encoding="utf-8"))

            self.assertTrue(result.ok)
            self.assertTrue(copilot_root.is_dir())
            self.assertFalse(copilot_root.is_symlink())
            self.assertEqual((copilot_root / "docx").resolve(), (repo / "skills/docx").resolve())
            self.assertEqual((copilot_root / "pdf").resolve(), (repo / "skills/pdf").resolve())
            self.assertEqual(payload["containers"][0]["path"], str(copilot_root))
            self.assertEqual(payload["containers"][0]["link_target"], str(repo / "skills"))

    def test_apply_rejects_leaf_changed_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            cc_skill = home / ".cc-switch/skills/docx"
            cc_skill.parent.mkdir(parents=True)
            cc_skill.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(cc_skill)
            state = build_test_state(repo, home, installed_commands={"claude": "/bin/claude"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            external = write_skill(root / "external-repo", "docx", "docx")
            target.unlink()
            target.symlink_to(external)

            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertFalse(result.ok)
            self.assertEqual(target.resolve(), external.resolve())
            self.assertTrue(plan.snapshot_path.is_file())

    def test_container_exchange_failure_restores_original_directory_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            real_replace = os.replace

            def fail_install(source, destination, *args, **kwargs):
                if Path(source).name.endswith(".tmp") and Path(destination) == copilot_root:
                    raise OSError("deterministic exchange failure")
                return real_replace(source, destination, *args, **kwargs)

            with patch("tools.agent_manager.skills.os.replace", side_effect=fail_install):
                result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertFalse(result.ok)
            self.assertTrue(copilot_root.is_symlink())
            self.assertEqual(copilot_root.resolve(), (repo / "skills").resolve())
            self.assertEqual(list(copilot_root.parent.glob(".skills.lucas-skills-*")), [])

    def test_container_verification_failure_preserves_unknown_entry_in_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            real_verify = importlib.import_module(
                "tools.agent_manager.skills"
            )._target_is_direct_link
            injected = False

            def inject_unknown_and_fail(target: Path, source: Path) -> bool:
                nonlocal injected
                if target == copilot_root / "docx" and not injected:
                    injected = True
                    (copilot_root / "local-note.txt").write_text(
                        "preserve me\n",
                        encoding="utf-8",
                    )
                    return False
                return real_verify(target, source)

            with patch(
                "tools.agent_manager.skills._target_is_direct_link",
                side_effect=inject_unknown_and_fail,
            ):
                result = apply_adoption(plan, {item.key: item for item in state.adapters})

            recoveries = list(
                copilot_root.parent.glob(".skills.lucas-skills-*.recovery")
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "adoption-failed")
            self.assertTrue(copilot_root.is_symlink())
            self.assertEqual(copilot_root.resolve(), (repo / "skills").resolve())
            self.assertEqual(len(recoveries), 1)
            self.assertEqual(
                (recoveries[0] / "local-note.txt").read_text(encoding="utf-8"),
                "preserve me\n",
            )
            self.assertIn(str(recoveries[0]), result.results[0].message)
            self.assertEqual(
                list(copilot_root.parent.glob(".skills.lucas-skills-*.old")),
                [],
            )

    def test_container_restore_does_not_overwrite_competitor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            real_verify = importlib.import_module(
                "tools.agent_manager.skills"
            )._target_is_direct_link
            real_symlink = os.symlink
            injected = False

            def inject_unknown_and_fail(target: Path, source: Path) -> bool:
                nonlocal injected
                if target == copilot_root / "docx" and not injected:
                    injected = True
                    (copilot_root / "local-note.txt").write_text(
                        "preserve me\n",
                        encoding="utf-8",
                    )
                    return False
                return real_verify(target, source)

            def occupy_restore_path(source, destination, *args, **kwargs):
                if Path(destination) == copilot_root:
                    copilot_root.write_text("competitor\n", encoding="utf-8")
                return real_symlink(source, destination, *args, **kwargs)

            with (
                patch(
                    "tools.agent_manager.skills._target_is_direct_link",
                    side_effect=inject_unknown_and_fail,
                ),
                patch(
                    "tools.agent_manager.skills.os.symlink",
                    side_effect=occupy_restore_path,
                ),
            ):
                result = apply_adoption(plan, {item.key: item for item in state.adapters})

            recoveries = list(
                copilot_root.parent.glob(".skills.lucas-skills-*.recovery")
            )
            backups = list(copilot_root.parent.glob(".skills.lucas-skills-*.old"))
            self.assertFalse(result.ok)
            self.assertTrue(copilot_root.is_file())
            self.assertEqual(
                copilot_root.read_text(encoding="utf-8"),
                "competitor\n",
            )
            self.assertEqual(len(recoveries), 1)
            self.assertEqual(len(backups), 1)
            self.assertTrue(backups[0].is_symlink())
            self.assertEqual(
                (recoveries[0] / "local-note.txt").read_text(encoding="utf-8"),
                "preserve me\n",
            )
            self.assertIn(str(copilot_root), result.results[0].message)
            self.assertIn(str(recoveries[0]), result.results[0].message)
            self.assertIn(str(backups[0]), result.results[0].message)

    def test_snapshot_write_failure_leaves_legacy_link_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            cc_skill = home / ".cc-switch/skills/docx"
            cc_skill.parent.mkdir(parents=True)
            cc_skill.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(cc_skill)
            state = build_test_state(repo, home, installed_commands={"claude": "/bin/claude"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")

            with patch.object(Path, "write_text", side_effect=OSError("snapshot failed")):
                with self.assertRaisesRegex(OSError, "snapshot failed"):
                    apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertTrue(target.is_symlink())
            self.assertEqual(Path(os.readlink(target)), cc_skill)


class SetOperationTests(unittest.TestCase):

    def test_plan_is_read_only_and_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            home = root / "home"
            write_skill(repo, "docx", "docx")
            scan = scan_repository(repo)
            adapters = build_adapters(home)
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan, adapters, surfaces)

            plan = plan_set(state, ["docx"], ["claude"], True)
            repeated = plan_set(
                state,
                ["docx", "docx"],
                ["claude", "claude"],
                True,
            )
            target = home / ".claude/skills/docx"
            self.assertFalse(os.path.lexists(target))
            self.assertEqual(len(repeated.changes), 1)

            result = apply_plan(plan, {item.key: item for item in adapters})
            self.assertTrue(result.ok)
            self.assertEqual(target.resolve(), (repo / "skills/docx").resolve())

            repeated_apply = apply_plan(plan, {item.key: item for item in adapters})
            self.assertTrue(repeated_apply.ok)
            self.assertEqual(repeated_apply.results[0].code, "no-op")

            second = apply_plan(
                plan_set(
                    scan_managed_state(scan, adapters, surfaces),
                    ["docx"],
                    ["claude"],
                    True,
                ),
                {item.key: item for item in adapters},
            )
            self.assertTrue(second.ok)
            self.assertEqual(second.results[0].code, "no-op")

    def test_apply_refuses_when_path_changed_after_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            home = root / "home"
            write_skill(repo, "pdf", "pdf")
            scan = scan_repository(repo)
            adapters = build_adapters(home)
            surfaces = detect_surfaces(
                which=lambda command: "/bin/codex" if command == "codex" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan, adapters, surfaces)
            plan = plan_set(state, ["pdf"], ["codex"], True)
            target = home / ".codex/skills/pdf"
            target.parent.mkdir(parents=True)
            target.mkdir()

            result = apply_plan(plan, {item.key: item for item in adapters})

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertTrue(target.is_dir())

    def test_unavailable_surface_is_a_successful_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            adapters = build_adapters(home)
            surfaces = detect_surfaces(
                which=lambda _: None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)

            result = apply_plan(
                plan_set(state, ["pdf"], ["claude"], True),
                {item.key: item for item in adapters},
            )

            self.assertTrue(result.ok)
            self.assertTrue(
                any(item.code == "unavailable" and item.ok for item in result.results)
            )

    def test_batch_reports_partial_failure_and_keeps_safe_successes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            occupied = home / ".claude/skills/pdf"
            occupied.mkdir(parents=True)
            adapters = build_adapters(home)
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)

            result = apply_plan(
                plan_set(state, ["docx", "pdf"], ["claude"], True),
                {item.key: item for item in adapters},
            )

            self.assertFalse(result.ok)
            self.assertTrue((home / ".claude/skills/docx").is_symlink())
            self.assertTrue(occupied.is_dir())
            self.assertEqual({item.code for item in result.results}, {"applied", "blocked"})

    def test_disable_removes_direct_and_recognized_legacy_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            direct = by_key["claude-shared"].root / "docx"
            direct.parent.mkdir(parents=True)
            direct.symlink_to(skill)
            legacy_source = home / ".cc-switch/skills/docx"
            legacy_source.parent.mkdir(parents=True)
            legacy_source.symlink_to(skill)
            legacy = by_key["codex-shared"].root / "docx"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(legacy_source)
            surfaces = detect_surfaces(
                which=lambda command: f"/bin/{command}" if command in {"claude", "codex"} else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)

            result = apply_plan(
                plan_set(state, ["docx"], ["claude", "codex"], False),
                by_key,
            )

            self.assertTrue(result.ok)
            self.assertEqual([item.code for item in result.results], ["applied", "applied"])
            self.assertFalse(os.path.lexists(direct))
            self.assertFalse(os.path.lexists(legacy))
            self.assertTrue(legacy_source.is_symlink())

    def test_disable_requires_adopt_for_copilot_root_directory_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            copilot_root = by_key["copilot-shared"].root
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(
                repo / "skills",
                target_is_directory=True,
            )
            surfaces = detect_surfaces(
                which=lambda command: "/bin/copilot" if command == "copilot" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)

            plan = plan_set(state, ["docx"], ["copilot"], False)
            result = apply_plan(plan, by_key)

            self.assertEqual(plan.changes[0].action, "requires-adopt")
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "requires-adopt")
            self.assertTrue(copilot_root.is_symlink())
            self.assertEqual(copilot_root.resolve(), (repo / "skills").resolve())

    def test_disable_preserves_directory_and_external_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            directory = by_key["claude-shared"].root / "docx"
            directory.mkdir(parents=True)
            external_source = root / "external/docx"
            external_source.mkdir(parents=True)
            external = by_key["codex-shared"].root / "docx"
            external.parent.mkdir(parents=True)
            external.symlink_to(external_source)
            plan = ChangePlan(
                (
                    PlannedChange(
                        "remove",
                        "docx",
                        "claude-shared",
                        skill,
                        directory,
                        PathSnapshot("directory"),
                        "disable managed skill",
                    ),
                    PlannedChange(
                        "remove",
                        "docx",
                        "codex-shared",
                        skill,
                        external,
                        PathSnapshot("symlink", os.readlink(external)),
                        "disable managed skill",
                    ),
                ),
                scan_repository(repo),
            )

            result = apply_plan(plan, by_key)

            self.assertFalse(result.ok)
            self.assertEqual([item.code for item in result.results], ["target-conflict"] * 2)
            self.assertTrue(directory.is_dir())
            self.assertTrue(external.is_symlink())
            self.assertEqual(external.resolve(), external_source)

    def test_invalid_plan_items_fail_closed_and_batch_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)
            generated = plan_set(state, ["docx", "pdf"], ["claude"], True)
            docx, pdf = generated.changes
            external = root / "external"
            external.mkdir()
            malformed = (
                replace(docx, action="unknown"),
                replace(docx, adapter_key="missing-adapter"),
                replace(docx, slug="Bad", target=by_key["claude-shared"].root / "Bad"),
                replace(docx, target=root / "outside/docx"),
                replace(docx, source=external),
            )
            real_snapshot = importlib.import_module(
                "tools.agent_manager.skills"
            ).snapshot_path

            def snapshot_with_error(path: Path):
                if path == pdf.target:
                    raise OSError("deterministic path failure")
                return real_snapshot(path)

            with patch(
                "tools.agent_manager.skills.snapshot_path",
                side_effect=snapshot_with_error,
            ):
                result = apply_plan(
                    ChangePlan(malformed + (pdf, docx), generated.repository),
                    by_key,
                )

            self.assertFalse(result.ok)
            self.assertEqual(
                [item.code for item in result.results],
                ["invalid-plan"] * 5 + ["verification-failed", "applied"],
            )
            self.assertTrue(docx.target.is_symlink())
            self.assertFalse(os.path.lexists(pdf.target))

    def test_apply_rejects_source_removed_after_planning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            create_source = write_skill(repo, "docx", "docx")
            remove_source = write_skill(repo, "pdf", "pdf")
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            remove_target = by_key["claude-shared"].root / "pdf"
            remove_target.parent.mkdir(parents=True)
            remove_target.symlink_to(remove_source)
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)
            create_plan = plan_set(state, ["docx"], ["claude"], True)
            remove_plan = plan_set(state, ["pdf"], ["claude"], False)
            (create_source / "SKILL.md").unlink()
            (remove_source / "SKILL.md").unlink()

            create_result = apply_plan(create_plan, by_key)
            remove_result = apply_plan(remove_plan, by_key)

            self.assertEqual(create_result.results[0].code, "state-changed")
            self.assertEqual(remove_result.results[0].code, "state-changed")
            self.assertFalse(os.path.lexists(create_plan.changes[0].target))
            self.assertTrue(remove_target.is_symlink())

    def test_create_race_never_overwrites_competitor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            external = root / "external/docx"
            external.mkdir(parents=True)
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            plan = plan_set(
                scan_managed_state(scan_repository(repo), adapters, surfaces),
                ["docx"],
                ["claude"],
                True,
            )
            target = plan.changes[0].target
            real_symlink = os.symlink
            injected = False

            def racing_symlink(
                source,
                destination,
                target_is_directory=False,
                *,
                dir_fd=None,
            ):
                nonlocal injected
                if not injected:
                    injected = True
                    real_symlink(external, target)
                return real_symlink(
                    source,
                    destination,
                    target_is_directory,
                    dir_fd=dir_fd,
                )

            with patch("tools.agent_manager.skills.os.symlink", side_effect=racing_symlink):
                result = apply_plan(plan, by_key)

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), external)

    def test_remove_race_preserves_competitor_and_isolated_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            external = root / "external/docx"
            external.mkdir(parents=True)
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            target = by_key["claude-shared"].root / "docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(skill)
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            plan = plan_set(
                scan_managed_state(scan_repository(repo), adapters, surfaces),
                ["docx"],
                ["claude"],
                False,
            )
            real_rename, real_replace, real_symlink = os.rename, os.replace, os.symlink
            injected = False

            def race(delegate, source, destination, *args, **kwargs):
                nonlocal injected
                if injected:
                    return delegate(source, destination, *args, **kwargs)
                injected = True
                src_dir_fd = kwargs.get("src_dir_fd")
                os.unlink(source, dir_fd=src_dir_fd)
                real_symlink(external, source, dir_fd=src_dir_fd)
                result = delegate(source, destination, *args, **kwargs)
                fd = os.open(
                    source,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                    dir_fd=src_dir_fd,
                )
                os.close(fd)
                return result

            with (
                patch(
                    "tools.agent_manager.skills.os.rename",
                    side_effect=lambda src, dst, *args, **kwargs: race(
                        real_rename, src, dst, *args, **kwargs
                    ),
                ),
                patch(
                    "tools.agent_manager.skills.os.replace",
                    side_effect=lambda src, dst, *args, **kwargs: race(
                        real_replace, src, dst, *args, **kwargs
                    ),
                ),
            ):
                result = apply_plan(plan, by_key)

            isolated = list(target.parent.glob(".docx.lucas-skills-*.old"))
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertTrue(target.is_file())
            self.assertEqual(len(isolated), 1)
            self.assertTrue(isolated[0].is_symlink())
            self.assertEqual(isolated[0].resolve(), external)

    def test_create_rejects_parent_replaced_with_external_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            external = root / "external"
            external.mkdir()
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            plan = plan_set(
                scan_managed_state(scan_repository(repo), adapters, surfaces),
                ["docx"],
                ["claude"],
                True,
            )
            adapter_root = by_key["claude-shared"].root
            moved_root = root / "moved-skills"
            real_mkdir = Path.mkdir
            injected = False

            def racing_mkdir(path: Path, *args, **kwargs):
                nonlocal injected
                result = real_mkdir(path, *args, **kwargs)
                if path == adapter_root and not injected:
                    injected = True
                    path.rename(moved_root)
                    path.symlink_to(external, target_is_directory=True)
                return result

            with patch.object(Path, "mkdir", autospec=True, side_effect=racing_mkdir):
                result = apply_plan(plan, by_key)

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertFalse(os.path.lexists(external / "docx"))

    def test_apply_rejects_repository_skill_symlinked_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            external_skill = write_skill(root / "external-repo", "docx", "docx")
            (repo / "skills").mkdir(parents=True)
            (repo / "skills/docx").symlink_to(
                external_skill,
                target_is_directory=True,
            )
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            plan = plan_set(
                scan_managed_state(scan_repository(repo), adapters, surfaces),
                ["docx"],
                ["claude"],
                True,
            )

            result = apply_plan(plan, by_key)

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "invalid-plan")
            self.assertFalse(os.path.lexists(plan.changes[0].target))

    def test_create_removes_its_link_if_source_disappears_during_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            source = write_skill(repo, "docx", "docx")
            moved_source = root / "moved-docx"
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            plan = plan_set(
                scan_managed_state(scan_repository(repo), adapters, surfaces),
                ["docx"],
                ["claude"],
                True,
            )
            real_symlink = os.symlink
            injected = False

            def disappearing_source(
                link_source,
                destination,
                target_is_directory=False,
                *,
                dir_fd=None,
            ):
                nonlocal injected
                result = real_symlink(
                    link_source,
                    destination,
                    target_is_directory,
                    dir_fd=dir_fd,
                )
                if not injected:
                    injected = True
                    source.rename(moved_source)
                return result

            with patch(
                "tools.agent_manager.skills.os.symlink",
                side_effect=disappearing_source,
            ):
                result = apply_plan(plan, by_key)

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertFalse(os.path.lexists(plan.changes[0].target))


class UmbrellaParserTests(unittest.TestCase):
    def assert_parse_exit(self, argv: list[str], expected: int) -> None:
        with (
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as caught,
        ):
            main(argv)
        self.assertEqual(caught.exception.code, expected)

    def test_help_contract_covers_root_and_every_command_level(self) -> None:
        for argv in (
            ["--help"],
            ["status", "--help"],
            ["doctor", "--help"],
            ["serve", "--help"],
            ["skills", "--help"],
            ["skills", "status", "--help"],
            ["skills", "set", "--help"],
            ["skills", "adopt", "--help"],
            ["instructions", "--help"],
            ["instructions", "status", "--help"],
            ["instructions", "set", "--help"],
            ["instructions", "adopt", "--help"],
        ):
            with self.subTest(argv=argv):
                self.assert_parse_exit(argv, 0)

    def test_old_flat_skill_commands_are_parser_errors(self) -> None:
        for argv in (
            ["set", "docx", "--tool", "claude", "--on"],
            ["adopt"],
        ):
            with self.subTest(argv=argv):
                self.assert_parse_exit(argv, 2)

    def test_replace_existing_is_exclusive_to_instructions_adopt(self) -> None:
        invalid = (
            ["status", "--replace-existing"],
            ["doctor", "--replace-existing"],
            ["skills", "status", "--replace-existing"],
            ["skills", "set", "docx", "--tool", "claude", "--on", "--replace-existing"],
            ["skills", "adopt", "--replace-existing"],
            ["instructions", "status", "--replace-existing"],
            ["instructions", "set", "--target", "codex", "--on", "--replace-existing"],
        )
        for argv in invalid:
            with self.subTest(argv=argv):
                self.assert_parse_exit(argv, 2)

    def test_instruction_apply_requires_one_valid_reviewed_fingerprint(self) -> None:
        digest = "a" * 64
        for argv in (
            ["instructions", "set", "--target", "codex", "--on", "--apply"],
            ["instructions", "adopt", "--apply"],
            ["instructions", "set", "--target", "codex", "--on", "--expect-fingerprint", digest],
            ["instructions", "adopt", "--expect-fingerprint", digest],
            ["instructions", "adopt", "--apply", "--expect-fingerprint", "A" * 64],
            ["instructions", "adopt", "--apply", "--expect-fingerprint", "a" * 63],
            ["skills", "adopt", "--expect-fingerprint", digest],
        ):
            with self.subTest(argv=argv):
                self.assert_parse_exit(argv, 2)

class AggregateCliContractTests(unittest.TestCase):
    def invoke(self, argv: list[str], repo: Path, home: Path) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        code = main(
            argv,
            home=home,
            repo_root=repo,
            stdout=output,
            which=lambda _: None,
            applications=home.parent / "Applications",
        )
        return code, json.loads(output.getvalue())

    def test_status_json_has_exact_aggregate_schema_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")

            code, payload = self.invoke(["status", "--json"], repo, home)

            self.assertEqual(code, 0)
            self.assertEqual(
                set(payload),
                {
                    "mode", "ok", "code", "message", "repo_root", "skills",
                    "instructions", "surfaces", "summary", "scanned_at",
                },
            )
            self.assertEqual(
                set(payload["summary"]),
                {
                    "skills_enabled", "skills_total", "instructions_enabled",
                    "instructions_total", "conflicts", "issues",
                },
            )
            self.assertEqual(
                set(payload["skills"]),
                {"records", "adapters", "targets", "issues"},
            )
            self.assertEqual(
                set(payload["instructions"]),
                {"source", "source_sha256", "source_text", "targets", "manual_surfaces", "issues"},
            )
            self.assertEqual(payload["summary"]["skills_total"], 1)
            self.assertEqual(payload["summary"]["instructions_total"], 5)
            self.assertRegex(payload["scanned_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$")

    def test_domain_statuses_keep_the_common_envelope_and_one_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            common = {"mode", "ok", "code", "message", "repo_root", "surfaces", "summary", "scanned_at"}

            skills_code, skills = self.invoke(["skills", "status", "--json"], repo, home)
            instructions_code, instructions = self.invoke(
                ["instructions", "status", "--json"], repo, home
            )

            self.assertEqual((skills_code, instructions_code), (0, 0))
            self.assertEqual(set(skills), common | {"skills"})
            self.assertEqual(set(skills["skills"]), {"records", "adapters", "targets", "issues"})
            self.assertEqual(set(instructions), common | {"instructions"})
            self.assertEqual(
                set(instructions["instructions"]),
                {"source", "source_sha256", "source_text", "targets", "manual_surfaces", "issues"},
            )

    def test_instruction_missing_and_matching_copy_are_healthy_but_failures_are_not(self) -> None:
        for shape, expected in (("missing", 0), ("matching-copy", 0), ("conflict", 1), ("broken", 1)):
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                repo, home = root / "repo", root / "home"
                write_skill(repo, "docx", "docx")
                target = home / ".codex/AGENTS.md"
                if shape != "missing":
                    target.parent.mkdir(parents=True)
                if shape == "matching-copy":
                    target.write_bytes((repo / "AGENTS.md").read_bytes())
                elif shape == "conflict":
                    target.write_text("different\n", encoding="utf-8")
                elif shape == "broken":
                    target.symlink_to(target.parent / "absent.md")

                code, payload = self.invoke(["status", "--json"], repo, home)

                self.assertEqual(code, expected)
                self.assertEqual(payload["ok"], expected == 0)

    def test_invalid_instruction_source_fails_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            (repo / "AGENTS.md").unlink()

            code, payload = self.invoke(["status", "--json"], repo, home)

            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertGreater(payload["summary"]["issues"], 0)

    def test_instruction_planning_errors_keep_the_review_schema(self) -> None:
        cases = (
            ("set", "invalid-source", False),
            ("adopt", "invalid-source", False),
            ("set", "state-changed", False),
            ("adopt", "state-changed", True),
        )
        for command, error, apply in cases:
            with self.subTest(command=command, error=error, apply=apply), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                repo, home = root / "repo", root / "home"
                write_skill(repo, "docx", "docx")
                (home / ".codex").mkdir(parents=True)
                argv = ["instructions", command]
                if command == "set":
                    argv.extend(["--target", "codex", "--on"])
                if apply:
                    argv.extend(["--apply", "--expect-fingerprint", "a" * 64])
                argv.append("--json")

                if error == "invalid-source":
                    (repo / "AGENTS.md").unlink()
                    code, payload = self.invoke(argv, repo, home)
                else:
                    with patch(
                        f"tools.agent_manager.cli.plan_instruction_{'set' if command == 'set' else 'adoption'}",
                        side_effect=InstructionPlanError(
                            "state-changed",
                            "planning state changed",
                        ),
                    ):
                        code, payload = self.invoke(argv, repo, home)

                self.assertEqual(code, 1)
                self.assertEqual(payload["changes"], [])
                self.assertIsNone(payload["fingerprint"])
                self.assertIsNone(payload["snapshot_path"])
                if apply:
                    self.assertEqual(payload["results"], [])
                else:
                    self.assertNotIn("results", payload)

    def test_doctor_reports_prepared_instruction_snapshot_without_recovery_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            snapshot = home / ".local/state/lucas-agent-manager/snapshots" / f"instructions-{'a' * 64}.json"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(
                json.dumps({"phase": "prepared", "fingerprint": "a" * 64, "targets": []}),
                encoding="utf-8",
            )
            before = snapshot.read_bytes()

            code, payload = self.invoke(["doctor", "--json"], repo, home)

            self.assertEqual(code, 1)
            self.assertEqual(payload["code"], "incomplete-transaction")
            self.assertIn("inventory", payload)
            self.assertEqual(snapshot.read_bytes(), before)


class CliTests(unittest.TestCase):
    def test_doctor_success_has_stable_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["doctor", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda _: None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertIsNone(payload["code"])
            self.assertEqual(payload["message"], "")
            self.assertEqual(
                [item["slug"] for item in payload["skills"]["records"]],
                ["docx"],
            )
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["skills"]["targets"]), 4)
            self.assertEqual(payload["inventory"], [])
            self.assertEqual(payload["skills"]["issues"], [])

    def test_adopt_preview_has_stable_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["skills", "adopt", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda _: None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertIsNone(payload["code"])
            self.assertEqual(payload["message"], "")
            self.assertEqual(payload["skills"]["issues"], [])
            self.assertEqual(
                set(payload["changes"]),
                {"link_changes", "container_changes", "snapshot_path"},
            )
            self.assertEqual(payload["changes"]["link_changes"], [])
            self.assertEqual(payload["changes"]["container_changes"], [])
            self.assertIsNotNone(payload["changes"]["snapshot_path"])
            self.assertEqual(payload["results"], [])

    def test_adopt_apply_writes_snapshot_under_aggregate_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            legacy = home / ".cc-switch/skills/docx"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(legacy)
            output = io.StringIO()

            code = main(
                ["skills", "adopt", "--apply", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            snapshot = Path(payload["changes"]["snapshot_path"])
            self.assertEqual(code, 0)
            self.assertEqual(
                snapshot.parent,
                home / ".local/state/lucas-agent-manager/snapshots",
            )
            self.assertTrue(snapshot.is_file())
            self.assertFalse((home / ".local/state/lucas-skills-manager").exists())

    def test_invalid_repository_blocks_set_preview_and_apply_without_writes(self) -> None:
        for apply in (False, True):
            with self.subTest(apply=apply), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                repo, home = root / "repo", root / "home"
                write_skill(repo, "docx", "docx")
                invalid = repo / "skills/invalid"
                invalid.mkdir()
                (invalid / "SKILL.md").write_text("# invalid\n", encoding="utf-8")
                output = io.StringIO()
                argv = ["skills", "set", "--all", "--tool", "claude", "--on"]
                if apply:
                    argv.append("--apply")
                argv.append("--json")

                code = main(
                    argv,
                    home=home,
                    repo_root=repo,
                    stdout=output,
                    which=lambda command: "/bin/claude" if command == "claude" else None,
                    applications=root / "Applications",
                )

                payload = json.loads(output.getvalue())
                self.assertEqual(code, 1)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["code"], "invalid-skill")
                self.assertEqual(
                    [item["slug"] for item in payload["skills"]["records"]],
                    ["docx"],
                )
                self.assertEqual(
                    [issue["code"] for issue in payload["skills"]["issues"]],
                    ["invalid-frontmatter"],
                )
                self.assertIn("invalid-frontmatter", payload["message"])
                self.assertIn(str(invalid / "SKILL.md"), payload["message"])
                self.assertEqual(payload["changes"], [])
                self.assertEqual(payload["results"], [])
                self.assertFalse(os.path.lexists(home / ".claude/skills/docx"))

    def test_invalid_repository_text_error_lists_issue_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            invalid = repo / "skills/invalid"
            invalid.mkdir()
            (invalid / "SKILL.md").write_text("# invalid\n", encoding="utf-8")
            output = io.StringIO()

            code = main(
                ["skills", "set", "--all", "--tool", "claude", "--on"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            self.assertEqual(code, 1)
            self.assertIn("invalid-frontmatter", output.getvalue())
            self.assertIn(str(invalid / "SKILL.md"), output.getvalue())

    def test_invalid_repository_blocks_adopt_preview_and_apply_without_writes(self) -> None:
        for apply in (False, True):
            with self.subTest(apply=apply), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                repo, home = root / "repo", root / "home"
                skill = write_skill(repo, "docx", "docx")
                invalid = repo / "skills/invalid"
                invalid.mkdir()
                (invalid / "SKILL.md").write_text("# invalid\n", encoding="utf-8")
                legacy = home / ".cc-switch/skills/docx"
                legacy.parent.mkdir(parents=True)
                legacy.symlink_to(skill)
                target = home / ".claude/skills/docx"
                target.parent.mkdir(parents=True)
                target.symlink_to(legacy)
                output = io.StringIO()
                argv = ["skills", "adopt"]
                if apply:
                    argv.append("--apply")
                argv.append("--json")

                code = main(
                    argv,
                    home=home,
                    repo_root=repo,
                    stdout=output,
                    which=lambda command: "/bin/claude" if command == "claude" else None,
                    applications=root / "Applications",
                )

                payload = json.loads(output.getvalue())
                self.assertEqual(code, 1)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["code"], "invalid-skill")
                self.assertEqual(
                    [issue["code"] for issue in payload["skills"]["issues"]],
                    ["invalid-frontmatter"],
                )
                self.assertEqual(payload["changes"]["link_changes"], [])
                self.assertEqual(payload["changes"]["container_changes"], [])
                self.assertEqual(payload["results"], [])
                self.assertEqual(Path(os.readlink(target)), legacy)
                self.assertFalse(
                    (home / ".local/state/lucas-skills-manager").exists()
                )

    def test_status_failure_keeps_status_fields_and_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            invalid = repo / "skills/invalid"
            invalid.mkdir()
            (invalid / "SKILL.md").write_text("# invalid\n", encoding="utf-8")
            output = io.StringIO()

            code = main(
                ["status", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda _: None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(
                [item["slug"] for item in payload["skills"]["records"]],
                ["docx"],
            )
            self.assertEqual(len(payload["skills"]["adapters"]), 4)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["skills"]["targets"]), 4)
            self.assertEqual(
                [issue["code"] for issue in payload["skills"]["issues"]],
                ["invalid-frontmatter"],
            )

    def test_adopt_error_keeps_state_and_change_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            with patch(
                "tools.agent_manager.cli.plan_adoption",
                side_effect=OSError("failed"),
            ):
                code = main(
                    ["skills", "adopt", "--json"],
                    home=home,
                    repo_root=repo,
                    stdout=output,
                    which=lambda _: None,
                    applications=root / "Applications",
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["code"], "adoption-failed")
            self.assertEqual(
                [item["slug"] for item in payload["skills"]["records"]],
                ["docx"],
            )
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["skills"]["targets"]), 4)
            self.assertEqual(payload["skills"]["issues"], [])
            self.assertEqual(payload["changes"]["link_changes"], [])
            self.assertEqual(payload["changes"]["container_changes"], [])
            self.assertEqual(payload["results"], [])

    def test_skill_adopt_post_rescan_failure_preserves_execution_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            legacy = home / ".cc-switch/skills/docx"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(legacy)
            which = lambda command: "/bin/claude" if command == "claude" else None

            initial_state = agent_manager_cli.build_agent_state(
                repo,
                home,
                which,
                root / "Applications",
            )
            plan = plan_adoption(
                initial_state.skills,
                home / ".local/state/lucas-skills-manager",
            )
            expected_changes = agent_manager_cli.to_jsonable(
                {
                    "link_changes": plan.link_changes,
                    "container_changes": plan.container_changes,
                    "snapshot_path": plan.snapshot_path,
                }
            )
            result = BatchResult(
                True,
                (
                    OperationResult(
                        True,
                        "applied",
                        "docx",
                        "claude-shared",
                        target,
                        "adopted link",
                    ),
                ),
            )
            output = io.StringIO()
            with (
                patch(
                    "tools.agent_manager.cli.build_agent_state",
                    side_effect=[initial_state, OSError("post scan failed")],
                ),
                patch(
                    "tools.agent_manager.cli.apply_adoption",
                    return_value=result,
                ) as apply_mock,
                patch(
                    "tools.agent_manager.cli.plan_adoption",
                    return_value=plan,
                ),
            ):
                code = main(
                    ["skills", "adopt", "--apply", "--json"],
                    home=home,
                    repo_root=repo,
                    stdout=output,
                    which=which,
                    applications=root / "Applications",
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            apply_mock.assert_called_once()
            self.assertEqual(payload["changes"], expected_changes)
            self.assertEqual(payload["results"][0]["code"], "applied")
            self.assertEqual(payload["code"], "post-apply-verification-failed")
            self.assertIn("apply completed", payload["message"])
            self.assertIn("post scan failed", payload["message"])

    def test_status_text_counts_legacy_as_enabled_without_skill_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx", "do not print this")
            legacy = home / ".cc-switch/skills/docx"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(legacy)
            output = io.StringIO()

            code = main(
                ["status"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            text = output.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("Skills: 1/1", text)
            self.assertIn("Instructions: 0/5", text)
            self.assertIn("Conflicts: 0", text)
            self.assertIn("Next:", text)
            self.assertNotIn("do not print this", text)

    def test_doctor_parse_error_is_not_reported_as_invalid_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text("[plugins]\ninvalid =\n", encoding="utf-8")
            output = io.StringIO()

            code = main(
                ["doctor", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda _: None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(payload["mode"], "doctor")
            self.assertEqual(payload["code"], "internal-error")
            self.assertEqual(
                [item["slug"] for item in payload["skills"]["records"]],
                ["docx"],
            )
            self.assertEqual(len(payload["skills"]["adapters"]), 4)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["skills"]["targets"]), 4)
            self.assertEqual(payload["inventory"], [])
            self.assertEqual(payload["skills"]["issues"], [])

    def test_set_error_uses_plan_mode_in_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["skills", "set", "missing", "--tool", "claude", "--on", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["code"], "invalid-skill")
            self.assertEqual(
                [item["slug"] for item in payload["skills"]["records"]],
                ["docx"],
            )
            self.assertEqual(len(payload["skills"]["adapters"]), 4)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["skills"]["targets"]), 4)
            self.assertEqual(payload["skills"]["issues"], [])
            self.assertEqual(payload["changes"], [])
            self.assertEqual(payload["results"], [])

    def test_set_without_apply_only_prints_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["skills", "set", "docx", "--tool", "claude", "--on", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["mode"], "plan")
            self.assertIsNone(payload["code"])
            self.assertEqual(payload["skills"]["issues"], [])
            self.assertEqual(len(payload["changes"]), 1)
            self.assertEqual(payload["results"], [])
            self.assertFalse(os.path.lexists(home / ".claude/skills/docx"))

    def test_set_preview_returns_target_conflict_for_blocked_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            occupied = home / ".claude/skills/docx"
            occupied.mkdir(parents=True)
            output = io.StringIO()

            code = main(
                ["skills", "set", "docx", "--tool", "claude", "--on", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "target-conflict")
            self.assertEqual(payload["changes"][0]["action"], "blocked")
            self.assertEqual(payload["changes"][0]["target"], str(occupied))
            self.assertTrue(occupied.is_dir())

    def test_set_preview_returns_requires_adopt_for_legacy_directory_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            target_root = home / ".copilot/skills"
            target_root.parent.mkdir(parents=True)
            target_root.symlink_to(repo / "skills")
            output = io.StringIO()

            code = main(
                ["skills", "set", "docx", "--tool", "copilot", "--off", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/copilot" if command == "copilot" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "requires-adopt")
            self.assertEqual(payload["changes"][0]["action"], "requires-adopt")
            self.assertTrue(target_root.is_symlink())

    def test_status_json_contains_tools_surfaces_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            output = io.StringIO()

            code = main(
                ["status", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda _: None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["skills"]["records"][0]["slug"], "pdf")
            self.assertEqual(len(payload["skills"]["adapters"]), 4)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["instructions"]["targets"]), 5)
            self.assertEqual(payload["skills"]["issues"], [])

    def test_antigravity_cli_set_and_doctor_plugin_issue_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            apps = root / "Applications"
            (apps / "Antigravity.app").mkdir(parents=True)

            # Enable via CLI targeting antigravity
            out_set = io.StringIO()
            set_code = main(
                ["skills", "set", "docx", "--tool", "antigravity", "--on", "--apply", "--json"],
                home=home,
                repo_root=repo,
                stdout=out_set,
                which=lambda _: None,
                applications=apps,
            )
            set_payload = json.loads(out_set.getvalue())
            self.assertEqual(set_code, 0)
            self.assertTrue(set_payload["ok"])
            link = home / ".gemini/config/skills/docx"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), (repo / "skills/docx").resolve())

            # Corrupt Antigravity plugin manifest surfaces through doctor
            bad_plugin = home / ".gemini/config/plugins/broken"
            write_skill(bad_plugin, "x", "x")
            (bad_plugin / "plugin.json").write_text("{bad\n", encoding="utf-8")
            out_doctor = io.StringIO()
            doctor_code = main(
                ["doctor", "--json"],
                home=home,
                repo_root=repo,
                stdout=out_doctor,
                which=lambda _: None,
                applications=apps,
            )
            doctor_payload = json.loads(out_doctor.getvalue())
            self.assertEqual(doctor_code, 1)
            self.assertFalse(doctor_payload["ok"])
            self.assertEqual(doctor_payload["code"], "plugin-manifest-invalid")

    def test_batch_partial_failure_returns_one_with_per_item_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            occupied = home / ".claude/skills/pdf"
            occupied.mkdir(parents=True)
            output = io.StringIO()

            code = main(
                ["skills", "set", "--all", "--tool", "claude", "--on", "--apply", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "partial-failure")
            self.assertEqual(len(payload["changes"]), 2)
            self.assertEqual(payload["skills"]["issues"], [])
            self.assertEqual(
                {item["code"] for item in payload["results"]},
                {"applied", "blocked"},
            )
            self.assertTrue((home / ".claude/skills/docx").is_symlink())
            self.assertTrue(occupied.is_dir())
