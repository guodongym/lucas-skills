from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectLayoutTests(unittest.TestCase):
    def test_pyproject_declares_two_console_scripts_and_uv_build(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["requires-python"], ">=3.11")
        self.assertEqual(project["project"]["dependencies"], ["PyYAML"])
        self.assertEqual(
            project["project"]["scripts"],
            {
                "skill-manager": "tools.skill_manager.cli:main",
                "upstream-sync": "tools.upstream_sync.vendor:main",
            },
        )
        self.assertEqual(project["build-system"]["build-backend"], "uv_build")
        self.assertEqual(project["tool"]["uv"]["build-backend"]["module-root"], "")
        self.assertEqual(project["tool"]["uv"]["build-backend"]["module-name"], "tools")

    def test_uv_environment_is_ignored_but_lock_is_tracked_by_policy(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".venv/", ignore)
        self.assertTrue((ROOT / "uv.lock").is_file())

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
