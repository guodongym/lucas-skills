# Agent Manager and Personal Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the repository-private `skill-manager` with one `agent-manager` that preserves all Skill behavior, safely manages five global personal-instruction links from the repository `AGENTS.md`, and exposes both resources through a redesigned local Agent routing console.

**Architecture:** Rename the package without a compatibility layer, then separate shared filesystem primitives, the existing Skills domain, the new Instructions domain, CLI orchestration, localhost HTTP transport, and static UI assets. Instructions use a trusted repository source, explicit dry-run plans, byte-exact snapshots, same-directory atomic replacement, and reverse-order rollback; the browser consumes server truth and never writes outside the exact HTTP operations.

**Tech Stack:** Python 3.11+, `uv`, `uv_build>=0.11.28,<0.12`, PyYAML, standard-library `unittest` and HTTP server, native HTML/CSS/JavaScript, Node.js for extracted pure-function tests, macOS filesystem semantics.

**Execution Gate:** This plan is awaiting review. Do not execute any implementation task until the user explicitly approves the reviewed plan. Approval to implement does not authorize writes to the real HOME; real Instructions apply and legacy-state archival each require the separate gates in Task 10.

## Global Constraints

- Public management entry point is exactly `uv run agent-manager`; remove `skill-manager`, `tools.skill_manager`, aliases, wrappers, shims, and deprecation messages.
- Keep `uv run upstream-sync` independent and behaviorally unchanged.
- Runtime dependencies remain exactly `PyYAML`; do not add a frontend framework, CSS framework, icon package, external font, CDN, or build step.
- Preserve all existing Skill scan, inventory, adapter, Desktop/CLI detection, set/adopt, conflict protection, FD safety, snapshot, and recovery behavior for the current 15 Skills and 75 targets.
- Current tool families are Claude, Codex, GitHub Copilot, and Antigravity; Antigravity CLI command detection remains `agy`.
- The five managed Instructions targets are `shared`, `claude`, `codex`, `copilot`, and `antigravity`; Copilot Desktop remains a manual surface.
- The sole Instructions source is the running checkout's trusted `<repo>/AGENTS.md`; invalid or symlinked source state fails closed for every Instructions write.
- All set/adopt operations default to preview. `instructions adopt --replace-existing` is a legal dry-run that shows the exact replace plan; only adding explicit `--apply` writes.
- Every Instructions apply requires the 64-character lowercase SHA-256 returned by its reviewed preview as `--expect-fingerprint` / `expected_fingerprint`; mismatch fails before snapshot or HOME mutation.
- Instructions directories are never replaced or deleted, including with `--replace-existing`.
- An Instructions request is atomic across its selected targets; apply-time drift, snapshot failure, mutation failure, or verification failure triggers reverse-order rollback.
- Cross-directory atomicity covers catchable in-process failures, not SIGKILL or power loss; each leaf transition remains atomic, snapshots use `prepared`/`committed`, and read-only diagnostics report incomplete transactions without auto-recovery writes.
- Arbitrary regular-file bytes are Base64-encoded in JSON snapshots with permission mode and SHA-256; do not decode them as text.
- New state root is `~/.local/state/lucas-agent-manager/`; runtime does not read the old `~/.local/state/lucas-skills-manager/` format.
- HTTP binds only `127.0.0.1` on a random port, validates Host/Origin/content type/body size/method/path, uses `X-Agent-Manager-Token`, and serves only `/`, `/app.css`, and `/app.js` through component-wise `O_NOFOLLOW` checks.
- `index.html` is the only token-templated asset; CSS and JS are returned byte-for-byte. CSP excludes `unsafe-inline`.
- Use the approved visual tokens: Canvas `#F4F6F8`, Ink `#171A1F`, Muted `#69717D`, Route `#2563EB`, Healthy `#16825D`, Attention `#B86B12`.
- Preserve completed historical spec/plan documents as execution evidence; exclude them from old-command residual scans instead of rewriting them.
- Implementation and automated tests use an isolated worktree plus temporary HOME. No task before Task 10 may modify real global links or move real state directories.
- Every implementation commit follows repository commit conventions, includes a body with rationale and verification, and ends with `Co-authored-by: OpenAI Codex <noreply@openai.com>`.

---

## File Map

| Path | Action | Responsibility |
| --- | --- | --- |
| `pyproject.toml` | Modify | Replace the console script and package-data expectations |
| `tools/agent_manager/__init__.py` | Move/modify | Agent Manager package marker |
| `tools/agent_manager/core.py` | Rewrite | Shared snapshots, hashing, path identity, errors, and filesystem safety primitives |
| `tools/agent_manager/skills.py` | Create from move | Existing Skill repository, adapter, inventory, plan, apply, and adoption behavior |
| `tools/agent_manager/instructions.py` | Create | Instruction source validation, states, planning, snapshotting, atomic apply, and rollback |
| `tools/agent_manager/cli.py` | Move/rewrite | Umbrella parser, domain dispatch, text/JSON output, aggregate status and doctor |
| `tools/agent_manager/server.py` | Create from extraction | Local HTTP server, exact API schema, token injection, secure static reads |
| `tools/agent_manager/web/index.html` | Rewrite | Accessible semantic shell and four views |
| `tools/agent_manager/web/app.css` | Create | Approved visual system, responsive layout, focus and reduced-motion rules |
| `tools/agent_manager/web/app.js` | Create | Server-state rendering, topology, filters, drawers, preview/apply and clipboard flow |
| `tests/test_agent_manager.py` | Rename/modify | Existing 106 Skill, CLI, HTTP, and security regression tests during migration |
| `tests/test_agent_manager_instructions.py` | Create | Instruction state, plan, snapshot, atomicity, rollback, race, and source-trust tests |
| `tests/test_agent_manager_http.py` | Create | Namespaced API, request schema, security headers, token, and static-file tests |
| `tests/test_agent_manager_web.py` | Create | Static UI contracts and Node-executed real JavaScript behavior tests |
| `tests/test_project_layout.py` | Modify | Console scripts, package paths, removed compatibility surface, wheel data contract |
| `README.md` | Modify | Unified CLI, Instructions management, Web UI startup, safety and migration gates |
| `docs/superpowers/specs/2026-07-16-agent-manager-and-personal-instructions-design.md` | Modify at closeout | Mark implemented only after branch verification succeeds |
| `docs/superpowers/specs/2026-07-14-global-skill-manager-design.md` | Verify only | Preserve historical command evidence |
| `docs/superpowers/plans/2026-07-14-global-skill-manager.md` | Verify only | Preserve historical command evidence |
| `docs/superpowers/specs/2026-07-15-repository-layout-and-cli-design.md` | Verify only | Preserve historical command evidence |
| `docs/superpowers/plans/2026-07-15-repository-layout-and-cli.md` | Verify only | Preserve historical command evidence |

---

### Task 1: Rename the runtime package and command without changing Skill behavior

**Files:**
- Move: `tools/skill_manager/` → `tools/agent_manager/`
- Modify after move: `tools/agent_manager/web/index.html`
- Move: `tests/test_skill_manager.py` → `tests/test_agent_manager.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_project_layout.py`
- Modify: `tests/test_agent_manager.py`

