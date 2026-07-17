from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.agent_manager import cli as instructions_cli
from tools.agent_manager import core, instructions
from tools.agent_manager.cli import main
from tools.agent_manager.instructions import (
    InstructionBatchResult,
    InstructionPlanError,
    InstructionResult,
    InvalidInstructionSource,
    InstructionState,
    apply_instruction_plan,
    build_instruction_targets,
    plan_instruction_adoption,
    plan_instruction_set,
    scan_incomplete_transactions,
    scan_instructions,
    validate_instruction_source,
)


SOURCE_BYTES = b"# Repository instructions\n\nKeep changes focused.\n"


def build_repository(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    home = root / "home"
    repo.mkdir(parents=True)
    home.mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    (repo / "skills").mkdir()
    (repo / "AGENTS.md").write_bytes(SOURCE_BYTES)
    return repo.resolve(), home.resolve()


def status_for(scan, key: str):
    return next(status for status in scan.targets if status.key == key)


def filesystem_manifest(root: Path) -> tuple[tuple[object, ...], ...]:
    entries: list[tuple[object, ...]] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in sorted((*names, *filenames)):
            path = base / name
            relative = path.relative_to(root)
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                entries.append((str(relative), "symlink", os.readlink(path)))
            elif stat.S_ISDIR(metadata.st_mode):
                entries.append((str(relative), "directory", stat.S_IMODE(metadata.st_mode)))
            elif stat.S_ISREG(metadata.st_mode):
                entries.append(
                    (str(relative), "file", stat.S_IMODE(metadata.st_mode), path.read_bytes())
                )
            else:
                entries.append((str(relative), "special", stat.S_IMODE(metadata.st_mode)))
    return tuple(entries)


def direct_link(path: Path, source: Path) -> bool:
    if not path.is_symlink():
        return False
    raw = Path(os.readlink(path))
    absolute_raw = raw if raw.is_absolute() else path.parent / raw
    return absolute_raw.resolve(strict=True) == source.resolve(strict=True)


def create_instruction_shape(
    home: Path,
    repo: Path,
    key: str,
    shape: str,
) -> Path:
    target = next(item.path for item in build_instruction_targets(home) if item.key == key)
    source = repo / "AGENTS.md"
    if shape == "missing":
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if shape == "enabled":
        target.symlink_to(source)
    elif shape == "indirect-link":
        bridge = home / ".agents/bridge.md"
        bridge.parent.mkdir(parents=True, exist_ok=True)
        bridge.symlink_to(source)
        target.symlink_to(bridge)
    elif shape == "matching-copy":
        target.write_bytes(SOURCE_BYTES)
    elif shape == "conflict":
        target.write_bytes(b"different bytes\n")
    elif shape == "foreign-link":
        foreign = home.parent / f"{key}-foreign.md"
        foreign.write_bytes(b"foreign\n")
        target.symlink_to(foreign)
    elif shape == "broken":
        target.symlink_to(target.parent / "missing.md")
    elif shape == "directory":
        target.mkdir()
    elif shape == "special":
        os.mkfifo(target)
    else:
        raise AssertionError(f"unknown test shape: {shape}")
    return target


def create_instruction_parents(home: Path, *keys: str) -> None:
    selected = set(keys)
    for target in build_instruction_targets(home):
        if not selected or target.key in selected:
            target.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)


def enable_other_instruction_targets(home: Path, repo: Path, *excluded: str) -> None:
    skipped = set(excluded)
    for target in build_instruction_targets(home):
        if target.key not in skipped:
            create_instruction_shape(home, repo, target.key, "enabled")


