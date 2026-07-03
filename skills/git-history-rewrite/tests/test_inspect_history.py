import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
INSPECTOR = REPO_ROOT / "skills" / "git-history-rewrite" / "scripts" / "inspect_history.py"


def run(cmd, cwd):
    subprocess.run(cmd, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class InspectHistoryTest(unittest.TestCase):
    def test_default_base_uses_integration_branch_not_feature_upstream(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "origin.git"
            work = root / "work"
            run(["git", "init", "-q", "--bare", str(remote)], cwd=root)
            run(["git", "init", "-q", "--initial-branch=main", str(work)], cwd=root)
            run(["git", "config", "user.email", "test@example.com"], cwd=work)
            run(["git", "config", "user.name", "Test User"], cwd=work)
            run(["git", "remote", "add", "origin", str(remote)], cwd=work)

            (work / "app.txt").write_text("base\n")
            run(["git", "add", "app.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "base"], cwd=work)
            run(["git", "push", "-q", "-u", "origin", "main"], cwd=work)

            run(["git", "checkout", "-q", "-b", "feature"], cwd=work)
            (work / "app.txt").write_text("base\nfeature\n")
            run(["git", "commit", "-q", "-am", "feat: add feature"], cwd=work)
            (work / "app.txt").write_text("base\nfeature\nfixup\n")
            run(["git", "commit", "-q", "-am", "fixup: adjust feature"], cwd=work)
            run(["git", "push", "-q", "-u", "origin", "feature"], cwd=work)

            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json"],
                cwd=work,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)

            self.assertEqual(report["upstream"], "origin/feature")
            self.assertEqual(report["base_source"], "merge-base with origin/main")
            subjects = [line.split(" ", 1)[1] for line in report["commits"]]
            self.assertEqual(subjects, ["feat: add feature", "fixup: adjust feature"])
            self.assertTrue(
                any("force-with-lease" in risk for risk in report["risks"]),
                report["risks"],
            )


if __name__ == "__main__":
    unittest.main()