**Interfaces:**
- Produces console script `agent-manager = "tools.agent_manager.cli:main"`.
- Preserves `tools.agent_manager.cli.main(argv, *, home, repo_root, stdout, which, applications) -> int`.
- Temporarily preserves the existing flat Skill subcommands inside the renamed package; Task 5 replaces the parser with the final nested grammar.
- Preserves every existing Skill dataclass and function under `tools.agent_manager.core` until Task 2.

- [ ] **Step 1: Change layout tests first**

Update `tests/test_project_layout.py` so the expected script map is:

```python
{
    "agent-manager": "tools.agent_manager.cli:main",
    "upstream-sync": "tools.upstream_sync.vendor:main",
}
```

Add a removal contract:

```python
def test_skill_manager_runtime_compatibility_is_removed(self) -> None:
    self.assertFalse((ROOT / "tools/skill_manager").exists())
    self.assertFalse((ROOT / "tests/test_skill_manager.py").exists())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    self.assertNotIn("skill-manager", project["project"]["scripts"])
```

- [ ] **Step 2: Run the focused tests and verify the old names fail**

Run:

```bash
uv run python -m unittest tests.test_project_layout -v
```

Expected: FAIL because `skill-manager` and `tools/skill_manager` still exist.

- [ ] **Step 3: Move the package and regression test mechanically**

Run:

```bash
git mv tools/skill_manager tools/agent_manager
git mv tests/test_skill_manager.py tests/test_agent_manager.py
```

In `tests/test_agent_manager.py`, replace import and patch prefixes exactly:

```python
from tools.agent_manager.cli import create_server, main
from tools.agent_manager.core import (
    _enabled_codex_plugin_sources,
    apply_adoption,
    apply_plan,
    ChangePlan,
    LinkState,
    PathSnapshot,
    PlannedChange,
    build_adapters,
    detect_surfaces,
    plan_adoption,
    plan_set,
    scan_inventory,
    scan_managed_state,
    scan_repository,
)
```

Replace all string patch targets `tools.skill_manager.core` with `tools.agent_manager.core`, all page paths with `tools/agent_manager/web/index.html`, and all temporary fixture components `skill_manager` with `agent_manager`. In both the moved page and test assertions, replace `__SKILL_MANAGER_TOKEN__` with `__AGENT_MANAGER_TOKEN__`, `window.SKILL_MANAGER_TOKEN` with `window.AGENT_MANAGER_TOKEN`, and `X-Skill-Manager-Token` with `X-Agent-Manager-Token`. Rename test classes or prose only where they refer to the live runtime name; do not rewrite historical-document assertions.

- [ ] **Step 4: Rename the console script and live runtime identifiers**

Change `pyproject.toml`:

```toml
[project.scripts]
agent-manager = "tools.agent_manager.cli:main"
upstream-sync = "tools.upstream_sync.vendor:main"
```

In the renamed `cli.py`, set:

```python
TOOLS = ("claude", "codex", "copilot", "antigravity")
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_PATH_PARTS = ("tools", "agent_manager", "web")
```

Change the parser `prog` to `agent-manager` and class names to `AgentManagerHTTPServer` / `AgentManagerRequestHandler`. The HTML placeholder, window token variable, and request header were renamed in Step 3; do not change endpoint behavior yet.

- [ ] **Step 5: Verify the rename preserves the baseline**

Run:

```bash
uv lock --check
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run agent-manager --help
```

Expected: all 106 pre-existing tests plus the new removal assertion pass; help exits `0` and prints `agent-manager`; `uv run skill-manager --help` fails because the console script no longer exists.

- [ ] **Step 6: Commit the package rename**

```bash
git add -A -- pyproject.toml tools/agent_manager tests/test_agent_manager.py tests/test_project_layout.py uv.lock
git commit -m "refactor(agent-manager): rename skill manager runtime" \
  -m "Remove the private skill-manager entry point and move the runtime package to agent_manager without changing Skill behavior." \
  -m "Verification: uv lock --check; full unittest discovery; agent-manager --help." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 2: Separate shared filesystem primitives from the Skills domain

**Files:**
- Move: `tools/agent_manager/core.py` → `tools/agent_manager/skills.py`
- Create: `tools/agent_manager/core.py`
- Modify: `tools/agent_manager/cli.py`
- Modify: `tests/test_agent_manager.py`

**Interfaces:**
- `tools.agent_manager.skills` exports every existing Skill public type and operation currently imported by tests and CLI.
- `tools.agent_manager.core.PathSnapshot` remains `PathSnapshot(kind: str, link_target: str | None = None)` for Skill plan compatibility.
- `tools.agent_manager.core.path_snapshot(path: Path) -> PathSnapshot` replaces the moved `snapshot_path` implementation; `skills.py` re-exports it as `snapshot_path` to preserve internal test semantics under the new package only.
- `tools.agent_manager.core.lexists(path: Path) -> bool`, `under(path: Path, root: Path) -> bool`, and shared error types provide the minimal common boundary.

- [ ] **Step 1: Add module-boundary tests before moving code**

Add to `tests/test_project_layout.py`:

```python
def test_agent_manager_skills_and_shared_core_are_separate(self) -> None:
    package = ROOT / "tools/agent_manager"
    for name in ("cli.py", "core.py", "skills.py"):
        with self.subTest(name=name):
            self.assertTrue((package / name).is_file())
```

For this task, run only the `skills.py` / shared-core expectations by adding:

```python
def test_skills_domain_exports_existing_operations(self) -> None:
    from tools.agent_manager import skills

    for name in ("scan_repository", "scan_inventory", "plan_set", "apply_plan", "plan_adoption", "apply_adoption"):
        self.assertTrue(callable(getattr(skills, name)))
```

- [ ] **Step 2: Verify the boundary tests fail**

Run:

```bash
uv run python -m unittest tests.test_project_layout.ProjectLayoutTests.test_skills_domain_exports_existing_operations -v
```

Expected: ERROR because `tools.agent_manager.skills` does not exist.

- [ ] **Step 3: Move the Skill implementation and create the shared core**

Run:

```bash
git mv tools/agent_manager/core.py tools/agent_manager/skills.py
```

Create `tools/agent_manager/core.py` with these concrete shared definitions:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathSnapshot:
    kind: str
    link_target: str | None = None


class InvalidPlanError(ValueError):
    pass


class StateChangedError(RuntimeError):
    pass


class TargetConflictError(OSError):
    pass


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def under(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    except ValueError:
        return False
    return True


def path_snapshot(path: Path) -> PathSnapshot:
    if not lexists(path):
        return PathSnapshot("missing")
    if path.is_symlink():
        return PathSnapshot("symlink", os.readlink(path))
    if path.is_dir():
        return PathSnapshot("directory")
    return PathSnapshot("file")
```

In `skills.py`, import and locally alias these names:

```python
from .core import (
    InvalidPlanError as _InvalidPlanError,
    PathSnapshot,
    StateChangedError as _StateChangedError,
    TargetConflictError as _TargetConflictError,
    lexists as _lexists,
    path_snapshot as snapshot_path,
    under as _under,
)
```

Delete the moved duplicate definitions only after the import is present. Do not move Skill-specific dataclasses, adapters, container adoption, plugin manifest, inventory, or FD operations into shared core.

- [ ] **Step 4: Retarget CLI and test imports**

Change CLI business imports to `.skills`. Change dynamic patch/import strings for Skill functions from `tools.agent_manager.core` to `tools.agent_manager.skills`; keep shared `PathSnapshot` assertions importing through `skills` re-export so the existing regression suite describes the Skill API rather than shared internals.

