from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UpstreamSyncLayoutTests(unittest.TestCase):
    def test_missing_pyyaml_points_to_uv_managed_setup(self) -> None:
        result = subprocess.run(
            [sys.executable, "-S", str(ROOT / "tools/upstream_sync/vendor.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uv sync", result.stderr)
        self.assertIn("uv run upstream-sync", result.stderr)
        self.assertNotIn("pip install", result.stderr)

    def test_paths_are_derived_from_checked_in_tool_location(self) -> None:
        from tools.upstream_sync import vendor

        self.assertEqual(vendor.TOOL_ROOT, ROOT / "tools/upstream_sync")
        self.assertEqual(vendor.REPO_ROOT, ROOT)
        self.assertEqual(vendor.CONFIG_FILE, vendor.TOOL_ROOT / "upstream.yml")
        self.assertEqual(vendor.LOCK_FILE, vendor.TOOL_ROOT / "upstream.lock.yml")
        self.assertEqual(vendor.repository_path("skills/docx"), ROOT / "skills/docx")

    def test_standard_help_flag_is_successful(self) -> None:
        from tools.upstream_sync import vendor

        output = io.StringIO()
        with redirect_stdout(output):
            result = vendor.main(["--help"])
        self.assertEqual(result, 0)
        self.assertIn("uv run upstream-sync check", output.getvalue())
