# Repository Layout and CLI Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move both repository tools under a clear `tools/` hierarchy and expose them as two `uv run` console commands backed by one committed `pyproject.toml` and `uv.lock`.

**Architecture:** Keep the repository-specific tools as one flat-layout Python package named `tools`, with independent `skill-manager` and `upstream-sync` entry points. Resolve the managed repository and mutable upstream files from checked-in source locations, preserve the Skill manager's file-descriptor-based web security boundary, and keep all real Skill operations dry-run unless separately authorized.

**Tech Stack:** Python 3.11+, local `uv` 0.11+, CI uv 0.11.28, `uv_build>=0.11.28,<0.12`, PyYAML, standard-library `unittest`, native HTML/CSS/JavaScript, GitHub Actions.

**Execution Gate:** This plan is awaiting review. Do not execute any task until the user explicitly approves the written plan.

## Global Constraints

- `requires-python = ">=3.11"`; runtime dependencies contain only `PyYAML`.
- Build backend is `uv_build>=0.11.28,<0.12` with `module-root = ""` and `module-name = "tools"`.
- The generic top-level package name `tools` is accepted only for this repository-private uv environment; do not add a `src/` layer or rename it to `lucas_tools`.
- Public command prefixes are exactly `uv run skill-manager` and `uv run upstream-sync`; do not retain root compatibility shims.
- `uv.lock` is committed; `.venv/` is ignored.
- `tools/upstream_sync/upstream.yml` and `tools/upstream_sync/upstream.lock.yml` are resolved beside `vendor.py`; mapping `dst` values remain relative to the repository root.
- `tools/skill_manager/web/index.html` remains protected against path traversal and symlink substitution. Open `tools`, `skill_manager`, and `web` one component at a time with `O_DIRECTORY | O_NOFOLLOW`.
- Do not change Skill manager behavior, adoption safety rules, inventory semantics, or external Skill contents.
- Do not run `adopt --apply` or any other real global Skill write during this plan.
- Delete `img.png`; its durable conclusions already live in `AGENTS.md` and Git history retains the artifact.
- GitHub Actions uses `astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b` (v8.1.0), pins uv `0.11.28`, and runs `uv run --frozen`.
- Preserve the completed 2026-07-14 Skill manager spec/plan verbatim as historical execution evidence; exclude them from legacy-command residual scans.

---

## File Map

| Path | Action | Responsibility |
| --- | --- | --- |
| `pyproject.toml` | Create | Project metadata, PyYAML dependency, build backend, two console scripts |
| `uv.lock` | Create | Reproducible Python dependency resolution |
| `.gitignore` | Modify | Ignore `.venv/` |
| `tools/__init__.py` | Create | Flat-layout package marker |
| `tools/skill_manager/__init__.py` | Create | Skill manager package marker |
| `tools/skill_manager/cli.py` | Move/modify | CLI, localhost HTTP service, repository and web path resolution |
| `tools/skill_manager/core.py` | Move/modify | Existing scan, plan, apply, adoption, and inventory logic |
| `tools/skill_manager/web/index.html` | Move | Existing management page |
| `tools/upstream_sync/__init__.py` | Create | Upstream sync package marker |
| `tools/upstream_sync/vendor.py` | Move/modify | Upstream CLI, config/lock and repository-destination resolution |
| `tools/upstream_sync/upstream.yml` | Move | Upstream source configuration |
| `tools/upstream_sync/upstream.lock.yml` | Move | Tracked upstream synchronization state |
| `tests/test_project_layout.py` | Create | Packaging, entry point, ignore, and root-layout contracts |
| `tests/test_upstream_sync.py` | Create | Upstream path and CLI contracts |
| `tests/test_skill_manager.py` | Modify | New imports, patch targets, web paths, repository default tests |
| `.github/workflows/sync-upstream.yml` | Modify | Install uv and call frozen `upstream-sync` entry point |
| `README.md` | Modify | New structure, setup, commands, and file descriptions |
| `docs/upstream-sync.md` | Move/modify | Upstream sync design with new paths and commands |
| `docs/superpowers/specs/2026-07-15-repository-layout-and-cli-design.md` | Modify | Mark the reviewed design implemented only after verification |
| Completed 2026-07-14 Skill manager spec/plan | Verify only | Preserve the original execution commands as historical evidence |
| `img.png` | Delete | Remove unreferenced, already-absorbed review image |