- [ ] **Step 5: Run the complete regression suite**

Run:

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run python -m py_compile tools/agent_manager/core.py tools/agent_manager/skills.py tools/agent_manager/cli.py
```

Expected: all tests pass with no Skill JSON, filesystem, adoption, or HTTP behavior change.

- [ ] **Step 6: Commit the domain split**

```bash
git add tools/agent_manager/core.py tools/agent_manager/skills.py tools/agent_manager/cli.py tests/test_agent_manager.py tests/test_project_layout.py
git commit -m "refactor(agent-manager): separate skills domain" \
  -m "Keep proven Skill behavior intact while establishing a small shared filesystem core for the Instructions domain." \
  -m "Verification: full unittest discovery; py_compile for agent manager modules." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 3: Implement trusted Instructions scanning and state classification

**Files:**
- Create: `tools/agent_manager/instructions.py`
- Create: `tests/test_agent_manager_instructions.py`
- Modify: `tools/agent_manager/core.py`

**Interfaces:**
- `InstructionState`: `enabled`, `missing`, `indirect-link`, `matching-copy`, `conflict`, `broken`, `manual`.
- `InstructionTarget(key: str, path: Path, surfaces: tuple[str, ...])`.
- `InstructionStatus(key, state, path, source, raw_target, resolved_target, source_sha256, target_sha256, message)`.
- `ManualInstructionSurface(key="copilot-desktop", state=InstructionState.MANUAL, message: str)`.
- `InstructionScan(repo_root, source, source_sha256, source_text, targets, manual_surfaces, issues)`.
- `build_instruction_targets(home: Path) -> tuple[InstructionTarget, ...]` returns the five approved paths in stable target-key order.
- `scan_instructions(repo_root: Path, home: Path) -> InstructionScan` performs no writes.
- `validate_instruction_source(scan: InstructionScan) -> None` raises `InvalidInstructionSource` when source validation produced any issue.

- [ ] **Step 1: Write state-classification tests**

Create fixtures in `tests/test_agent_manager_instructions.py` that build a repository with real `pyproject.toml`, `skills/`, and `AGENTS.md`, then assert:

```python
self.assertEqual(
    [target.key for target in build_instruction_targets(home)],
    ["shared", "claude", "codex", "copilot", "antigravity"],
)
self.assertEqual(
    [target.path for target in build_instruction_targets(home)],
    [
        home / ".agents/AGENTS.md",
        home / ".claude/CLAUDE.md",
        home / ".codex/AGENTS.md",
        home / ".copilot/copilot-instructions.md",
        home / ".gemini/GEMINI.md",
    ],
)
```

Add independent tests for direct absolute and relative links (`enabled`), missing, two-hop link to source (`indirect-link`), byte-identical regular file (`matching-copy`), different regular file / directory / valid foreign link (`conflict`), broken link and symlink cycle (`broken`), plus a Copilot Desktop `manual` surface.

- [ ] **Step 2: Write source fail-closed tests**

Test missing `AGENTS.md`, symlinked `AGENTS.md`, non-regular source, missing repository markers, unreadable source, invalid UTF-8 bytes, and source replacement between open and `fstat`. Each scan must return an issue with a stable code; `validate_instruction_source(scan)` must raise `InvalidInstructionSource`.

- [ ] **Step 3: Run tests and verify missing module failure**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_instructions -v
```

Expected: ERROR because `tools.agent_manager.instructions` does not exist.

- [ ] **Step 4: Add byte-safe source capture to shared core**

Add:

```python
@dataclass(frozen=True)
class FileSnapshot:
    kind: str
    link_target: str | None = None
    mode: int | None = None
    sha256: str | None = None
    content_base64: str | None = None
    device: int | None = None
    inode: int | None = None
```

Implement `capture_file_snapshot(path: Path, *, include_content: bool) -> FileSnapshot` with `os.lstat`; for regular files open with `O_RDONLY | O_NOFOLLOW`, compare `lstat` and `fstat` device/inode, read bytes from the fd, set `mode=stat.S_IMODE(st_mode)`, compute SHA-256, and Base64-encode only when `include_content=True`. Return raw `os.readlink` for links, `directory` for directories, and `missing` for absence. Reject sockets, devices, and FIFOs as `special`.

- [ ] **Step 5: Implement Instructions scan types and classification**

In `instructions.py`, define the exact target mapping as data, validate `repo_root` markers, call `capture_file_snapshot(source, include_content=True)`, Base64-decode the captured bytes, strictly decode them as UTF-8 into `source_text`, and classify each target from a no-follow snapshot. Resolve only a known symlink target for classification; catch `FileNotFoundError`, `RuntimeError`, and `OSError` as `broken`. For regular files compare SHA-256 rather than decoded text. Populate `target_sha256` only for regular files and `resolved_target` only when resolution succeeds. Invalid source encoding produces `invalid-source-encoding`, `source_text=None`, and a fail-closed scan.

Use stable messages such as `direct repository link`, `link resolves through another entry`, `file content matches repository source`, `target differs from repository source`, `target is a directory`, and `link cannot be resolved`.

- [ ] **Step 6: Verify scan is read-only and deterministic**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_instructions -v
uv run python -m py_compile tools/agent_manager/core.py tools/agent_manager/instructions.py
```

Expected: all scan tests pass; a recursive before/after filesystem snapshot of the temporary HOME is identical.

- [ ] **Step 7: Commit Instructions scanning**

