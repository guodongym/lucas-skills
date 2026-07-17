from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import stat
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from .core import (
    FileSnapshot,
    FileSnapshotChangedError,
    capture_file_snapshot,
    install_backup_noreplace,
)


class InstructionState(StrEnum):
    ENABLED = "enabled"
    MISSING = "missing"
    INDIRECT_LINK = "indirect-link"
    MATCHING_COPY = "matching-copy"
    CONFLICT = "conflict"
    BROKEN = "broken"
    MANUAL = "manual"


@dataclass(frozen=True)
class InstructionTarget:
    key: str
    path: Path
    surfaces: tuple[str, ...]


@dataclass(frozen=True)
class InstructionStatus:
    key: str
    surfaces: tuple[str, ...]
    state: InstructionState
    path: Path
    source: Path
    raw_target: str | None
    resolved_target: Path | None
    source_sha256: str | None
    target_sha256: str | None
    message: str


@dataclass(frozen=True)
class ManualInstructionSurface:
    key: str = "copilot-desktop"
    state: InstructionState = InstructionState.MANUAL
    message: str = "configure repository instructions manually in Copilot Desktop Settings"


@dataclass(frozen=True)
class InstructionIssue:
    code: str
    path: Path
    message: str


@dataclass(frozen=True)
class InstructionScan:
    repo_root: Path
    source: Path
    source_sha256: str | None
    source_text: str | None
    targets: tuple[InstructionStatus, ...]
    manual_surfaces: tuple[ManualInstructionSurface, ...]
    issues: tuple[InstructionIssue, ...]


@dataclass(frozen=True)
class ParentExpectation:
    kind: str
    device: int | None = None
    inode: int | None = None


@dataclass(frozen=True)
class InstructionChange:
    action: str
    key: str
    source: Path
    target: Path
    expected: FileSnapshot
    parent_expected: ParentExpectation
    reason: str


@dataclass(frozen=True)
class InstructionPlan:
    changes: tuple[InstructionChange, ...]
    repo_root: Path
    source: Path
    source_sha256: str
    fingerprint: str
    snapshot_path: Path | None
    replace_existing: bool
    adopt: bool = False
    enabled: bool | None = None


@dataclass(frozen=True)
class InstructionResult:
    ok: bool
    code: str
    key: str
    path: Path
    message: str
    recovery_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class InstructionBatchResult:
    ok: bool
    results: tuple[InstructionResult, ...]
    snapshot_path: Path | None


@dataclass(frozen=True)
class IncompleteTransaction:
    code: str
    path: Path
    fingerprint: str
    recovery_paths: tuple[Path, ...]
    message: str


class InvalidInstructionSource(ValueError):
    pass


class InstructionPlanError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


_TARGETS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "shared",
        ".agents/AGENTS.md",
        (
            "claude-desktop",
            "claude-cli",
            "codex-desktop",
            "codex-cli",
            "copilot-cli",
            "antigravity-desktop",
            "antigravity-cli",
        ),
    ),
    ("claude", ".claude/CLAUDE.md", ("claude-desktop", "claude-cli")),
    ("codex", ".codex/AGENTS.md", ("codex-desktop", "codex-cli")),
    ("copilot", ".copilot/copilot-instructions.md", ("copilot-cli",)),
    (
        "antigravity",
        ".gemini/GEMINI.md",
        ("antigravity-desktop", "antigravity-cli"),
    ),
)


def build_instruction_targets(home: Path) -> tuple[InstructionTarget, ...]:
    return tuple(
        InstructionTarget(key, home / relative_path, surfaces)
        for key, relative_path, surfaces in _TARGETS
    )


def _issue(code: str, path: Path, message: str) -> InstructionIssue:
    return InstructionIssue(code, path, message)


def _capture_source(
    source: Path,
) -> tuple[FileSnapshot | None, str | None, tuple[InstructionIssue, ...]]:
    try:
        snapshot = capture_file_snapshot(source, include_content=True)
    except FileSnapshotChangedError as exc:
        return None, None, (
            _issue("source-changed-during-read", source, str(exc)),
        )
    except OSError as exc:
        return None, None, (_issue("source-unreadable", source, str(exc)),)

    if snapshot.kind == "missing":
        return snapshot, None, (_issue("missing-source", source, "AGENTS.md does not exist"),)
    if snapshot.kind != "file":
        return snapshot, None, (
            _issue("invalid-source-kind", source, "AGENTS.md must be a regular file"),
        )

    try:
        content = base64.b64decode(snapshot.content_base64 or "", validate=True)
        source_text = content.decode("utf-8", errors="strict")
    except (ValueError, UnicodeDecodeError) as exc:
        return snapshot, None, (
            _issue("invalid-source-encoding", source, str(exc)),
        )
    return snapshot, source_text, ()


def _repository_marker_issues(repo_root: Path) -> tuple[InstructionIssue, ...]:
    issues: list[InstructionIssue] = []
    expected = (
        (repo_root / "pyproject.toml", "file"),
        (repo_root / "skills", "directory"),
    )
    for path, required_kind in expected:
        try:
            snapshot = capture_file_snapshot(path, include_content=False)
        except OSError as exc:
            issues.append(_issue("invalid-repository-marker", path, str(exc)))
            continue
        if snapshot.kind == "missing":
            issues.append(
                _issue(
                    "missing-repository-marker",
                    path,
                    f"required repository marker is missing: {path.name}",
                )
            )
        elif snapshot.kind != required_kind:
            issues.append(
                _issue(
                    "invalid-repository-marker",
                    path,
                    f"repository marker must be a {required_kind}: {path.name}",
                )
            )
    return tuple(issues)


def _status(
    target: InstructionTarget,
    source: Path,
    source_sha256: str | None,
) -> InstructionStatus:
    raw_target: str | None = None
    resolved_target: Path | None = None
    target_sha256: str | None = None
    try:
        snapshot = capture_file_snapshot(target.path, include_content=False)
    except OSError:
        return InstructionStatus(
            target.key,
            target.surfaces,
            InstructionState.BROKEN,
            target.path,
            source,
            None,
            None,
            source_sha256,
            None,
            "target cannot be read",
        )

    if snapshot.kind == "missing":
        state = InstructionState.MISSING
        message = "target does not exist"
    elif snapshot.kind == "file":
        target_sha256 = snapshot.sha256
        if source_sha256 is not None and target_sha256 == source_sha256:
            state = InstructionState.MATCHING_COPY
            message = "file content matches repository source"
        else:
            state = InstructionState.CONFLICT
            message = "target differs from repository source"
    elif snapshot.kind == "directory":
        state = InstructionState.CONFLICT
        message = "target is a directory"
    elif snapshot.kind == "symlink":
        raw_target = snapshot.link_target
        raw_path = Path(raw_target or "")
        if not raw_path.is_absolute():
            raw_path = target.path.parent / raw_path
        direct_target = Path(os.path.abspath(raw_path))
        try:
            resolved_target = direct_target.resolve(strict=True)
        except (FileNotFoundError, RuntimeError, OSError):
            state = InstructionState.BROKEN
            message = "link cannot be resolved"
        else:
            try:
                direct_snapshot = capture_file_snapshot(
                    direct_target,
                    include_content=False,
                )
            except OSError:
                direct_snapshot = None
            if (
                direct_target == source
                and resolved_target == source
                and direct_snapshot is not None
                and direct_snapshot.kind == "file"
            ):
                state = InstructionState.ENABLED
                message = "direct repository link"
            elif resolved_target == source:
                state = InstructionState.INDIRECT_LINK
                message = "link resolves through another entry"
            else:
                state = InstructionState.CONFLICT
                message = "link resolves to another source"
    else:
        state = InstructionState.CONFLICT
        message = "target is a special file"

    return InstructionStatus(
        target.key,
        target.surfaces,
        state,
        target.path,
        source,
        raw_target,
        resolved_target,
        source_sha256,
        target_sha256,
        message,
    )


