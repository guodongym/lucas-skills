from __future__ import annotations

import io
import http.client
import importlib
import json
import os
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tools.skill_manager.cli import create_server, main
from tools.skill_manager.core import (
    _enabled_codex_plugin_sources,
    apply_adoption,
    apply_plan,
    ChangePlan,
    LinkState,
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


@contextmanager
def running_http_server(
    repo: Path,
    home: Path,
    applications: Path,
    which=lambda _: None,
):
    server = create_server(repo, home, "test-token", applications, which)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield server, thread, f"http://{host}:{port}"
    finally:
        thread.join(timeout=0.05)
        if thread.is_alive():
            server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class PackageLayoutTests(unittest.TestCase):
    def test_default_repo_root_points_to_checkout(self) -> None:
        from tools.skill_manager import cli

        self.assertEqual(cli.DEFAULT_REPO_ROOT, Path(__file__).resolve().parents[1])


class ReadmeTests(unittest.TestCase):
    def test_documents_on_demand_service_and_adoption_gate(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        required = (
            "uv run skill-manager status",
            "uv run skill-manager doctor",
            "uv run skill-manager serve --open",
            "uv run skill-manager adopt --apply --json",
            "uv run upstream-sync check",
            "uv run upstream-sync sync",
        )
        for text in (*required, "uv --version", "服务不需要后台常驻"):
            self.assertIn(text, readme)
        for path in ("pyproject.toml", "uv.lock", "tools/"):
            self.assertIn(path, readme)
        for obsolete in ("pip install pyyaml", "python " "vendor.py"):
            self.assertNotIn(obsolete, readme)

    def test_documents_json_review_and_post_integration_acceptance(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        commands = (
            "uv run skill-manager status --json",
            "uv run skill-manager doctor --json",
            "uv run skill-manager set docx --tool codex --on --json",
            "uv run skill-manager set docx --tool codex --on --apply --json",
            "uv run skill-manager adopt --json",
            "uv run skill-manager adopt --apply --json",
        )
        for command in commands:
            self.assertIn(command, readme)
        for text in (
            "文本输出仅提供摘要",
            "完整字段",
            "集成后验收门",
            "preview / cancel / port shutdown",
        ):
            self.assertIn(text, readme)
        self.assertLess(
            readme.index("uv run skill-manager set docx --tool codex --on --json"),
            readme.index(
                "uv run skill-manager set docx --tool codex --on --apply --json"
            ),
        )
        self.assertLess(
            readme.index("uv run skill-manager adopt --json"),
            readme.index("uv run skill-manager adopt --apply --json"),
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
            write_skill(repo, "wps365", "wps365-skills")

            with patch.dict(os.environ, {"HOME": str(temp_home)}):
                self.assertEqual(Path.home(), temp_home)
                result = scan_repository(repo)

            self.assertEqual([skill.slug for skill in result.skills], ["wps365"])
            self.assertEqual(result.skills[0].name, "wps365-skills")
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


class WebPageTests(unittest.TestCase):
    @staticmethod
    def _tool_surface_rows(surfaces: list[dict[str, object]], tool: str) -> object:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        start = page.index("const TOOL_ADAPTERS")
        end = page.index("async function api")
        script = page[start:end] + (
            "\nconsole.log(JSON.stringify(toolSurfaceRows("
            f"{{surfaces: {json.dumps(surfaces)}}}, {json.dumps(tool)})));"
        )
        completed = subprocess.run(
            ["node", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_page_contains_required_views_and_no_external_assets(self) -> None:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        for element_id in (
            "summary",
            "managed-view",
            "inventory-view",
            "managed-table",
            "inventory-table",
            "rescan-button",
            "adopt-button",
            "shutdown-button",
            "managed-search",
            "managed-filter",
            "inventory-search",
            "inventory-filter",
            "enable-all-button",
            "disable-all-button",
        ):
            self.assertIn(f'id="{element_id}"', page)
        self.assertIn("__SKILL_MANAGER_TOKEN__", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("innerHTML", page)

    def test_page_wires_api_matrix_confirmation_and_feedback(self) -> None:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        for function_name in (
            "api",
            "loadStatus",
            "loadInventory",
            "setSkill",
            "setAll",
            "previewAdoption",
            "shutdown",
            "toolState",
            "renderSummary",
            "renderManaged",
            "renderInventory",
            "switchView",
            "showError",
            "confirmPlan",
        ):
            self.assertIn(f"function {function_name}(", page)
        for api_path in (
            '"/api/status"',
            '"/api/inventory"',
            '"/api/set"',
            '"/api/adopt"',
            '"/api/shutdown"',
        ):
            self.assertIn(api_path, page)
        self.assertIn('"X-Skill-Manager-Token"', page)
        self.assertIn("const TOOL_ADAPTERS", page)
        self.assertIn("apply: false", page)
        self.assertIn("apply: true", page)
        self.assertIn("confirmPlan(", page)
        self.assertIn("addEventListener", page)
        self.assertIn("Promise.all([loadStatus(), loadInventory()])", page)
        self.assertIn("正在", page)
        self.assertIn("操作失败", page)

    def test_page_confirmation_lists_complete_preview_even_when_not_ok(self) -> None:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        self.assertIn("function planItemText(item)", page)
        self.assertIn("const details = changes.map(planItemText);", page)
        self.assertIn("...(details.length ? details", page)
        self.assertNotIn("if (!preview.ok)", page)
        self.assertIn("document.getElementById(\"confirm-body\").textContent", page)

    def test_page_restores_row_controls_after_loading(self) -> None:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        self.assertIn("if (!busy && state.status) renderManaged(state.status);", page)

    def test_page_avoids_a_default_favicon_request(self) -> None:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="icon" href="data:,">', page)

    def test_page_resets_search_flex_basis_on_mobile(self) -> None:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        self.assertIn(".filters input { flex: 0 0 auto; width: 100%; }", page)

    def test_page_renders_shared_surface_when_only_desktop_is_installed(self) -> None:
        rows = self._tool_surface_rows(
            [
                {"key": "claude-desktop", "installed": True, "detector": "application"},
                {"key": "claude-cli", "installed": False, "detector": "command:claude"},
            ],
            "claude",
        )

        self.assertEqual(
            rows,
            [
                {"key": "claude-desktop", "label": "Desktop", "installed": True},
                {"key": "claude-cli", "label": "CLI", "installed": False},
            ],
        )

    def test_page_renders_shared_surface_when_only_cli_is_installed(self) -> None:
        rows = self._tool_surface_rows(
            [
                {"key": "codex-desktop", "installed": False, "detector": "application"},
                {"key": "codex-cli", "installed": True, "detector": "command:codex"},
            ],
            "codex",
        )

        self.assertEqual(
            rows,
            [
                {"key": "codex-desktop", "label": "Desktop", "installed": False},
                {"key": "codex-cli", "label": "CLI", "installed": True},
            ],
        )

    def test_page_displays_all_surface_and_inventory_fields_with_text_content(self) -> None:
        page = Path("tools/skill_manager/web/index.html").read_text(encoding="utf-8")
        for key in (
            "claude-desktop",
            "claude-cli",
            "codex-desktop",
            "codex-cli",
            "copilot-desktop",
            "copilot-cli",
            "antigravity-desktop",
            "antigravity-cli",
        ):
            self.assertIn(key, page)
        self.assertIn('id="surface-summary"', page)
        self.assertIn("toolSurfaceText(payload, tool)", page)
        self.assertIn("record.surfaces", page)
        self.assertIn("node.textContent = text", page)
        self.assertIn("#surface-summary", page)


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
                    "antigravity-desktop",
                    "antigravity-cli",
                },
            )
            self.assertEqual(adapters["claude-shared"].root, home / ".claude/skills")
            self.assertEqual(adapters["codex-shared"].root, home / ".codex/skills")
            self.assertEqual(adapters["copilot-shared"].root, home / ".copilot/skills")
            self.assertEqual(
                adapters["antigravity-desktop"].root,
                home / ".gemini/config/skills",
            )
            self.assertEqual(
                adapters["antigravity-cli"].root,
                home / ".gemini/antigravity-cli/plugins/lucas-skills/skills",
            )

    def test_detects_exact_surfaces_codex_fallback_and_agy_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            applications = Path(tmp) / "Applications"
            (applications / "Codex.app").mkdir(parents=True)
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

    def test_classifies_direct_legacy_conflict_broken_and_unavailable(self) -> None:
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

            conflict = by_key["antigravity-desktop"].root / "docx"
            conflict.mkdir(parents=True)

            broken = by_key["copilot-shared"].root / "docx"
            broken.parent.mkdir(parents=True)
            broken.symlink_to(home / "missing/docx")

            installed = {"claude-cli": "/bin/claude", "codex-cli": "/bin/codex"}
            surfaces = detect_surfaces(
                which=lambda command: installed.get(f"{command}-cli"),
                applications=root / "Applications",
            )
            state = scan_managed_state(scan, adapters, surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(statuses[("claude-shared", "docx")].state, LinkState.ENABLED)
            self.assertEqual(statuses[("codex-shared", "docx")].state, LinkState.LEGACY)
            self.assertEqual(
                statuses[("antigravity-desktop", "docx")].state,
                LinkState.UNAVAILABLE,
            )
            self.assertEqual(statuses[("copilot-shared", "docx")].state, LinkState.UNAVAILABLE)
            self.assertTrue(os.path.lexists(broken))


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
                [source.root for source in sources],
                [newest / "custom-skills"],
            )
            self.assertEqual([issue.code for issue in issues], ["plugin-manifest-missing"])
            self.assertEqual(issues[0].path, cache / "market/missing")

    def test_lists_managed_flat_markdown_and_antigravity_plugin_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            managed_skill = write_skill(repo, "docx", "docx")
            managed_link = home / ".codex/skills/docx"
            managed_link.parent.mkdir(parents=True)
            managed_link.symlink_to(managed_skill)
            flat = home / ".gemini/antigravity-cli/skills/flat.md"
            flat.parent.mkdir(parents=True)
            flat.write_text(
                "---\nname: flat\ndescription: flat markdown\n---\n",
                encoding="utf-8",
            )
            plugin_skill = home / ".gemini/config/plugins/demo/skills/plugin-skill"
            plugin_skill.mkdir(parents=True)
            (plugin_skill / "SKILL.md").write_text(
                "---\nname: plugin-skill\ndescription: plugin skill\n---\n",
                encoding="utf-8",
            )
            state = build_test_state(repo, home)

            records = scan_inventory(state, home)
            by_slug = {record.slug: record for record in records}

            self.assertEqual(by_slug["docx"].source_type, "managed")
            self.assertEqual(by_slug["flat"].source_type, "local-copy")
            self.assertEqual(by_slug["flat"].surfaces, ("antigravity-cli",))
            self.assertEqual(by_slug["plugin-skill"].source_type, "plugin")
            self.assertEqual(
                by_slug["plugin-skill"].surfaces,
                ("antigravity-desktop",),
            )

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

            self.assertEqual([source.root for source in sources], [valid_skills])
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
                [source.root for source in sources],
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

    def test_flat_markdown_symlink_is_listed_once_without_false_duplicate(self) -> None:
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
            linked = home / ".gemini/antigravity-cli/skills/flat.md"
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
            (applications / "Antigravity.app").mkdir(parents=True)
            (applications / "GitHub Copilot.app").mkdir(parents=True)
            conflict = home / ".gemini/config/skills/docx"
            conflict.mkdir(parents=True)
            broken = home / ".copilot/skills/docx"
            broken.parent.mkdir(parents=True)
            broken.symlink_to(home / "missing/docx")
            adapters = build_adapters(home)
            surfaces = detect_surfaces(which=lambda _: None, applications=applications)

            state = scan_managed_state(scan_repository(repo), adapters, surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(
                statuses[("antigravity-desktop", "docx")].state,
                LinkState.CONFLICT,
            )
            self.assertEqual(statuses[("copilot-shared", "docx")].state, LinkState.ERROR)
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
            self.assertEqual(payload["containers"], [])
            self.assertEqual(payload["bridges"], [])

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

            with patch("tools.skill_manager.core.os.replace", side_effect=fail_install):
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
                "tools.skill_manager.core"
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
                "tools.skill_manager.core._target_is_direct_link",
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
                "tools.skill_manager.core"
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
                    "tools.skill_manager.core._target_is_direct_link",
                    side_effect=inject_unknown_and_fail,
                ),
                patch(
                    "tools.skill_manager.core.os.symlink",
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


class AntigravityTests(unittest.TestCase):
    def test_unavailable_desktop_bridge_is_skipped_without_official_root_or_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            legacy = home / ".gemini/skills"
            legacy.mkdir(parents=True)
            (legacy / "pdf").symlink_to(repo / "skills/pdf")
            bridge = home / ".gemini/config/plugins/custom-skills/skills"
            bridge.parent.mkdir(parents=True)
            bridge.symlink_to(legacy)
            state = build_test_state(repo, home)

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")

            self.assertEqual(plan.container_changes, ())
            self.assertEqual(plan.bridge_removals, ())
            self.assertEqual(
                [(item.adapter_key, item.action) for item in plan.link_changes],
                [("antigravity-desktop", "unavailable")],
            )
            self.assertFalse((home / ".gemini/config/skills").exists())
            self.assertTrue(bridge.is_symlink())

    def test_enabling_cli_skill_creates_managed_plugin_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            state = build_test_state(repo, home, installed_commands={"agy": "/bin/agy"})
            plan = plan_set(state, ["pdf"], ["antigravity"], True)

            result = apply_plan(plan, {item.key: item for item in state.adapters})

            manifest = home / ".gemini/antigravity-cli/plugins/lucas-skills/plugin.json"
            self.assertTrue(result.ok)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["name"], "lucas-skills")
            self.assertEqual(
                (home / ".gemini/antigravity-cli/plugins/lucas-skills/skills/pdf").resolve(),
                (repo / "skills/pdf").resolve(),
            )

    def test_refuses_mixed_custom_skills_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            legacy = home / ".gemini/skills"
            legacy.mkdir(parents=True)
            (legacy / "pdf").symlink_to(repo / "skills/pdf")
            write_skill(home / "external", "private", "private")
            (legacy / "private").symlink_to(home / "external/skills/private")
            plugin_skills = home / ".gemini/config/plugins/custom-skills/skills"
            plugin_skills.parent.mkdir(parents=True)
            plugin_skills.symlink_to(legacy)
            state = build_test_state(repo, home, installed_apps={"Antigravity.app"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")

            self.assertTrue(any(item.action == "blocked" and "mixed" in item.reason for item in plan.link_changes))
            self.assertTrue(plugin_skills.is_symlink())

    def test_adopts_fully_managed_custom_skills_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            legacy = home / ".gemini/skills"
            legacy.mkdir(parents=True)
            (legacy / "pdf").symlink_to(repo / "skills/pdf")
            plugin_root = home / ".gemini/config/plugins/custom-skills"
            plugin_root.mkdir(parents=True)
            (plugin_root / "plugin.json").write_text('{"name":"custom-skills"}\n', encoding="utf-8")
            plugin_skills = plugin_root / "skills"
            plugin_skills.symlink_to(legacy)
            state = build_test_state(repo, home, installed_apps={"Antigravity.app"})

            result = apply_adoption(
                plan_adoption(state, home / ".local/state/lucas-skills-manager"),
                {item.key: item for item in state.adapters},
            )

            desktop_link = home / ".gemini/config/skills/pdf"
            self.assertTrue(result.ok)
            self.assertFalse(os.path.lexists(plugin_skills))
            self.assertTrue((plugin_root / "plugin.json").is_file())
            self.assertTrue(desktop_link.is_symlink())
            self.assertEqual(desktop_link.resolve(), (repo / "skills/pdf").resolve())

    def test_keeps_bridge_when_legacy_container_changes_after_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            legacy = home / ".gemini/skills"
            legacy.mkdir(parents=True)
            (legacy / "pdf").symlink_to(repo / "skills/pdf")
            plugin_skills = home / ".gemini/config/plugins/custom-skills/skills"
            plugin_skills.parent.mkdir(parents=True)
            plugin_skills.symlink_to(legacy)
            state = build_test_state(repo, home, installed_apps={"Antigravity.app"})
            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            external = write_skill(home / "external", "private", "private")
            (legacy / "private").symlink_to(external)

            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            desktop_link = home / ".gemini/config/skills/pdf"
            self.assertFalse(result.ok)
            self.assertEqual(
                [item.code for item in result.results],
                ["applied", "bridge-removal-failed"],
            )
            self.assertTrue(desktop_link.is_symlink())
            self.assertEqual(desktop_link.resolve(), (repo / "skills/pdf").resolve())
            self.assertTrue(plugin_skills.is_symlink())

    def test_reuses_legacy_desktop_change_for_bridge_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            legacy = home / ".gemini/skills"
            legacy.mkdir(parents=True)
            legacy_skill = legacy / "pdf"
            legacy_skill.symlink_to(repo / "skills/pdf")
            plugin_skills = home / ".gemini/config/plugins/custom-skills/skills"
            plugin_skills.parent.mkdir(parents=True)
            plugin_skills.symlink_to(legacy)
            desktop_link = home / ".gemini/config/skills/pdf"
            desktop_link.parent.mkdir(parents=True)
            desktop_link.symlink_to(legacy_skill)
            state = build_test_state(repo, home, installed_apps={"Antigravity.app"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            desktop_changes = [
                item for item in plan.link_changes if item.target == desktop_link
            ]
            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertEqual(len(desktop_changes), 1)
            self.assertEqual(desktop_changes[0].action, "create")
            self.assertTrue(result.ok)
            self.assertEqual([item.code for item in result.results], ["applied", "applied"])
            self.assertEqual(Path(os.readlink(desktop_link)), (repo / "skills/pdf").resolve())
            self.assertFalse(os.path.lexists(plugin_skills))


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
                which=lambda command: "/bin/agy" if command == "agy" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)

            result = apply_plan(
                plan_set(state, ["pdf"], ["antigravity"], True),
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
                "tools.skill_manager.core"
            ).snapshot_path

            def snapshot_with_error(path: Path):
                if path == pdf.target:
                    raise OSError("deterministic path failure")
                return real_snapshot(path)

            with patch(
                "tools.skill_manager.core.snapshot_path",
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

            with patch("tools.skill_manager.core.os.symlink", side_effect=racing_symlink):
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
                    "tools.skill_manager.core.os.rename",
                    side_effect=lambda src, dst, *args, **kwargs: race(
                        real_rename, src, dst, *args, **kwargs
                    ),
                ),
                patch(
                    "tools.skill_manager.core.os.replace",
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
                "tools.skill_manager.core.os.symlink",
                side_effect=disappearing_source,
            ):
                result = apply_plan(plan, by_key)

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertFalse(os.path.lexists(plan.changes[0].target))


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
            self.assertEqual([item["slug"] for item in payload["skills"]], ["docx"])
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["targets"]), 5)
            self.assertEqual(payload["inventory"], [])
            self.assertEqual(payload["issues"], [])

    def test_adopt_preview_has_stable_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["adopt", "--json"],
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
            self.assertEqual(payload["issues"], [])
            self.assertEqual(payload["changes"]["link_changes"], [])
            self.assertEqual(payload["changes"]["container_changes"], [])
            self.assertEqual(payload["changes"]["bridge_removals"], [])
            self.assertIsNotNone(payload["changes"]["snapshot_path"])
            self.assertEqual(payload["results"], [])

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
                argv = ["set", "--all", "--tool", "claude", "--on"]
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
                self.assertEqual([item["slug"] for item in payload["skills"]], ["docx"])
                self.assertEqual(
                    [issue["code"] for issue in payload["issues"]],
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
                ["set", "--all", "--tool", "claude", "--on"],
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
                argv = ["adopt"]
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
                    [issue["code"] for issue in payload["issues"]],
                    ["invalid-frontmatter"],
                )
                self.assertEqual(payload["changes"]["link_changes"], [])
                self.assertEqual(payload["changes"]["container_changes"], [])
                self.assertEqual(payload["changes"]["bridge_removals"], [])
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
            self.assertEqual([item["slug"] for item in payload["skills"]], ["docx"])
            self.assertEqual(len(payload["adapters"]), 5)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["targets"]), 5)
            self.assertEqual(
                [issue["code"] for issue in payload["issues"]],
                ["invalid-frontmatter"],
            )

    def test_adopt_error_keeps_state_and_change_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            with patch(
                "tools.skill_manager.cli.plan_adoption",
                side_effect=OSError("failed"),
            ):
                code = main(
                    ["adopt", "--json"],
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
            self.assertEqual([item["slug"] for item in payload["skills"]], ["docx"])
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["targets"]), 5)
            self.assertEqual(payload["issues"], [])
            self.assertEqual(payload["changes"]["link_changes"], [])
            self.assertEqual(payload["changes"]["container_changes"], [])
            self.assertEqual(payload["changes"]["bridge_removals"], [])
            self.assertEqual(payload["results"], [])

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
            self.assertIn("Skills: 1", text)
            self.assertIn("claude: 1 enabled", text)
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
            self.assertEqual([item["slug"] for item in payload["skills"]], ["docx"])
            self.assertEqual(len(payload["adapters"]), 5)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["targets"]), 5)
            self.assertEqual(payload["inventory"], [])
            self.assertEqual(payload["issues"], [])

    def test_set_error_uses_plan_mode_in_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["set", "missing", "--tool", "claude", "--on", "--json"],
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
            self.assertEqual([item["slug"] for item in payload["skills"]], ["docx"])
            self.assertEqual(len(payload["adapters"]), 5)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(len(payload["targets"]), 5)
            self.assertEqual(payload["issues"], [])
            self.assertEqual(payload["changes"], [])
            self.assertEqual(payload["results"], [])

    def test_set_without_apply_only_prints_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["set", "docx", "--tool", "claude", "--on", "--json"],
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
            self.assertEqual(payload["issues"], [])
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
                ["set", "docx", "--tool", "claude", "--on", "--json"],
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
                ["set", "docx", "--tool", "copilot", "--off", "--json"],
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

    def test_adopt_preview_exposes_blocked_change_as_target_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            legacy_root = home / "legacy-antigravity"
            legacy_root.mkdir(parents=True)
            (legacy_root / "docx").symlink_to(skill)
            bridge = home / ".gemini/config/plugins/custom-skills/skills"
            bridge.parent.mkdir(parents=True)
            bridge.symlink_to(legacy_root)
            occupied = home / ".gemini/config/skills/docx"
            occupied.mkdir(parents=True)
            applications = root / "Applications"
            (applications / "Antigravity.app").mkdir(parents=True)
            output = io.StringIO()

            code = main(
                ["adopt", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda _: None,
                applications=applications,
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "target-conflict")
            self.assertEqual(payload["changes"]["link_changes"][0]["action"], "blocked")
            self.assertTrue(bridge.is_symlink())

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
            self.assertEqual(payload["skills"][0]["slug"], "pdf")
            self.assertEqual(len(payload["adapters"]), 5)
            self.assertEqual(len(payload["surfaces"]), 8)
            self.assertEqual(payload["issues"], [])

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
                ["set", "--all", "--tool", "claude", "--on", "--apply", "--json"],
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
            self.assertEqual(payload["issues"], [])
            self.assertEqual(
                {item["code"] for item in payload["results"]},
                {"applied", "blocked"},
            )
            self.assertTrue((home / ".claude/skills/docx").is_symlink())
            self.assertTrue(occupied.is_dir())

    def test_unavailable_surface_does_not_make_cli_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            output = io.StringIO()

            code = main(
                [
                    "set",
                    "pdf",
                    "--tool",
                    "antigravity",
                    "--on",
                    "--apply",
                    "--json",
                ],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/agy" if command == "agy" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertIn(
                "unavailable",
                {item["code"] for item in payload["results"]},
            )


class HttpServerTests(unittest.TestCase):
    @staticmethod
    def _write_request(base_url: str, path: str, payload: object):
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": base_url,
                "X-Skill-Manager-Token": "test-token",
            },
        )
        return urllib.request.urlopen(request, timeout=2)

    @staticmethod
    def _error_payload(error: urllib.error.HTTPError) -> dict[str, object]:
        return json.loads(error.read())

    def test_binds_loopback_and_read_apis_recover_from_filesystem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(skill)

            def read_status() -> dict[str, object]:
                with running_http_server(
                    repo,
                    home,
                    root / "Applications",
                    lambda command: "/bin/claude" if command == "claude" else None,
                ) as (server, _thread, base_url):
                    self.assertEqual(server.server_address[0], "127.0.0.1")
                    response = urllib.request.urlopen(f"{base_url}/api/status", timeout=2)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                    self.assertNotIn("Access-Control-Allow-Origin", response.headers)
                    return json.loads(response.read())

            first = read_status()
            second = read_status()
            self.assertEqual(first["targets"], second["targets"])
            self.assertTrue(target.is_symlink())

            with running_http_server(repo, home, root / "Applications") as (
                _server,
                _thread,
                base_url,
            ):
                inventory = json.loads(
                    urllib.request.urlopen(f"{base_url}/api/inventory", timeout=2).read()
                )
                self.assertTrue(inventory["ok"])
                self.assertIn("inventory", inventory)
                self.assertTrue(target.is_symlink())

    def test_write_requires_exact_host_origin_and_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (server, _thread, base_url):
                body = json.dumps(
                    {
                        "skill": "docx",
                        "tool": "claude",
                        "enabled": True,
                        "apply": True,
                    }
                ).encode()
                missing = urllib.request.Request(
                    f"{base_url}/api/set",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(missing, timeout=2)
                self.assertEqual(caught.exception.code, 403)
                self.assertEqual(self._error_payload(caught.exception)["code"], "invalid-token")

                wrong_origin = urllib.request.Request(
                    f"{base_url}/api/set",
                    data=body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": "http://127.0.0.1:1",
                        "X-Skill-Manager-Token": "test-token",
                    },
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(wrong_origin, timeout=2)
                self.assertEqual(caught.exception.code, 403)

                host, port = server.server_address
                connection = http.client.HTTPConnection(host, port, timeout=2)
                connection.putrequest("GET", "/api/status", skip_host=True)
                connection.putheader("Host", "localhost:9999")
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                self.assertEqual(json.loads(response.read())["code"], "invalid-host")
                connection.close()

                connection = http.client.HTTPConnection(host, port, timeout=2)
                connection.putrequest("POST", "/api/set")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(len(body)))
                connection.putheader("Origin", base_url)
                connection.putheader("Origin", base_url)
                connection.putheader("X-Skill-Manager-Token", "test-token")
                connection.putheader("X-Skill-Manager-Token", "test-token")
                connection.endheaders(body)
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.close()

                response = self._write_request(base_url, "/api/set", json.loads(body))
                self.assertTrue(json.loads(response.read())["ok"])
                self.assertEqual(
                    (home / ".claude/skills/docx").resolve(),
                    (repo / "skills/docx").resolve(),
                )

    def test_rejects_invalid_content_type_body_shape_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(repo, home, root / "Applications") as (
                server,
                _thread,
                base_url,
            ):
                common = {
                    "Origin": base_url,
                    "X-Skill-Manager-Token": "test-token",
                }
                request = urllib.request.Request(
                    f"{base_url}/api/set",
                    data=b"{}",
                    method="POST",
                    headers={**common, "Content-Type": "text/plain"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request, timeout=2)
                self.assertEqual(caught.exception.code, 415)

                for payload in ([], {"apply": True, "unexpected": True}):
                    with self.subTest(payload=payload):
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            self._write_request(base_url, "/api/adopt", payload)
                        self.assertEqual(caught.exception.code, 400)
                        self.assertEqual(
                            self._error_payload(caught.exception)["code"],
                            "invalid-request",
                        )

                oversized = urllib.request.Request(
                    f"{base_url}/api/set",
                    data=b" " * (64 * 1024 + 1),
                    method="POST",
                    headers={**common, "Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(oversized, timeout=2)
                self.assertEqual(caught.exception.code, 413)

                duplicate_body = b'{"apply":false,"apply":true}'
                duplicate = urllib.request.Request(
                    f"{base_url}/api/adopt",
                    data=duplicate_body,
                    method="POST",
                    headers={**common, "Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(duplicate, timeout=2)
                self.assertEqual(caught.exception.code, 400)

                host, port = server.server_address
                connection = http.client.HTTPConnection(host, port, timeout=2)
                connection.putrequest("POST", "/api/adopt")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Origin", base_url)
                connection.putheader("X-Skill-Manager-Token", "test-token")
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 411)
                response.read()
                connection.close()

            self.assertFalse((home / ".local/state/lucas-skills-manager").exists())

    def test_rejects_path_traversal_and_unsupported_routes_or_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            web_root = repo / "tools/skill_manager/web"
            web_root.mkdir(parents=True)
            (web_root / "index.html").write_text(
                "<script>const token = __SKILL_MANAGER_TOKEN__;</script>",
                encoding="utf-8",
            )
            with running_http_server(repo, home, root / "Applications") as (
                server,
                _thread,
                base_url,
            ):
                index = urllib.request.urlopen(f"{base_url}/", timeout=2).read().decode()
                self.assertIn('const token = "test-token";', index)

                for path in ("/index.html", "/../cli.py", "/api/unknown"):
                    with self.subTest(path=path), self.assertRaises(
                        urllib.error.HTTPError
                    ) as caught:
                        urllib.request.urlopen(f"{base_url}{path}", timeout=2)
                    self.assertEqual(caught.exception.code, 404)

                outside = root / "outside.html"
                outside.write_text("sensitive", encoding="utf-8")
                (web_root / "index.html").unlink()
                (web_root / "index.html").symlink_to(outside)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(f"{base_url}/", timeout=2)
                self.assertEqual(caught.exception.code, 404)

                host, port = server.server_address
                methods = (
                    ("GET", "/api/set"),
                    ("POST", "/api/status"),
                    ("PUT", "/api/set"),
                )
                for method, path in methods:
                    with self.subTest(method=method, path=path):
                        connection = http.client.HTTPConnection(host, port, timeout=2)
                        connection.request(method, path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 405)
                        self.assertIn("Allow", response.headers)
                        response.read()
                        connection.close()

    def test_rejects_symlinked_web_root_without_reading_external_index(self) -> None:
        for symlinked_component in ("web", "skill_manager"):
            with self.subTest(symlinked_component=symlinked_component):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp).resolve()
                    repo, home = root / "repo", root / "home"
                    write_skill(repo, "docx", "docx")
                    external = root / f"external-{symlinked_component}"

                    if symlinked_component == "web":
                        external.mkdir()
                        (external / "index.html").write_text(
                            "sensitive-external-file",
                            encoding="utf-8",
                        )
                        (repo / "tools/skill_manager").mkdir(parents=True)
                        (repo / "tools/skill_manager/web").symlink_to(external)
                    else:
                        (external / "web").mkdir(parents=True)
                        (external / "web/index.html").write_text(
                            "sensitive-external-file",
                            encoding="utf-8",
                        )
                        (repo / "tools").mkdir()
                        (repo / "tools/skill_manager").symlink_to(external)

                    with running_http_server(
                        repo,
                        home,
                        root / "Applications",
                    ) as (_server, _thread, base_url):
                        with self.assertRaises(urllib.error.HTTPError) as caught:
                            urllib.request.urlopen(f"{base_url}/", timeout=2)

                        self.assertIn(caught.exception.code, {403, 404})
                        body = caught.exception.read().decode()
                        self.assertEqual(
                            caught.exception.headers.get_content_type(),
                            "application/json",
                        )
                        self.assertNotIn("sensitive-external-file", body)

    def test_manifest_owner_conflict_is_409_but_invalid_manifest_is_500(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            manifest = home / ".gemini/antigravity-cli/plugins/lucas-skills/plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"name":"other-owner"}\n', encoding="utf-8")

            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/agy" if command == "agy" else None,
            ) as (_server, _thread, base_url):
                request = {
                    "skill": "docx",
                    "tool": "antigravity",
                    "enabled": True,
                    "apply": True,
                }
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(base_url, "/api/set", request)
                self.assertEqual(caught.exception.code, 409)
                self.assertEqual(
                    self._error_payload(caught.exception)["code"],
                    "target-conflict",
                )

                manifest.write_text("{\n", encoding="utf-8")
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(base_url, "/api/set", request)
                self.assertEqual(caught.exception.code, 500)
                self.assertEqual(
                    self._error_payload(caught.exception)["code"],
                    "internal-error",
                )

            self.assertFalse(
                os.path.lexists(
                    home / ".gemini/antigravity-cli/plugins/lucas-skills/skills/docx"
                )
            )

    def test_trace_and_connect_are_structured_405_for_static_and_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(repo, home, root / "Applications") as (
                server,
                _thread,
                _base_url,
            ):
                host, port = server.server_address
                requests = (
                    ("TRACE", "/", "GET"),
                    ("CONNECT", "/api/status", "GET"),
                    ("TRACE", "/api/set", "POST"),
                    ("CONNECT", "/api/shutdown", "POST"),
                    ("PROPFIND", "/", "GET"),
                )
                for method, path, allowed in requests:
                    with self.subTest(method=method, path=path):
                        connection = http.client.HTTPConnection(host, port, timeout=2)
                        connection.request(method, path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 405)
                        self.assertEqual(response.headers["Allow"], allowed)
                        self.assertEqual(
                            response.headers.get_content_type(),
                            "application/json",
                        )
                        self.assertEqual(
                            json.loads(response.read())["code"],
                            "method-not-allowed",
                        )
                        connection.close()

    def test_set_preview_apply_and_invalid_skill_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, _thread, base_url):
                preview = json.loads(
                    self._write_request(
                        base_url,
                        "/api/set",
                        {"all": True, "tool": "claude", "enabled": True, "apply": False},
                    ).read()
                )
                self.assertEqual(preview["mode"], "plan")
                self.assertEqual(len(preview["changes"]), 1)
                self.assertFalse(os.path.lexists(home / ".claude/skills/docx"))

                applied = json.loads(
                    self._write_request(
                        base_url,
                        "/api/set",
                        {"all": True, "tool": "claude", "enabled": True, "apply": True},
                    ).read()
                )
                self.assertEqual(applied["mode"], "apply")
                self.assertTrue((home / ".claude/skills/docx").is_symlink())

                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/set",
                        {
                            "skill": "../evil",
                            "tool": "claude",
                            "enabled": True,
                            "apply": True,
                        },
                    )
                self.assertEqual(caught.exception.code, 400)
                self.assertEqual(self._error_payload(caught.exception)["code"], "invalid-skill")
                self.assertFalse(os.path.lexists(home / ".claude/evil"))

    def test_conflicted_set_preview_returns_full_plan_then_apply_is_409(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            occupied = home / ".claude/skills/pdf"
            occupied.mkdir(parents=True)
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, _thread, base_url):
                preview_response = self._write_request(
                    base_url,
                    "/api/set",
                    {"all": True, "tool": "claude", "enabled": True, "apply": False},
                )
                self.assertEqual(preview_response.status, 200)
                preview = json.loads(preview_response.read())
                self.assertFalse(preview["ok"])
                self.assertEqual(preview["code"], "target-conflict")
                self.assertEqual(
                    {item["action"] for item in preview["changes"]},
                    {"create", "blocked"},
                )
                self.assertFalse(os.path.lexists(home / ".claude/skills/docx"))

                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/set",
                        {"all": True, "tool": "claude", "enabled": True, "apply": True},
                    )
                self.assertEqual(caught.exception.code, 409)
                applied = self._error_payload(caught.exception)
                self.assertEqual(applied["code"], "target-conflict")
                self.assertEqual(
                    {item["code"] for item in applied["results"]},
                    {"applied", "blocked"},
                )
                self.assertTrue((home / ".claude/skills/docx").is_symlink())
                self.assertTrue(occupied.is_dir())

    def test_conflicted_adoption_preview_is_http_200_with_complete_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            legacy_root = home / "legacy-antigravity"
            legacy_root.mkdir(parents=True)
            (legacy_root / "docx").symlink_to(skill)
            bridge = home / ".gemini/config/plugins/custom-skills/skills"
            bridge.parent.mkdir(parents=True)
            bridge.symlink_to(legacy_root)
            (home / ".gemini/config/skills/docx").mkdir(parents=True)
            applications = root / "Applications"
            (applications / "Antigravity.app").mkdir(parents=True)

            with running_http_server(repo, home, applications) as (
                _server,
                _thread,
                base_url,
            ):
                response = self._write_request(
                    base_url,
                    "/api/adopt",
                    {"apply": False},
                )
                self.assertEqual(response.status, 200)
                preview = json.loads(response.read())
                self.assertFalse(preview["ok"])
                self.assertEqual(preview["code"], "target-conflict")
                self.assertEqual(
                    [item["action"] for item in preview["changes"]["link_changes"]],
                    ["blocked"],
                )
                self.assertEqual(len(preview["changes"]["bridge_removals"]), 1)
                self.assertEqual(
                    preview["changes"]["bridge_removals"][0]["path"],
                    str(bridge),
                )
                self.assertTrue(bridge.is_symlink())

    def test_target_conflict_is_409_and_preserves_occupied_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            occupied = home / ".claude/skills/docx"
            occupied.mkdir(parents=True)
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, _thread, base_url):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self._write_request(
                        base_url,
                        "/api/set",
                        {
                            "skill": "docx",
                            "tool": "claude",
                            "enabled": True,
                            "apply": True,
                        },
                    )
                self.assertEqual(caught.exception.code, 409)
                self.assertEqual(
                    self._error_payload(caught.exception)["code"],
                    "target-conflict",
                )
                self.assertTrue(occupied.is_dir())

    def test_adopt_requires_apply_and_shutdown_stops_service(self) -> None:
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
            with running_http_server(
                repo,
                home,
                root / "Applications",
                lambda command: "/bin/claude" if command == "claude" else None,
            ) as (_server, thread, base_url):
                preview = json.loads(
                    self._write_request(base_url, "/api/adopt", {"apply": False}).read()
                )
                self.assertEqual(preview["mode"], "plan")
                self.assertEqual(Path(os.readlink(target)), legacy)
                self.assertFalse((home / ".local/state/lucas-skills-manager").exists())

                applied = json.loads(
                    self._write_request(base_url, "/api/adopt", {"apply": True}).read()
                )
                self.assertEqual(applied["mode"], "apply")
                self.assertEqual(target.resolve(), skill.resolve())

                response = self._write_request(base_url, "/api/shutdown", {})
                self.assertTrue(json.loads(response.read())["ok"])
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())

    def test_serve_opens_browser_only_when_requested(self) -> None:
        class FakeServer:
            server_address = ("127.0.0.1", 43210)

            def serve_forever(self) -> None:
                return None

            def server_close(self) -> None:
                return None

        for open_browser in (False, True):
            with self.subTest(open_browser=open_browser), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                output = io.StringIO()
                argv = ["serve"] + (["--open"] if open_browser else [])
                with (
                    patch(
                        "tools.skill_manager.cli.secrets.token_urlsafe",
                        return_value="generated-token",
                    ),
                    patch(
                        "tools.skill_manager.cli.create_server",
                        return_value=FakeServer(),
                    ) as create,
                    patch("tools.skill_manager.cli.webbrowser.open") as browser_open,
                ):
                    code = main(
                        argv,
                        home=root / "home",
                        repo_root=root / "repo",
                        stdout=output,
                        applications=root / "Applications",
                    )

                self.assertEqual(code, 0)
                self.assertEqual(output.getvalue(), "http://127.0.0.1:43210/\n")
                self.assertEqual(browser_open.called, open_browser)
                create.assert_called_once()