```bash
git add tools/agent_manager/core.py tools/agent_manager/instructions.py tests/test_agent_manager_instructions.py
git commit -m "feat(agent-manager): scan personal instructions" \
  -m "Classify five global instruction targets from one trusted repository AGENTS.md without mutating HOME." \
  -m "Verification: instruction scan suite; py_compile for core and instructions." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 4: Add Instructions plans, snapshots, atomic apply, and rollback

**Files:**
- Modify: `tools/agent_manager/core.py`
- Modify: `tools/agent_manager/instructions.py`
- Modify: `tests/test_agent_manager_instructions.py`

**Interfaces:**
- `InstructionChange(action, key, source, target, expected, reason)`.
- `InstructionPlan(changes, repo_root, source, source_sha256, fingerprint, snapshot_path, replace_existing)`.
- `InstructionResult(ok, code, key, path, message)` and `InstructionBatchResult(ok, results, snapshot_path)`.
- `plan_instruction_set(scan, target_keys: Sequence[str], enabled: bool, state_dir: Path) -> InstructionPlan`.
- `plan_instruction_adoption(scan, state_dir: Path, *, replace_existing: bool) -> InstructionPlan`.
- `apply_instruction_plan(plan: InstructionPlan, home: Path, *, expected_fingerprint: str) -> InstructionBatchResult`.
- `scan_incomplete_transactions(state_dir: Path) -> tuple[IncompleteTransaction, ...]` reports prepared snapshots and retained recovery paths without mutation.

- [ ] **Step 1: Write plan-semantics tests**

Assert exact actions:

```python
set_on = {
    "missing": "create",
    "enabled": "no-op",
    "indirect-link": "blocked",
    "matching-copy": "blocked",
    "conflict": "blocked",
    "broken": "blocked",
}
adopt_without_replace = {
    "missing": "create",
    "enabled": "no-op",
    "indirect-link": "replace",
    "matching-copy": "replace",
    "conflict": "blocked",
    "broken": "blocked",
}
```

With `replace_existing=True`, different regular files, valid foreign links, and broken links become `replace`; directories and special files remain `unsupported-target`. `set --off` maps only `enabled` to `remove`, `missing` to `no-op`, and every other state to `blocked`.

- [ ] **Step 2: Write apply and byte-exact snapshot tests**

Use non-UTF-8 bytes such as `b"\xff\x00rules\n"` in a conflicting regular file. After replace apply, assert the snapshot JSON decodes to the original bytes, stores `stat.S_IMODE(mode)` and SHA-256, and the target is a direct link to the trusted source. Restore from the snapshot fixture and assert byte and mode equality.

Add a five-target adoption test covering current-machine shapes: two enabled links, one conflicting file, one missing target, and one indirect link. Preview performs zero writes; approved apply produces five direct links and one snapshot.

- [ ] **Step 3: Write failure, rollback, and race tests**

Cover all of these concrete cases:

- source hash changes after planning;
- target lstat identity changes after planning;
- apply omits, malforms, or supplies a different expected fingerprint;
- snapshot directory creation or snapshot fsync fails before mutation;
- second or fourth target replacement fails after earlier targets changed;
- post-replacement direct-link verification fails;
- rollback target is occupied by a competitor;
- parent component is replaced by an external symlink;
- a newly created parent receives a competitor file before rollback;
- repeated apply is idempotent.
- a synthetic `prepared` snapshot is reported as `incomplete-transaction` with zero automatic writes.

Assertions: successful rollback restores every earlier target; competitor content is never overwritten; an unrecoverable isolated backup path appears in the failed item message; newly created parents are removed only when still empty and device/inode match the creation record.

- [ ] **Step 4: Run the new tests and verify they fail on missing operations**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_instructions -v
```

Expected: FAIL because plan/apply functions are absent.

- [ ] **Step 5: Implement deterministic planning and fingerprint validation**

Build plans only from the five fixed targets. For each selected target, recapture with `include_content=True`, verify its kind/hash/raw target still matches the supplied scan status, and store that full `FileSnapshot` as the preview expectation. Store the source SHA-256. Before apply, rescan the trusted source and every selected target, recompute the plan, validate the expected fingerprint as exactly 64 lowercase hexadecimal characters, compare it to the recomputed fingerprint with `secrets.compare_digest`, and require exact snapshot equality. Reject unknown keys, duplicate keys after normalization, invalid source, blocked actions, and `replace_existing=True` on a non-adopt plan with stable codes.

Canonicalize repo/source identity, source hash, replace flag, target keys, actions, and full expected snapshots as sorted JSON, then compute the SHA-256 plan fingerprint. Use the deterministic snapshot path:

```python
state_dir / "snapshots" / f"instructions-{fingerprint}.json"
```

An unchanged replace preview and apply must produce identical changes, fingerprint, and snapshot path. If the path already exists, never overwrite it: a prepared record yields `incomplete-transaction` and a committed record yields `snapshot-conflict`. A no-write plan returns `snapshot_path: null` and does not enter this path.

- [ ] **Step 6: Implement durable snapshot writing before mutation**

Serialize `version`, `phase: "prepared"`, `created_at`, `fingerprint`, `repo_root`, `source`, `source_sha256`, `replace_existing`, and selected target snapshots. Create the final deterministic path without replacing an existing file; write through a sibling temporary file with mode `0o600`, flush and `os.fsync`, atomically install only when the final path is absent, then fsync the snapshots directory. No target mutation may occur if any snapshot step fails. After every target verifies, rewrite the same snapshot through a new temporary file with `phase: "committed"`, fsync it, atomically replace the prepared snapshot, and fsync the directory. If commit-marker writing fails, perform the normal reverse rollback and leave the prepared snapshot available for diagnosis.

- [ ] **Step 7: Implement FD-based atomic replacement and reverse rollback**

Open HOME and each fixed first-level directory with `O_DIRECTORY | O_NOFOLLOW`. Create a missing first-level directory with `os.mkdir(..., mode=0o700, dir_fd=home_fd)` and record its device/inode. For each write action:

1. rename an existing file/link to `.agent-manager-<uuid>.backup` in the same directory;
2. create `.agent-manager-<uuid>.tmp` as a direct symlink to the source;
3. atomically rename the temp link to the target leaf;
4. verify the raw absolute target equals the source and resolves to it;
5. keep the backup until the whole selected batch verifies.

On failure, walk applied entries in reverse: isolate the manager-created link, restore the backup only if the target leaf is absent, and never overwrite a competitor. After the committed marker is durable, unlink backups and fsync parent directories. For `remove`, isolate and verify the direct managed link before unlinking it; rollback renames it back only into an empty leaf. `scan_incomplete_transactions` treats every readable prepared snapshot as diagnostic state and includes any retained `.backup` paths; it never restores during status or doctor.

- [ ] **Step 8: Verify atomic behavior and the complete repository suite**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_instructions -v
uv run python -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Expected: all tests pass, including byte-exact recovery and five-target rollback; no test touches real HOME.

- [ ] **Step 9: Commit Instructions writes**

```bash
git add tools/agent_manager/core.py tools/agent_manager/instructions.py tests/test_agent_manager_instructions.py
git commit -m "feat(agent-manager): manage personal instruction links" \
  -m "Add dry-run plans, byte-exact snapshots, guarded replacement, and atomic rollback across selected instruction targets." \
  -m "Verification: instruction transaction suite; full unittest discovery; git diff --check." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 5: Implement the umbrella CLI and aggregate state

**Files:**
- Modify: `tools/agent_manager/cli.py`
- Modify: `tools/agent_manager/web/index.html`
- Modify: `tests/test_agent_manager.py`
- Modify: `tests/test_agent_manager_instructions.py`

**Interfaces:**
- `agent-manager status [--json]`, `doctor [--json]`, and `serve [--open]`.
- `agent-manager skills status|set|adopt` with existing Skill arguments moved under `skills`.
- `agent-manager instructions status|set|adopt` with fixed target keys.
- `build_agent_state(repo_root, home, which, applications) -> AgentState` containing repository, Skill state, Instruction scan, surfaces, summary, and scan timestamp.
- Exit codes: healthy/valid `0`, domain or verification failure `1`, parser error `2`.

- [ ] **Step 1: Add parser and help-contract tests**

Test `main(["--help"])`, every top-level command, every domain status, Skill set/adopt preview, and Instructions set/adopt preview. Assert old flat forms such as `agent-manager set ...` and `agent-manager adopt` exit `2`. Accept `instructions adopt --replace-existing --json` as dry-run; reject `--replace-existing` on every command except Instructions adopt. Require `--expect-fingerprint` for Instructions set/adopt apply, reject it on previews and all Skill commands, and reject values outside `[0-9a-f]{64}`. Assert reviewed dry-run replace and apply replace produce identical changes, fingerprints, and planned snapshot paths when the filesystem is unchanged.

- [ ] **Step 2: Add aggregate JSON and exit-code tests**

For `status --json`, assert exact top-level keys:

```python
{
    "mode", "ok", "code", "message", "repo_root", "skills",
    "instructions", "surfaces", "summary", "scanned_at",
}
```

Assert summary contains `skills_enabled`, `skills_total`, `instructions_enabled`, `instructions_total`, `conflicts`, and `issues`. Missing/matching-copy Instructions do not fail status; conflict/broken/invalid source do. `doctor` adds `inventory`, reports prepared Instructions snapshots as `incomplete-transaction`, and preserves existing inventory exit behavior. Status and doctor perform zero recovery writes.

Use these exact domain containers so CLI, transitional UI, and final UI share one contract:

```python
payload["skills"] = {
    "records": state.skills.repository.skills,
    "adapters": state.skills.adapters,
    "targets": state.skills.targets,
    "issues": state.skills.repository.issues,
}
payload["instructions"] = {
    "source": state.instructions.source,
    "source_sha256": state.instructions.source_sha256,
    "source_text": state.instructions.source_text,
    "targets": state.instructions.targets,
    "manual_surfaces": state.instructions.manual_surfaces,
    "issues": state.instructions.issues,
}
```

For `skills status --json`, return the common envelope plus the exact `skills` container above. For `instructions status --json`, return the common envelope plus the exact `instructions` container above. Domain status commands do not flatten or rename their container fields.

Instructions set/adopt preview and apply add top-level `changes`, `fingerprint`, and `snapshot_path`; apply also adds `results`. Preserve the reviewed plan fields after post-apply rescan so callers can compare the executed fingerprint with the preview.

- [ ] **Step 3: Run CLI tests and verify the flat parser fails the contract**

Run:

```bash
uv run python -m unittest \
  tests.test_agent_manager.CliTests \
  tests.test_agent_manager_instructions -v