def scan_instructions(repo_root: Path, home: Path) -> InstructionScan:
    repo_root = repo_root.expanduser().resolve()
    source = repo_root / "AGENTS.md"
    source_snapshot, source_text, source_issues = _capture_source(source)
    source_sha256 = source_snapshot.sha256 if source_snapshot is not None else None
    issues = (*source_issues, *_repository_marker_issues(repo_root))
    targets = build_instruction_targets(home)
    statuses = tuple(
        _status(target, source, source_sha256)
        for target in targets
    )
    return InstructionScan(
        repo_root,
        source,
        source_sha256,
        source_text,
        statuses,
        (ManualInstructionSurface(),),
        issues,
    )


def validate_instruction_source(scan: InstructionScan) -> None:
    if scan.issues:
        codes = ", ".join(issue.code for issue in scan.issues)
        raise InvalidInstructionSource(f"invalid instruction source: {codes}")


_WRITE_ACTIONS = frozenset({"create", "replace", "remove"})
_PLAN_ACTIONS = _WRITE_ACTIONS | frozenset(
    {"no-op", "blocked", "unsupported-target"}
)
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _snapshot_dict(snapshot: FileSnapshot) -> dict[str, object]:
    return {
        "kind": snapshot.kind,
        "link_target": snapshot.link_target,
        "mode": snapshot.mode,
        "sha256": snapshot.sha256,
        "content_base64": snapshot.content_base64,
        "device": snapshot.device,
        "inode": snapshot.inode,
    }


def _parent_expectation(path: Path) -> ParentExpectation:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return ParentExpectation("missing")
    if stat.S_ISDIR(metadata.st_mode):
        kind = "directory"
    elif stat.S_ISLNK(metadata.st_mode):
        kind = "symlink"
    elif stat.S_ISREG(metadata.st_mode):
        kind = "file"
    else:
        kind = "special"
    return ParentExpectation(kind, metadata.st_dev, metadata.st_ino)


def _parent_expectation_dict(expected: ParentExpectation) -> dict[str, object]:
    return {
        "kind": expected.kind,
        "device": expected.device,
        "inode": expected.inode,
    }


def _home_from_scan(scan: InstructionScan) -> Path:
    statuses = {status.key: status for status in scan.targets}
    if set(statuses) != {key for key, _relative, _surfaces in _TARGETS}:
        raise InstructionPlanError("invalid-scan", "scan does not contain the five fixed targets")
    shared = statuses["shared"].path
    home = _absolute(shared.parent.parent)
    expected = {target.key: target.path for target in build_instruction_targets(home)}
    if any(_absolute(status.path) != expected[key] for key, status in statuses.items()):
        raise InstructionPlanError(
            "invalid-scan", "scan target paths are not the fixed HOME targets"
        )
    return home


def _normalize_keys(target_keys: Sequence[str]) -> tuple[str, ...]:
    known = [key for key, _relative, _surfaces in _TARGETS]
    normalized: list[str] = []
    for key in target_keys:
        if not isinstance(key, str):
            raise InstructionPlanError("unknown-target", "instruction target must be a string")
        value = key.strip().lower()
        if value not in known:
            raise InstructionPlanError("unknown-target", f"unknown instruction target: {key}")
        if value in normalized:
            raise InstructionPlanError("duplicate-target", f"duplicate instruction target: {value}")
        normalized.append(value)
    if not normalized:
        raise InstructionPlanError("missing-target", "at least one instruction target is required")
    selected = set(normalized)
    return tuple(key for key in known if key in selected)


def _snapshot_matches_status(snapshot: FileSnapshot, status: InstructionStatus) -> bool:
    if status.state == InstructionState.MISSING:
        return snapshot.kind == "missing"
    if status.state in {InstructionState.MATCHING_COPY, InstructionState.CONFLICT}:
        if snapshot.kind == "file":
            return snapshot.sha256 == status.target_sha256
        if snapshot.kind == "directory":
            return status.message == "target is a directory"
        if snapshot.kind == "special":
            return status.message == "target is a special file"
    if snapshot.kind == "symlink":
        return snapshot.link_target == status.raw_target
    return False


def _plan_fingerprint_payload(
    *,
    repo_root: Path,
    source: Path,
    source_sha256: str,
    replace_existing: bool,
    adopt: bool,
    enabled: bool | None,
    changes: tuple[InstructionChange, ...],
) -> dict[str, object]:
    return {
        "repo_root": str(repo_root),
        "source": str(source),
        "source_sha256": source_sha256,
        "replace_existing": replace_existing,
        "adopt": adopt,
        "enabled": enabled,
        "targets": [
            {
                "key": change.key,
                "source": str(change.source),
                "target": str(change.target),
                "action": change.action,
                "expected": _snapshot_dict(change.expected),
                "parent_expected": _parent_expectation_dict(change.parent_expected),
            }
            for change in changes
        ],
    }