---

### Task 1: Move both tools and establish the uv command contract

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `tools/__init__.py`
- Create: `tools/skill_manager/__init__.py`
- Create: `tools/upstream_sync/__init__.py`
- Create: `tests/test_project_layout.py`
- Create: `tests/test_upstream_sync.py`
- Move: `skill_manager.py` → `tools/skill_manager/cli.py`
- Move: `skill_manager_core.py` → `tools/skill_manager/core.py`
- Move: `skill_manager_web/index.html` → `tools/skill_manager/web/index.html`
- Move: `vendor.py` → `tools/upstream_sync/vendor.py`
- Move: `upstream.yml` → `tools/upstream_sync/upstream.yml`
- Move: `upstream.lock.yml` → `tools/upstream_sync/upstream.lock.yml`
- Modify: `.gitignore`
- Modify: `tests/test_skill_manager.py`
- Modify: `.github/workflows/sync-upstream.yml`

**Interfaces:**
- Produces: console script `skill-manager = tools.skill_manager.cli:main`.
- Produces: console script `upstream-sync = tools.upstream_sync.vendor:main`.
- Produces: `tools.skill_manager.cli.DEFAULT_REPO_ROOT: Path` equal to the checkout root.
- Produces: `tools.upstream_sync.vendor.TOOL_ROOT`, `REPO_ROOT`, `CONFIG_FILE`, and `LOCK_FILE` as absolute `Path` values derived from `__file__`.
- Produces: `tools.upstream_sync.vendor.repository_path(relative: str | Path) -> Path` for resolving mapping destinations against `REPO_ROOT`.
- Preserves: the current keyword-injectable `tools.skill_manager.cli.main` and `create_server` signatures plus all existing core dataclasses/functions; only their import path changes.

- [ ] **Step 1: Add failing project-layout tests**

Create `tests/test_project_layout.py` with concrete package and root-cleanliness contracts:

```python
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
```

- [ ] **Step 2: Add failing upstream path and CLI tests**

Create `tests/test_upstream_sync.py`:

```python
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UpstreamSyncLayoutTests(unittest.TestCase):
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
```

- [ ] **Step 3: Retarget Skill manager tests before moving implementation**

In `tests/test_skill_manager.py` make these exact mechanical replacements:

```python
from tools.skill_manager.cli import create_server, main
```

For the existing multi-name core import, change only its module prefix from `skill_manager_core` to `tools.skill_manager.core`; preserve the exact imported symbol list.

Add `import importlib` with the standard-library imports. Replace the three dynamic imports currently used by the adoption rollback and snapshot-failure tests:

```python
real_verify = importlib.import_module(
    "tools.skill_manager.core"
)._target_is_direct_link
real_snapshot = importlib.import_module("tools.skill_manager.core").snapshot_path
```

There are two `_target_is_direct_link` occurrences and one `snapshot_path` occurrence. Do not mechanically rewrite them as `__import__("tools.skill_manager.core")`: dotted `__import__` returns the top-level `tools` package. Regular `patch(...)` target strings still use the direct prefix replacement below.

- Replace patch/import targets from `skill_manager_core` to `tools.skill_manager.core`.
- Replace `Path("skill_manager_web/index.html")` with `Path("tools/skill_manager/web/index.html")`.
- Replace temporary HTTP fixture roots from `repo / "skill_manager_web"` to `repo / "tools/skill_manager/web"`.
- Update traversal fixture `/../skill_manager.py` to `/../cli.py`.

Add a default-root contract without invoking real writes:

```python
class PackageLayoutTests(unittest.TestCase):
    def test_default_repo_root_points_to_checkout(self) -> None:
        from tools.skill_manager import cli

        self.assertEqual(cli.DEFAULT_REPO_ROOT, Path(__file__).resolve().parents[1])
```