```

Expected: FAIL because nested domain commands and aggregate payloads are absent.

- [ ] **Step 4: Build the final nested parser**

Implement parser helpers `_add_json`, `_add_skill_commands`, and `_add_instruction_commands`. Use `resource` and `command` destinations so dispatch is explicit. Preserve keyword injection in `main`; do not read global `Path.home()` or `shutil.which` inside domain functions when injected values are available.

The Instructions parser accepts:

```text
status [--json]
set --target {shared,claude,codex,copilot,antigravity,all} (--on|--off) [--apply --expect-fingerprint SHA256] [--json]
adopt [--replace-existing] [--apply --expect-fingerprint SHA256] [--json]
```

- [ ] **Step 5: Add aggregate state and dispatch**

Build Skills and Instructions from one repository/home/surface scan per request. Keep Skill payload fields unchanged inside `skills`. Serialize dataclasses, `Path`, enum, mappings, tuples, and lists through the existing `to_jsonable` behavior. For apply commands, rebuild aggregate state after mutation and attach original `changes` plus actual `results`.

Because the current `cli.py` also builds `/api/status`, switch that read API to the same aggregate schema in this task. Update its existing HTTP assertions accordingly. Minimally adapt the current single-file page to read Skill records, adapters, targets, and issues from `payload.skills`; retain the old Skill write routes and body shapes until Task 6. This keeps the intermediate commit usable without introducing a second transitional payload builder.

Text status prints repository path, `Skills: enabled/total`, `Instructions: enabled/total`, conflicts/issues, and the exact next command. Text domain commands remain concise; full paths, changes, and results remain JSON-only.

- [ ] **Step 6: Verify CLI behavior without real writes**

Run all CLI tests with temporary HOME, then:

```bash
uv run agent-manager --help
uv run agent-manager skills --help
uv run agent-manager instructions --help
HOME="$(mktemp -d)" uv run agent-manager status --json
uv run python -m unittest discover -s tests -p 'test_*.py'
```

The three help commands and temporary-HOME status exit `0`; full unittest discovery passes with no HTTP or page regression. Do not run any `--apply` against real HOME.

- [ ] **Step 7: Commit the umbrella CLI**

```bash
git add tools/agent_manager/cli.py tools/agent_manager/web/index.html tests/test_agent_manager.py tests/test_agent_manager_instructions.py
git commit -m "feat(agent-manager): add umbrella command structure" \
  -m "Expose Skills and Instructions as nested resources while keeping aggregate status and doctor at the top level." \
  -m "Verification: CLI suites; help for root and both resources; read-only aggregate status; full unittest discovery." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 6: Extract and harden the namespaced localhost HTTP API

**Files:**
- Create: `tools/agent_manager/server.py`
- Modify: `tools/agent_manager/cli.py`
- Modify: `tools/agent_manager/web/index.html`
- Create: `tests/test_agent_manager_http.py`
- Modify: `tests/test_agent_manager.py`

**Interfaces:**
- `create_server(repo_root, home, token, applications, which) -> AgentManagerHTTPServer` lives only in `server.py`; HTTP tests import it from that module and CLI imports only `_serve`.
- Exact read routes in this task: `/`, `/api/status`, `/api/inventory`. Task 7 adds `/app.css` and `/app.js` when those assets are created.
- Exact write routes: `/api/skills/set`, `/api/skills/adopt`, `/api/instructions/set`, `/api/instructions/adopt`, `/api/shutdown`.
- Exact token header: `X-Agent-Manager-Token`.
- Exact request objects are those in the approved spec; no defaulting omitted fields.

- [ ] **Step 1: Move HTTP tests to a dedicated module and update route expectations**

Move the existing HTTP test helpers and `HttpServerTests` from `tests/test_agent_manager.py` into `tests/test_agent_manager_http.py`. Preserve every existing Host, Origin, token, body-size, method, traversal, symlink, conflict-status, shutdown, and browser-open assertion. Replace live write routes with namespaced routes and add Instructions preview/apply tests against temporary HOME.

- [ ] **Step 2: Add exact-schema and token-bootstrap tests**

For each write route, test missing, extra, wrong-type, and unknown fields. Assert preview with blocked changes is HTTP `200` and `ok:false`; apply conflicts are `409`; permission errors `403`; unexpected/rollback failures `500`.

Lock both Skill set shapes to the same five-key object: single uses `{"skill":"docx","all":false,"tool":"codex","on":true,"apply":false}`; all uses `{"skill":null,"all":true,"tool":"all","on":true,"apply":false}`. Instructions set/adopt always include `expected_fingerprint`: it is `null` for preview and the reviewed 64-character lowercase hex digest for apply. Accept Instructions adopt with `replace_existing:true` for both preview and apply, and assert unchanged-state responses share changes, fingerprint, and snapshot path. Missing, malformed, or mismatched apply fingerprints return `400 invalid-request` or `409 state-changed` before any snapshot/HOME write.

For `/`, preserve the current single-file bootstrap in this task: assert the response contains the escaped test token exactly once and contains no placeholder. Task 7 moves the token into `<meta name="agent-manager-token">` when it externalizes JavaScript.

- [ ] **Step 3: Preserve index and intermediate-directory symlink attack tests**

For `index.html` and each intermediate component (`tools`, `agent_manager`, `web`), replace the checked-in path in a temporary fixture with a symlink to an external secret. Request `/` and assert non-200 plus zero secret bytes in the body. Task 7 repeats the leaf attack for all three final assets.