def _build_instruction_plan(
    scan: InstructionScan,
    target_keys: Sequence[str],
    state_dir: Path,
    *,
    adopt: bool,
    enabled: bool | None,
    replace_existing: bool,
) -> InstructionPlan:
    try:
        validate_instruction_source(scan)
    except InvalidInstructionSource as exc:
        raise InstructionPlanError("invalid-source", str(exc)) from exc
    if not isinstance(replace_existing, bool):
        raise InstructionPlanError("invalid-plan", "replace_existing must be boolean")
    if replace_existing and not adopt:
        raise InstructionPlanError(
            "invalid-replace-mode", "replace_existing is only valid for instruction adoption"
        )
    keys = _normalize_keys(target_keys)
    home = _home_from_scan(scan)
    repo_root = scan.repo_root.resolve()
    source = repo_root / "AGENTS.md"
    if scan.source != source or scan.source_sha256 is None:
        raise InstructionPlanError("invalid-source", "instruction source identity is invalid")
    try:
        source_snapshot = capture_file_snapshot(source, include_content=False)
    except OSError as exc:
        raise InstructionPlanError("state-changed", str(exc)) from exc
    if source_snapshot.kind != "file" or source_snapshot.sha256 != scan.source_sha256:
        raise InstructionPlanError("state-changed", "instruction source changed after scan")

    statuses = {status.key: status for status in scan.targets}
    changes: list[InstructionChange] = []
    for key in keys:
        status = statuses[key]
        try:
            parent_expected = _parent_expectation(status.path.parent)
        except OSError as exc:
            raise InstructionPlanError("state-changed", str(exc)) from exc
        if parent_expected.kind in {"file", "special"}:
            expected = FileSnapshot("missing")
            target_matches = (
                status.state == InstructionState.BROKEN
                and status.message == "target cannot be read"
            )
        else:
            try:
                expected = capture_file_snapshot(status.path, include_content=True)
            except OSError as exc:
                raise InstructionPlanError("state-changed", str(exc)) from exc
            target_matches = _snapshot_matches_status(expected, status)
        if not target_matches:
            raise InstructionPlanError("state-changed", f"target changed after scan: {key}")

        if adopt:
            if status.state == InstructionState.MISSING:
                action, reason = "create", "create direct repository link"
            elif status.state == InstructionState.ENABLED:
                action, reason = "no-op", "already a direct repository link"
            elif status.state in {InstructionState.INDIRECT_LINK, InstructionState.MATCHING_COPY}:
                action, reason = "replace", "adopt existing instruction entry"
            elif expected.kind in {"directory", "special"}:
                action = "unsupported-target"
                reason = "directories and special files are not replaceable"
            elif replace_existing:
                action, reason = "replace", "replace conflicting instruction entry"
            else:
                action = "blocked"
                reason = "existing instruction entry requires explicit replacement"
        elif enabled:
            if status.state == InstructionState.MISSING:
                action, reason = "create", "create direct repository link"
            elif status.state == InstructionState.ENABLED:
                action, reason = "no-op", "already a direct repository link"
            else:
                action, reason = "blocked", "target is not safe to enable with set"
        else:
            if status.state == InstructionState.ENABLED:
                action, reason = "remove", "remove direct repository link"
            elif status.state == InstructionState.MISSING:
                action, reason = "no-op", "target is already absent"
            else:
                action, reason = "blocked", "only a direct managed link can be removed"
        if action != "no-op" and parent_expected.kind != "directory":
            action = "blocked"
            reason = (
                "parent-missing"
                if parent_expected.kind == "missing"
                else "parent-not-directory"
            )
        changes.append(
            InstructionChange(
                action,
                key,
                source,
                status.path,
                expected,
                parent_expected,
                reason,
            )
        )

    frozen_changes = tuple(changes)
    fingerprint_payload = _plan_fingerprint_payload(
        repo_root=repo_root,
        source=source,
        source_sha256=scan.source_sha256,
        replace_existing=replace_existing,
        adopt=adopt,
        enabled=enabled,
        changes=frozen_changes,
    )
    canonical = json.dumps(
        fingerprint_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    fingerprint = hashlib.sha256(canonical).hexdigest()
    has_writes = any(change.action in _WRITE_ACTIONS for change in frozen_changes)
    applyable = not any(
        change.action in {"blocked", "unsupported-target"}
        for change in frozen_changes
    )
    snapshot_path = (
        _absolute(state_dir) / "snapshots" / f"instructions-{fingerprint}.json"
        if has_writes and applyable
        else None
    )
    return InstructionPlan(
        frozen_changes,
        repo_root,
        source,
        scan.source_sha256,
        fingerprint,
        snapshot_path,
        replace_existing,
        adopt,
        enabled,
    )


def plan_instruction_set(
    scan: InstructionScan,
    target_keys: Sequence[str],
    enabled: bool,
    state_dir: Path,
) -> InstructionPlan:
    if not isinstance(enabled, bool):
        raise InstructionPlanError("invalid-plan", "enabled must be boolean")
    return _build_instruction_plan(
        scan,
        target_keys,
        state_dir,
        adopt=False,
        enabled=enabled,
        replace_existing=False,
    )


def plan_instruction_adoption(
    scan: InstructionScan,
    state_dir: Path,
    *,
    replace_existing: bool,
) -> InstructionPlan:
    return _build_instruction_plan(
        scan,
        [key for key, _relative, _surfaces in _TARGETS],
        state_dir,
        adopt=True,
        enabled=None,
        replace_existing=replace_existing,
    )


def _snapshot_payload(plan: InstructionPlan, *, phase: str) -> dict[str, object]:
    return {
        "version": 1,
        "phase": phase,
        "created_at": datetime.now(UTC).isoformat(),
        "fingerprint": plan.fingerprint,
        "repo_root": str(plan.repo_root),
        "source": str(plan.source),
        "source_sha256": plan.source_sha256,
        "replace_existing": plan.replace_existing,
        "targets": [
            {
                "key": change.key,
                "path": str(change.target),
                "action": change.action,
                "expected": _snapshot_dict(change.expected),
                "parent_expected": _parent_expectation_dict(change.parent_expected),
            }
            for change in plan.changes
        ],
    }


def _ensure_snapshot_directory(snapshot_path: Path) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)


def _fsync_snapshot_directory(directory_fd: int) -> None:
    os.fsync(directory_fd)


def _encode_snapshot(payload: dict[str, object]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n"
    ).encode("utf-8")


def _write_temp_snapshot(directory_fd: int, payload: dict[str, object]) -> str:
    temporary = f".agent-manager-{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        data = _encode_snapshot(payload)
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except OSError:
            pass
        raise
    os.close(descriptor)
    return temporary


def _existing_snapshot_code(snapshot_path: Path) -> str:
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "snapshot-conflict"
    return (
        "incomplete-transaction"
        if isinstance(payload, dict) and payload.get("phase") == "prepared"
        else "snapshot-conflict"
    )


@dataclass(frozen=True)
class _SnapshotFileIdentity:
    device: int
    inode: int
    mode: int
    content: bytes


@dataclass(frozen=True)
class _PreparedSnapshotStage:
    payload: dict[str, object]
    identity: _SnapshotFileIdentity


class _SnapshotRecoveryState(StrEnum):
    HOME_ROLLBACK_SAFE = "home-rollback-safe"
    RECOVERY_REQUIRED = "recovery-required"


class _SnapshotCommitFailure(OSError):
    def __init__(
        self,
        message: str,
        *,
        recovery_state: _SnapshotRecoveryState,
        recovery_paths: tuple[Path, ...] = (),
    ):
        super().__init__(message)
        self.recovery_state = recovery_state
        self.recovery_paths = recovery_paths


