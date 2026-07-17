from __future__ import annotations

import re
import subprocess
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectLayoutTests(unittest.TestCase):
    def test_agent_manager_skills_and_shared_core_are_separate(self) -> None:
        package = ROOT / "tools/agent_manager"
        for name in ("cli.py", "core.py", "skills.py"):
            with self.subTest(name=name):
                self.assertTrue((package / name).is_file())

    def test_skills_domain_exports_existing_operations(self) -> None:
        from tools.agent_manager import skills

        for name in (
            "scan_repository",
            "scan_inventory",
            "plan_set",
            "apply_plan",
            "plan_adoption",
            "apply_adoption",
        ):
            self.assertTrue(callable(getattr(skills, name)))

    def test_pyproject_declares_two_console_scripts_and_uv_build(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["requires-python"], ">=3.11")
        self.assertEqual(project["project"]["dependencies"], ["PyYAML"])
        self.assertEqual(
            project["project"]["scripts"],
            {
                "agent-manager": "tools.agent_manager.cli:main",
                "upstream-sync": "tools.upstream_sync.vendor:main",
            },
        )
        self.assertEqual(project["build-system"]["build-backend"], "uv_build")
        self.assertEqual(project["tool"]["uv"]["build-backend"]["module-root"], "")
        self.assertEqual(project["tool"]["uv"]["build-backend"]["module-name"], "tools")
        self.assertEqual(
            project["tool"]["uv"]["build-backend"]["source-include"],
            [
                "tools/agent_manager/web/index.html",
                "tools/agent_manager/web/app.css",
                "tools/agent_manager/web/app.js",
                "tools/upstream_sync/upstream.yml",
                "tools/upstream_sync/upstream.lock.yml",
            ],
        )

    def test_uv_environment_is_ignored_but_lock_is_tracked_by_policy(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".venv/", ignore)
        self.assertTrue((ROOT / "uv.lock").is_file())

    def test_skill_manager_runtime_compatibility_is_removed(self) -> None:
        self.assertFalse((ROOT / "tools" / "skill_manager").exists())
        self.assertFalse((ROOT / "tests/test_skill_manager.py").exists())
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertNotIn("skill-manager", project["project"]["scripts"])

    def test_wheel_contains_only_expected_non_python_package_data(self) -> None:
        expected = {
            "tools/agent_manager/web/app.css",
            "tools/agent_manager/web/app.js",
            "tools/agent_manager/web/index.html",
            "tools/upstream_sync/upstream.lock.yml",
            "tools/upstream_sync/upstream.yml",
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["uv", "build", "--wheel", "--out-dir", tmp],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            wheels = list(Path(tmp).glob("*.whl"))
            self.assertEqual(len(wheels), 1, wheels)
            with zipfile.ZipFile(wheels[0]) as archive:
                package_data = {
                    name
                    for name in archive.namelist()
                    if name.startswith("tools/")
                    and not name.endswith(("/", ".py", ".pyi"))
                }
        self.assertEqual(package_data, expected)

    def test_active_runtime_and_docs_have_no_removed_live_interfaces(self) -> None:
        banned = (
            "uv run " + "skill-manager",
            "tools" + ".skill_manager",
            "tools" + "/skill_manager",
            "/api/" + "set",
            "/api/" + "adopt",
        )
        runtime_files = [
            *(
                path
                for path in (ROOT / "tools").rglob("*")
                if path.is_file() and path.suffix in {".py", ".html", ".css", ".js"}
            ),
            *(ROOT / "tests").glob("test_*.py"),
            ROOT / "README.md",
            ROOT / "pyproject.toml",
        ]
        for path in runtime_files:
            text = path.read_text(encoding="utf-8")
            for removed in banned:
                with self.subTest(path=path.relative_to(ROOT), removed=removed):
                    self.assertNotIn(removed, text)

        historical = {
            ROOT / "docs/superpowers/specs/2026-07-14-global-skill-manager-design.md",
            ROOT / "docs/superpowers/plans/2026-07-14-global-skill-manager.md",
            ROOT / "docs/superpowers/specs/2026-07-15-repository-layout-and-cli-design.md",
            ROOT / "docs/superpowers/plans/2026-07-15-repository-layout-and-cli.md",
        }
        shell_fence = re.compile(
            r"^```(?:bash|sh|shell|zsh|console)[ \t]*$\n(.*?)^```[ \t]*$",
            flags=re.DOTALL | re.MULTILINE,
        )
        old_command = "uv run " + "skill-manager"
        for path in (ROOT / "docs").rglob("*.md"):
            if path in historical:
                continue
            for block in shell_fence.findall(path.read_text(encoding="utf-8")):
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertNotIn(old_command, block)

    def test_legacy_root_tool_paths_are_gone(self) -> None:
        for relative in (
            "skill_manager.py",
            "skill_manager_core.py",
            "skill_manager_web",
            "vendor.py",
            "upstream.yml",
            "upstream.lock.yml",
        ):
            with self.subTest(relative=relative):
                self.assertFalse((ROOT / relative).exists())