- [ ] **Step 4: Run HTTP tests and verify old server fails**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_http -v
```

Expected: FAIL because `server.py`, namespaced routes, and exact schemas are absent.

- [ ] **Step 5: Extract server transport from CLI**

Move request handlers, secure static reading, status-to-HTTP mapping, server class, `create_server`, and `_serve` into `server.py`. `cli.py` retains only command parsing/dispatch and imports `_serve`. Business handlers call the same Skills and Instructions plan/apply functions as CLI; do not duplicate state or error semantics.

Update the existing single-file page write calls to `/api/skills/set` and `/api/skills/adopt`, and send the exact five-field set body including `skill:null` for all-mode. Its aggregate status field adaptation was completed in Task 5. Keep all current preview/apply/security behavior; do not add the new navigation or Instructions UI until Task 7.

- [ ] **Step 6: Implement strict routes, schemas, and security headers**

Use an explicit route map, exact key-set equality, `type(value) is bool` for booleans, `secrets.compare_digest` on encoded bytes, loopback Host validation, same-origin Origin validation, `application/json` with optional UTF-8 charset, and `MAX_REQUEST_BODY = 64 * 1024`.

Keep the current page functional during this intermediate extraction with:

```text
default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'
```

Also set `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store`. Task 7 removes both `unsafe-inline` values after scripts and styles are external.

- [ ] **Step 7: Preserve secure index reads and token injection**

Open `tools`, `agent_manager`, and `web` one directory component at a time with `O_DIRECTORY | O_NOFOLLOW`; open `index.html` with `O_NOFOLLOW`, verify `S_ISREG`, and read from the fd. Decode/replace `__AGENT_MANAGER_TOKEN__` only in this file, escaping with the representation expected by the current JavaScript bootstrap. Task 7 generalizes the reader to the two new leaves and switches token escaping to HTML attribute context.

- [ ] **Step 8: Run HTTP and full regression suites**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_http -v
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run python -m py_compile tools/agent_manager/*.py
```

Expected: all API, security, Skill, Instructions, and CLI tests pass.

- [ ] **Step 9: Commit the HTTP split**

```bash
git add tools/agent_manager/cli.py tools/agent_manager/server.py tools/agent_manager/web/index.html tests/test_agent_manager.py tests/test_agent_manager_http.py
git commit -m "feat(agent-manager): expose namespaced local API" \
  -m "Separate HTTP transport from CLI and add strict Skills and Instructions routes while preserving secure index serving." \
  -m "Verification: HTTP security suite; full unittest discovery; py_compile." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 7: Build the read-only Agent routing console shell

**Files:**
- Rewrite: `tools/agent_manager/web/index.html`
- Create: `tools/agent_manager/web/app.css`
- Create: `tools/agent_manager/web/app.js`
- Modify: `tools/agent_manager/server.py`
- Create: `tests/test_agent_manager_web.py`
- Modify: `tests/test_agent_manager_http.py`
- Modify: `tests/test_agent_manager.py` (move its existing `WebPageTests` into the new Web test module)

**Interfaces:**
- Four views: `overview`, `skills`, `instructions`, `inventory`.
- `loadStatus()`, `renderOverview(state)`, `renderSkills(state)`, `renderInstructions(state)`, `renderInventory(records)` consume server truth.
- `buildTopology(state) -> Array<RouteModel>`, `filterSkillRows(...)`, `compactHomePath(...)`, and `summarizePlan(...)` are pure functions exported to `globalThis.AgentManagerTest` only when `globalThis.__AGENT_MANAGER_TEST__ === true`.
- No write action is enabled in this task; Task 8 wires preview/apply.

- [ ] **Step 1: Add static design and accessibility contracts**

Move the existing `WebPageTests` helpers and assertions from `tests/test_agent_manager.py` into `tests/test_agent_manager_web.py`, preserving their real-JavaScript extraction coverage while updating paths and names. Then assert separate assets, four navigation labels, one `<main>`, one live region, semantic buttons, drawer and dialog containers, viewport meta, no external URLs, no inline `<style>` or executable inline `<script>`, token meta placeholder, and links to `/app.css` and `/app.js`.

Assert CSS contains the six approved color values, Avenir Next/system UI/SF Mono stacks, `:focus-visible`, `@media (max-width: 720px)`, `@media (prefers-reduced-motion: reduce)`, sticky table selectors, and no `backdrop-filter`.

Extend `tests/test_agent_manager_http.py` so `/app.css` and `/app.js` must equal checked-in bytes and never contain the token. Repeat leaf symlink substitution for all three files and intermediate substitution for `tools`, `agent_manager`, and `web`. Assert the final CSP contains `script-src 'self'` and `style-src 'self'` without `unsafe-inline`.

- [ ] **Step 2: Add Node tests for read-only pure functions**

Load the checked-in `app.js` into Node with `globalThis.__AGENT_MANAGER_TEST__ = true`. Test:

- four route models from four tool families;
- distinct Skill and Instructions line styles;
- health/attention labels independent of color;
- Skill query plus state filter;
- `~` path shortening only inside the exact HOME prefix;
- plan summary counts by action and code.

- [ ] **Step 3: Run Web tests and verify the monolithic page fails**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_web -v
```

Expected: FAIL because CSS/JS files and the new information architecture do not exist.

- [ ] **Step 4: Write semantic HTML and token bootstrap**

Create a stable shell with left navigation, top repository bar, status summary, topology SVG container, attention list, Skill table, Instructions list, inventory table, details drawer, confirmation dialog, toast live region, and shutdown button. Put the token in:

```html
<meta name="agent-manager-token" content="__AGENT_MANAGER_TOKEN__">
```

Load `/app.css` and `/app.js` with normal external tags. Use text labels next to all status icons.

- [ ] **Step 5: Implement the visual system and responsive shell**

Define CSS custom properties for the approved palette, an 88px desktop rhythm, 240px navigation, quiet separators, sticky Skill header/first column, right drawer, and a single 180ms route-state transition. At `720px`, convert navigation to a horizontal top strip, topology to a vertical stack, drawer to a bottom sheet, and expose a visible horizontal-scroll hint for the matrix. Disable transitions under reduced motion.

- [ ] **Step 6: Implement token handling and read-only rendering**

On startup, read the token meta value, remove the meta node, fetch `/api/status`, and render all four views with `createElement`, `textContent`, `setAttribute`, and DOM event listeners only. Never insert server strings with `innerHTML`. Fetch inventory only when its view is opened or refreshed. Display `scanned_at`, empty/error states, full paths in `title`, and exact server messages in the details drawer.

Update `server.py` to serve exactly `/`, `/app.css`, and `/app.js` through the same component-wise fd traversal. Inject and HTML-attribute escape the token only for `index.html`; return CSS/JS byte-for-byte. Remove `unsafe-inline` from CSP now that the page has no inline executable code or styles.

- [ ] **Step 7: Verify the read-only console**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_web -v
uv run python -m unittest tests.test_agent_manager_http -v
```

Expected: Web contracts and static serving pass; no write endpoint is called by initial rendering.

- [ ] **Step 8: Commit the console shell**

```bash
git add tools/agent_manager/web tools/agent_manager/server.py tests/test_agent_manager_web.py tests/test_agent_manager_http.py tests/test_agent_manager.py
git commit -m "feat(agent-manager): redesign routing console shell" \
  -m "Replace the monolithic debug-style page with an accessible four-view routing console driven by server state." \
  -m "Verification: Web contract and Node behavior suites; HTTP static-asset suite." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 8: Wire contextual preview, apply, drawers, and manual Copilot guidance

