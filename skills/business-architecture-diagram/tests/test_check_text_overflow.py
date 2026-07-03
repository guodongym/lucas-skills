import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_text_overflow.py"

OK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
  <style>.card { fill: #fff; } .card-title { font-size: 20px; text-anchor: middle; }</style>
  <rect x="40" y="40" width="320" height="96" class="card"/>
  <text x="200" y="90" class="card-title">短标题</text>
</svg>
"""

OVERFLOW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
  <style>.card { fill: #fff; } .card-title { font-size: 20px; text-anchor: middle; }</style>
  <rect x="40" y="40" width="120" height="96" class="card"/>
  <text x="100" y="90" class="card-title">这是一个明显超出卡片宽度的超长标题文本</text>
</svg>
"""

BROKEN_REF_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
  <style>.arrow { stroke: #888; }</style>
  <path d="M0,0 L100,100" class="arrow" marker-end="url(#missing-marker)"/>
</svg>
"""


def run_script(svg_text: str):
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
        f.write(svg_text)
        path = f.name
    return subprocess.run(
        ["python3", str(SCRIPT), path],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


class CheckTextOverflowTest(unittest.TestCase):
    def test_ok_svg_passes(self):
        proc = run_script(OK_SVG)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_overflow_is_reported(self):
        proc = run_script(OVERFLOW_SVG)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("OVERFLOW", proc.stdout)

    def test_missing_marker_ref_is_reported(self):
        proc = run_script(BROKEN_REF_SVG)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing-marker", proc.stdout)

    def test_missing_file_reports_clean_error(self):
        proc = subprocess.run(
            ["python3", str(SCRIPT), "/nonexistent/no-such.svg"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error: cannot parse", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