def _capture_snapshot_identity(
    directory_fd: int,
    name: str,
) -> _SnapshotFileIdentity:
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError(f"snapshot entry is not a regular file: {name}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        identity = (before.st_dev, before.st_ino)
        if (
            (after.st_dev, after.st_ino) != identity
            or (current.st_dev, current.st_ino) != identity
        ):
            raise OSError(f"snapshot entry changed while reading: {name}")
        return _SnapshotFileIdentity(
            before.st_dev,
            before.st_ino,
            stat.S_IMODE(before.st_mode),
            b"".join(chunks),
        )
    finally:
        os.close(descriptor)


def _snapshot_identity_matches(
    directory_fd: int,
    name: str,
    expected: _SnapshotFileIdentity,
) -> bool:
    try:
        actual = _capture_snapshot_identity(directory_fd, name)
        return secrets.compare_digest(actual.content, expected.content) and actual == expected
    except OSError:
        return False


def _write_prepared_snapshot(plan: InstructionPlan) -> _PreparedSnapshotStage:
    if plan.snapshot_path is None:
        raise InstructionPlanError("invalid-plan", "write plan has no snapshot path")
    _ensure_snapshot_directory(plan.snapshot_path)
    directory_fd = os.open(plan.snapshot_path.parent, _DIRECTORY_FLAGS)
    temporary: str | None = None
    try:
        payload = _snapshot_payload(plan, phase="prepared")
        temporary = _write_temp_snapshot(directory_fd, payload)
        temporary_identity = _capture_snapshot_identity(directory_fd, temporary)
        if temporary_identity.mode != 0o600 or not secrets.compare_digest(
            temporary_identity.content,
            _encode_snapshot(payload),
        ):
            raise OSError("prepared snapshot temporary failed exact verification")
        try:
            install_backup_noreplace(directory_fd, temporary, plan.snapshot_path.name)
            temporary = None
        except FileExistsError as exc:
            code = _existing_snapshot_code(plan.snapshot_path)
            raise InstructionPlanError(
                code, f"snapshot already exists: {plan.snapshot_path}"
            ) from exc
        identity = _capture_snapshot_identity(directory_fd, plan.snapshot_path.name)
        if identity != temporary_identity:
            raise OSError("installed prepared snapshot identity changed during installation")
        _fsync_snapshot_directory(directory_fd)
        if not _snapshot_identity_matches(
            directory_fd,
            plan.snapshot_path.name,
            identity,
        ):
            raise OSError("prepared snapshot changed before directory fsync completed")
        return _PreparedSnapshotStage(payload, identity)
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                pass
        os.close(directory_fd)


def _mark_snapshot_committed(
    plan: InstructionPlan,
    prepared_stage: _PreparedSnapshotStage,
) -> None:
    if plan.snapshot_path is None:
        raise InstructionPlanError("invalid-plan", "write plan has no snapshot path")
    directory_fd = os.open(plan.snapshot_path.parent, _DIRECTORY_FLAGS)
    temporary: str | None = None
    prepared_recovery = f".agent-manager-{uuid.uuid4().hex}.prepared"
    prepared_recovery_path = plan.snapshot_path.parent / prepared_recovery
    committed_recovery: str | None = None
    prepared_isolated = False
    try:
        if not _snapshot_identity_matches(
            directory_fd,
            plan.snapshot_path.name,
            prepared_stage.identity,
        ):
            raise _SnapshotCommitFailure(
                "manager-owned prepared snapshot changed before commit",
                recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
            )
        os.rename(
            plan.snapshot_path.name,
            prepared_recovery,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        prepared_isolated = True
        if not _snapshot_identity_matches(
            directory_fd,
            prepared_recovery,
            prepared_stage.identity,
        ):
            try:
                install_backup_noreplace(
                    directory_fd,
                    prepared_recovery,
                    plan.snapshot_path.name,
                )
                prepared_isolated = False
                _fsync_snapshot_directory(directory_fd)
            except OSError as restore_exc:
                raise _SnapshotCommitFailure(
                    "prepared snapshot changed during isolation; "
                    f"isolated entry retained at {prepared_recovery_path}; "
                    f"restore failed: {restore_exc}",
                    recovery_state=_SnapshotRecoveryState.RECOVERY_REQUIRED,
                    recovery_paths=(prepared_recovery_path,),
                ) from restore_exc
            raise _SnapshotCommitFailure(
                "prepared snapshot changed during isolation and was restored",
                recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
                recovery_paths=(plan.snapshot_path,),
            )
        _fsync_snapshot_directory(directory_fd)

        committed = dict(prepared_stage.payload)
        committed["phase"] = "committed"
        temporary = _write_temp_snapshot(directory_fd, committed)
        committed_identity = _capture_snapshot_identity(directory_fd, temporary)
        if committed_identity.mode != 0o600 or not secrets.compare_digest(
            committed_identity.content,
            _encode_snapshot(committed),
        ):
            raise OSError("committed snapshot temporary failed exact verification")
        try:
            install_backup_noreplace(
                directory_fd,
                temporary,
                plan.snapshot_path.name,
            )
        except FileExistsError as exc:
            raise _SnapshotCommitFailure(
                "snapshot destination occupied during commit; "
                f"prepared snapshot retained at {prepared_recovery_path}",
                recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
                recovery_paths=(prepared_recovery_path,),
            ) from exc
        temporary = None
        if not _snapshot_identity_matches(
            directory_fd,
            plan.snapshot_path.name,
            committed_identity,
        ):
            raise _SnapshotCommitFailure(
                "committed snapshot changed immediately after installation; "
                f"prepared snapshot retained at {prepared_recovery_path}",
                recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
                recovery_paths=(prepared_recovery_path,),
            )
        try:
            _fsync_snapshot_directory(directory_fd)
        except OSError as fsync_exc:
            committed_recovery = f".agent-manager-{uuid.uuid4().hex}.committed-failed"
            committed_recovery_path = plan.snapshot_path.parent / committed_recovery
            try:
                os.rename(
                    plan.snapshot_path.name,
                    committed_recovery,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                )
                if not _snapshot_identity_matches(
                    directory_fd,
                    committed_recovery,
                    committed_identity,
                ):
                    raise OSError("committed snapshot changed during failure isolation")
                install_backup_noreplace(
                    directory_fd,
                    prepared_recovery,
                    plan.snapshot_path.name,
                )
                prepared_isolated = False
                _fsync_snapshot_directory(directory_fd)
            except OSError as restore_exc:
                recovery_paths = [prepared_recovery_path]
                if committed_recovery is not None:
                    recovery_paths.append(committed_recovery_path)
                raise _SnapshotCommitFailure(
                    f"committed snapshot fsync failed: {fsync_exc}; "
                    f"prepared restore failed: {restore_exc}; retained: "
                    f"{', '.join(map(str, recovery_paths))}",
                    recovery_state=_SnapshotRecoveryState.RECOVERY_REQUIRED,
                    recovery_paths=tuple(recovery_paths),
                ) from restore_exc

            try:
                os.unlink(committed_recovery, dir_fd=directory_fd)
            except OSError as cleanup_exc:
                raise _SnapshotCommitFailure(
                    f"committed snapshot fsync failed: {fsync_exc}; prepared snapshot "
                    f"restored; committed recovery retained: {cleanup_exc}",
                    recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
                    recovery_paths=(committed_recovery_path,),
                ) from cleanup_exc
            committed_recovery = None
            try:
                _fsync_snapshot_directory(directory_fd)
            except OSError as cleanup_fsync_exc:
                raise _SnapshotCommitFailure(
                    f"committed snapshot fsync failed: {fsync_exc}; prepared snapshot "
                    f"restored; committed recovery cleanup fsync failed: {cleanup_fsync_exc}",
                    recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
                    recovery_paths=(committed_recovery_path,),
                ) from cleanup_fsync_exc
            raise _SnapshotCommitFailure(
                f"committed snapshot fsync failed: {fsync_exc}; prepared snapshot restored",
                recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
                recovery_paths=(plan.snapshot_path,),
            ) from fsync_exc

        os.unlink(prepared_recovery, dir_fd=directory_fd)
        prepared_isolated = False
    except _SnapshotCommitFailure:
        raise
    except Exception as exc:
        if prepared_isolated:
            try:
                install_backup_noreplace(
                    directory_fd,
                    prepared_recovery,
                    plan.snapshot_path.name,
                )
                prepared_isolated = False
                _fsync_snapshot_directory(directory_fd)
            except OSError as restore_exc:
                raise _SnapshotCommitFailure(
                    f"snapshot commit failed: {exc}; prepared restore failed: {restore_exc}; "
                    f"recovery retained at {prepared_recovery_path}",
                    recovery_state=_SnapshotRecoveryState.RECOVERY_REQUIRED,
                    recovery_paths=(prepared_recovery_path,),
                ) from restore_exc
            raise _SnapshotCommitFailure(
                f"snapshot commit failed: {exc}; prepared snapshot restored",
                recovery_state=_SnapshotRecoveryState.HOME_ROLLBACK_SAFE,
                recovery_paths=(plan.snapshot_path,),
            ) from exc
        raise
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                pass
        os.close(directory_fd)


def _entry_snapshot(directory_fd: int, name: str) -> FileSnapshot:
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return FileSnapshot("missing")
    device, inode = metadata.st_dev, metadata.st_ino
    if stat.S_ISLNK(metadata.st_mode):
        link_target = os.readlink(name, dir_fd=directory_fd)
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (after.st_dev, after.st_ino) != (device, inode):
            raise OSError("symlink changed while reading through parent descriptor")
        return FileSnapshot(
            "symlink",
            link_target=link_target,
            device=device,
            inode=inode,
        )
    if stat.S_ISDIR(metadata.st_mode):
        return FileSnapshot(
            "directory",
            mode=stat.S_IMODE(metadata.st_mode),
            device=device,
            inode=inode,
        )
    if not stat.S_ISREG(metadata.st_mode):
        return FileSnapshot(
            "special",
            mode=stat.S_IMODE(metadata.st_mode),
            device=device,
            inode=inode,
        )
    return FileSnapshot(
        "file",
        mode=stat.S_IMODE(metadata.st_mode),
        device=device,
        inode=inode,
    )


def _entry_matches_expected(
    directory_fd: int,
    name: str,
    expected: FileSnapshot,
) -> bool:
    actual = _entry_snapshot(directory_fd, name)
    metadata_matches = (
        actual.kind == expected.kind
        and actual.link_target == expected.link_target
        and actual.mode == expected.mode
        and actual.device == expected.device
        and actual.inode == expected.inode
    )
    if not metadata_matches or expected.kind != "file":
        return metadata_matches
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (expected.device, expected.inode):
            return False
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not (
            (after.st_dev, after.st_ino) == (expected.device, expected.inode)
            and (current.st_dev, current.st_ino) == (expected.device, expected.inode)
        ):
            return False
    finally:
        os.close(descriptor)
    return (
        hashlib.sha256(content).hexdigest() == expected.sha256
        and base64.b64encode(content).decode("ascii") == expected.content_base64
    )


def _verify_direct_link(
    directory_fd: int,
    parent: Path,
    leaf: str,
    source: Path,
) -> bool:
    snapshot = _entry_snapshot(directory_fd, leaf)
    if snapshot.kind != "symlink" or snapshot.link_target is None:
        return False
    raw = Path(snapshot.link_target)
    absolute_raw = raw if raw.is_absolute() else parent / raw
    absolute_raw = _absolute(absolute_raw)
    if absolute_raw != source:
        return False
    try:
        return absolute_raw.resolve(strict=True) == source
    except (OSError, RuntimeError):
        return False


def _install_direct_link(
    directory_fd: int,
    parent: Path,
    leaf: str,
    source: Path,
) -> None:
    temporary = f".agent-manager-{uuid.uuid4().hex}.tmp"
    os.symlink(str(source), temporary, dir_fd=directory_fd)
    try:
        install_backup_noreplace(directory_fd, temporary, leaf)
    except BaseException:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except OSError:
            pass
        raise


def _parent_identity_matches(
    home_fd: int,
    parent_name: str,
    parent_fd: int,
    identity: tuple[int, int],
) -> bool:
    opened = os.fstat(parent_fd)
    try:
        current = os.stat(parent_name, dir_fd=home_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return (
        stat.S_ISDIR(opened.st_mode)
        and stat.S_ISDIR(current.st_mode)
        and (opened.st_dev, opened.st_ino) == identity
        and (current.st_dev, current.st_ino) == identity
    )


@dataclass
class _AppliedInstruction:
    change: InstructionChange
    parent_name: str
    parent: Path
    parent_fd: int
    parent_identity: tuple[int, int]
    backup_name: str | None = None
    manager_snapshot: FileSnapshot | None = None


@dataclass(frozen=True)
class _RollbackOutcome:
    restored: bool
    messages: tuple[str, ...]
    recovery_paths: tuple[Path, ...]


@dataclass(frozen=True)
class _CleanupOutcome:
    messages: tuple[str, ...]
    recovery_paths: tuple[Path, ...]


class _InstructionApplyFailure(RuntimeError):
    def __init__(self, entry: _AppliedInstruction, cause: Exception):
        super().__init__(str(cause))
        self.entry = entry


def _open_parent(
    home_fd: int,
    home: Path,
    change: InstructionChange,
) -> _AppliedInstruction:
    relative = change.target.relative_to(home)
    if len(relative.parts) != 2:
        raise InstructionPlanError(
            "invalid-plan", "instruction target is not a fixed two-part path"
        )
    parent_name = relative.parts[0]
    expected = change.parent_expected
    if (
        expected.kind != "directory"
        or expected.device is None
        or expected.inode is None
    ):
        raise InstructionPlanError(
            "invalid-plan", "write target does not have a reviewed parent directory"
        )
    identity = (expected.device, expected.inode)
    parent_fd: int | None = None
    try:
        metadata = os.stat(parent_name, dir_fd=home_fd, follow_symlinks=False)
        if not stat.S_ISDIR(metadata.st_mode) or (
            metadata.st_dev,
            metadata.st_ino,
        ) != identity:
            raise OSError(
                f"instruction parent changed before opening: {home / parent_name}"
            )
        parent_fd = os.open(parent_name, _DIRECTORY_FLAGS, dir_fd=home_fd)
        if not _parent_identity_matches(home_fd, parent_name, parent_fd, identity):
            raise OSError(f"instruction parent changed while opening: {home / parent_name}")
    except BaseException:
        if parent_fd is not None:
            os.close(parent_fd)
        raise
    return _AppliedInstruction(
        change,
        parent_name,
        home / parent_name,
        parent_fd,
        identity,
    )


def _source_still_matches(plan: InstructionPlan) -> bool:
    try:
        snapshot = capture_file_snapshot(plan.source, include_content=False)
    except OSError:
        return False
    return snapshot.kind == "file" and snapshot.sha256 == plan.source_sha256


def _apply_one(
    plan: InstructionPlan,
    home_fd: int,
    home: Path,
    change: InstructionChange,
) -> _AppliedInstruction:
    entry = _open_parent(home_fd, home, change)
    leaf = change.target.name
    try:
        if not _entry_matches_expected(entry.parent_fd, leaf, change.expected):
            raise OSError("target changed before atomic mutation")
        if change.action in {"replace", "remove"}:
            entry.backup_name = f".agent-manager-{uuid.uuid4().hex}.backup"
            os.rename(
                leaf,
                entry.backup_name,
                src_dir_fd=entry.parent_fd,
                dst_dir_fd=entry.parent_fd,
            )
            if not _entry_matches_expected(
                entry.parent_fd, entry.backup_name, change.expected
            ):
                raise OSError("target changed during isolation")
        if not _parent_identity_matches(
            home_fd,
            entry.parent_name,
            entry.parent_fd,
            entry.parent_identity,
        ):
            raise OSError("instruction parent changed during apply")
        if not _source_still_matches(plan):
            raise OSError("instruction source changed during apply")
        if change.action in {"create", "replace"}:
            _install_direct_link(entry.parent_fd, entry.parent, leaf, plan.source)
            manager_snapshot = _entry_snapshot(entry.parent_fd, leaf)
            if not (
                manager_snapshot.kind == "symlink"
                and manager_snapshot.link_target == str(plan.source)
            ):
                raise OSError("installed link identity cannot be captured")
            entry.manager_snapshot = manager_snapshot
            if not _verify_direct_link(entry.parent_fd, entry.parent, leaf, plan.source):
                raise OSError("post-replacement direct-link verification failed")
        elif change.action == "remove":
            if _entry_snapshot(entry.parent_fd, leaf).kind != "missing":
                raise OSError("target reappeared during removal")
        else:
            raise InstructionPlanError("invalid-plan", f"unknown write action: {change.action}")
        if not _parent_identity_matches(
            home_fd,
            entry.parent_name,
            entry.parent_fd,
            entry.parent_identity,
        ):
            raise OSError("instruction parent changed after apply")
        return entry
    except Exception as exc:
        raise _InstructionApplyFailure(entry, exc) from exc


def _isolate_owned_link(entry: _AppliedInstruction, source: Path) -> tuple[str | None, str | None]:
    leaf = entry.change.target.name
    if entry.manager_snapshot is None or not _entry_matches_expected(
        entry.parent_fd,
        leaf,
        entry.manager_snapshot,
    ):
        return None, None
    before = entry.manager_snapshot
    recovery = f".agent-manager-{uuid.uuid4().hex}.rollback"
    os.rename(leaf, recovery, src_dir_fd=entry.parent_fd, dst_dir_fd=entry.parent_fd)
    if not _entry_matches_expected(entry.parent_fd, recovery, before):
        try:
            install_backup_noreplace(entry.parent_fd, recovery, leaf)
            return None, "target changed during rollback isolation and was restored"
        except OSError:
            return recovery, "target changed during rollback isolation"
    return recovery, None


def _rollback_entries(
    entries: list[_AppliedInstruction],
    home_fd: int,
    home: Path,
    source: Path,
) -> dict[str, _RollbackOutcome]:
    outcomes: dict[str, _RollbackOutcome] = {}
    for entry in reversed(entries):
        messages: list[str] = []
        recovery_paths: set[Path] = set()
        leaf = entry.change.target.name
        recovery: str | None = None
        durable = True
        try:
            if entry.change.action in {"create", "replace"}:
                recovery, warning = _isolate_owned_link(entry, source)
                if warning:
                    messages.append(f"{entry.change.key}: {warning}")
            if entry.backup_name is not None:
                try:
                    install_backup_noreplace(entry.parent_fd, entry.backup_name, leaf)
                    entry.backup_name = None
                except FileExistsError:
                    backup_path = entry.parent / entry.backup_name
                    messages.append(
                        f"{entry.change.key}: rollback target occupied; "
                        f"original retained at {backup_path}"
                    )
                    recovery_paths.add(backup_path)
            if recovery is not None:
                try:
                    os.unlink(recovery, dir_fd=entry.parent_fd)
                    recovery = None
                except OSError:
                    recovery_path = entry.parent / recovery
                    messages.append(
                        f"{entry.change.key}: isolated manager link retained at "
                        f"{recovery_path}"
                    )
                    recovery_paths.add(recovery_path)
            os.fsync(entry.parent_fd)
        except OSError as exc:
            durable = False
            recovery_paths.add(entry.change.target)
            retained = (
                str(entry.parent / entry.backup_name)
                if entry.backup_name is not None
                else "no backup path confirmed"
            )
            messages.append(f"{entry.change.key}: rollback failed: {exc}; {retained}")
            if entry.backup_name is not None:
                recovery_paths.add(entry.parent / entry.backup_name)
            if recovery is not None:
                recovery_paths.add(entry.parent / recovery)

        try:
            parent_matches = _parent_identity_matches(
                home_fd,
                entry.parent_name,
                entry.parent_fd,
                entry.parent_identity,
            )
            target_restored = parent_matches and _entry_matches_expected(
                entry.parent_fd,
                leaf,
                entry.change.expected,
            )
            current = _entry_snapshot(entry.parent_fd, leaf)
        except OSError as exc:
            parent_matches = False
            target_restored = False
            current = FileSnapshot("missing")
            messages.append(
                f"{entry.change.key}: rollback verification failed: {exc}"
            )
        if not parent_matches:
            recovery_paths.add(entry.parent)
            messages.append(
                f"{entry.change.key}: rollback parent identity was not restored"
            )
        if not target_restored:
            if current.kind != "missing":
                recovery_paths.add(entry.change.target)
            messages.append(f"{entry.change.key}: rollback target was not restored")
        outcomes[entry.change.key] = _RollbackOutcome(
            restored=durable and target_restored and not recovery_paths,
            messages=tuple(messages),
            recovery_paths=tuple(sorted(recovery_paths)),
        )

    return outcomes


def _applied_entry_error(
    entry: _AppliedInstruction,
    home_fd: int,
) -> str | None:
    try:
        if not _parent_identity_matches(
            home_fd,
            entry.parent_name,
            entry.parent_fd,
            entry.parent_identity,
        ):
            return f"parent identity changed: {entry.parent}"
        leaf = entry.change.target.name
        if entry.change.action in {"create", "replace"}:
            if entry.manager_snapshot is None or not _entry_matches_expected(
                entry.parent_fd,
                leaf,
                entry.manager_snapshot,
            ):
                return f"manager-created target changed: {entry.change.target}"
        elif entry.change.action == "remove":
            if _entry_snapshot(entry.parent_fd, leaf).kind != "missing":
                return f"removed target was reoccupied: {entry.change.target}"
    except OSError as exc:
        return f"target verification failed for {entry.change.target}: {exc}"
    return None


def _verify_applied_batch(
    entries: list[_AppliedInstruction],
    home_fd: int,
) -> None:
    errors: list[str] = []
    for entry in entries:
        error = _applied_entry_error(entry, home_fd)
        if error is None:
            continue
        if entry.backup_name is not None:
            error += f"; recovery retained at {entry.parent / entry.backup_name}"
        errors.append(f"{entry.change.key}: {error}")
    if errors:
        raise OSError("pre-commit target verification failed; " + "; ".join(errors))


def _cleanup_committed(
    entries: list[_AppliedInstruction],
    home_fd: int,
) -> dict[str, _CleanupOutcome]:
    outcomes: dict[str, _CleanupOutcome] = {}
    for entry in entries:
        messages: list[str] = []
        recovery_paths: set[Path] = set()
        error = _applied_entry_error(entry, home_fd)
        if error is not None:
            if entry.backup_name is not None:
                recovery_path = entry.parent / entry.backup_name
                error += f"; recovery retained at {recovery_path}"
                recovery_paths.add(recovery_path)
            else:
                recovery_paths.add(entry.change.target)
            messages.append(f"{entry.change.key}: cleanup verification failed: {error}")
        else:
            if entry.backup_name is not None:
                try:
                    os.unlink(entry.backup_name, dir_fd=entry.parent_fd)
                    entry.backup_name = None
                except OSError as exc:
                    recovery_path = entry.parent / entry.backup_name
                    recovery_paths.add(recovery_path)
                    messages.append(f"backup retained at {recovery_path}: {exc}")
            try:
                os.fsync(entry.parent_fd)
            except OSError as exc:
                recovery_paths.add(
                    entry.parent / entry.backup_name
                    if entry.backup_name is not None
                    else entry.change.target
                )
                messages.append(f"parent fsync failed for {entry.parent}: {exc}")
        if messages:
            outcomes[entry.change.key] = _CleanupOutcome(
                tuple(messages), tuple(sorted(recovery_paths))
            )
    return outcomes


def _batch_error(
    code: str,
    message: str,
    path: Path,
    snapshot_path: Path | None,
    *,
    key: str = "*",
) -> InstructionBatchResult:
    return InstructionBatchResult(
        False,
        (InstructionResult(False, code, key, path, message),),
        snapshot_path,
    )


def _caused_by_permission_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, PermissionError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _validate_plan_shape(plan: InstructionPlan, home: Path) -> None:
    if not isinstance(plan, InstructionPlan):
        raise InstructionPlanError("invalid-plan", "instruction plan type is invalid")
    if plan.repo_root != plan.repo_root.resolve() or plan.source != plan.repo_root / "AGENTS.md":
        raise InstructionPlanError("invalid-plan", "repository or source identity is invalid")
    if not _FINGERPRINT_RE.fullmatch(plan.fingerprint):
        raise InstructionPlanError("invalid-plan", "plan fingerprint is malformed")
    if plan.replace_existing and not plan.adopt:
        raise InstructionPlanError(
            "invalid-replace-mode", "replace_existing is only valid for instruction adoption"
        )
    known = {target.key: target.path for target in build_instruction_targets(home)}
    seen: set[str] = set()
    for change in plan.changes:
        if change.key not in known:
            raise InstructionPlanError("unknown-target", f"unknown target in plan: {change.key}")
        if change.key in seen:
            raise InstructionPlanError(
                "duplicate-target", f"duplicate target in plan: {change.key}"
            )
        seen.add(change.key)
        if change.target != known[change.key] or change.source != plan.source:
            raise InstructionPlanError("invalid-plan", "planned path identity is invalid")
        if change.action not in _PLAN_ACTIONS:
            raise InstructionPlanError("invalid-plan", f"unknown action: {change.action}")
        if not isinstance(change.parent_expected, ParentExpectation):
            raise InstructionPlanError("invalid-plan", "parent expectation is invalid")
        parent_expected = change.parent_expected
        if parent_expected.kind not in {
            "missing",
            "directory",
            "symlink",
            "file",
            "special",
        }:
            raise InstructionPlanError("invalid-plan", "parent kind is invalid")
        if parent_expected.kind == "missing":
            if parent_expected.device is not None or parent_expected.inode is not None:
                raise InstructionPlanError("invalid-plan", "missing parent has an identity")
        elif parent_expected.device is None or parent_expected.inode is None:
            raise InstructionPlanError("invalid-plan", "existing parent identity is incomplete")
        if change.action in _WRITE_ACTIONS and parent_expected.kind != "directory":
            raise InstructionPlanError(
                "invalid-plan", "write target parent is not a reviewed directory"
            )
    if not seen:
        raise InstructionPlanError("invalid-plan", "instruction plan has no targets")
    has_writes = any(change.action in _WRITE_ACTIONS for change in plan.changes)
    applyable = not any(
        change.action in {"blocked", "unsupported-target"}
        for change in plan.changes
    )
    if has_writes and applyable:
        if (
            plan.snapshot_path is None
            or plan.snapshot_path.name != f"instructions-{plan.fingerprint}.json"
            or plan.snapshot_path.parent.name != "snapshots"
        ):
            raise InstructionPlanError("invalid-plan", "snapshot path is not fingerprint-derived")
    elif plan.snapshot_path is not None:
        raise InstructionPlanError(
            "invalid-plan", "non-applyable or no-write plan must not have a snapshot path"
        )


def _recompute_plan(plan: InstructionPlan, home: Path) -> InstructionPlan:
    scan = scan_instructions(plan.repo_root, home)
    state_dir = plan.snapshot_path.parent.parent if plan.snapshot_path is not None else Path(".")
    if plan.adopt:
        return plan_instruction_adoption(
            scan,
            state_dir,
            replace_existing=plan.replace_existing,
        )
    if plan.enabled is None:
        raise InstructionPlanError("invalid-plan", "set plan has no enabled intent")
    return plan_instruction_set(
        scan,
        [change.key for change in plan.changes],
        plan.enabled,
        state_dir,
    )


def apply_instruction_plan(
    plan: InstructionPlan,
    home: Path,
    *,
    expected_fingerprint: str,
) -> InstructionBatchResult:
    home = _absolute(home)
    if not isinstance(expected_fingerprint, str) or not _FINGERPRINT_RE.fullmatch(
        expected_fingerprint
    ):
        return _batch_error(
            "invalid-fingerprint",
            "expected fingerprint must be exactly 64 lowercase hexadecimal characters",
            home,
            getattr(plan, "snapshot_path", None),
        )
    try:
        _validate_plan_shape(plan, home)
    except InstructionPlanError as exc:
        return _batch_error(exc.code, str(exc), home, getattr(plan, "snapshot_path", None))
    if not secrets.compare_digest(expected_fingerprint, plan.fingerprint):
        return _batch_error(
            "state-changed",
            "reviewed fingerprint does not match the supplied plan",
            home,
            plan.snapshot_path,
        )
    try:
        recomputed = _recompute_plan(plan, home)
    except (InstructionPlanError, OSError, RuntimeError, ValueError) as exc:
        return _batch_error(
            "state-changed",
            f"instruction state changed after planning: {exc}",
            home,
            plan.snapshot_path,
        )
    if not secrets.compare_digest(expected_fingerprint, recomputed.fingerprint):
        return _batch_error(
            "state-changed",
            "instruction state changed after review",
            home,
            plan.snapshot_path,
        )
    if (
        plan.changes != recomputed.changes
        or plan.repo_root != recomputed.repo_root
        or plan.source != recomputed.source
        or plan.source_sha256 != recomputed.source_sha256
        or plan.snapshot_path != recomputed.snapshot_path
        or plan.replace_existing != recomputed.replace_existing
    ):
        return _batch_error(
            "state-changed",
            "instruction plan no longer matches exact filesystem snapshots",
            home,
            plan.snapshot_path,
        )

    blocked = [
        change
        for change in plan.changes
        if change.action in {"blocked", "unsupported-target"}
    ]
    if blocked:
        results = tuple(
            InstructionResult(
                False,
                change.action if change in blocked else "not-applied",
                change.key,
                change.target,
                change.reason if change in blocked else "batch contains blocked targets",
            )
            for change in plan.changes
        )
        return InstructionBatchResult(False, results, plan.snapshot_path)

    writes = [change for change in plan.changes if change.action in _WRITE_ACTIONS]
    if not writes:
        return InstructionBatchResult(
            True,
            tuple(
                InstructionResult(True, "no-op", change.key, change.target, change.reason)
                for change in plan.changes
            ),
            None,
        )

    try:
        prepared_stage = _write_prepared_snapshot(plan)
    except InstructionPlanError as exc:
        return _batch_error(exc.code, str(exc), plan.snapshot_path or home, plan.snapshot_path)
    except (OSError, RuntimeError, ValueError) as exc:
        return _batch_error(
            "permission-denied" if _caused_by_permission_error(exc) else "snapshot-failed",
            str(exc),
            plan.snapshot_path or home,
            plan.snapshot_path,
        )

    try:
        home_fd = os.open(home, _DIRECTORY_FLAGS)
    except OSError as exc:
        return _batch_error(
            "permission-denied" if _caused_by_permission_error(exc) else "apply-failed",
            str(exc),
            home,
            plan.snapshot_path,
        )
    entries: list[_AppliedInstruction] = []
    failed_change: InstructionChange | None = None
    batch_failure_path: Path | None = None
    failure: BaseException | None = None
    try:
        for change in writes:
            failed_change = change
            try:
                entry = _apply_one(plan, home_fd, home, change)
            except _InstructionApplyFailure as exc:
                entries.append(exc.entry)
                raise
            entries.append(entry)
        if not _source_still_matches(plan):
            failed_change = writes[-1]
            raise OSError("instruction source changed before transaction commit")
        _verify_applied_batch(entries, home_fd)
        try:
            _mark_snapshot_committed(plan, prepared_stage)
        except _SnapshotCommitFailure:
            failed_change = None
            batch_failure_path = plan.snapshot_path
            raise
        except Exception as exc:
            failed_change = None
            batch_failure_path = plan.snapshot_path
            raise OSError(f"commit marker failed: {exc}") from exc
    except Exception as exc:
        failure = exc

    if failure is not None:
        permission_denied = _caused_by_permission_error(failure)
        recovery_required = (
            isinstance(failure, _SnapshotCommitFailure)
            and failure.recovery_state == _SnapshotRecoveryState.RECOVERY_REQUIRED
        )
        recovery_paths = (
            failure.recovery_paths
            if isinstance(failure, _SnapshotCommitFailure)
            else ()
        )
        rollback_outcomes = (
            {}
            if recovery_required
            else _rollback_entries(entries, home_fd, home, plan.source)
        )
        rollback_messages = (
            ["HOME rollback skipped because durable prepared recovery is unavailable"]
            if recovery_required
            else [
                rollback_message
                for outcome in rollback_outcomes.values()
                for rollback_message in outcome.messages
            ]
        )
        message = str(failure)
        if rollback_messages:
            message += "; " + "; ".join(rollback_messages)
        results: list[InstructionResult] = []
        failed_key = failed_change.key if failed_change is not None else "*"
        applied_keys = {entry.change.key for entry in entries}
        for change in plan.changes:
            rollback_outcome = rollback_outcomes.get(change.key)
            result_recovery_paths = tuple(
                sorted(
                    {
                        *recovery_paths,
                        *(rollback_outcome.recovery_paths if rollback_outcome else ()),
                    }
                )
            )
            if recovery_required and change.key in applied_keys:
                results.append(
                    InstructionResult(
                        False,
                        "rollback-skipped",
                        change.key,
                        change.target,
                        message,
                        result_recovery_paths,
                    )
                )
            elif rollback_outcome is not None and not rollback_outcome.restored:
                results.append(
                    InstructionResult(
                        False,
                        "rollback-incomplete",
                        change.key,
                        change.target,
                        message,
                        result_recovery_paths,
                    )
                )
            elif change.key == failed_key:
                results.append(
                    InstructionResult(
                        False,
                        "permission-denied" if permission_denied else "apply-failed",
                        change.key,
                        change.target,
                        message,
                        result_recovery_paths,
                    )
                )
            elif rollback_outcome is not None:
                results.append(
                    InstructionResult(
                        False,
                        "rolled-back",
                        change.key,
                        change.target,
                        message,
                        result_recovery_paths,
                    )
                )
            else:
                results.append(
                    InstructionResult(
                        False,
                        "not-applied",
                        change.key,
                        change.target,
                        message,
                        result_recovery_paths,
                    )
                )
        if batch_failure_path is not None:
            results.append(
                InstructionResult(
                    False,
                    "permission-denied" if permission_denied else "apply-failed",
                    "*",
                    batch_failure_path,
                    message,
                    tuple(sorted(set(recovery_paths))),
                )
            )
        for entry in entries:
            os.close(entry.parent_fd)
        os.close(home_fd)
        return InstructionBatchResult(False, tuple(results), plan.snapshot_path)

    cleanup_outcomes = _cleanup_committed(entries, home_fd)
    results: list[InstructionResult] = []
    for change in plan.changes:
        cleanup = cleanup_outcomes.get(change.key)
        if cleanup is not None:
            results.append(
                InstructionResult(
                    False,
                    "cleanup-failed",
                    change.key,
                    change.target,
                    "; ".join(cleanup.messages),
                    cleanup.recovery_paths,
                )
            )
        elif change.action in _WRITE_ACTIONS:
            results.append(
                InstructionResult(
                    True, "applied", change.key, change.target, change.reason
                )
            )
        else:
            results.append(
                InstructionResult(
                    True, "no-op", change.key, change.target, change.reason
                )
            )
    for entry in entries:
        os.close(entry.parent_fd)
    os.close(home_fd)
    return InstructionBatchResult(
        not cleanup_outcomes, tuple(results), plan.snapshot_path
    )


def scan_incomplete_transactions(state_dir: Path) -> tuple[IncompleteTransaction, ...]:
    snapshots = _absolute(state_dir) / "snapshots"
    if not snapshots.is_dir() or snapshots.is_symlink():
        return ()

    def read_payload(path: Path) -> dict[str, object] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def target_backups(payload: dict[str, object]) -> set[Path]:
        backups: set[Path] = set()
        targets = payload.get("targets")
        if not isinstance(targets, list):
            return backups
        for target in targets:
            if not isinstance(target, dict) or not isinstance(target.get("path"), str):
                continue
            try:
                backups.update(
                    Path(target["path"]).parent.glob(".agent-manager-*.backup")
                )
            except OSError:
                continue
        return backups

    incomplete: list[IncompleteTransaction] = []
    reported_recoveries: set[Path] = set()
    recovery_paths = (
        *snapshots.glob(".agent-manager-*.prepared"),
        *snapshots.glob(".agent-manager-*.committed-failed"),
    )
    recovery_records = tuple(
        (path, payload)
        for path in recovery_paths
        if (payload := read_payload(path)) is not None
    )

    def append_prepared(path: Path, payload: dict[str, object]) -> None:
        fingerprint = payload.get("fingerprint")
        if not isinstance(fingerprint, str):
            return
        related = tuple(
            (candidate_path, candidate_payload)
            for candidate_path, candidate_payload in recovery_records
            if candidate_payload.get("fingerprint") == fingerprint
        )
        recovery: set[Path] = {candidate_path for candidate_path, _ in related}
        recovery.update(target_backups(payload))
        for candidate_path, candidate_payload in related:
            reported_recoveries.add(candidate_path)
            recovery.update(target_backups(candidate_payload))
        ordered_recovery = tuple(sorted(recovery))
        message = "prepared instruction transaction requires manual review"
        if ordered_recovery:
            message += "; retained recovery: " + ", ".join(map(str, ordered_recovery))
        incomplete.append(
            IncompleteTransaction(
                "incomplete-transaction",
                path,
                fingerprint,
                ordered_recovery,
                message,
            )
        )

    for path in sorted(snapshots.glob("instructions-*.json")):
        payload = read_payload(path)
        if payload is not None and payload.get("phase") == "prepared":
            append_prepared(path, payload)

    for recovery_path, payload in sorted(recovery_records, key=lambda item: str(item[0])):
        if recovery_path in reported_recoveries or payload.get("phase") != "prepared":
            continue
        append_prepared(recovery_path, payload)
    return tuple(sorted(incomplete, key=lambda item: str(item.path)))