class InstructionCliContractTests(unittest.TestCase):
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

    def test_set_preview_exposes_review_fields_without_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_parents(home, "codex")

            code, payload = self.invoke(
                ["instructions", "set", "--target", "codex", "--on", "--json"],
                repo,
                home,
            )

            self.assertEqual(code, 0)
            self.assertEqual(payload["mode"], "plan")
            self.assertEqual(payload["changes"][0]["key"], "codex")
            self.assertRegex(payload["fingerprint"], r"^[0-9a-f]{64}$")
            self.assertTrue(payload["snapshot_path"].endswith(f"instructions-{payload['fingerprint']}.json"))
            self.assertNotIn("results", payload)
            self.assertFalse(os.path.lexists(home / ".codex/AGENTS.md"))

    def test_status_json_retains_exact_instruction_surface_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))

            code, payload = self.invoke(
                ["instructions", "status", "--json"], repo, home
            )

        self.assertEqual(code, 0)
        surfaces = {
            target["key"]: target.get("surfaces")
            for target in payload["instructions"]["targets"]
        }
        self.assertEqual(
            surfaces,
            {
                "shared": [
                    "claude-desktop",
                    "claude-cli",
                    "codex-desktop",
                    "codex-cli",
                    "copilot-cli",
                    "antigravity-desktop",
                    "antigravity-cli",
                ],
                "claude": ["claude-desktop", "claude-cli"],
                "codex": ["codex-desktop", "codex-cli"],
                "copilot": ["copilot-cli"],
                "antigravity": ["antigravity-desktop", "antigravity-cli"],
            },
        )

    def test_replace_preview_and_apply_preserve_the_reviewed_plan_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_parents(home)
            create_instruction_shape(home, repo, "codex", "conflict")
            enable_other_instruction_targets(home, repo, "codex")

            preview_code, preview = self.invoke(
                ["instructions", "adopt", "--replace-existing", "--json"],
                repo,
                home,
            )
            apply_code, applied = self.invoke(
                [
                    "instructions", "adopt", "--replace-existing", "--apply",
                    "--expect-fingerprint", preview["fingerprint"], "--json",
                ],
                repo,
                home,
            )

            self.assertEqual((preview_code, apply_code), (0, 0))
            self.assertEqual(applied["changes"], preview["changes"])
            self.assertEqual(applied["fingerprint"], preview["fingerprint"])
            self.assertEqual(applied["snapshot_path"], preview["snapshot_path"])
            self.assertIn("results", applied)
            self.assertTrue(direct_link(home / ".codex/AGENTS.md", repo / "AGENTS.md"))

    def test_post_apply_rescan_failure_preserves_the_execution_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = build_repository(root)
            create_instruction_parents(home, "codex")
            preview_code, preview = self.invoke(
                ["instructions", "set", "--target", "codex", "--on", "--json"],
                repo,
                home,
            )
            self.assertEqual(preview_code, 0)
            target = home / ".codex/AGENTS.md"
            result = InstructionBatchResult(
                True,
                (InstructionResult(True, "applied", "codex", target, "created link"),),
                Path(preview["snapshot_path"]),
            )
            initial_state = instructions_cli.build_agent_state(
                repo,
                home,
                lambda _: None,
                root / "Applications",
            )
            output = io.StringIO()
            with (
                patch(
                    "tools.agent_manager.cli.build_agent_state",
                    side_effect=[initial_state, OSError("post scan failed")],
                ),
                patch(
                    "tools.agent_manager.cli.apply_instruction_plan",
                    return_value=result,
                ) as apply_mock,
            ):
                code = main(
                    [
                        "instructions", "set", "--target", "codex", "--on",
                        "--apply", "--expect-fingerprint", preview["fingerprint"], "--json",
                    ],
                    home=home,
                    repo_root=repo,
                    stdout=output,
                    which=lambda _: None,
                    applications=root / "Applications",
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            apply_mock.assert_called_once()
            self.assertEqual(payload["changes"], preview["changes"])
            self.assertEqual(payload["fingerprint"], preview["fingerprint"])
            self.assertEqual(payload["snapshot_path"], preview["snapshot_path"])
            self.assertEqual(payload["results"][0]["code"], "applied")
            self.assertEqual(payload["code"], "post-apply-verification-failed")
            self.assertIn("apply completed", payload["message"])
            self.assertIn("post scan failed", payload["message"])

    def test_text_previews_print_executable_instruction_next_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_parents(home)
            create_instruction_shape(home, repo, "codex", "conflict")
            enable_other_instruction_targets(home, repo, "codex")
            cases = (
                (
                    ["instructions", "set", "--target", "shared", "--off"],
                    "agent-manager instructions set --target shared --off --apply --expect-fingerprint ",
                ),
                (
                    ["instructions", "adopt", "--replace-existing"],
                    "agent-manager instructions adopt --replace-existing --apply --expect-fingerprint ",
                ),
            )
            for argv, prefix in cases:
                with self.subTest(argv=argv):
                    output = io.StringIO()
                    code = main(
                        argv,
                        home=home,
                        repo_root=repo,
                        stdout=output,
                        which=lambda _: None,
                        applications=root / "Applications",
                    )
                    self.assertEqual(code, 0)
                    next_line = next(
                        line for line in output.getvalue().splitlines()
                        if line.startswith("Next: ")
                    )
                    self.assertTrue(next_line.startswith(f"Next: {prefix}"))
                    self.assertRegex(next_line, r"[0-9a-f]{64}$")

    def test_blocked_text_preview_prints_the_parent_fix_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = build_repository(root)
            output = io.StringIO()

            code = main(
                ["instructions", "set", "--target", "codex", "--on"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda _: None,
                applications=root / "Applications",
            )

            self.assertEqual(code, 1)
            self.assertIn(
                f"Next: mkdir -m 700 {home / '.codex'}\n",
                output.getvalue(),
            )
            self.assertNotIn("repeat the command", output.getvalue())


class AtomicInstallPrimitiveTests(unittest.TestCase):
    def test_link_noreplace_preserves_regular_file_and_rejects_competitor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup = root / "backup"
            target = root / "target"
            backup.write_bytes(b"\xff\x00original\n")
            backup.chmod(0o640)
            before = backup.stat()
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                core.install_backup_noreplace(directory_fd, backup.name, target.name)
            finally:
                os.close(directory_fd)

            installed = target.stat()
            self.assertFalse(backup.exists())
            self.assertEqual(installed.st_ino, before.st_ino)
            self.assertEqual(stat.S_IMODE(installed.st_mode), 0o640)
            self.assertEqual(target.read_bytes(), b"\xff\x00original\n")

            retained = root / "retained"
            retained.write_bytes(b"retained\n")
            target.write_bytes(b"competitor\n")
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                with self.assertRaises(FileExistsError):
                    core.install_backup_noreplace(directory_fd, retained.name, target.name)
            finally:
                os.close(directory_fd)
            self.assertEqual(target.read_bytes(), b"competitor\n")
            self.assertEqual(retained.read_bytes(), b"retained\n")

    def test_link_noreplace_preserves_symlink_itself_without_following(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            foreign = root / "foreign"
            foreign.write_bytes(b"foreign\n")
            backup = root / "backup"
            target = root / "target"
            backup.symlink_to("foreign")
            before = backup.lstat()
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                core.install_backup_noreplace(directory_fd, backup.name, target.name)
            finally:
                os.close(directory_fd)

            self.assertFalse(os.path.lexists(backup))
            self.assertTrue(target.is_symlink())
            self.assertEqual(os.readlink(target), "foreign")
            self.assertEqual(target.lstat().st_ino, before.st_ino)
            self.assertNotEqual(target.lstat().st_ino, foreign.stat().st_ino)


class InstructionPlanTests(unittest.TestCase):
    def test_set_off_blocks_link_through_an_intermediate_directory_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            alias = root / "repo-alias"
            alias.symlink_to(repo, target_is_directory=True)
            target = home / ".codex/AGENTS.md"
            target.parent.mkdir()
            target.symlink_to(alias / "AGENTS.md")

            plan = plan_instruction_set(
                scan_instructions(repo, home), ["codex"], False, root / "state"
            )

        self.assertEqual(plan.changes[0].action, "blocked")
        self.assertEqual(plan.changes[0].reason, "only a direct managed link can be removed")
        self.assertIsNone(plan.snapshot_path)

    def test_missing_parent_is_blocked_and_apply_never_enters_mkdir_swap_race(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            plan = plan_instruction_set(
                scan_instructions(repo, home), ["shared"], True, root / "state"
            )
            parent = home / ".agents"
            moved_parent = home / ".agents-manager-created"
            real_mkdir = instructions.os.mkdir
            mkdir_calls = 0

            def swap_after_mkdir(path, *args, **kwargs):
                nonlocal mkdir_calls
                mkdir_calls += 1
                result = real_mkdir(path, *args, **kwargs)
                parent.rename(moved_parent)
                real_mkdir(path, *args, **kwargs)
                return result

            with patch(
                "tools.agent_manager.instructions.os.mkdir",
                side_effect=swap_after_mkdir,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            change = plan.changes[0]
            self.assertEqual(change.action, "blocked")
            self.assertEqual(change.reason, "parent-missing")
            self.assertEqual(change.parent_expected.kind, "missing")
            self.assertIsNone(plan.snapshot_path)
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "blocked")
            self.assertEqual(mkdir_calls, 0)
            self.assertFalse(parent.exists())
            self.assertFalse(moved_parent.exists())

    def test_existing_parent_identity_is_reviewed_and_changes_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            parent = home / ".agents"
            parent.mkdir(mode=0o700)
            first = plan_instruction_set(
                scan_instructions(repo, home), ["shared"], True, root / "state"
            )
            first_expected = first.changes[0].parent_expected

            parent.rmdir()
            parent.mkdir(mode=0o700)
            second = plan_instruction_set(
                scan_instructions(repo, home), ["shared"], True, root / "state"
            )

            self.assertEqual(first_expected.kind, "directory")
            self.assertIsNotNone(first_expected.device)
            self.assertIsNotNone(first_expected.inode)
            self.assertNotEqual(
                (first_expected.device, first_expected.inode),
                (
                    second.changes[0].parent_expected.device,
                    second.changes[0].parent_expected.inode,
                ),
            )
            self.assertNotEqual(first.fingerprint, second.fingerprint)

    def test_non_directory_parents_are_blocked_with_stable_reason(self) -> None:
        for shape, expected_kind in (
            ("file", "file"),
            ("symlink", "symlink"),
            ("special", "special"),
        ):
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                parent = home / ".agents"
                if shape == "file":
                    parent.write_bytes(b"not a directory\n")
                elif shape == "symlink":
                    external = root / "external"
                    external.mkdir()
                    parent.symlink_to(external)
                else:
                    os.mkfifo(parent)

                plan = plan_instruction_set(
                    scan_instructions(repo, home), ["shared"], True, root / "state"
                )

                change = plan.changes[0]
                self.assertEqual(change.action, "blocked")
                self.assertEqual(change.reason, "parent-not-directory")
                self.assertEqual(change.parent_expected.kind, expected_kind)
                self.assertIsNone(plan.snapshot_path)

    def test_set_on_action_matrix(self) -> None:
        expected = {
            "missing": "create",
            "enabled": "no-op",
            "indirect-link": "blocked",
            "matching-copy": "blocked",
            "conflict": "blocked",
            "broken": "blocked",
        }
        for shape, action in expected.items():
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                create_instruction_shape(home, repo, "codex", shape)
                if shape == "missing":
                    create_instruction_parents(home, "codex")

                plan = plan_instruction_set(
                    scan_instructions(repo, home),
                    ["codex"],
                    True,
                    root / "state",
                )

                self.assertEqual(plan.changes[0].action, action)

    def test_set_off_action_matrix(self) -> None:
        expected = {
            "missing": "no-op",
            "enabled": "remove",
            "indirect-link": "blocked",
            "matching-copy": "blocked",
            "conflict": "blocked",
            "broken": "blocked",
        }
        for shape, action in expected.items():
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                create_instruction_shape(home, repo, "codex", shape)
                if shape == "missing":
                    create_instruction_parents(home, "codex")

                plan = plan_instruction_set(
                    scan_instructions(repo, home),
                    ["codex"],
                    False,
                    root / "state",
                )

                self.assertEqual(plan.changes[0].action, action)

    def test_adoption_action_matrix_without_replace(self) -> None:
        expected = {
            "missing": "create",
            "enabled": "no-op",
            "indirect-link": "replace",
            "matching-copy": "replace",
            "conflict": "blocked",
            "broken": "blocked",
        }
        for shape, action in expected.items():
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                create_instruction_shape(home, repo, "codex", shape)
                if shape == "missing":
                    create_instruction_parents(home, "codex")

                plan = plan_instruction_adoption(
                    scan_instructions(repo, home),
                    root / "state",
                    replace_existing=False,
                )

                change = next(item for item in plan.changes if item.key == "codex")
                self.assertEqual(change.action, action)

    def test_adoption_replace_accepts_files_and_links_but_not_directories_or_specials(self) -> None:
        shapes = {
            "shared": "conflict",
            "claude": "foreign-link",
            "codex": "broken",
            "copilot": "directory",
            "antigravity": "special",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            for key, shape in shapes.items():
                create_instruction_shape(home, repo, key, shape)

            plan = plan_instruction_adoption(
                scan_instructions(repo, home),
                root / "state",
                replace_existing=True,
            )

        self.assertEqual(
            {change.key: change.action for change in plan.changes},
            {
                "shared": "replace",
                "claude": "replace",
                "codex": "replace",
                "copilot": "unsupported-target",
                "antigravity": "unsupported-target",
            },
        )

    def test_plan_is_read_only_deterministic_and_uses_full_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            target = create_instruction_shape(home, repo, "codex", "conflict")
            enable_other_instruction_targets(home, repo, "codex")
            target.write_bytes(b"\xff\x00rules\n")
            before = filesystem_manifest(root)
            scan = scan_instructions(repo, home)

            left = plan_instruction_adoption(scan, root / "state", replace_existing=True)
            right = plan_instruction_adoption(scan, root / "state", replace_existing=True)

            self.assertEqual(left, right)
            self.assertRegex(left.fingerprint, r"^[0-9a-f]{64}$")
            self.assertEqual(
                left.snapshot_path,
                root / "state/snapshots" / f"instructions-{left.fingerprint}.json",
            )
            expected = next(item.expected for item in left.changes if item.key == "codex")
            self.assertEqual(base64.b64decode(expected.content_base64 or ""), b"\xff\x00rules\n")
            self.assertEqual(filesystem_manifest(root), before)

    def test_no_write_plan_has_no_snapshot_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_shape(home, repo, "codex", "enabled")

            plan = plan_instruction_set(
                scan_instructions(repo, home), ["codex"], True, root / "state"
            )

        self.assertIsNone(plan.snapshot_path)

    def test_blocked_mixed_plan_is_stable_and_does_not_publish_snapshot_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_parents(home, "shared")
            create_instruction_shape(home, repo, "codex", "conflict")
            enable_other_instruction_targets(home, repo, "shared", "codex")
            scan = scan_instructions(repo, home)

            left = plan_instruction_adoption(
                scan, root / "state", replace_existing=False
            )
            right = plan_instruction_adoption(
                scan, root / "state", replace_existing=False
            )

            self.assertEqual(left.fingerprint, right.fingerprint)
            self.assertEqual(
                {change.key: change.action for change in left.changes},
                {
                    "shared": "create",
                    "claude": "no-op",
                    "codex": "blocked",
                    "copilot": "no-op",
                    "antigravity": "no-op",
                },
            )
            self.assertIsNone(left.snapshot_path)
            home_before = filesystem_manifest(home)
            result = apply_instruction_plan(
                left, home, expected_fingerprint=left.fingerprint
            )
            self.assertFalse(result.ok)
            self.assertIsNone(result.snapshot_path)
            self.assertEqual(
                [(item.key, item.code, item.path) for item in result.results],
                [
                    (
                        change.key,
                        "blocked" if change.key == "codex" else "not-applied",
                        change.target,
                    )
                    for change in left.changes
                ],
            )
            self.assertTrue(all(not item.ok for item in result.results))
            self.assertEqual(filesystem_manifest(home), home_before)
            self.assertFalse((home / ".agents/AGENTS.md").exists())
            self.assertFalse((root / "state").exists())

    def test_rejects_unknown_duplicate_and_invalid_source_with_stable_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            scan = scan_instructions(repo, home)
            cases = (
                (["unknown"], "unknown-target"),
                (["codex", " CODEX "], "duplicate-target"),
            )
            for keys, code in cases:
                with self.subTest(code=code):
                    with self.assertRaises(InstructionPlanError) as raised:
                        plan_instruction_set(scan, keys, True, root / "state")
                    self.assertEqual(raised.exception.code, code)

            (repo / "AGENTS.md").unlink()
            with self.assertRaises(InstructionPlanError) as raised:
                plan_instruction_set(
                    scan_instructions(repo, home), ["codex"], True, root / "state"
                )
            self.assertEqual(raised.exception.code, "invalid-source")


class InstructionApplyTests(unittest.TestCase):
    def test_existing_parent_replaced_after_plan_is_state_changed_without_leaf_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            parent = home / ".agents"
            parent.mkdir(mode=0o700)
            plan = plan_instruction_set(
                scan_instructions(repo, home), ["shared"], True, root / "state"
            )
            reviewed = plan.changes[0].parent_expected
            moved = home / ".agents-reviewed"
            parent.rename(moved)
            parent.mkdir(mode=0o700)

            result = apply_instruction_plan(
                plan, home, expected_fingerprint=plan.fingerprint
            )

            self.assertEqual(reviewed.kind, "directory")
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertFalse((parent / "AGENTS.md").exists())
            self.assertFalse((moved / "AGENTS.md").exists())

    def test_stable_existing_parent_create_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            parent = home / ".agents"
            parent.mkdir(mode=0o700)
            plan = plan_instruction_set(
                scan_instructions(repo, home), ["shared"], True, root / "state"
            )

            result = apply_instruction_plan(
                plan, home, expected_fingerprint=plan.fingerprint
            )

            self.assertTrue(result.ok)
            self.assertEqual(result.results[0].code, "applied")
            self.assertTrue(direct_link(parent / "AGENTS.md", repo / "AGENTS.md"))

    def build_single_write_plan(
        self,
        root: Path,
        action: str,
    ) -> tuple[Path, Path, Path, object]:
        repo, home = build_repository(root)
        if action == "create":
            create_instruction_parents(home, "codex")
            target = next(
                item.path for item in build_instruction_targets(home) if item.key == "codex"
            )
            plan = plan_instruction_set(
                scan_instructions(repo, home), ["codex"], True, root / "state"
            )
        elif action == "remove":
            target = create_instruction_shape(home, repo, "codex", "enabled")
            plan = plan_instruction_set(
                scan_instructions(repo, home), ["codex"], False, root / "state"
            )
        elif action == "replace":
            for key in ("shared", "claude", "copilot", "antigravity"):
                create_instruction_shape(home, repo, key, "enabled")
            target = create_instruction_shape(home, repo, "codex", "conflict")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )
        else:
            raise AssertionError(f"unknown action: {action}")
        self.assertEqual(
            [change.action for change in plan.changes if change.action != "no-op"],
            [action],
        )
        return repo, home, target, plan

    def test_prepared_install_rejects_byte_identical_different_inode_aba(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo, home, _target, plan = self.build_single_write_plan(root, "replace")
            before_home = filesystem_manifest(home)
            real_install = instructions.install_backup_noreplace
            competitor_inode: int | None = None
            swapped = False

            def replace_installed_prepared(directory_fd: int, backup: str, target: str):
                nonlocal competitor_inode, swapped
                result = real_install(directory_fd, backup, target)
                if target == plan.snapshot_path.name and not swapped:
                    swapped = True
                    installed = plan.snapshot_path.read_bytes()
                    competitor = plan.snapshot_path.with_name("prepared-competitor.json")
                    competitor.write_bytes(installed)
                    competitor.chmod(0o600)
                    competitor_inode = competitor.stat().st_ino
                    os.replace(competitor, plan.snapshot_path)
                return result

            with patch(
                "tools.agent_manager.instructions.install_backup_noreplace",
                side_effect=replace_installed_prepared,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertTrue(swapped)
            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "snapshot-failed")
            self.assertEqual(filesystem_manifest(home), before_home)
            self.assertEqual(plan.snapshot_path.stat().st_ino, competitor_inode)
            self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "prepared")

    def test_recovery_required_never_reports_applied_entries_as_rolled_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_parents(home)
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=False
            )
            recovery_paths = (root / "state/snapshots/manual-recovery",)
            failure = instructions._SnapshotCommitFailure(
                "forced recovery requirement",
                recovery_state=instructions._SnapshotRecoveryState.RECOVERY_REQUIRED,
                recovery_paths=recovery_paths,
            )

            with patch(
                "tools.agent_manager.instructions._mark_snapshot_committed",
                side_effect=failure,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertTrue(
                all(target.path.is_symlink() for target in build_instruction_targets(home))
            )
            write_results = [item for item in result.results if item.key != "*"]
            self.assertEqual(
                {item.code for item in write_results},
                {"rollback-skipped"},
            )
            self.assertTrue(
                all(item.recovery_paths == recovery_paths for item in write_results)
            )
            batch_failure = next(item for item in result.results if item.key == "*")
            self.assertEqual(batch_failure.code, "apply-failed")
            self.assertEqual(batch_failure.path, plan.snapshot_path)
            self.assertEqual(batch_failure.recovery_paths, recovery_paths)

    def test_committed_recovery_cleanup_failure_still_rolls_back_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo, home, target, plan = self.build_single_write_plan(root, "replace")
            original = target.read_bytes()
            real_fsync = instructions._fsync_snapshot_directory
            real_unlink = instructions.os.unlink
            committed_fsync_failed = False

            def fail_committed_fsync(directory_fd: int):
                nonlocal committed_fsync_failed
                if plan.snapshot_path.exists():
                    payload = json.loads(plan.snapshot_path.read_text())
                    if payload.get("phase") == "committed" and not committed_fsync_failed:
                        committed_fsync_failed = True
                        raise OSError("committed directory fsync failed")
                return real_fsync(directory_fd)

            def retain_committed_recovery(path, *args, **kwargs):
                if str(path).endswith(".committed-failed"):
                    raise OSError("retain committed recovery")
                return real_unlink(path, *args, **kwargs)

            with (
                patch(
                    "tools.agent_manager.instructions._fsync_snapshot_directory",
                    side_effect=fail_committed_fsync,
                ),
                patch(
                    "tools.agent_manager.instructions.os.unlink",
                    side_effect=retain_committed_recovery,
                ),
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertTrue(committed_fsync_failed)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "prepared")
            retained = tuple(
                plan.snapshot_path.parent.glob(".agent-manager-*.committed-failed")
            )
            self.assertEqual(len(retained), 1)
            self.assertTrue(
                all(item.code != "rollback-skipped" for item in result.results)
            )
            self.assertIn(retained[0], result.results[-1].recovery_paths)

    def test_competitor_before_commit_barrier_aborts_all_write_actions(self) -> None:
        for action in ("create", "replace", "remove"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _repo, home, target, plan = self.build_single_write_plan(root, action)
                real_source_check = instructions._source_still_matches
                checks = 0

                def replace_before_barrier(current_plan):
                    nonlocal checks
                    checks += 1
                    if checks == 2:
                        if os.path.lexists(target):
                            target.unlink()
                        target.write_bytes(b"commit competitor\n")
                    return real_source_check(current_plan)

                with patch(
                    "tools.agent_manager.instructions._source_still_matches",
                    side_effect=replace_before_barrier,
                ):
                    result = apply_instruction_plan(
                        plan, home, expected_fingerprint=plan.fingerprint
                    )

                self.assertFalse(result.ok)
                self.assertEqual(target.read_bytes(), b"commit competitor\n")
                self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "prepared")
                if action in {"replace", "remove"}:
                    backups = list(target.parent.glob(".agent-manager-*.backup"))
                    self.assertEqual(len(backups), 1)
                    messages = " ".join(item.message for item in result.results)
                    self.assertIn(str(backups[0]), messages)

    def test_competitor_before_cleanup_retains_recovery_for_all_write_actions(self) -> None:
        for action in ("create", "replace", "remove"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _repo, home, target, plan = self.build_single_write_plan(root, action)
                real_commit = instructions._mark_snapshot_committed

                def replace_after_commit(*args, **kwargs):
                    result = real_commit(*args, **kwargs)
                    if os.path.lexists(target):
                        target.unlink()
                    target.write_bytes(b"cleanup competitor\n")
                    return result

                with patch(
                    "tools.agent_manager.instructions._mark_snapshot_committed",
                    side_effect=replace_after_commit,
                ):
                    result = apply_instruction_plan(
                        plan, home, expected_fingerprint=plan.fingerprint
                    )

                self.assertFalse(result.ok)
                self.assertEqual(target.read_bytes(), b"cleanup competitor\n")
                self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "committed")
                self.assertIn("cleanup-failed", [item.code for item in result.results])
                if action in {"replace", "remove"}:
                    backups = list(target.parent.glob(".agent-manager-*.backup"))
                    self.assertEqual(len(backups), 1)
                    messages = " ".join(item.message for item in result.results)
                    self.assertIn(str(backups[0]), messages)

    def test_cleanup_failure_is_attributed_only_to_its_transaction_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            shared = create_instruction_shape(home, repo, "shared", "conflict")
            claude = create_instruction_shape(home, repo, "claude", "conflict")
            enable_other_instruction_targets(home, repo, "shared", "claude")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )
            real_unlink = os.unlink
            shared_parent_inode = shared.parent.stat().st_ino
            failed = False

            def fail_shared_backup(path, *args, dir_fd=None, **kwargs):
                nonlocal failed
                is_shared_backup = (
                    not failed
                    and str(path).endswith(".backup")
                    and dir_fd is not None
                    and os.fstat(dir_fd).st_ino == shared_parent_inode
                )
                if is_shared_backup:
                    failed = True
                    raise OSError("shared backup cleanup denied")
                return real_unlink(path, *args, dir_fd=dir_fd, **kwargs)

            with patch(
                "tools.agent_manager.instructions.os.unlink",
                side_effect=fail_shared_backup,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            by_key = {item.key: item for item in result.results}
            shared_backups = tuple(shared.parent.glob(".agent-manager-*.backup"))
            claude_backups = tuple(claude.parent.glob(".agent-manager-*.backup"))

            self.assertFalse(result.ok)
            self.assertTrue(failed)
            self.assertEqual(by_key["shared"].code, "cleanup-failed")
            self.assertTrue(by_key["claude"].ok)
            self.assertEqual(by_key["claude"].code, "applied")
            self.assertEqual(by_key["claude"].recovery_paths, ())
            self.assertEqual(by_key["shared"].recovery_paths, shared_backups)
            self.assertIn("shared backup cleanup denied", by_key["shared"].message)
            self.assertEqual(claude_backups, ())
            self.assertTrue(direct_link(shared, repo / "AGENTS.md"))
            self.assertTrue(direct_link(claude, repo / "AGENTS.md"))

    def test_committed_directory_fsync_failure_restores_prepared_before_home_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo, home, target, plan = self.build_single_write_plan(root, "replace")
            original = target.read_bytes()
            real_fsync = instructions._fsync_snapshot_directory
            failed = False

            def fail_committed_fsync(directory_fd: int):
                nonlocal failed
                if plan.snapshot_path.exists():
                    payload = json.loads(plan.snapshot_path.read_text())
                    if payload.get("phase") == "committed" and not failed:
                        failed = True
                        raise OSError("committed directory fsync failed")
                return real_fsync(directory_fd)

            with patch(
                "tools.agent_manager.instructions._fsync_snapshot_directory",
                side_effect=fail_committed_fsync,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertTrue(failed)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "prepared")
            incomplete = scan_incomplete_transactions(root / "state")
            self.assertEqual(incomplete[0].path, plan.snapshot_path)

    def test_snapshot_competitor_is_not_overwritten_and_owned_prepared_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo, home, target, plan = self.build_single_write_plan(root, "replace")
            original = target.read_bytes()
            competitor_payload = {
                "phase": "prepared",
                "fingerprint": plan.fingerprint,
                "competitor": True,
            }
            competitor_bytes = json.dumps(competitor_payload, sort_keys=True).encode()
            real_write_temp = instructions._write_temp_snapshot
            writes = 0

            def swap_after_committed_temp(directory_fd: int, payload):
                nonlocal writes
                temporary = real_write_temp(directory_fd, payload)
                writes += 1
                if writes == 2:
                    competitor = plan.snapshot_path.with_name("competitor.json")
                    competitor.write_bytes(competitor_bytes)
                    os.replace(competitor, plan.snapshot_path)
                return temporary

            with patch(
                "tools.agent_manager.instructions._write_temp_snapshot",
                side_effect=swap_after_committed_temp,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(plan.snapshot_path.read_bytes(), competitor_bytes)
            recoveries = list(plan.snapshot_path.parent.glob(".agent-manager-*.prepared"))
            self.assertEqual(len(recoveries), 1)
            self.assertEqual(json.loads(recoveries[0].read_text())["phase"], "prepared")
            self.assertIn(str(recoveries[0]), " ".join(item.message for item in result.results))
            incomplete = scan_incomplete_transactions(root / "state")
            self.assertIn(recoveries[0], incomplete[0].recovery_paths)

    def test_blocked_batch_performs_no_snapshot_or_home_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_shape(home, repo, "codex", "conflict")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=False
            )
            before = filesystem_manifest(root)

            result = apply_instruction_plan(
                plan, home, expected_fingerprint=plan.fingerprint
            )

            self.assertFalse(result.ok)
            self.assertIn("blocked", [item.code for item in result.results])
            self.assertEqual(filesystem_manifest(root), before)

    def test_set_off_removes_only_the_reviewed_direct_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            target = create_instruction_shape(home, repo, "codex", "enabled")
            plan = plan_instruction_set(
                scan_instructions(repo, home), ["codex"], False, root / "state"
            )

            result = apply_instruction_plan(
                plan, home, expected_fingerprint=plan.fingerprint
            )

            self.assertTrue(result.ok, result.results)
            self.assertFalse(os.path.lexists(target))
            self.assertEqual(result.results[0].code, "applied")
            self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "committed")

    def test_replace_snapshot_is_byte_exact_and_committed_before_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            target = create_instruction_shape(home, repo, "codex", "conflict")
            enable_other_instruction_targets(home, repo, "codex")
            original = b"\xff\x00rules\n"
            target.write_bytes(original)
            target.chmod(0o640)
            state_dir = root / "state"
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), state_dir, replace_existing=True
            )

            result = apply_instruction_plan(
                plan, home, expected_fingerprint=plan.fingerprint
            )

            self.assertTrue(result.ok, result.results)
            self.assertTrue(direct_link(target, repo / "AGENTS.md"))
            self.assertEqual(os.readlink(target), str(plan.source))
            self.assertIsNotNone(result.snapshot_path)
            payload = json.loads(result.snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["phase"], "committed")
            self.assertEqual(stat.S_IMODE(result.snapshot_path.stat().st_mode), 0o600)
            entry = next(item for item in payload["targets"] if item["key"] == "codex")
            expected = entry["expected"]
            self.assertEqual(base64.b64decode(expected["content_base64"]), original)
            self.assertEqual(expected["mode"], 0o640)
            self.assertEqual(expected["sha256"], hashlib.sha256(original).hexdigest())

            restored = root / "restored"
            restored.write_bytes(base64.b64decode(expected["content_base64"]))
            restored.chmod(expected["mode"])
            self.assertEqual(restored.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(restored.stat().st_mode), 0o640)

    def test_five_target_adoption_preview_is_read_only_then_converges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            source = repo / "AGENTS.md"
            create_instruction_shape(home, repo, "shared", "enabled")
            create_instruction_shape(home, repo, "claude", "enabled")
            create_instruction_shape(home, repo, "codex", "conflict")
            create_instruction_shape(home, repo, "antigravity", "indirect-link")
            create_instruction_parents(home, "copilot")
            before = filesystem_manifest(home)

            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )

            self.assertEqual(filesystem_manifest(home), before)
            self.assertFalse(plan.snapshot_path.exists())
            self.assertEqual(len(plan.changes), 5)
            result = apply_instruction_plan(
                plan, home, expected_fingerprint=plan.fingerprint
            )

            self.assertTrue(result.ok, result.results)
            self.assertTrue(
                all(
                    direct_link(item.path, source)
                    for item in build_instruction_targets(home)
                )
            )
            self.assertEqual(len(list((root / "state/snapshots").glob("instructions-*.json"))), 1)

    def test_rejects_invalid_reviewed_fingerprints_before_writes(self) -> None:
        values = (None, "", "A" * 64, "0" * 63, "0" * 64)
        for value in values:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                target = create_instruction_shape(home, repo, "codex", "conflict")
                enable_other_instruction_targets(home, repo, "codex")
                plan = plan_instruction_adoption(
                    scan_instructions(repo, home), root / "state", replace_existing=True
                )
                before = filesystem_manifest(root)

                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=value  # type: ignore[arg-type]
                )

                self.assertFalse(result.ok)
                expected_code = "state-changed" if value == "0" * 64 else "invalid-fingerprint"
                self.assertEqual(result.results[0].code, expected_code)
                self.assertEqual(filesystem_manifest(root), before)
                self.assertTrue(target.is_file())

    def test_rejects_source_hash_change_and_target_identity_change(self) -> None:
        for mutation in ("source", "target"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                target = create_instruction_shape(home, repo, "codex", "conflict")
                enable_other_instruction_targets(home, repo, "codex")
                plan = plan_instruction_adoption(
                    scan_instructions(repo, home), root / "state", replace_existing=True
                )
                if mutation == "source":
                    (repo / "AGENTS.md").write_bytes(b"changed source\n")
                else:
                    replacement = target.with_suffix(".replacement")
                    replacement.write_bytes(target.read_bytes())
                    replacement.chmod(stat.S_IMODE(target.stat().st_mode))
                    os.replace(replacement, target)
                before = filesystem_manifest(root)

                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

                self.assertFalse(result.ok)
                self.assertEqual(result.results[0].code, "state-changed")
                self.assertEqual(filesystem_manifest(root), before)

    def test_snapshot_directory_and_fsync_failures_happen_before_home_mutation(self) -> None:
        for failure in ("mkdir", "fsync"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                target = create_instruction_shape(home, repo, "codex", "conflict")
                enable_other_instruction_targets(home, repo, "codex")
                plan = plan_instruction_adoption(
                    scan_instructions(repo, home), root / "state", replace_existing=True
                )
                before = filesystem_manifest(home)
                if failure == "mkdir":
                    context = patch(
                        "tools.agent_manager.instructions._ensure_snapshot_directory",
                        side_effect=OSError("mkdir failed"),
                    )
                else:
                    context = patch(
                        "tools.agent_manager.instructions._fsync_snapshot_directory",
                        side_effect=OSError("fsync failed"),
                    )
                with context:
                    result = apply_instruction_plan(
                        plan, home, expected_fingerprint=plan.fingerprint
                    )

                self.assertFalse(result.ok)
                self.assertEqual(result.results[0].code, "snapshot-failed")
                self.assertEqual(filesystem_manifest(home), before)
                self.assertTrue(target.is_file())

    def test_snapshot_permission_failure_is_permission_denied_before_home_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo, home, target, plan = self.build_single_write_plan(root, "create")
            before = filesystem_manifest(home)

            with patch(
                "tools.agent_manager.instructions._ensure_snapshot_directory",
                side_effect=PermissionError("snapshot directory denied"),
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertEqual(len(result.results), 1)
            self.assertEqual(result.results[0].key, "*")
            self.assertEqual(result.results[0].code, "permission-denied")
            self.assertEqual(result.results[0].path, plan.snapshot_path)
            self.assertIn("snapshot directory denied", result.results[0].message)
            self.assertEqual(filesystem_manifest(home), before)
            self.assertFalse(target.exists())
            self.assertFalse(plan.snapshot_path.exists())

    def test_snapshot_commit_permission_failure_is_attributed_to_snapshot_after_rollback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo, home, target, plan = self.build_single_write_plan(root, "create")
            before = filesystem_manifest(home)

            with patch(
                "tools.agent_manager.instructions._mark_snapshot_committed",
                side_effect=PermissionError("snapshot commit denied"),
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertEqual(
                [(item.key, item.code, item.path) for item in result.results],
                [
                    ("codex", "rolled-back", target),
                    ("*", "permission-denied", plan.snapshot_path),
                ],
            )
            self.assertEqual(filesystem_manifest(home), before)
            self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "prepared")

    def test_existing_prepared_and_committed_snapshots_are_never_overwritten(self) -> None:
        cases = (
            ("prepared", "incomplete-transaction"),
            ("committed", "snapshot-conflict"),
        )
        for phase, code in cases:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                create_instruction_shape(home, repo, "codex", "conflict")
                enable_other_instruction_targets(home, repo, "codex")
                plan = plan_instruction_adoption(
                    scan_instructions(repo, home), root / "state", replace_existing=True
                )
                plan.snapshot_path.parent.mkdir(parents=True)
                original = json.dumps({"phase": phase, "sentinel": "keep"})
                plan.snapshot_path.write_text(original, encoding="utf-8")
                before = filesystem_manifest(home)

                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

                self.assertFalse(result.ok)
                self.assertEqual(result.results[0].code, code)
                self.assertEqual(plan.snapshot_path.read_text(encoding="utf-8"), original)
                self.assertEqual(filesystem_manifest(home), before)

    def test_second_and_fourth_write_failures_reverse_all_earlier_changes(self) -> None:
        for fail_at in (2, 4):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                for target in build_instruction_targets(home):
                    create_instruction_shape(home, repo, target.key, "conflict")
                plan = plan_instruction_adoption(
                    scan_instructions(repo, home), root / "state", replace_existing=True
                )
                before = filesystem_manifest(home)
                real_install = instructions._install_direct_link
                calls = 0

                def fail_selected(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == fail_at:
                        raise OSError(f"write {fail_at} failed")
                    return real_install(*args, **kwargs)

                with patch(
                    "tools.agent_manager.instructions._install_direct_link",
                    side_effect=fail_selected,
                ):
                    result = apply_instruction_plan(
                        plan, home, expected_fingerprint=plan.fingerprint
                    )

                self.assertFalse(result.ok)
                self.assertEqual(filesystem_manifest(home), before)
                self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "prepared")

    def test_reverse_rollback_reports_replace_competitor_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            first = create_instruction_shape(home, repo, "shared", "conflict")
            create_instruction_shape(home, repo, "claude", "conflict")
            for key in ("codex", "copilot", "antigravity"):
                create_instruction_shape(home, repo, key, "enabled")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )
            self.assertEqual(
                [change.key for change in plan.changes if change.action == "replace"],
                ["shared", "claude"],
            )
            real_apply = instructions._apply_one
            calls = 0

            def replace_first_then_fail_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    first.unlink()
                    first.write_bytes(b"rollback competitor\n")
                    raise OSError("second replace failed")
                return real_apply(*args, **kwargs)

            with patch(
                "tools.agent_manager.instructions._apply_one",
                side_effect=replace_first_then_fail_second,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            first_result = next(item for item in result.results if item.key == "shared")
            backups = tuple(first.parent.glob(".agent-manager-*.backup"))
            self.assertFalse(result.ok)
            self.assertEqual(first.read_bytes(), b"rollback competitor\n")
            self.assertEqual(len(backups), 1)
            self.assertEqual(first_result.code, "rollback-incomplete")
            self.assertEqual(set(first_result.recovery_paths), {first, backups[0]})

    def test_reverse_rollback_reports_create_and_remove_competitors(self) -> None:
        for action in ("create", "remove"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                if action == "create":
                    create_instruction_parents(home, "shared", "claude")
                if action == "remove":
                    first = create_instruction_shape(home, repo, "shared", "enabled")
                    create_instruction_shape(home, repo, "claude", "enabled")
                    enabled = False
                else:
                    first = next(
                        target.path
                        for target in build_instruction_targets(home)
                        if target.key == "shared"
                    )
                    enabled = True
                plan = plan_instruction_set(
                    scan_instructions(repo, home),
                    ["shared", "claude"],
                    enabled,
                    root / "state",
                )
                self.assertEqual(
                    [
                        change.key
                        for change in plan.changes
                        if change.action == action
                    ],
                    ["shared", "claude"],
                )
                real_apply = instructions._apply_one
                calls = 0

                def complete_first_then_fail_second(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        if os.path.lexists(first):
                            first.unlink()
                        first.write_bytes(b"rollback competitor\n")
                        raise OSError(f"second {action} failed")
                    return real_apply(*args, **kwargs)

                with patch(
                    "tools.agent_manager.instructions._apply_one",
                    side_effect=complete_first_then_fail_second,
                ):
                    result = apply_instruction_plan(
                        plan, home, expected_fingerprint=plan.fingerprint
                    )

                first_result = next(
                    item for item in result.results if item.key == "shared"
                )
                backups = tuple(first.parent.glob(".agent-manager-*.backup"))
                expected_recovery = {first}
                if action == "remove":
                    self.assertEqual(len(backups), 1)
                    expected_recovery.add(backups[0])
                else:
                    self.assertEqual(backups, ())
                self.assertFalse(result.ok)
                self.assertEqual(first.read_bytes(), b"rollback competitor\n")
                self.assertEqual(first_result.code, "rollback-incomplete")
                self.assertEqual(
                    set(first_result.recovery_paths), expected_recovery
                )

    def test_reverse_rollback_fsync_failure_reports_target_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            first = create_instruction_shape(home, repo, "shared", "conflict")
            create_instruction_shape(home, repo, "claude", "conflict")
            for key in ("codex", "copilot", "antigravity"):
                create_instruction_shape(home, repo, key, "enabled")
            original = first.read_bytes()
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )
            real_apply = instructions._apply_one
            real_fsync = instructions.os.fsync
            calls = 0
            rollback_started = False
            rollback_fsync_failed = False

            def fail_second(*args, **kwargs):
                nonlocal calls, rollback_started
                calls += 1
                if calls == 2:
                    rollback_started = True
                    raise OSError("second replace failed")
                return real_apply(*args, **kwargs)

            def fail_rollback_fsync(descriptor: int):
                nonlocal rollback_fsync_failed
                if rollback_started and not rollback_fsync_failed:
                    rollback_fsync_failed = True
                    raise OSError("rollback fsync failed")
                return real_fsync(descriptor)

            with (
                patch(
                    "tools.agent_manager.instructions._apply_one",
                    side_effect=fail_second,
                ),
                patch(
                    "tools.agent_manager.instructions.os.fsync",
                    side_effect=fail_rollback_fsync,
                ),
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            first_result = next(item for item in result.results if item.key == "shared")
            self.assertTrue(rollback_fsync_failed)
            self.assertEqual(first.read_bytes(), original)
            self.assertEqual(first_result.code, "rollback-incomplete")
            self.assertEqual(first_result.recovery_paths, (first,))

    def test_post_replacement_verification_failure_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            target = create_instruction_shape(home, repo, "codex", "conflict")
            enable_other_instruction_targets(home, repo, "codex")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )
            before = filesystem_manifest(home)

            with patch(
                "tools.agent_manager.instructions._verify_direct_link",
                return_value=False,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertEqual(filesystem_manifest(home), before)
            codex = next(item for item in result.results if item.key == "codex")
            self.assertEqual(codex.code, "apply-failed")
            self.assertEqual(codex.recovery_paths, ())
            self.assertTrue(target.is_file())

    def test_competitor_is_never_overwritten_and_backup_path_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            first = create_instruction_shape(home, repo, "shared", "conflict")
            create_instruction_shape(home, repo, "claude", "conflict")
            enable_other_instruction_targets(home, repo, "shared", "claude")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )
            real_install = instructions._install_direct_link
            calls = 0

            def race_then_fail(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    first.unlink()
                    first.write_bytes(b"competitor\n")
                    raise OSError("later write failed")
                return real_install(*args, **kwargs)

            with patch(
                "tools.agent_manager.instructions._install_direct_link",
                side_effect=race_then_fail,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertEqual(first.read_bytes(), b"competitor\n")
            self.assertIn(".backup", " ".join(item.message for item in result.results))
            self.assertTrue(list(first.parent.glob(".agent-manager-*.backup")))

    def test_preexisting_parent_open_failure_has_no_created_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            parent = home / ".agents"
            parent.mkdir()
            plan = plan_instruction_set(
                scan_instructions(repo, home), ["shared"], True, root / "state"
            )
            real_open = instructions.os.open

            def fail_preexisting_parent_open(path, *args, **kwargs):
                if path == ".agents":
                    raise PermissionError("pre-existing parent open failed")
                return real_open(path, *args, **kwargs)

            with patch(
                "tools.agent_manager.instructions.os.open",
                side_effect=fail_preexisting_parent_open,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            shared = next(item for item in result.results if item.key == "shared")
            self.assertFalse(result.ok)
            self.assertTrue(parent.is_dir())
            self.assertEqual(shared.code, "permission-denied")
            self.assertEqual(shared.path, home / ".agents/AGENTS.md")
            self.assertIn("pre-existing parent open failed", shared.message)
            self.assertEqual(shared.recovery_paths, ())
            self.assertFalse(shared.path.exists())

    def test_parent_replaced_by_external_symlink_is_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            target = create_instruction_shape(home, repo, "shared", "conflict")
            enable_other_instruction_targets(home, repo, "shared")
            external = root / "external"
            external.mkdir()
            (external / target.name).write_bytes(b"external\n")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )
            real_check = instructions._parent_identity_matches
            changed = False
            checks = 0

            def replace_parent(*args, **kwargs):
                nonlocal changed, checks
                checks += 1
                if checks == 2 and not changed:
                    changed = True
                    os.rename(home / ".agents", home / ".agents-moved")
                    (home / ".agents").symlink_to(external)
                return real_check(*args, **kwargs)

            with patch(
                "tools.agent_manager.instructions._parent_identity_matches",
                side_effect=replace_parent,
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertEqual((external / target.name).read_bytes(), b"external\n")
            self.assertEqual(
                (home / ".agents-moved/AGENTS.md").read_bytes(),
                b"different bytes\n",
            )

    def test_commit_marker_failure_rolls_back_and_leaves_prepared_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_shape(home, repo, "codex", "conflict")
            enable_other_instruction_targets(home, repo, "codex")
            before = filesystem_manifest(home)
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=True
            )

            with patch(
                "tools.agent_manager.instructions._mark_snapshot_committed",
                side_effect=OSError("commit marker failed"),
            ):
                result = apply_instruction_plan(
                    plan, home, expected_fingerprint=plan.fingerprint
                )

            self.assertFalse(result.ok)
            self.assertEqual(filesystem_manifest(home), before)
            codex = next(item for item in result.results if item.key == "codex")
            self.assertEqual(codex.code, "rolled-back")
            self.assertEqual(codex.recovery_paths, ())
            batch_failure = next(item for item in result.results if item.key == "*")
            self.assertEqual(batch_failure.code, "apply-failed")
            self.assertEqual(batch_failure.path, plan.snapshot_path)
            problem = instructions_cli._batch_problem(result)
            self.assertIsNotNone(problem)
            self.assertEqual(problem[0], "apply-failed")
            self.assertIs(problem[1], batch_failure)
            self.assertEqual(json.loads(plan.snapshot_path.read_text())["phase"], "prepared")

    def test_repeated_apply_via_fresh_plan_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            create_instruction_parents(home, "codex")
            first = plan_instruction_set(
                scan_instructions(repo, home), ["codex"], True, root / "state"
            )
            first_result = apply_instruction_plan(
                first, home, expected_fingerprint=first.fingerprint
            )
            after_first = filesystem_manifest(home)

            second = plan_instruction_set(
                scan_instructions(repo, home), ["codex"], True, root / "state"
            )
            second_result = apply_instruction_plan(
                second, home, expected_fingerprint=second.fingerprint
            )

            self.assertTrue(first_result.ok, first_result.results)
            self.assertTrue(second_result.ok, second_result.results)
            self.assertEqual(second_result.results[0].code, "no-op")
            self.assertIsNone(second.snapshot_path)
            self.assertEqual(filesystem_manifest(home), after_first)


class IncompleteTransactionTests(unittest.TestCase):
    def test_standalone_prepared_collects_target_backup_and_sibling_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "state/snapshots"
            snapshots.mkdir(parents=True)
            target = root / "home/.codex/AGENTS.md"
            target.parent.mkdir(parents=True)
            backup = target.parent / ".agent-manager-original.backup"
            backup.write_bytes(b"original\n")
            fingerprint = "c" * 64
            payload = {
                "version": 1,
                "phase": "prepared",
                "fingerprint": fingerprint,
                "targets": [{"key": "codex", "path": str(target)}],
            }
            prepared = snapshots / ".agent-manager-isolated.prepared"
            prepared.write_text(json.dumps(payload), encoding="utf-8")
            sibling = snapshots / ".agent-manager-sibling.committed-failed"
            sibling_payload = dict(payload)
            sibling_payload["phase"] = "committed"
            sibling.write_text(json.dumps(sibling_payload), encoding="utf-8")

            incomplete = scan_incomplete_transactions(root / "state")

            self.assertEqual(len(incomplete), 1)
            self.assertEqual(incomplete[0].path, prepared)
            self.assertEqual(
                set(incomplete[0].recovery_paths),
                {prepared, backup, sibling},
            )

    def test_reports_standalone_prepared_recovery_after_commit_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "state/snapshots"
            snapshots.mkdir(parents=True)
            recovery = snapshots / ".agent-manager-deadbeef.prepared"
            recovery.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "phase": "prepared",
                        "fingerprint": "b" * 64,
                        "targets": [],
                    }
                ),
                encoding="utf-8",
            )
            before = filesystem_manifest(root)

            incomplete = scan_incomplete_transactions(root / "state")

            self.assertEqual(len(incomplete), 1)
            self.assertEqual(incomplete[0].path, recovery)
            self.assertEqual(incomplete[0].recovery_paths, (recovery,))
            self.assertEqual(filesystem_manifest(root), before)

    def test_reports_prepared_snapshot_and_retained_backups_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_dir = root / "state"
            snapshots = state_dir / "snapshots"
            snapshots.mkdir(parents=True)
            target = root / "home/.codex/AGENTS.md"
            target.parent.mkdir(parents=True)
            backup = target.parent / ".agent-manager-deadbeef.backup"
            backup.write_bytes(b"recovery\n")
            record = snapshots / f"instructions-{'a' * 64}.json"
            record.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "phase": "prepared",
                        "fingerprint": "a" * 64,
                        "targets": [{"key": "codex", "path": str(target)}],
                    }
                ),
                encoding="utf-8",
            )
            before_state = filesystem_manifest(root)

            incomplete = scan_incomplete_transactions(state_dir)

            self.assertEqual(len(incomplete), 1)
            self.assertEqual(incomplete[0].code, "incomplete-transaction")
            self.assertEqual(incomplete[0].path, record)
            self.assertEqual(incomplete[0].recovery_paths, (backup,))
            self.assertEqual(filesystem_manifest(root), before_state)