Extend the existing symlinked-web-root HTTP test so both the final `web` component and an intermediate `skill_manager` component are rejected when replaced by symlinks.

- [ ] **Step 4: Run the new tests and verify they fail for the intended missing package**

Run:

```bash
uv run --no-project --python '>=3.11' python3 -m unittest \
  tests.test_project_layout tests.test_upstream_sync \
  tests.test_skill_manager.PackageLayoutTests -v
```

Expected: FAIL/ERROR because `pyproject.toml`, `uv.lock`, and `tools.skill_manager` / `tools.upstream_sync` do not exist yet. Failures must not come from touching the real HOME or Agent directories.

- [ ] **Step 5: Move tracked files and add package markers**

Run:

```bash
mkdir -p tools/skill_manager/web tools/upstream_sync
git mv skill_manager.py tools/skill_manager/cli.py
git mv skill_manager_core.py tools/skill_manager/core.py
git mv skill_manager_web/index.html tools/skill_manager/web/index.html
rmdir skill_manager_web
git mv vendor.py tools/upstream_sync/vendor.py
git mv upstream.yml tools/upstream_sync/upstream.yml
git mv upstream.lock.yml tools/upstream_sync/upstream.lock.yml
```

Create `tools/__init__.py`, `tools/skill_manager/__init__.py`, and `tools/upstream_sync/__init__.py` with one-line module docstrings only:

```python
"""Repository-local tooling."""
```

Use the more specific text `"""Global Skill manager."""` and `"""Upstream Skill synchronization."""` for the two subpackages.

- [ ] **Step 6: Create `pyproject.toml` and ignore `.venv/`**

Create this exact initial project file:

```toml
[project]
name = "lucas-skills-tools"
version = "0.1.0"
description = "Repository-local tools for managing and synchronizing lucas-skills"
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["PyYAML"]

[project.scripts]
skill-manager = "tools.skill_manager.cli:main"
upstream-sync = "tools.upstream_sync.vendor:main"

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-root = ""
module-name = "tools"
```

Append to `.gitignore`:

```gitignore
# uv project environment
.venv/
```

Run `uv lock` and require creation of root `uv.lock` without installing extra runtime dependencies beyond PyYAML.

- [ ] **Step 7: Update Skill manager imports, repository root, and secure web traversal**

In `tools/skill_manager/cli.py`:

Change the existing core import's module path from `skill_manager_core` to `.core`, preserving every current imported symbol. Add these constants immediately after the existing top-level constants:

```python
DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_PATH_PARTS = ("tools", "skill_manager", "web")
```

Change the default in `main`:

```python
repo_root = (repo_root or DEFAULT_REPO_ROOT).expanduser().resolve()
```

Preserve component-level `O_NOFOLLOW` protection with this helper and call it from `_read_web_index` instead of opening a slash-containing relative path:

```python
def _open_directory_chain(root_fd: int, parts: Sequence[str], flags: int) -> int:
    current_fd = os.dup(root_fd)
    try:
        for part in parts:
            next_fd = os.open(part, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise
```

`_read_web_index` must open `repo_fd`, call `_open_directory_chain(repo_fd, WEB_PATH_PARTS, directory_flags)`, open only the validated leaf file relative to `web_fd`, and close every descriptor in `finally` blocks. Do not rename this function. Do not use `Path.read_bytes`, `resolve`, or a single `os.open("tools/skill_manager/web", ...)` shortcut.

- [ ] **Step 8: Update upstream path resolution and CLI help**

In `tools/upstream_sync/vendor.py` replace cwd-relative constants with:

```python
TOOL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOL_ROOT.parents[1]
CACHE_DIR = Path.home() / ".cache" / "upstream-sync"
CONFIG_FILE = TOOL_ROOT / "upstream.yml"
LOCK_FILE = TOOL_ROOT / "upstream.lock.yml"


def repository_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate
```

Use `repository_path(dst)` in both `cmd_diff` and `cmd_sync`. Keep printed mapping names as the original config strings so output and PR parsing remain stable.

Make the entry point injectable and standard-help compatible:

```python
def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"help", "-h", "--help"}:
        print_help()
        return 0

    cmd = args[0]
    if cmd == "check":
        cmd_check()
    elif cmd == "diff":
        cmd_diff()
    elif cmd == "sync":
        upstream_filter = None
        if "--upstream" in args:
            idx = args.index("--upstream")
            if idx + 1 >= len(args):
                print("错误: --upstream 需要指定名称", file=sys.stderr)
                return 2
            upstream_filter = args[idx + 1]
        cmd_sync(upstream_filter)
    else:
        print(f"错误: 未知命令 '{cmd}'", file=sys.stderr)
        print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Replace every help/example prefix `python vendor.py` with `uv run upstream-sync`.

In `print_help`, also update the file-description section to point users to the moved repository-relative paths:

```text
  tools/upstream_sync/upstream.yml       上游配置（手动维护）
  tools/upstream_sync/upstream.lock.yml  同步状态记录（自动生成，建议提交到 git）
```

- [ ] **Step 9: Update GitHub Actions to the frozen project command**

In `.github/workflows/sync-upstream.yml`, replace `actions/setup-python` and `pip install pyyaml` with:

```yaml
      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          version: "0.11.28"
          enable-cache: true
```

Replace the two tool invocations only:

```bash
output=$(uv run --frozen upstream-sync check)
SYNC_OUTPUT=$(uv run --frozen upstream-sync sync)
```

Do not change PR branch naming, warning extraction, commit generation, or push behavior.

- [ ] **Step 10: Run targeted tests and packaging checks**

Run:

```bash
uv lock --check
uv run python -m unittest tests.test_project_layout tests.test_upstream_sync -v
uv run python -m unittest discover -s tests -p 'test_skill_manager.py'
uv run skill-manager --help
uv run upstream-sync --help
dist_dir=$(mktemp -d /tmp/lucas-skills-tools-dist.XXXXXX)
uv build --out-dir "$dist_dir"
```

Expected:

- Every command exits 0.
- The complete suite contains at least 100 passing test methods: the current 94 plus three project-layout tests, two upstream-sync tests, and one Skill manager package-layout test.
- The built wheel contains `tools/skill_manager/web/index.html`, `tools/upstream_sync/upstream.yml`, and `tools/upstream_sync/upstream.lock.yml` because they live under the configured module root.

Inspect the wheel without extracting into the repository:

```bash
unzip -l "$dist_dir"/*.whl | rg 'tools/(skill_manager/web/index.html|upstream_sync/upstream(\.lock)?\.yml)'
```

Expected: exactly three matching data-file paths.

- [ ] **Step 11: Commit the code, package, tests, config, and workflow slice**

```bash
git add .gitignore .github/workflows/sync-upstream.yml pyproject.toml uv.lock \
  tools tests/test_project_layout.py tests/test_upstream_sync.py tests/test_skill_manager.py
git commit -m "refactor(repo): 整理工具目录并统一 uv 入口" \
  -m "将两个仓库工具归入 tools flat package，通过 pyproject scripts 提供独立命令，并保持 Skill 页面安全路径与上游映射根目录语义。" \
  -m "验证：uv lock --check、至少 100 项完整测试、两个 --help 和 uv build 通过。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 2: Update documentation and remove obsolete root artifacts

**Files:**
- Modify: `README.md`
- Move: `DESIGN.md` → `docs/upstream-sync.md`
- Delete: `img.png`
- Modify: `tests/test_skill_manager.py`
- Modify: `docs/superpowers/specs/2026-07-15-repository-layout-and-cli-design.md`

**Interfaces:**
- Documents only the two new console commands; no old shim commands remain.
- Preserves the separate explicit confirmation gate for `uv run skill-manager adopt --apply --json`.
- Keeps the root tree and file descriptions aligned with the actual checkout.

- [ ] **Step 1: Change documentation contract tests first**

Update `ReadmeTests` in `tests/test_skill_manager.py` so its required command strings are:

```python
required = (
    "uv run skill-manager status",
    "uv run skill-manager doctor",
    "uv run skill-manager serve --open",
    "uv run skill-manager adopt --apply --json",
    "uv run upstream-sync check",
    "uv run upstream-sync sync",
)
```

Update its preview-before-apply ordering checks to use:

```python
"uv run skill-manager set docx --tool codex --on --json"
"uv run skill-manager set docx --tool codex --on --apply --json"
"uv run skill-manager adopt --json"
"uv run skill-manager adopt --apply --json"
```

Add assertions that README mentions `pyproject.toml`, `uv.lock`, and `tools/`, and no longer contains `pip install pyyaml` or `python vendor.py`.

- [ ] **Step 2: Run README tests and verify failure against old documentation**

Run:

```bash
uv run python -m unittest tests.test_skill_manager.ReadmeTests -v
```

Expected: FAIL because README still documents the old root commands and layout.

- [ ] **Step 3: Move the upstream design and delete the absorbed image**

Run:

```bash
git mv DESIGN.md docs/upstream-sync.md
git rm img.png
```

Do not create a replacement image or an `AGENTS.md` rationale document. Record the reason in the commit body.

- [ ] **Step 4: Rewrite README around the actual root and uv commands**

Update the root tree to show `pyproject.toml`, `uv.lock`, `tools/`, `skills/`, `tests/`, and `docs/`. Replace setup and command sections with:

```bash
uv sync
uv run upstream-sync check
uv run upstream-sync diff
uv run upstream-sync sync
uv run skill-manager status
uv run skill-manager doctor
uv run skill-manager serve --open
```

Keep all `--json`, preview-before-apply, service lifecycle, post-integration acceptance, and cc-switch migration wording. Replace only the executable prefix; do not weaken the separate `adopt --apply` authorization requirement.

Change the upstream design link to `[docs/upstream-sync.md](docs/upstream-sync.md)` and update the file table to the moved config/lock paths.

- [ ] **Step 5: Update the moved upstream design and preserve historical evidence**

In `docs/upstream-sync.md`, apply these context-aware replacements after the move:

- Root tree entries: move `vendor.py`, `upstream.yml`, and `upstream.lock.yml` under `tools/upstream_sync/`.
- Executable examples and workflow descriptions: `python vendor.py check|diff|sync` and prose such as “运行 vendor.py check” → the corresponding `uv run upstream-sync check|diff|sync` command.
- File descriptions: `upstream.yml` and `upstream.lock.yml` → `tools/upstream_sync/upstream.yml` and `tools/upstream_sync/upstream.lock.yml` where they describe repository paths. Plain filenames may remain where the text describes files relative to `vendor.py`.
- Internal-flow heading: `vendor.py` may remain as the module filename; do not rename the implementation file or invent an umbrella command.

Do not edit `docs/superpowers/specs/2026-07-14-global-skill-manager-design.md` or `docs/superpowers/plans/2026-07-14-global-skill-manager.md`: their old paths and commands record the implementation that actually ran. Do not mark the 2026-07-15 design spec implemented until the next verification step passes.

- [ ] **Step 6: Run documentation tests and residual-reference scans**

Run:

```bash
uv run python -m unittest tests.test_skill_manager.ReadmeTests -v
! rg -n \
  --glob '!docs/superpowers/specs/2026-07-14-global-skill-manager-design.md' \
  --glob '!docs/superpowers/plans/2026-07-14-global-skill-manager.md' \
  --glob '!docs/superpowers/specs/2026-07-15-repository-layout-and-cli-design.md' \
  --glob '!docs/superpowers/plans/2026-07-15-repository-layout-and-cli.md' \
  'python3 skill_manager.py|python vendor.py|skill_manager_web/index.html|^├── upstream.yml|^├── vendor.py' \
  README.md docs .github tests tools
git diff --check
```

Expected:

- README tests PASS.
- `rg` returns no runnable old command or obsolete root-layout reference in maintained code and documentation. The two excluded 2026-07-14 documents retain historical commands; the two excluded 2026-07-15 documents may describe the migration itself.
- `git diff --check` exits 0.

- [ ] **Step 7: Mark the reviewed design implemented after verification**

In `docs/superpowers/specs/2026-07-15-repository-layout-and-cli-design.md`, make this exact status change:

```markdown
**状态：** 已实施
```

Run:

```bash
rg -n '^\*\*状态：\*\* 已实施$' docs/superpowers/specs/2026-07-15-repository-layout-and-cli-design.md
git diff --check
```

Expected: one status match and no whitespace errors.

- [ ] **Step 8: Commit the documentation and root cleanup slice**

```bash
git add -A -- README.md DESIGN.md img.png docs tests/test_skill_manager.py
git commit -m "docs(repo): 更新目录与命令说明" \
  -m "同步 tools 目录、两个 uv 入口和上游配置新路径，并删除结论已沉淀到 AGENTS.md 的未引用评审截图。" \
  -m "验证：README 契约测试、旧命令残留扫描和 git diff --check 通过。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

---

### Task 3: Run final read-only acceptance

**Files:**
- Verify only; no planned file modifications.

**Interfaces:**
- Confirms the final tree, package, two CLI surfaces, documentation, and real-environment read-only behavior.
- Must not call any command containing both `--apply` and an executable Skill operation.

- [ ] **Step 1: Record the real symlink baseline**

Hash every symlink path and raw target under the six managed roots:

```bash
roots=("$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.copilot/skills" \
  "$HOME/.gemini/config/skills" "$HOME/.gemini/config/plugins/custom-skills/skills" \
  "$HOME/.gemini/antigravity-cli/plugins/lucas-skills/skills")
for root in "${roots[@]}"; do
  if [[ -e "$root" || -L "$root" ]]; then find "$root" -type l -print; fi
done | sort | while IFS= read -r link; do
  printf '%s -> %s\n' "$link" "$(readlink "$link")"
done | shasum -a 256
```

Save the printed hash in the execution notes; do not write a snapshot into the repository.

- [ ] **Step 2: Run complete static and automated verification**

```bash
uv lock --check
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run python -m py_compile \
  tools/skill_manager/cli.py tools/skill_manager/core.py \
  tools/upstream_sync/vendor.py tests/test_project_layout.py \
  tests/test_skill_manager.py tests/test_upstream_sync.py
awk '/<script/{n++; next} /<\/script>/{if(n==2) exit} n==2' \
  tools/skill_manager/web/index.html | node --check -
uv run skill-manager --help
uv run upstream-sync --help
git diff --check origin/main..HEAD
```

Expected: every command exits 0 and the complete unittest output reports `OK` with zero failures/errors.

- [ ] **Step 3: Run canonical real-environment read-only commands**

```bash
uv run skill-manager status --json
uv run skill-manager doctor --json || [[ $? -eq 1 ]]
uv run skill-manager adopt --json
```

Expected:

- `status` and `adopt` have no repository scan issue and the adoption plan remains preview-only.
- `doctor` may exit 1 for the already-known external broken/duplicate inventory records; record those exact records without treating them as a directory-refactor regression.
- No command includes `--apply`.

- [ ] **Step 4: Recompute the real symlink hash and compare**

Repeat Task 3 Step 1 exactly. Expected: the before and after hashes are identical.

- [ ] **Step 5: Verify final repository state and commit structure**

```bash
git status --short --branch
plan_commit=$(git log -1 --format=%H -- docs/superpowers/plans/2026-07-15-repository-layout-and-cli.md)
git log --reverse --oneline "$plan_commit"..HEAD
find . -maxdepth 1 -mindepth 1 -not -name '.git' -print | sort
```

Expected:

- Worktree is clean.
- Exactly the planned implementation commits are present after the reviewed spec commit.
- Root contains repository metadata plus `.github/`, `docs/`, `skills/`, `tests/`, `tools/`, `pyproject.toml`, and `uv.lock`; no legacy tool files or `img.png` remain.

- [ ] **Step 6: Stop for migration authorization**

Report the new commit SHAs, test count, CLI results, root tree, symlink hash equality, and any known `doctor` inventory warnings. Do not execute the previously previewed real migration until the user separately confirms it after seeing the fresh `uv run skill-manager adopt --json` summary.
