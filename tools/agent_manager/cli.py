from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shlex
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TextIO

from .instructions import (
    IncompleteTransaction,
    InstructionBatchResult,
    InstructionScan,
    InstructionState,
    apply_instruction_plan,
    plan_instruction_adoption,
    plan_instruction_set,
    scan_incomplete_transactions,
    scan_instructions,
)
from .skills import (
    AdoptionPlan,
    BatchResult,
    LinkState,
    ManagedState,
    RepositoryScan,
    ScanIssue,
    SurfaceStatus,
    _enabled_codex_plugin_sources,
    apply_adoption,
    apply_plan,
    build_adapters,
    detect_surfaces,
    plan_adoption,
    plan_set,
    scan_inventory,
    scan_managed_state,
    scan_repository,
)
from .server import _serve


TOOLS = ("claude", "codex", "copilot", "antigravity")
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
INSTRUCTION_TARGETS = ("shared", "claude", "codex", "copilot", "antigravity")
FINGERPRINT_PATTERN = r"[0-9a-f]{64}"


@dataclasses.dataclass(frozen=True)
class AgentSummary:
    skills_enabled: int
    skills_total: int
    instructions_enabled: int
    instructions_total: int
    conflicts: int
    issues: int


@dataclasses.dataclass(frozen=True)
class AgentState:
    repository: RepositoryScan
    skills: ManagedState
    instructions: InstructionScan
    surfaces: tuple[SurfaceStatus, ...]
    summary: AgentSummary
    scanned_at: str
    incomplete_transactions: tuple[IncompleteTransaction, ...]