class InstructionTargetTests(unittest.TestCase):
    def test_builds_only_the_five_approved_targets_in_stable_order(self) -> None:
        home = Path("/tmp/agent-manager-home")
        targets = build_instruction_targets(home)

        self.assertEqual(
            [target.key for target in targets],
            ["shared", "claude", "codex", "copilot", "antigravity"],
        )
        self.assertEqual(
            [target.path for target in targets],
            [
                home / ".agents/AGENTS.md",
                home / ".claude/CLAUDE.md",
                home / ".codex/AGENTS.md",
                home / ".copilot/copilot-instructions.md",
                home / ".gemini/GEMINI.md",
            ],
        )

    def test_reports_copilot_desktop_as_a_manual_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))

            scan = scan_instructions(repo, home)

        self.assertEqual(len(scan.manual_surfaces), 1)
        manual = scan.manual_surfaces[0]
        self.assertEqual(manual.key, "copilot-desktop")
        self.assertEqual(manual.state, InstructionState.MANUAL)
        self.assertIn("Settings", manual.message)


class InstructionClassificationTests(unittest.TestCase):
    def test_classifies_intermediate_directory_symlink_as_indirect_for_raw_target_forms(self) -> None:
        for relative in (False, True):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, home = build_repository(root)
                alias = root / "repo-alias"
                alias.symlink_to(repo, target_is_directory=True)
                target = home / ".codex/AGENTS.md"
                target.parent.mkdir()
                raw_target = (
                    os.path.relpath(alias / "AGENTS.md", target.parent)
                    if relative
                    else str(alias / "AGENTS.md")
                )
                target.symlink_to(raw_target)

                status = status_for(scan_instructions(repo, home), "codex")

                self.assertEqual(status.state, InstructionState.INDIRECT_LINK)
                self.assertEqual(status.raw_target, raw_target)
                self.assertEqual(status.resolved_target, (repo / "AGENTS.md").resolve())
                self.assertEqual(status.message, "link resolves through another entry")

    def test_adopt_normalizes_intermediate_directory_symlink_to_direct_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            enable_other_instruction_targets(home, repo, "codex")
            alias = root / "repo-alias"
            alias.symlink_to(repo, target_is_directory=True)
            target = home / ".codex/AGENTS.md"
            target.parent.mkdir()
            target.symlink_to(alias / "AGENTS.md")
            plan = plan_instruction_adoption(
                scan_instructions(repo, home), root / "state", replace_existing=False
            )

            result = apply_instruction_plan(
                plan, home, expected_fingerprint=plan.fingerprint
            )

            self.assertTrue(result.ok)
            self.assertEqual(
                next(change for change in plan.changes if change.key == "codex").action,
                "replace",
            )
            self.assertEqual(os.readlink(target), str((repo / "AGENTS.md").resolve()))
            self.assertEqual(
                status_for(scan_instructions(repo, home), "codex").state,
                InstructionState.ENABLED,
            )

    def test_classifies_direct_absolute_link_as_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            target = home / ".agents/AGENTS.md"
            target.parent.mkdir()
            target.symlink_to(repo / "AGENTS.md")

            status = status_for(scan_instructions(repo, home), "shared")

        self.assertEqual(status.state, InstructionState.ENABLED)
        self.assertEqual(status.raw_target, str(repo / "AGENTS.md"))
        self.assertEqual(status.resolved_target, (repo / "AGENTS.md").resolve())
        self.assertEqual(status.message, "direct repository link")

    def test_classifies_direct_relative_link_as_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            target = home / ".claude/CLAUDE.md"
            target.parent.mkdir()
            raw_target = os.path.relpath(repo / "AGENTS.md", target.parent)
            target.symlink_to(raw_target)

            status = status_for(scan_instructions(repo, home), "claude")

        self.assertEqual(status.state, InstructionState.ENABLED)
        self.assertEqual(status.raw_target, raw_target)
        self.assertEqual(status.resolved_target, (repo / "AGENTS.md").resolve())

    def test_classifies_absent_target_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))

            status = status_for(scan_instructions(repo, home), "codex")

        self.assertEqual(status.state, InstructionState.MISSING)
        self.assertIsNone(status.raw_target)
        self.assertIsNone(status.resolved_target)

    def test_classifies_two_hop_link_to_source_as_indirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            shared = home / ".agents/AGENTS.md"
            target = home / ".gemini/GEMINI.md"
            shared.parent.mkdir()
            target.parent.mkdir()
            shared.symlink_to(repo / "AGENTS.md")
            target.symlink_to(shared)

            status = status_for(scan_instructions(repo, home), "antigravity")

        self.assertEqual(status.state, InstructionState.INDIRECT_LINK)
        self.assertEqual(status.raw_target, str(shared))
        self.assertEqual(status.resolved_target, (repo / "AGENTS.md").resolve())
        self.assertEqual(status.message, "link resolves through another entry")

    def test_classifies_byte_identical_regular_file_as_matching_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            target = home / ".copilot/copilot-instructions.md"
            target.parent.mkdir()
            target.write_bytes(SOURCE_BYTES)

            scan = scan_instructions(repo, home)
            status = status_for(scan, "copilot")

        self.assertEqual(status.state, InstructionState.MATCHING_COPY)
        self.assertEqual(status.target_sha256, scan.source_sha256)
        self.assertEqual(status.message, "file content matches repository source")

    def test_classifies_different_regular_file_as_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            target = home / ".codex/AGENTS.md"
            target.parent.mkdir()
            target.write_bytes(b"different bytes\n")

            status = status_for(scan_instructions(repo, home), "codex")

        self.assertEqual(status.state, InstructionState.CONFLICT)
        self.assertIsNotNone(status.target_sha256)
        self.assertEqual(status.message, "target differs from repository source")

    def test_classifies_directory_as_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            target = home / ".claude/CLAUDE.md"
            target.mkdir(parents=True)

            status = status_for(scan_instructions(repo, home), "claude")

        self.assertEqual(status.state, InstructionState.CONFLICT)
        self.assertEqual(status.message, "target is a directory")

    def test_classifies_valid_foreign_link_as_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            foreign = root / "foreign.md"
            foreign.write_text("foreign\n", encoding="utf-8")
            target = home / ".copilot/copilot-instructions.md"
            target.parent.mkdir()
            target.symlink_to(foreign)

            status = status_for(scan_instructions(repo, home), "copilot")

        self.assertEqual(status.state, InstructionState.CONFLICT)
        self.assertEqual(status.resolved_target, foreign.resolve())
        self.assertEqual(status.message, "link resolves to another source")

    def test_classifies_from_captured_raw_target_when_link_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            source = repo / "AGENTS.md"
            foreign = root / "foreign.md"
            foreign.write_text("foreign\n", encoding="utf-8")
            target = home / ".copilot/copilot-instructions.md"
            target.parent.mkdir()
            target.symlink_to(foreign)
            real_capture = instructions.capture_file_snapshot
            replaced = False

            def replace_after_capture(
                path: Path,
                *,
                include_content: bool,
            ) -> core.FileSnapshot:
                nonlocal replaced
                snapshot = real_capture(path, include_content=include_content)
                if Path(path) == target and not replaced:
                    target.unlink()
                    target.symlink_to(source)
                    replaced = True
                return snapshot

            with patch(
                "tools.agent_manager.instructions.capture_file_snapshot",
                side_effect=replace_after_capture,
            ):
                status = status_for(scan_instructions(repo, home), "copilot")

        self.assertEqual(status.state, InstructionState.CONFLICT)
        self.assertEqual(status.raw_target, str(foreign))
        self.assertEqual(status.resolved_target, foreign.resolve())
        self.assertEqual(status.message, "link resolves to another source")

    def test_classifies_broken_link_as_broken(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            target = home / ".agents/AGENTS.md"
            target.parent.mkdir()
            target.symlink_to(target.parent / "missing.md")

            status = status_for(scan_instructions(repo, home), "shared")

        self.assertEqual(status.state, InstructionState.BROKEN)
        self.assertIsNone(status.resolved_target)
        self.assertEqual(status.message, "link cannot be resolved")

    def test_classifies_symlink_cycle_as_broken(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            target = home / ".gemini/GEMINI.md"
            other = home / ".gemini/other.md"
            target.parent.mkdir()
            target.symlink_to(other)
            other.symlink_to(target)

            status = status_for(scan_instructions(repo, home), "antigravity")

        self.assertEqual(status.state, InstructionState.BROKEN)
        self.assertIsNone(status.resolved_target)
        self.assertEqual(status.message, "link cannot be resolved")

    def test_scan_leaves_temporary_home_byte_for_byte_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            link = home / ".agents/AGENTS.md"
            regular = home / ".codex/AGENTS.md"
            broken = home / ".gemini/GEMINI.md"
            link.parent.mkdir()
            regular.parent.mkdir()
            broken.parent.mkdir()
            link.symlink_to(repo / "AGENTS.md")
            regular.write_bytes(b"\xfflocal bytes\n")
            broken.symlink_to("missing.md")
            before = filesystem_manifest(home)

            scan_instructions(repo, home)

            self.assertEqual(filesystem_manifest(home), before)


class InstructionSourceValidationTests(unittest.TestCase):
    def assert_invalid_source(self, repo: Path, home: Path, code: str):
        scan = scan_instructions(repo, home)
        self.assertIn(code, [issue.code for issue in scan.issues])
        with self.assertRaises(InvalidInstructionSource):
            validate_instruction_source(scan)
        return scan

    def test_fails_closed_when_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            (repo / "AGENTS.md").unlink()

            scan = self.assert_invalid_source(repo, home, "missing-source")

        self.assertIsNone(scan.source_sha256)
        self.assertIsNone(scan.source_text)

    def test_fails_closed_when_source_is_a_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, home = build_repository(root)
            real_source = root / "real-AGENTS.md"
            real_source.write_bytes(SOURCE_BYTES)
            (repo / "AGENTS.md").unlink()
            (repo / "AGENTS.md").symlink_to(real_source)

            self.assert_invalid_source(repo, home, "invalid-source-kind")

    def test_fails_closed_when_source_is_not_a_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            (repo / "AGENTS.md").unlink()
            (repo / "AGENTS.md").mkdir()

            self.assert_invalid_source(repo, home, "invalid-source-kind")

    def test_fails_closed_when_repository_markers_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for marker in ("pyproject.toml", "skills"):
                with self.subTest(marker=marker):
                    repo, home = build_repository(root / marker.replace(".", "-"))
                    path = repo / marker
                    if path.is_dir():
                        path.rmdir()
                    else:
                        path.unlink()

                    self.assert_invalid_source(repo, home, "missing-repository-marker")

    def test_fails_closed_when_source_cannot_be_opened(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            source = (repo / "AGENTS.md").resolve()
            real_open = core.os.open

            def deny_source(path, flags, *args):
                if Path(path) == source:
                    raise PermissionError("denied by test")
                return real_open(path, flags, *args)

            with patch("tools.agent_manager.core.os.open", side_effect=deny_source):
                self.assert_invalid_source(repo, home, "source-unreadable")

    def test_fails_closed_when_source_is_not_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            (repo / "AGENTS.md").write_bytes(b"# invalid\n\xff\xfe")

            scan = self.assert_invalid_source(repo, home, "invalid-source-encoding")

        self.assertIsNotNone(scan.source_sha256)
        self.assertIsNone(scan.source_text)

    def test_fails_closed_when_source_is_replaced_between_open_and_fstat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, home = build_repository(Path(tmp))
            source = repo / "AGENTS.md"
            replacement = repo / "replacement.md"
            replacement.write_bytes(b"replacement\n")
            real_fstat = core.os.fstat
            replaced = False

            def replace_source(fd: int):
                nonlocal replaced
                metadata = real_fstat(fd)
                if not replaced:
                    os.replace(replacement, source)
                    replaced = True
                return metadata

            with patch("tools.agent_manager.core.os.fstat", side_effect=replace_source):
                self.assert_invalid_source(repo, home, "source-changed-during-read")


if __name__ == "__main__":
    unittest.main()
