import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/ezone"


class EzoneSkillTests(unittest.TestCase):
    def test_metadata_and_behavior_exercises_are_distributable(self):
        text = (SKILL / "SKILL.md").read_text()
        metadata = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(metadata["name"], "ezone")
        self.assertTrue(metadata["description"])
        interface = yaml.safe_load((SKILL / "agents/openai.yaml").read_text())["interface"]
        self.assertIn("$ezone", interface["default_prompt"])
        self.assertTrue(25 <= len(interface["short_description"]) <= 64)
        manifest = json.loads((SKILL / "evals/evals.json").read_text())
        self.assertEqual(manifest["skill_name"], "ezone")
        self.assertEqual(len({case["id"] for case in manifest["evals"]}), len(manifest["evals"]))
        for case in manifest["evals"]:
            self.assertEqual(case["kind"], "behavior")
            self.assertTrue(case["prompt"])
            self.assertTrue(case["expected_output"])
            self.assertTrue(case["assertions"])
            for relative in case["files"]:
                self.assertTrue((SKILL / relative).is_file())

    def test_copy_only_entry_links_and_cli_outside_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "shared/ezone"
            shutil.copytree(SKILL, destination, ignore=shutil.ignore_patterns("__pycache__"))
            self.assertTrue((destination / "SKILL.md").is_file())
            for document in [destination / "SKILL.md", *destination.glob("references/*.md")]:
                for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
                    if "://" not in target and not target.startswith("#"):
                        local = (document.parent / target.split("#")[0]).resolve()
                        self.assertTrue(local.is_relative_to(destination.resolve()), target)
                        self.assertTrue(local.is_file(), target)
            env = {key: value for key, value in os.environ.items() if not key.startswith("EZONE_") and key != "PYTHONPATH"}
            for args in [["--version"], ["--help"], ["--json", "doctor"]]:
                result = subprocess.run([sys.executable, "-E", "-s", str(destination / "scripts/ezone.py"), *args], cwd=folder, env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                if args == ["--version"]:
                    self.assertEqual(result.stdout.strip(), "0.2.0")
                if args[-1] == "doctor":
                    self.assertFalse(json.loads(result.stdout)["token_present"])

    def test_documented_commands_parse_against_actual_cli_without_execution(self):
        sys.path.insert(0, str(SKILL / "scripts"))
        try:
            spec = importlib.util.spec_from_file_location("ezone_documentation_test", SKILL / "scripts/ezone.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            original = argparse.ArgumentParser.parse_args
            commands = []
            for document in (SKILL / "references").glob("*.md"):
                commands.extend(line.strip()[3:] for line in document.read_text().splitlines() if line.startswith("ez "))
            self.assertTrue(commands)
            class Parsed(Exception):
                pass
            def parse_only(parser, args=None, namespace=None):
                original(parser, args, namespace)
                raise Parsed()
            for command in commands:
                with self.subTest(command=command), patch.object(argparse.ArgumentParser, "parse_args", parse_only):
                    with self.assertRaises(Parsed):
                        module.main(["--host", "https://example.test", "--repo", "123", "--company", "example", "--json", *shlex.split(command)])
        finally:
            sys.path.pop(0)

    def test_first_use_from_copied_skill_with_isolated_home(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            skill = root / 'shared/ezone'
            shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns('__pycache__'))
            home, project = root / 'home', root / 'project'
            home.mkdir()
            project.mkdir()
            (project / '.git').write_text('gitdir: /unused/worktree')
            config = json.loads((skill / 'assets/ezone.example.json').read_text())
            config.update(host='https://example.test', repo='123', company='acme')
            (project / '.ezone.json').write_text(json.dumps(config))
            nested = project / 'src'
            nested.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith('EZONE_') and k != 'PYTHONPATH'}
            env['HOME'] = str(home)
            entry = skill / 'scripts/ezone.py'
            def cli(*args, script=None):
                command = [sys.executable, '-E', '-s']
                command += ['-c', script, str(entry)] if script else [str(entry), *args]
                result = subprocess.run(command, cwd=nested, env=env, text=True, capture_output=True)
                self.assertNotIn('synthetic-personal-secret', result.stdout + result.stderr)
                return result
            # 外部认证探测由合成响应隔离，配置、存盘及跨进程读取均执行真实实现。
            login = """import io, json, runpy, sys
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
import ezone
with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value='synthetic-personal-secret'), patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'{"code":0,"data":[]}')):
    raise SystemExit(ezone.main(['auth', 'login']))
"""
            result = cli(script=login)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = cli('doctor')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['token_source'], 'credentials')
            self.assertTrue((home / '.config/ezone/credentials.json').is_file())
            result = cli('auth', 'logout')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['removed'])
            self.assertFalse(json.loads(cli('doctor').stdout)['token_present'])
            result = cli('auth', 'status')
            self.assertEqual(result.returncode, 4)
            self.assertIn('auth login', result.stderr)


if __name__ == "__main__":
    unittest.main()