def to_jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {
            field.name: to_jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true")


def _add_skill_commands(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True)
    _add_json(commands.add_parser("status"))

    set_parser = commands.add_parser("set")
    set_parser.add_argument("skill", nargs="?", default=None)
    set_parser.add_argument("--all", action="store_true")
    set_parser.add_argument(
        "--tool",
        choices=(*TOOLS, "all"),
        required=True,
    )
    toggle = set_parser.add_mutually_exclusive_group(required=True)
    toggle.add_argument("--on", action="store_true")
    toggle.add_argument("--off", action="store_true")
    set_parser.add_argument("--apply", action="store_true")
    _add_json(set_parser)

    adopt_parser = commands.add_parser("adopt")
    adopt_parser.add_argument("--apply", action="store_true")
    _add_json(adopt_parser)


def _fingerprint(value: str) -> str:
    if re.fullmatch(FINGERPRINT_PATTERN, value) is None:
        raise argparse.ArgumentTypeError(
            "fingerprint must be exactly 64 lowercase hexadecimal characters"
        )
    return value


def _add_instruction_commands(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True)
    _add_json(commands.add_parser("status"))

    set_parser = commands.add_parser("set")
    set_parser.add_argument(
        "--target",
        choices=(*INSTRUCTION_TARGETS, "all"),
        required=True,
    )
    toggle = set_parser.add_mutually_exclusive_group(required=True)
    toggle.add_argument("--on", action="store_true")
    toggle.add_argument("--off", action="store_true")
    set_parser.add_argument("--apply", action="store_true")
    set_parser.add_argument("--expect-fingerprint", type=_fingerprint)
    _add_json(set_parser)

    adopt_parser = commands.add_parser("adopt")
    adopt_parser.add_argument("--replace-existing", action="store_true")
    adopt_parser.add_argument("--apply", action="store_true")
    adopt_parser.add_argument("--expect-fingerprint", type=_fingerprint)
    _add_json(adopt_parser)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-manager")
    resources = parser.add_subparsers(dest="resource", required=True)
    for name in ("status", "doctor"):
        _add_json(resources.add_parser(name))

    _add_skill_commands(resources.add_parser("skills"))
    _add_instruction_commands(resources.add_parser("instructions"))

    serve_parser = resources.add_parser("serve")
    serve_parser.add_argument("--open", action="store_true")
    return parser


def _build_state(
    repo_root: Path,
    home: Path,
    which: Callable[[str], str | None],
    applications: Path,
) -> ManagedState:
    repository = scan_repository(repo_root)
    adapters = build_adapters(home)
    surfaces = detect_surfaces(which=which, applications=applications)
    return scan_managed_state(repository, adapters, surfaces)


def build_agent_state(
    repo_root: Path,
    home: Path,
    which: Callable[[str], str | None],
    applications: Path,
) -> AgentState:
    repository = scan_repository(repo_root)
    adapters = build_adapters(home)
    surfaces = detect_surfaces(which=which, applications=applications)
    skills = scan_managed_state(repository, adapters, surfaces)
    instruction_scan = scan_instructions(repo_root, home)
    incomplete = scan_incomplete_transactions(
        home / ".local/state/lucas-agent-manager"
    )
    enabled_skills = {
        target.slug
        for target in skills.targets
        if target.state in {LinkState.ENABLED, LinkState.LEGACY}
    }
    skill_conflicts = sum(
        target.state == LinkState.CONFLICT for target in skills.targets
    )
    skill_errors = sum(target.state == LinkState.ERROR for target in skills.targets)
    instruction_conflicts = sum(
        target.state == InstructionState.CONFLICT
        for target in instruction_scan.targets
    )
    instruction_errors = sum(
        target.state == InstructionState.BROKEN
        for target in instruction_scan.targets
    )
    summary = AgentSummary(
        len(enabled_skills),
        len(repository.skills),
        sum(
            target.state == InstructionState.ENABLED
            for target in instruction_scan.targets
        ),
        len(instruction_scan.targets),
        skill_conflicts + instruction_conflicts,
        len(repository.issues)
        + len(instruction_scan.issues)
        + skill_errors
        + instruction_errors
        + len(incomplete),
    )
    scanned_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return AgentState(
        repository,
        skills,
        instruction_scan,
        tuple(surfaces.values()),
        summary,
        scanned_at,
        incomplete,
    )


def _state_ok(state: ManagedState) -> bool:
    return not state.repository.issues and all(
        target.state not in {LinkState.CONFLICT, LinkState.ERROR}
        for target in state.targets
    )


def _instructions_ok(scan: InstructionScan) -> bool:
    return not scan.issues and all(
        target.state not in {InstructionState.CONFLICT, InstructionState.BROKEN}
        for target in scan.targets
    )


def _agent_state_ok(state: AgentState) -> bool:
    return (
        _state_ok(state.skills)
        and _instructions_ok(state.instructions)
        and not state.incomplete_transactions
    )


def _skills_container(state: AgentState) -> dict[str, object]:
    return {
        "records": state.skills.repository.skills,
        "adapters": state.skills.adapters,
        "targets": state.skills.targets,
        "issues": state.skills.repository.issues,
    }


def _instructions_container(state: AgentState) -> dict[str, object]:
    return {
        "source": state.instructions.source,
        "source_sha256": state.instructions.source_sha256,
        "source_text": state.instructions.source_text,
        "targets": state.instructions.targets,
        "manual_surfaces": state.instructions.manual_surfaces,
        "issues": state.instructions.issues,
    }


def _state_problem(state: AgentState, domain: str | None = None) -> tuple[str | None, str]:
    if state.incomplete_transactions and domain != "skills":
        issue = state.incomplete_transactions[0]
        return issue.code, issue.message
    if domain != "skills" and state.instructions.issues:
        issue = state.instructions.issues[0]
        return issue.code, issue.message
    if domain != "instructions" and state.skills.repository.issues:
        issue = state.skills.repository.issues[0]
        return issue.code, issue.message
    if domain != "skills":
        failed = next(
            (
                target for target in state.instructions.targets
                if target.state in {InstructionState.CONFLICT, InstructionState.BROKEN}
            ),
            None,
        )
        if failed is not None:
            return failed.state.value, failed.message
    if domain != "instructions":
        failed = next(
            (
                target for target in state.skills.targets
                if target.state in {LinkState.CONFLICT, LinkState.ERROR}
            ),
            None,
        )
        if failed is not None:
            return failed.state.value, failed.message
    return None, ""


def _base_payload(
    state: AgentState,
    mode: str,
    *,
    domain: str | None = None,
    ok: bool | None = None,
) -> dict[str, object]:
    if ok is None:
        if domain == "skills":
            ok = _state_ok(state.skills)
        elif domain == "instructions":
            ok = _instructions_ok(state.instructions) and not state.incomplete_transactions
        else:
            ok = _agent_state_ok(state)
    code, message = (None, "") if ok else _state_problem(state, domain)
    payload: dict[str, object] = {
        "mode": mode,
        "ok": ok,
        "code": code,
        "message": message,
        "repo_root": state.repository.repo_root,
        "surfaces": state.surfaces,
        "summary": state.summary,
        "scanned_at": state.scanned_at,
    }
    if domain != "instructions":
        payload["skills"] = _skills_container(state)
    if domain != "skills":
        payload["instructions"] = _instructions_container(state)
    return payload


def _empty_adoption_changes() -> dict[str, object]:
    return {
        "link_changes": (),
        "container_changes": (),
        "bridge_removals": (),
        "snapshot_path": None,
    }


def _command_payload(
    command: str,
    mode: str,
    repo_root: Path,
    state: AgentState | None = None,
    domain: str | None = None,
) -> dict[str, object]:
    payload = _base_payload(state, mode, domain=domain) if state is not None else {
        "mode": mode,
        "ok": False,
        "code": None,
        "message": "",
        "repo_root": repo_root,
        "surfaces": (),
        "summary": AgentSummary(0, 0, 0, 0, 0, 0),
        "scanned_at": "",
    }
    if state is None and domain != "instructions":
        payload["skills"] = {
            "records": (), "adapters": (), "targets": (), "issues": (),
        }
    if state is None and domain != "skills":
        payload["instructions"] = {
            "source": repo_root / "AGENTS.md",
            "source_sha256": None,
            "source_text": None,
            "targets": (),
            "manual_surfaces": (),
            "issues": (),
        }
    if command == "doctor":
        payload["inventory"] = ()
    elif command == "set":
        payload["changes"] = ()
        if domain == "instructions":
            payload["fingerprint"] = None
            payload["snapshot_path"] = None
        if domain != "instructions" or mode == "apply":
            payload["results"] = ()
    elif command == "adopt":
        payload["changes"] = (
            () if domain == "instructions" else _empty_adoption_changes()
        )
        if domain == "instructions":
            payload["fingerprint"] = None
            payload["snapshot_path"] = None
        if domain != "instructions" or mode == "apply":
            payload["results"] = ()
    return payload


def _set_error(payload: dict[str, object], code: str, message: str) -> None:
    payload["ok"] = False
    payload["code"] = code
    payload["message"] = message


def _repository_issue_message(issues: Sequence[ScanIssue]) -> str:
    details = "; ".join(f"{issue.code}: {issue.path}" for issue in issues)
    return (
        "repository contains invalid skills; no changes were planned or applied"
        f": {details}"
    )


def _batch_code(result: BatchResult | InstructionBatchResult) -> str | None:
    failures = [item for item in result.results if not item.ok]
    if not failures:
        return None
    if len(failures) != len(result.results):
        return "partial-failure"
    return failures[0].code


def _add_batch(
    payload: dict[str, object],
    result: BatchResult | InstructionBatchResult,
) -> None:
    payload["ok"] = result.ok
    payload["results"] = result.results
    code = _batch_code(result)
    if code is not None:
        payload["code"] = code
        failure = next(item for item in result.results if not item.ok)
        payload["message"] = failure.message


def _adoption_changes(plan: AdoptionPlan) -> dict[str, object]:
    return {
        "link_changes": plan.link_changes,
        "container_changes": plan.container_changes,
        "bridge_removals": plan.bridge_removals,
        "snapshot_path": plan.snapshot_path,
    }


def _set_plan_status(
    payload: dict[str, object],
    changes: Sequence[object],
) -> bool:
    conflict = next(
        (
            change
            for change in changes
            if getattr(change, "action", None)
            in {
                "blocked", "conflict", "error", "target-conflict",
                "unsupported-target",
            }
        ),
        None,
    )
    requires_adopt = next(
        (
            change
            for change in changes
            if getattr(change, "action", None) == "requires-adopt"
        ),
        None,
    )
    failure = conflict or requires_adopt
    if failure is None:
        payload["ok"] = True
        payload["code"] = None
        payload["message"] = ""
        payload.pop("path", None)
        return True
    code = "target-conflict" if conflict is not None else "requires-adopt"
    _set_error(payload, code, getattr(failure, "reason", "plan contains a conflict"))
    payload["path"] = getattr(failure, "target", None)
    return False


def _doctor_issues(state: ManagedState, home: Path) -> tuple[ScanIssue, ...]:
    _sources, plugin_issues = _enabled_codex_plugin_sources(home)
    return (*state.repository.issues, *plugin_issues)


def _instruction_preview_command(args: argparse.Namespace) -> str:
    command = f"agent-manager instructions {args.command}"
    if args.command == "set":
        toggle = "--on" if args.on else "--off"
        return f"{command} --target {args.target} {toggle}"
    if args.replace_existing:
        return f"{command} --replace-existing"
    return command


def _instruction_plan_next(
    args: argparse.Namespace,
    payload: Mapping[str, object],
) -> str:
    changes = payload.get("changes", ())
    blocked = next(
        (
            change for change in changes
            if getattr(change, "action", None) in {"blocked", "unsupported-target"}
        ),
        None,
    )
    if blocked is not None:
        target = Path(getattr(blocked, "target"))
        reason = getattr(blocked, "reason", "")
        review_path = target.parent if reason.startswith("parent-") else target
        quoted = shlex.quote(str(review_path))
        if reason == "parent-missing":
            return f"mkdir -m 700 {quoted}"
        return f"ls -ld {quoted}"

    preview = _instruction_preview_command(args)
    fingerprint = payload.get("fingerprint")
    if not isinstance(fingerprint, str):
        return preview
    return f"{preview} --apply --expect-fingerprint {fingerprint}"


def _write_text(
    stdout: TextIO,
    state: AgentState,
    mode: str,
    payload: Mapping[str, object],
    next_command: str | None = None,
) -> None:
    stdout.write(f"Repository: {state.repository.repo_root}\n")
    stdout.write(
        f"Skills: {state.summary.skills_enabled}/{state.summary.skills_total}\n"
    )
    stdout.write(
        "Instructions: "
        f"{state.summary.instructions_enabled}/{state.summary.instructions_total}\n"
    )
    stdout.write(f"Conflicts: {state.summary.conflicts}\n")
    stdout.write(f"Issues: {state.summary.issues}\n")
    if not payload.get("ok", False) and payload.get("code"):
        stdout.write(f"Error [{payload['code']}]: {payload.get('message', '')}\n")
    if "changes" in payload:
        changes = payload["changes"]
        count = len(changes) if isinstance(changes, (list, tuple)) else sum(
            len(items)
            for key, items in changes.items()
            if key.endswith("_changes") or key == "bridge_removals"
        ) if isinstance(changes, dict) else 0
        stdout.write(f"Changes: {count}\n")
    if "results" in payload:
        results = payload["results"]
        stdout.write(f"Results: {len(results) if isinstance(results, (list, tuple)) else 0}\n")
    if next_command is None:
        next_command = {
            "status": "agent-manager doctor",
            "doctor": "agent-manager skills status",
            "plan": "repeat the command with --apply",
            "apply": "agent-manager status",
        }[mode]
    stdout.write(f"Next: {next_command}\n")


def _write_payload(
    stdout: TextIO,
    state: AgentState,
    mode: str,
    payload: Mapping[str, object],
    json_output: bool,
    next_command: str | None = None,
) -> None:
    if json_output:
        json.dump(to_jsonable(dict(payload)), stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        _write_text(stdout, state, mode, payload, next_command)


def main(
    argv: Sequence[str] | None = None,
    *,
    home: Path | None = None,
    repo_root: Path | None = None,
    stdout: TextIO | None = None,
    which: Callable[[str], str | None] = shutil.which,
    applications: Path = Path("/Applications"),
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.resource == "skills" and args.command == "set":
        if bool(args.all) == bool(args.skill):
            parser.error("skills set requires exactly one of <skill> or --all")
    if args.resource == "instructions" and args.command in {"set", "adopt"}:
        has_fingerprint = args.expect_fingerprint is not None
        if args.apply and not has_fingerprint:
            parser.error("Instructions apply requires --expect-fingerprint")
        if not args.apply and has_fingerprint:
            parser.error("--expect-fingerprint is only accepted with --apply")

    stdout = stdout or sys.stdout
    home = (home or Path.home()).expanduser().resolve()
    repo_root = (repo_root or DEFAULT_REPO_ROOT).expanduser().resolve()
    applications = applications.expanduser().resolve()

    if args.resource == "serve":
        return _serve(stdout, args.open, repo_root, home, applications, which)

    command = getattr(args, "command", args.resource)
    domain = args.resource if args.resource in {"skills", "instructions"} else None
    if command in {"set", "adopt"}:
        mode = "apply" if args.apply else "plan"
    else:
        mode = args.resource if domain is None else command
    state: AgentState | None = None
    payload = _command_payload(command, mode, repo_root, domain=domain)
    try:
        state = build_agent_state(repo_root, home, which, applications)
        payload = _command_payload(command, mode, repo_root, state, domain)
        if command == "status":
            _write_payload(stdout, state, "status", payload, args.json)
            return 0 if payload["ok"] else 1

        if args.resource == "doctor":
            inventory = scan_inventory(state.skills, home)
            payload["inventory"] = inventory
            _sources, plugin_issues = _enabled_codex_plugin_sources(home)
            broken_inventory = any(
                record.source_type == "broken" or record.flags
                for record in inventory
            )
            ok = _agent_state_ok(state) and not plugin_issues and not broken_inventory
            payload["ok"] = ok
            if state.incomplete_transactions:
                issue = state.incomplete_transactions[0]
                payload["code"] = issue.code
                payload["message"] = issue.message
            elif plugin_issues:
                payload["code"] = plugin_issues[0].code
                payload["message"] = plugin_issues[0].message
            elif broken_inventory:
                payload["code"] = "inventory-issue"
                payload["message"] = "inventory contains broken or flagged records"
            _write_payload(stdout, state, "doctor", payload, args.json)
            return 0 if ok else 1

        if domain == "skills" and state.skills.repository.issues:
            _set_error(
                payload,
                "invalid-skill",
                _repository_issue_message(state.skills.repository.issues),
            )
            _write_payload(stdout, state, mode, payload, args.json)
            return 1

        if domain == "skills" and command == "set":
            slugs = (
                [skill.slug for skill in state.skills.repository.skills]
                if args.all
                else [args.skill]
            )
            plan = plan_set(state.skills, slugs, [args.tool], args.on)
            payload["changes"] = plan.changes
            if not args.apply:
                ok = _set_plan_status(payload, plan.changes)
                _write_payload(stdout, state, "plan", payload, args.json)
                return 0 if ok else 1

            result = apply_plan(
                plan,
                {adapter.key: adapter for adapter in state.skills.adapters},
            )
            _add_batch(payload, result)
            state = build_agent_state(repo_root, home, which, applications)
            changes = payload["changes"]
            payload = _command_payload(command, mode, repo_root, state, domain)
            payload["changes"] = changes
            _add_batch(payload, result)
            _write_payload(stdout, state, "apply", payload, args.json)
            return 0 if result.ok else 1

        if domain == "skills":
            plan = plan_adoption(
                state.skills,
                home / ".local/state/lucas-agent-manager",
            )
            payload["changes"] = _adoption_changes(plan)
            if not args.apply:
                ok = _set_plan_status(payload, plan.link_changes)
                _write_payload(stdout, state, "plan", payload, args.json)
                return 0 if ok else 1

            result = apply_adoption(
                plan,
                {adapter.key: adapter for adapter in state.skills.adapters},
            )
            changes = payload["changes"]
            _add_batch(payload, result)
            try:
                state = build_agent_state(repo_root, home, which, applications)
            except Exception as exc:
                _set_error(
                    payload,
                    "post-apply-verification-failed",
                    "skill adoption apply completed and returned results, "
                    f"but post-apply state verification failed: {exc}",
                )
                _write_payload(stdout, state, "apply", payload, args.json)
                return 1
            payload = _command_payload(command, mode, repo_root, state, domain)
            payload["changes"] = changes
            _add_batch(payload, result)
            _write_payload(stdout, state, "apply", payload, args.json)
            return 0 if result.ok else 1

        state_dir = home / ".local/state/lucas-agent-manager"
        if command == "set":
            targets = INSTRUCTION_TARGETS if args.target == "all" else (args.target,)
            instruction_plan = plan_instruction_set(
                state.instructions,
                targets,
                args.on,
                state_dir,
            )
        else:
            instruction_plan = plan_instruction_adoption(
                state.instructions,
                state_dir,
                replace_existing=args.replace_existing,
            )
        payload["changes"] = instruction_plan.changes
        payload["fingerprint"] = instruction_plan.fingerprint
        payload["snapshot_path"] = instruction_plan.snapshot_path
        if not args.apply:
            ok = _set_plan_status(payload, instruction_plan.changes)
            _write_payload(
                stdout,
                state,
                "plan",
                payload,
                args.json,
                _instruction_plan_next(args, payload),
            )
            return 0 if ok else 1

        instruction_result = apply_instruction_plan(
            instruction_plan,
            home,
            expected_fingerprint=args.expect_fingerprint,
        )
        reviewed = {
            "changes": payload["changes"],
            "fingerprint": payload["fingerprint"],
            "snapshot_path": payload["snapshot_path"],
        }
        payload.update(reviewed)
        _add_batch(payload, instruction_result)
        try:
            state = build_agent_state(repo_root, home, which, applications)
        except Exception as exc:
            _set_error(
                payload,
                "post-apply-verification-failed",
                "instruction apply completed and returned results, but post-apply "
                f"state verification failed: {exc}",
            )
            _write_payload(
                stdout,
                state,
                "apply",
                payload,
                args.json,
                "agent-manager instructions status",
            )
            return 1
        payload = _command_payload(command, mode, repo_root, state, domain)
        payload.update(reviewed)
        _add_batch(payload, instruction_result)
        _write_payload(stdout, state, "apply", payload, args.json)
        return 0 if instruction_result.ok else 1
    except ValueError as exc:
        if domain == "skills" and command == "set":
            code = "invalid-skill"
        elif domain == "skills" and command == "adopt":
            code = "adoption-failed"
        elif domain == "instructions":
            code = getattr(exc, "code", "invalid-instructions")
        else:
            code = "internal-error"
        _set_error(payload, code, str(exc))
    except PermissionError as exc:
        _set_error(payload, "permission-denied", str(exc))
    except (OSError, RuntimeError) as exc:
        code = (
            "adoption-failed"
            if domain == "skills" and command == "adopt"
            else "verification-failed"
        )
        _set_error(payload, code, str(exc))
    except Exception as exc:
        _set_error(payload, "internal-error", str(exc))

    if args.json:
        json.dump(to_jsonable(payload), stdout, ensure_ascii=False, indent=2)
        stdout.write("\n")
    else:
        stdout.write(f"Error [{payload['code']}]: {payload['message']}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