**Files:**
- Modify: `tools/agent_manager/web/index.html`
- Modify: `tools/agent_manager/web/app.css`
- Modify: `tools/agent_manager/web/app.js`
- Modify: `tests/test_agent_manager_web.py`
- Modify: `tests/test_agent_manager_http.py`

**Interfaces:**
- `api(path: str, body: object) -> Promise<object>` adds the token only to writes.
- `previewSkillSelection(action)`, `previewInstruction(target, action)`, and `applyPreview()` preserve the exact preview body for apply.
- `openDrawer(model)`, `closeDrawer()`, `openDangerDialog(preview)`, and `closeDangerDialog()` manage keyboard focus.
- `copyText(text) -> Promise<boolean>` uses Clipboard API, then focused hidden textarea plus `execCommand`, then manual selection guidance.

- [ ] **Step 1: Add interaction tests against real JavaScript**

Extend Node tests to assert endpoint/body construction for Skill single/all set, Skill adopt, Instruction set, Instruction adopt, replace preview, and replace apply. The initial adopt preview uses `replace_existing:false, expected_fingerprint:null`; choosing “preview replacement” sends `apply:false, replace_existing:true, expected_fingerprint:null` and renders the server-returned replace actions/fingerprint/snapshot path. After the danger dialog confirms that preview, apply sets `apply:true` and `expected_fingerprint` to the exact preview response fingerprint; every other plan-intent field remains unchanged.

Add static focus-order contracts: opening drawer/dialog stores the active element, focuses the first meaningful control, Escape closes, Tab is trapped inside modal, and close restores prior focus. Test copy fallbacks in the order Clipboard → focused textarea/`execCommand` → manual message.

- [ ] **Step 2: Add UI/API integration tests**

Start the real temporary HTTP server and execute representative request builders extracted from `app.js`. Verify every generated body passes server validation. Verify a blocked `replace_existing:false` response remains renderable; the user must request a server-side `replace_existing:true` preview before the danger dialog can enable apply. Never infer replace actions in the browser from blocked items.

- [ ] **Step 3: Run interaction tests and verify missing functions**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_web tests.test_agent_manager_http -v
```

Expected: FAIL because contextual operations and focus behavior are not wired.

- [ ] **Step 4: Implement contextual Skill operations**

Show row/cell details on selection. Only display bulk controls when at least one Skill row/cell is selected. Build preview requests from current selection, render every change in the drawer, and disable apply on blocked plans. After successful apply, always fetch full status and fetch inventory only when the inventory view is currently open; do not optimistically mutate the matrix.

- [ ] **Step 5: Implement Instructions operations and dangerous confirmation**

Each of the five file rows offers previewable enable/disable/adopt actions according to state. Regular-file/foreign-link/broken conflicts show original type, hash/raw target, and a separate “preview replacement” action. That action first requests the server-side replace preview; only a successful response opens the modal with every affected path, replace action, fingerprint, and snapshot destination. The final button sends the same plan intent with `apply:true` plus the reviewed fingerprint as `expected_fingerprint`; a mismatch response returns to preview instead of retrying automatically. Directories show `unsupported-target` with no replace button.

- [ ] **Step 6: Implement Copilot Desktop manual guidance**

Render a manual row with no managed path. Copy only `payload.instructions.source_text`; disable the button and show the source issue when that field is `null`. Then show these steps: open GitHub Copilot Desktop Settings, open custom instructions, replace the existing global text, save, and start a new session. Do not automate the app or claim synchronized state.

- [ ] **Step 7: Implement inline errors, refresh, shutdown, and session reminders**

Attach errors to their row and the overview attention area with server code/message/path. Keep success toasts brief. Re-scan after every operation. After a successful write, show “start a new session; restart the Desktop or CLI if cached rules remain.” Shutdown posts `{}` and replaces the page with a stopped-service state after success.

- [ ] **Step 8: Verify all Web interactions**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_web tests.test_agent_manager_http -v
uv run python -m unittest discover -s tests -p 'test_*.py'
```

Expected: all interaction, API, accessibility, security, and regression tests pass.

- [ ] **Step 9: Commit interactive management**

```bash
git add tools/agent_manager/web tests/test_agent_manager_web.py tests/test_agent_manager_http.py
git commit -m "feat(agent-manager): add safe console operations" \
  -m "Wire contextual previews, guarded apply, instruction conflict confirmation, and manual Copilot Desktop guidance." \
  -m "Verification: Web and HTTP suites; full unittest discovery." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 9: Update active documentation, package data, and complete branch verification

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`
- Modify: `tests/test_project_layout.py`
- Modify: `tests/test_agent_manager.py`
- Modify: `docs/superpowers/specs/2026-07-16-agent-manager-and-personal-instructions-design.md`
- Verify only: completed 2026-07-14 and 2026-07-15 spec/plan files

**Interfaces:**
- Wheel includes Python modules plus `web/index.html`, `web/app.css`, `web/app.js`, and all existing upstream-sync data files.
- README exposes the exact unified CLI and states that `serve --open` is on-demand, not a background service.
- Active non-historical docs contain no old runtime command or package path.

- [ ] **Step 1: Update documentation tests first**

Replace live README assertions with:

```text
uv run agent-manager status --json
uv run agent-manager doctor --json
uv run agent-manager skills set docx --tool codex --on --json
uv run agent-manager skills adopt --json
uv run agent-manager instructions status --json
uv run agent-manager instructions adopt --json
uv run agent-manager instructions adopt --replace-existing --json
uv run agent-manager instructions adopt --apply --replace-existing --expect-fingerprint
uv run agent-manager serve --open
```

Assert replace preview precedes fingerprint-bound apply, real HOME apply requires separate confirmation, Copilot Desktop is manual, the service need not remain running, and both Skill and Instructions target paths are shown in the UI.

- [ ] **Step 2: Add wheel and residual-scan tests**

Build a wheel into a temporary directory and inspect its zip names. Require exactly the three Agent Manager Web assets plus `tools/upstream_sync/upstream.yml` and `tools/upstream_sync/upstream.lock.yml` as non-Python package data.

Scan runtime code, tests, `README.md`, and `pyproject.toml`; fail on `uv run skill-manager`, imports of `tools.skill_manager`, paths under `tools/skill_manager`, or `/api/set` and `/api/adopt` as live routes. Separately scan executable code fences in current active docs for `uv run skill-manager`; allow plain prose in the 2026-07-16 spec/plan to name the removed interface. Exclude the four completed 2026-07-14/15 historical spec/plan paths from command scans because they preserve execution evidence.

- [ ] **Step 3: Run documentation/layout tests and verify stale docs fail**

Run:

```bash
uv run python -m unittest tests.test_project_layout tests.test_agent_manager.ReadmeTests -v
```

Expected: FAIL until README and package data are updated.

- [ ] **Step 4: Rewrite the README management section**

Document the directory tree, unified command hierarchy, four tools/eight detected surfaces, five Skill roots, five Instruction paths, Copilot Desktop manual boundary, state meanings, preview/apply examples, Web UI startup and shutdown, new-session reminder, old state archival gate, and post-integration read-only commands. Keep `upstream-sync` instructions unchanged except for surrounding Agent Manager naming.

- [ ] **Step 5: Update package data and mark the spec implemented after verification**

Keep the existing uv build backend, module root, module name, dependencies, and project name unchanged; `uv_build` must include the three checked-in Web files under the `tools` package without an added manifest or dependency. Change the design spec status to `已实现并通过分支验证` only after Step 6 succeeds.

