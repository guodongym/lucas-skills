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

    def test_empty_repo_reports_no_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            run(["git", "init", "-q", "--initial-branch=main", str(work)], cwd=tmp)
            proc = subprocess.run(
                ["python3", str(INSPECTOR)],
                cwd=work,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("no commits yet", proc.stderr)

    def test_detached_head_is_flagged_as_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            run(["git", "init", "-q", "--initial-branch=main", str(work)], cwd=tmp)
            run(["git", "config", "user.email", "test@example.com"], cwd=work)
            run(["git", "config", "user.name", "Test User"], cwd=work)
            (work / "a.txt").write_text("one\n")
            run(["git", "add", "a.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "one"], cwd=work)
            (work / "a.txt").write_text("two\n")
            run(["git", "commit", "-q", "-am", "two"], cwd=work)
            run(["git", "checkout", "-q", "--detach", "HEAD"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json", "--base", "HEAD~1"],
                cwd=work,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertEqual(report["branch"], "(detached HEAD)")
            self.assertTrue(
                any(risk.startswith("detached HEAD") for risk in report["risks"]),
                report["risks"],
            )

    def _init_repo(self, root: Path) -> Path:
        work = root / "work"
        run(["git", "init", "-q", "--initial-branch=main", str(work)], cwd=root)
        run(["git", "config", "user.email", "test@example.com"], cwd=work)
        run(["git", "config", "user.name", "Test User"], cwd=work)
        (work / "app.txt").write_text("base\n")
        run(["git", "add", "app.txt"], cwd=work)
        run(["git", "commit", "-q", "-m", "base"], cwd=work)
        return work

    def test_merge_commits_in_range_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self._init_repo(Path(tmp))
            run(["git", "checkout", "-q", "-b", "feature"], cwd=work)
            (work / "feat.txt").write_text("feature\n")
            run(["git", "add", "feat.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "feat: add feature"], cwd=work)
            run(["git", "checkout", "-q", "main"], cwd=work)
            (work / "main.txt").write_text("main\n")
            run(["git", "add", "main.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "chore: advance main"], cwd=work)
            run(["git", "checkout", "-q", "feature"], cwd=work)
            run(["git", "merge", "-q", "--no-edit", "main"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json", "--base", "main"],
                cwd=work, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertTrue(report["merge_commits"], report)
            self.assertTrue(any("merge commits" in r for r in report["risks"]), report["risks"])

    def test_behind_upstream_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = self._init_repo(root)
            remote = root / "origin.git"
            run(["git", "init", "-q", "--bare", str(remote)], cwd=root)
            run(["git", "remote", "add", "origin", str(remote)], cwd=work)
            (work / "app.txt").write_text("base\nmore\n")
            run(["git", "commit", "-q", "-am", "feat: more"], cwd=work)
            run(["git", "push", "-q", "-u", "origin", "main"], cwd=work)
            run(["git", "reset", "-q", "--hard", "HEAD~1"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json"],
                cwd=work, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertEqual(report["ahead_behind"], {"behind": 1, "ahead": 0})
            self.assertTrue(any("behind its upstream" in r for r in report["risks"]), report["risks"])

    def test_no_upstream_flagged_and_base_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = self._init_repo(root)
            remote = root / "origin.git"
            run(["git", "init", "-q", "--bare", str(remote)], cwd=root)
            run(["git", "remote", "add", "origin", str(remote)], cwd=work)
            run(["git", "push", "-q", "-u", "origin", "main"], cwd=work)
            run(["git", "checkout", "-q", "-b", "feature"], cwd=work)
            (work / "feat.txt").write_text("feature\n")
            run(["git", "add", "feat.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "feat: add feature"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json"],
                cwd=work, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertIsNone(report["upstream"])
            self.assertEqual(report["base_source"], "merge-base with origin/main")
            self.assertTrue(any("no upstream" in r for r in report["risks"]), report["risks"])


if __name__ == "__main__":
    unittest.main()