- [ ] **Step 6: Run the full branch acceptance suite**

Run:

```bash
git diff --check
uv lock --check
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run python -m py_compile tools/agent_manager/*.py tools/upstream_sync/vendor.py
uv build
uv run agent-manager --help
uv run upstream-sync --help
```

Inspect the wheel and require only the intended data files. Run `node --check tools/agent_manager/web/app.js`. Start the server with a temporary HOME, request all three assets and both read APIs, then shut it down; require no external network requests and no write outside the temporary HOME.

- [ ] **Step 7: Perform manual browser acceptance against temporary HOME**

Verify at `1440×900` and `390×844`: healthy, missing, conflict, loading, empty, and error states; keyboard-only navigation; visible focus; drawer/modal focus restore; reduced motion; topology labels; matrix horizontal-scroll hint; copy fallbacks; preview/cancel; shutdown; zero console errors; zero external requests. Save screenshots in `/tmp` only and do not commit them.

- [ ] **Step 8: Commit docs and release readiness**

```bash
git add README.md pyproject.toml uv.lock tests/test_project_layout.py tests/test_agent_manager.py docs/superpowers/specs/2026-07-16-agent-manager-and-personal-instructions-design.md
git commit -m "docs(agent-manager): document unified management workflow" \
  -m "Document the final command, instruction targets, Web console, safety gates, and on-demand service lifecycle; lock package-data verification." \
  -m "Verification: full unittest discovery; lock check; py_compile; uv build; both CLI help commands; Node syntax; manual responsive browser acceptance." \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 10: Integrate, run read-only real acceptance, and gate the one-time migration

**Files:**
- No repository code changes expected
- Real paths inspected only after integration: five Instructions targets and two state roots

**Interfaces:**
- Branch completion is separate from real HOME migration.
- Dangerous preview is `uv run agent-manager instructions adopt --replace-existing --json`; real apply adds `--apply` and the reviewed digest through `--expect-fingerprint`, and still requires a fresh explicit user authorization after reviewing that preview.
- Legacy state archival requires a second explicit authorization after hash inventory.

- [ ] **Step 1: Finish the implementation branch using the approved integration workflow**

Use `superpowers:finishing-a-development-branch`. Before merge/rebase, verify the exact reviewed commit range, clean worktree, full test suite, build, and browser evidence. Do not rewrite unrelated commits.

- [ ] **Step 2: Capture a read-only pre-acceptance filesystem manifest on canonical main**

For all 75 Skill targets, five Instructions paths, `~/.cc-switch`, `~/.local/state/lucas-skills-manager`, and `~/.local/state/lucas-agent-manager`, record path kind, raw symlink target, resolved target, regular-file SHA-256/mode, and directory entry names. Store the report under `/tmp`; do not modify any path.

- [ ] **Step 3: Run canonical read-only acceptance**

Run:

```bash
uv run agent-manager status --json
uv run agent-manager doctor --json
uv run agent-manager skills adopt --json
uv run agent-manager instructions adopt --json
uv run agent-manager instructions adopt --replace-existing --json > /tmp/agent-manager-instructions-replace-preview.json
```

The known external inventory anomalies may make `doctor --json` exit `1`; accept that exit only when the output is limited to the already recorded broken `dev-screenshot` and `pdf`/`skill-creator` duplicate flags, and record their exact paths. Any additional repository, managed-target, source, or incomplete-transaction issue blocks acceptance.

Start `uv run agent-manager serve --open`, inspect all four views, perform preview/cancel only, then shut down. Capture the same filesystem manifest and require byte-for-byte equality with Step 2. Report 75/75 Skill targets and the exact five Instructions replace-preview actions, fingerprint, and snapshot path.

- [ ] **Step 4: Stop and request explicit authorization for real Instructions apply**

Run a fresh byte/line diff between canonical `<repo>/AGENTS.md` and every conflicting regular target, especially `~/.codex/AGENTS.md`. Classify each differing rule as already superseded, needs to be merged into the repository source, or intentionally discarded. If any rule needs to be retained, stop, update/review the source first, and regenerate the plan.

Present the complete `/tmp/agent-manager-instructions-replace-preview.json` summary, especially the conflicting Codex file, missing Copilot CLI file, indirect Antigravity link, replace actions, fingerprint, snapshot path, and any blocked directory/special target. Do not regenerate or edit this reviewed file after authorization. Do not proceed on general implementation approval; require the user to explicitly authorize the real apply.

- [ ] **Step 5: After authorization, apply and verify the five direct links**

Run exactly:

```bash
FINGERPRINT="$(uv run python -c 'import json; print(json.load(open("/tmp/agent-manager-instructions-replace-preview.json", encoding="utf-8"))["fingerprint"])')"
uv run agent-manager instructions adopt --apply --replace-existing --expect-fingerprint "$FINGERPRINT" --json
uv run agent-manager instructions status --json
uv run agent-manager doctor --json
```

Require five `enabled` file targets, raw direct targets equal to canonical `<repo>/AGENTS.md`, a readable snapshot containing the original Codex bytes/mode/hash and old Gemini raw target, and unchanged 75 Skill targets. Start new Claude, Codex, Copilot CLI, Antigravity Desktop, and `agy` sessions to verify rule loading; synchronize Copilot Desktop manually through Settings.

`doctor --json` may still exit `1` only for the same recorded external inventory anomalies accepted in Step 3. Any new managed-target, Instructions, recovery, or repository issue fails post-apply verification.

- [ ] **Step 6: Inventory and separately authorize legacy state archival**

List relative paths, file counts, and SHA-256 for `~/.local/state/lucas-skills-manager/`. Confirm `~/.local/state/lucas-agent-manager/legacy-skill-manager/` does not exist. Present the proposed move and request explicit authorization.

- [ ] **Step 7: After archival authorization, move and verify old state**

Move the entire old directory to `~/.local/state/lucas-agent-manager/legacy-skill-manager/` without merging. Recompute relative paths, counts, and hashes; require equality before confirming the old path is absent. Do not delete `~/.cc-switch` in this task; report it as optional application cleanup because runtime Skill and Instructions links no longer depend on it.

- [ ] **Step 8: Deliver the final state report**

Report repository HEAD, pushed/merged state, automated test count, build result, browser acceptance, 75 Skill links, five Instructions links, Copilot Desktop manual status, new and legacy snapshot paths, cc-switch runtime reference count, and any remaining optional cleanup. Do not claim a tool loaded new rules unless a new session actually verified it.

---

## Plan Completion Checks

Before execution begins, review this plan against every design-spec section:

- package/CLI removal and nested command grammar: Tasks 1, 5, 9;
- module ownership: Tasks 2, 3, 4, 6, 7;
- five file targets and Copilot Desktop manual surface: Tasks 3, 5, 8;
- state classification and source trust: Task 3;
- dry-run, conflict boundary, snapshot, atomicity and rollback: Task 4;
- exact HTTP routes, schemas, token and static security: Task 6;
- approved information architecture, visual system and accessibility: Tasks 7 and 8;
- packaging, docs, residual scans and automated/manual acceptance: Task 9;
- canonical read-only gate, real apply and legacy archival: Task 10.

Implementation is not complete until every applicable checkbox is satisfied or an explicit reviewed deviation is recorded in the spec and plan.
