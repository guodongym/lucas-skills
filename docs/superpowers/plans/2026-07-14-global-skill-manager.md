# 全局 Skill 管理器实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前仓库内实现一个按需启动的全局 Skill 管理器，通过同一套 Python 核心和本地网页安全管理四个工具族的用户级软链，并提供只读全局 Skill 概览。

**Architecture:** `skill_manager_core.py` 是唯一业务层，负责仓库扫描、工具适配、状态分类、变更计划、接管、回滚与全局概览；`skill_manager.py` 只提供 CLI 和绑定 `127.0.0.1` 的 HTTP 服务；`skill_manager_web/index.html` 是无构建步骤的单页界面。文件系统软链始终是真实状态，页面和 CLI 每次操作后都重新扫描。

**Tech Stack:** `uv`、Python 3.11+、通过 `uv run --python '>=3.11' --with pyyaml` 按需提供的 PyYAML、Python 标准库 `argparse` / `dataclasses` / `http.server` / `tomllib` / `unittest`、原生 HTML/CSS/JavaScript。

## Global Constraints

- 首要运行环境是当前 macOS 主机。
- 只覆盖 Claude Code、Codex、GitHub Copilot、Antigravity 四个工具族；Desktop 与 CLI 都检测和验收。
- Codex Desktop 当前应用名为 `ChatGPT.app`（bundle id `com.openai.codex`），同时兼容迁移期 `Codex.app`；Claude Desktop 只验收 Code session 的本地 Skill，不把普通 Chat 的云端 Skill 当作同一表面。
- 当前仓库 `skills/` 是唯一受管 Skill 来源；不复制 Skill 内容。
- 文件系统是唯一真实状态；不增加数据库或持久化页面状态。
- 不向全局 Python 安装依赖；所有编译、测试和运行命令统一使用 `uv run --python '>=3.11' --with pyyaml python3 ...`。
- 管理服务只按需启动，只绑定 `127.0.0.1`，不创建 LaunchAgent 或常驻进程。
- 不覆盖普通文件、真实目录、工具内置 Skill 或其他来源软链。
- 外部、本地副本、内置和插件 Skill 第一版只读展示，不提供删除、移动或接管。
- 自动化测试必须使用临时仓库和临时 HOME，不写真实用户目录。
- 真实 `adopt --apply` 必须在实现完成后单独展示只读计划并取得用户确认。
- 设计依据：`docs/superpowers/specs/2026-07-14-global-skill-manager-design.md`。

---

## 文件职责

| 文件 | 动作 | 单一职责 |
| --- | --- | --- |
| `skill_manager_core.py` | Create | 领域模型、仓库扫描、适配器、状态、变更、接管、库存 |
| `skill_manager.py` | Create | CLI 参数、JSON 输出、本地 HTTP 服务、浏览器启动 |
| `skill_manager_web/index.html` | Create | 仓库 Skill 矩阵和全局概览页面 |
| `tests/test_skill_manager.py` | Create | 临时 HOME 下的核心、CLI、HTTP、静态页面测试 |
| `README.md` | Modify | 使用方法、安全边界、支持矩阵和退出 cc-switch 流程 |

稳定接口在任务中一次定义，后续任务只扩展行为，不改名：

```python
scan_repository(repo_root: Path) -> RepositoryScan
build_adapters(home: Path) -> tuple[TargetAdapter, ...]
detect_surfaces(which: Callable[[str], str | None], applications: Path = Path("/Applications")) -> dict[str, SurfaceStatus]
scan_managed_state(repository: RepositoryScan, adapters: Sequence[TargetAdapter], surfaces: Mapping[str, SurfaceStatus]) -> ManagedState
plan_set(state: ManagedState, slugs: Sequence[str], tools: Sequence[str], enabled: bool) -> ChangePlan
apply_plan(plan: ChangePlan, adapters: Mapping[str, TargetAdapter]) -> BatchResult
plan_adoption(state: ManagedState, state_root: Path) -> AdoptionPlan
apply_adoption(plan: AdoptionPlan, adapters: Mapping[str, TargetAdapter]) -> BatchResult
scan_inventory(state: ManagedState, home: Path) -> tuple[InventoryRecord, ...]
```

### Task 1: 仓库 Skill 扫描与领域模型

**Files:**
- Create: `skill_manager_core.py`
- Create: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: 仓库根目录 `Path` 和由 `uv run --python '>=3.11' --with pyyaml` 提供的 PyYAML。
- Produces: `SkillRecord`、`ScanIssue`、`RepositoryScan`、`scan_repository(repo_root)`；后续全部任务依赖这些名称和字段。

- [ ] **Step 1: 写仓库扫描失败测试**

在 `tests/test_skill_manager.py` 写入测试辅助函数和首组用例：

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skill_manager_core import scan_repository


def write_skill(root: Path, slug: str, name: str, description: str = "test skill") -> Path:
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_dir


class RepositoryScanTests(unittest.TestCase):
    def test_scans_valid_skill_and_allows_name_mismatch_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write_skill(repo, "wps365", "wps365-skills")

            result = scan_repository(repo)

            self.assertEqual([skill.slug for skill in result.skills], ["wps365"])
            self.assertEqual(result.skills[0].name, "wps365-skills")
            self.assertEqual(result.skills[0].warnings, ("name-mismatch",))
            self.assertEqual(result.issues, ())

    def test_rejects_missing_frontmatter_and_duplicate_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            invalid = repo / "skills" / "missing-frontmatter"
            invalid.mkdir(parents=True)
            (invalid / "SKILL.md").write_text("# invalid\n", encoding="utf-8")
            write_skill(repo, "one", "duplicate")
            write_skill(repo, "two", "duplicate")

            result = scan_repository(repo)

            self.assertEqual(result.skills, ())
            self.assertEqual(
                sorted(issue.code for issue in result.issues),
                ["duplicate-name", "duplicate-name", "invalid-frontmatter"],
            )
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv --version
uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v
```

Expected: `uv --version` 成功；测试以 `ERROR` 失败且包含 `ModuleNotFoundError: No module named 'skill_manager_core'`，不出现缺少 `yaml`。

- [ ] **Step 3: 实现最小扫描模型和解析逻辑**

在 `skill_manager_core.py` 新增以下模型和逻辑；`scan_repository` 只扫描 `skills/` 一级目录，重复 frontmatter `name` 的所有候选都排除：

```python
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class SkillRecord:
    slug: str
    name: str
    description: str
    path: Path
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanIssue:
    code: str
    path: Path
    message: str


@dataclass(frozen=True)
class RepositoryScan:
    repo_root: Path
    skills_root: Path
    skills: tuple[SkillRecord, ...]
    issues: tuple[ScanIssue, ...]


def _read_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter")
    try:
        closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("unterminated YAML frontmatter") from exc
    data = yaml.safe_load("\n".join(lines[1:closing]))
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def scan_repository(repo_root: Path) -> RepositoryScan:
    repo_root = repo_root.expanduser().resolve()
    skills_root = repo_root / "skills"
    candidates: list[SkillRecord] = []
    issues: list[ScanIssue] = []
    if not skills_root.is_dir():
        return RepositoryScan(
            repo_root,
            skills_root,
            (),
            (ScanIssue("missing-skills-root", skills_root, "skills directory does not exist"),),
        )

    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        slug = skill_dir.name
        skill_file = skill_dir / "SKILL.md"
        if not SLUG_RE.fullmatch(slug):
            issues.append(ScanIssue("invalid-slug", skill_dir, f"invalid directory slug: {slug}"))
            continue
        if not skill_file.is_file():
            issues.append(ScanIssue("missing-skill-file", skill_dir, "SKILL.md does not exist"))
            continue
        try:
            metadata = _read_frontmatter(skill_file)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            issues.append(ScanIssue("invalid-frontmatter", skill_file, str(exc)))
            continue
        name = metadata.get("name")
        description = metadata.get("description")
        if not isinstance(name, str) or not SLUG_RE.fullmatch(name):
            issues.append(ScanIssue("invalid-name", skill_file, "name must be a lowercase hyphenated slug"))
            continue
        if not isinstance(description, str) or not description.strip():
            issues.append(ScanIssue("invalid-description", skill_file, "description must be a non-empty string"))
            continue
        warnings = ("name-mismatch",) if name != slug else ()
        candidates.append(SkillRecord(slug, name, description.strip(), skill_dir.resolve(), warnings))

    name_counts = Counter(skill.name for skill in candidates)
    valid: list[SkillRecord] = []
    for skill in candidates:
        if name_counts[skill.name] > 1:
            issues.append(ScanIssue("duplicate-name", skill.path, f"duplicate name: {skill.name}"))
        else:
            valid.append(skill)
    return RepositoryScan(repo_root, skills_root, tuple(valid), tuple(issues))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `Ran 2 tests` 和 `OK`。

- [ ] **Step 5: 提交仓库扫描核心**

```bash
git add skill_manager_core.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 扫描仓库 Skills" \
  -m "建立部署 slug、frontmatter 元数据和扫描问题模型，为后续软链管理提供稳定输入。验证：uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 2: 工具适配器、表面检测与链接状态

**Files:**
- Modify: `skill_manager_core.py`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: `RepositoryScan`、`SkillRecord`。
- Produces: `TargetAdapter`、`SurfaceStatus`、`LinkState`、`TargetStatus`、`ManagedState`、`build_adapters`、`detect_surfaces`、`scan_managed_state`。

- [ ] **Step 1: 写适配矩阵和状态分类失败测试**

在测试文件追加：

```python
import os

from skill_manager_core import (
    LinkState,
    build_adapters,
    detect_surfaces,
    scan_managed_state,
)


class ManagedStateTests(unittest.TestCase):
    def test_builds_exact_target_roots(self) -> None:
        home = Path("/tmp/example-home")
        adapters = {item.key: item for item in build_adapters(home)}
        self.assertEqual(adapters["claude-shared"].root, home / ".claude/skills")
        self.assertEqual(adapters["codex-shared"].root, home / ".codex/skills")
        self.assertEqual(adapters["copilot-shared"].root, home / ".copilot/skills")
        self.assertEqual(adapters["antigravity-desktop"].root, home / ".gemini/config/skills")
        self.assertEqual(
            adapters["antigravity-cli"].root,
            home / ".gemini/antigravity-cli/plugins/lucas-skills/skills",
        )

    def test_classifies_direct_legacy_conflict_broken_and_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            home = root / "home"
            skill = write_skill(repo, "docx", "docx")
            scan = scan_repository(repo)
            adapters = build_adapters(home)
            by_key = {item.key: item for item in adapters}

            direct = by_key["claude-shared"].root / "docx"
            direct.parent.mkdir(parents=True)
            direct.symlink_to(skill)

            legacy_root = home / ".cc-switch/skills"
            legacy_root.mkdir(parents=True)
            (legacy_root / "docx").symlink_to(skill)
            legacy = by_key["codex-shared"].root / "docx"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(legacy_root / "docx")

            conflict = by_key["antigravity-desktop"].root / "docx"
            conflict.mkdir(parents=True)

            broken = by_key["copilot-shared"].root / "docx"
            broken.parent.mkdir(parents=True)
            broken.symlink_to(home / "missing/docx")

            installed = {"claude-cli": "/bin/claude", "codex-cli": "/bin/codex"}
            surfaces = detect_surfaces(
                which=lambda command: installed.get(f"{command}-cli"),
                applications=root / "Applications",
            )
            state = scan_managed_state(scan, adapters, surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(statuses[("claude-shared", "docx")].state, LinkState.ENABLED)
            self.assertEqual(statuses[("codex-shared", "docx")].state, LinkState.LEGACY)
            self.assertEqual(statuses[("antigravity-desktop", "docx")].state, LinkState.UNAVAILABLE)
            self.assertEqual(statuses[("copilot-shared", "docx")].state, LinkState.UNAVAILABLE)
            self.assertTrue(os.path.lexists(broken))
```

在同一个测试类加入表面可用时的精确断言：

```python
    def test_reports_conflict_and_broken_when_surfaces_are_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home, applications = root / "repo", root / "home", root / "Applications"
            write_skill(repo, "docx", "docx")
            (applications / "ChatGPT.app").mkdir(parents=True)
            (applications / "Antigravity.app").mkdir(parents=True)
            (applications / "GitHub Copilot.app").mkdir(parents=True)
            conflict = home / ".gemini/config/skills/docx"
            conflict.mkdir(parents=True)
            broken = home / ".copilot/skills/docx"
            broken.parent.mkdir(parents=True)
            broken.symlink_to(home / "missing/docx")
            adapters = build_adapters(home)
            surfaces = detect_surfaces(which=lambda _: None, applications=applications)

            state = scan_managed_state(scan_repository(repo), adapters, surfaces)
            statuses = {(item.adapter_key, item.slug): item for item in state.targets}

            self.assertEqual(statuses[("antigravity-desktop", "docx")].state, LinkState.CONFLICT)
            self.assertEqual(statuses[("copilot-shared", "docx")].state, LinkState.ERROR)
            self.assertTrue(surfaces["codex-desktop"].installed)
```

- [ ] **Step 2: 运行测试确认接口尚不存在**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `ImportError`，指出 `LinkState` 或 `build_adapters` 未定义。

- [ ] **Step 3: 实现固定适配器和表面检测**

在核心模块追加以下模型；`manifest_content` 预留给 Antigravity CLI，但本任务不写文件：

```python
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum


class LinkState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    LEGACY = "legacy"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class TargetAdapter:
    key: str
    tool: str
    home: Path
    root: Path
    surfaces: tuple[str, ...]
    manifest_path: Path | None = None
    manifest_content: str | None = None


@dataclass(frozen=True)
class SurfaceStatus:
    key: str
    installed: bool
    detector: str


@dataclass(frozen=True)
class TargetStatus:
    slug: str
    adapter_key: str
    tool: str
    state: LinkState
    path: Path
    raw_target: Path | None
    resolved_target: Path | None
    message: str


@dataclass(frozen=True)
class ManagedState:
    repository: RepositoryScan
    adapters: tuple[TargetAdapter, ...]
    surfaces: tuple[SurfaceStatus, ...]
    targets: tuple[TargetStatus, ...]


ANTIGRAVITY_MANIFEST = """{
  \"$schema\": \"https://antigravity.google/schemas/v1/plugin.json\",
  \"name\": \"lucas-skills\",
  \"description\": \"Global skills managed by lucas-skills.\"
}\n"""


def build_adapters(home: Path) -> tuple[TargetAdapter, ...]:
    plugin_root = home / ".gemini/antigravity-cli/plugins/lucas-skills"
    return (
        TargetAdapter("claude-shared", "claude", home, home / ".claude/skills", ("claude-desktop", "claude-cli")),
        TargetAdapter("codex-shared", "codex", home, home / ".codex/skills", ("codex-desktop", "codex-cli")),
        TargetAdapter("copilot-shared", "copilot", home, home / ".copilot/skills", ("copilot-desktop", "copilot-cli")),
        TargetAdapter("antigravity-desktop", "antigravity", home, home / ".gemini/config/skills", ("antigravity-desktop",)),
        TargetAdapter(
            "antigravity-cli",
            "antigravity",
            home,
            plugin_root / "skills",
            ("antigravity-cli",),
            plugin_root / "plugin.json",
            ANTIGRAVITY_MANIFEST,
        ),
    )


def detect_surfaces(
    which: Callable[[str], str | None] = shutil.which,
    applications: Path = Path("/Applications"),
) -> dict[str, SurfaceStatus]:
    app_candidates = {
        "claude-desktop": (applications / "Claude.app", applications / "Claude Code.app"),
        "codex-desktop": (applications / "ChatGPT.app", applications / "Codex.app"),
        "copilot-desktop": (applications / "GitHub Copilot.app",),
        "antigravity-desktop": (applications / "Antigravity.app",),
    }
    cli_commands = {
        "claude-cli": "claude",
        "codex-cli": "codex",
        "copilot-cli": "copilot",
        "antigravity-cli": "agy",
    }
    result = {
        key: SurfaceStatus(key, any(path.exists() for path in paths), "application")
        for key, paths in app_candidates.items()
    }
    result.update(
        {
            key: SurfaceStatus(key, which(command) is not None, f"command:{command}")
            for key, command in cli_commands.items()
        }
    )
    return result
```

- [ ] **Step 4: 实现链接分类和完整状态扫描**

追加精确分类规则；直接链接要求原始目标就是仓库 Skill，只有原始目标位于 `~/.cc-switch/skills` 或 `~/.gemini/skills` 且最终解析正确时才是 `legacy`：

```python
def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _absolute_link_target(path: Path) -> Path:
    raw = Path(os.readlink(path))
    return raw if raw.is_absolute() else path.parent / raw


def _under(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
        return True
    except ValueError:
        return False


def _adapter_available(adapter: TargetAdapter, surfaces: Mapping[str, SurfaceStatus]) -> bool:
    return any(surfaces[key].installed for key in adapter.surfaces)


def _classify_target(
    skill: SkillRecord,
    adapter: TargetAdapter,
    surfaces: Mapping[str, SurfaceStatus],
    legacy_roots: tuple[Path, ...],
    repository_skills_root: Path,
) -> TargetStatus:
    target = adapter.root / skill.slug
    if not _adapter_available(adapter, surfaces):
        return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.UNAVAILABLE, target, None, None, "surface not installed")
    if adapter.root.is_symlink():
        resolved_root = adapter.root.resolve(strict=False)
        if resolved_root == repository_skills_root.resolve(strict=False):
            return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.LEGACY, target, adapter.root, skill.path, "whole-directory link requires adoption")
        return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.CONFLICT, target, adapter.root, resolved_root, "target root is an unmanaged symlink")
    if not _lexists(target):
        return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.DISABLED, target, None, None, "target is absent")
    if not target.is_symlink():
        return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.CONFLICT, target, None, target.resolve(strict=False), "target is not a symlink")
    raw_target = _absolute_link_target(target)
    resolved = target.resolve(strict=False)
    if not resolved.exists():
        return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.ERROR, target, raw_target, resolved, "broken symlink")
    expected = skill.path.resolve()
    if Path(os.path.abspath(raw_target)) == expected:
        return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.ENABLED, target, raw_target, resolved, "direct repository link")
    if resolved == expected and any(_under(raw_target, root) for root in legacy_roots):
        return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.LEGACY, target, raw_target, resolved, "recognized legacy link")
    return TargetStatus(skill.slug, adapter.key, adapter.tool, LinkState.CONFLICT, target, raw_target, resolved, "symlink belongs to another source")


def scan_managed_state(
    repository: RepositoryScan,
    adapters: Sequence[TargetAdapter],
    surfaces: Mapping[str, SurfaceStatus],
) -> ManagedState:
    if not adapters:
        return ManagedState(repository, (), tuple(surfaces.values()), ())
    home = adapters[0].home
    legacy_roots = (home / ".cc-switch/skills", home / ".gemini/skills")
    targets = tuple(
        _classify_target(skill, adapter, surfaces, legacy_roots, repository.skills_root)
        for adapter in adapters
        for skill in repository.skills
    )
    return ManagedState(repository, tuple(adapters), tuple(surfaces.values()), targets)
```

- [ ] **Step 5: 运行状态测试并修正测试夹具**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: 所有测试 `OK`；表面不可用优先于磁盘冲突，表面可用时分别得到 `conflict` 和 `error`。

- [ ] **Step 6: 提交工具适配与状态模型**

```bash
git add skill_manager_core.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 识别工具与链接状态" \
  -m "加入四个工具族的 Desktop/CLI 检测和 direct、legacy、conflict、unavailable、error 状态分类。验证：uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 3: 幂等启停计划与安全软链写入

**Files:**
- Modify: `skill_manager_core.py`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: `ManagedState`、`TargetAdapter`、`TargetStatus`。
- Produces: `PathSnapshot`、`PlannedChange`、`ChangePlan`、`OperationResult`、`BatchResult`、`plan_set`、`apply_plan`。

- [ ] **Step 1: 写启用、停用、冲突和状态漂移失败测试**

追加测试，要求计划默认不写文件，执行时重验快照：

```python
from skill_manager_core import apply_plan, plan_set


class SetOperationTests(unittest.TestCase):
    def test_plan_is_read_only_and_apply_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            home = root / "home"
            write_skill(repo, "docx", "docx")
            scan = scan_repository(repo)
            adapters = build_adapters(home)
            surfaces = detect_surfaces(which=lambda command: "/bin/claude" if command == "claude" else None, applications=root / "Applications")
            state = scan_managed_state(scan, adapters, surfaces)

            plan = plan_set(state, ["docx"], ["claude"], True)
            target = home / ".claude/skills/docx"
            self.assertFalse(os.path.lexists(target))

            result = apply_plan(plan, {item.key: item for item in adapters})
            self.assertTrue(result.ok)
            self.assertEqual(target.resolve(), (repo / "skills/docx").resolve())

            second = apply_plan(
                plan_set(scan_managed_state(scan, adapters, surfaces), ["docx"], ["claude"], True),
                {item.key: item for item in adapters},
            )
            self.assertTrue(second.ok)
            self.assertEqual(second.results[0].code, "no-op")

    def test_apply_refuses_when_path_changed_after_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo = root / "repo"
            home = root / "home"
            write_skill(repo, "pdf", "pdf")
            scan = scan_repository(repo)
            adapters = build_adapters(home)
            surfaces = detect_surfaces(which=lambda command: "/bin/codex" if command == "codex" else None, applications=root / "Applications")
            state = scan_managed_state(scan, adapters, surfaces)
            plan = plan_set(state, ["pdf"], ["codex"], True)
            target = home / ".codex/skills/pdf"
            target.parent.mkdir(parents=True)
            target.mkdir()

            result = apply_plan(plan, {item.key: item for item in adapters})

            self.assertFalse(result.ok)
            self.assertEqual(result.results[0].code, "state-changed")
            self.assertTrue(target.is_dir())

    def test_unavailable_surface_is_a_successful_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            adapters = build_adapters(home)
            surfaces = detect_surfaces(
                which=lambda command: "/bin/agy" if command == "agy" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)

            result = apply_plan(plan_set(state, ["pdf"], ["antigravity"], True), {item.key: item for item in adapters})

            self.assertTrue(result.ok)
            self.assertTrue(any(item.code == "unavailable" and item.ok for item in result.results))

    def test_batch_reports_partial_failure_and_keeps_safe_successes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            occupied = home / ".claude/skills/pdf"
            occupied.mkdir(parents=True)
            adapters = build_adapters(home)
            surfaces = detect_surfaces(
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )
            state = scan_managed_state(scan_repository(repo), adapters, surfaces)

            result = apply_plan(
                plan_set(state, ["docx", "pdf"], ["claude"], True),
                {item.key: item for item in adapters},
            )

            self.assertFalse(result.ok)
            self.assertTrue((home / ".claude/skills/docx").is_symlink())
            self.assertTrue(occupied.is_dir())
            self.assertEqual({item.code for item in result.results}, {"applied", "blocked"})
```

另加停用测试：只有直接或受识别旧链接可删除；普通目录和外部软链必须保留并返回 `target-conflict`。

- [ ] **Step 2: 运行测试确认 `plan_set` 尚不存在**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `ImportError` 指向 `plan_set` 或 `apply_plan`。

- [ ] **Step 3: 实现快照、计划和结果模型**

追加：

```python
import uuid


@dataclass(frozen=True)
class PathSnapshot:
    kind: str
    link_target: str | None = None


@dataclass(frozen=True)
class PlannedChange:
    action: str
    slug: str
    adapter_key: str
    source: Path
    target: Path
    expected: PathSnapshot
    reason: str


@dataclass(frozen=True)
class ChangePlan:
    changes: tuple[PlannedChange, ...]


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    code: str
    slug: str
    adapter_key: str
    path: Path
    message: str


@dataclass(frozen=True)
class BatchResult:
    ok: bool
    results: tuple[OperationResult, ...]


def snapshot_path(path: Path) -> PathSnapshot:
    if not _lexists(path):
        return PathSnapshot("missing")
    if path.is_symlink():
        return PathSnapshot("symlink", os.readlink(path))
    if path.is_dir():
        return PathSnapshot("directory")
    return PathSnapshot("file")
```

- [ ] **Step 4: 实现计划生成和原子软链操作**

`plan_set` 将 tool 选择展开到对应 adapters；Antigravity 同时命中 Desktop 和 CLI。规则固定为：`disabled + on → create`、`enabled + off → remove`、同状态 → `no-op`、`unavailable → unavailable` 成功跳过、`legacy + on → requires-adopt`、其余不可写状态 → `blocked`。

```python
def plan_set(state: ManagedState, slugs: Sequence[str], tools: Sequence[str], enabled: bool) -> ChangePlan:
    skill_by_slug = {skill.slug: skill for skill in state.repository.skills}
    selected_adapters = {adapter.key for adapter in state.adapters if adapter.tool in tools or "all" in tools}
    statuses = {(item.adapter_key, item.slug): item for item in state.targets}
    changes: list[PlannedChange] = []
    for slug in slugs:
        if slug not in skill_by_slug:
            raise ValueError(f"unknown skill slug: {slug}")
        skill = skill_by_slug[slug]
        for adapter in state.adapters:
            if adapter.key not in selected_adapters:
                continue
            status = statuses[(adapter.key, slug)]
            if enabled and status.state == LinkState.DISABLED:
                action, reason = "create", "enable skill"
            elif not enabled and status.state in {LinkState.ENABLED, LinkState.LEGACY}:
                action, reason = "remove", "disable managed skill"
            elif (enabled and status.state == LinkState.ENABLED) or (not enabled and status.state == LinkState.DISABLED):
                action, reason = "no-op", "already in requested state"
            elif status.state == LinkState.UNAVAILABLE:
                action, reason = "unavailable", "surface is not installed"
            elif enabled and status.state == LinkState.LEGACY:
                action, reason = "requires-adopt", "legacy link must be adopted first"
            else:
                action, reason = "blocked", status.message
            changes.append(
                PlannedChange(action, slug, adapter.key, skill.path, status.path, snapshot_path(status.path), reason)
            )
    return ChangePlan(tuple(changes))


def _install_link(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.lucas-skills-{uuid.uuid4().hex}.tmp"
    temporary.symlink_to(source)
    try:
        os.replace(temporary, target)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def _remove_link(target: Path) -> None:
    temporary = target.parent / f".{target.name}.lucas-skills-{uuid.uuid4().hex}.old"
    os.replace(target, temporary)
    try:
        temporary.unlink()
    except OSError:
        os.replace(temporary, target)
        raise


def _safe_managed_link(change: PlannedChange, adapter: TargetAdapter) -> bool:
    if not change.target.is_symlink():
        return False
    raw = Path(os.path.abspath(_absolute_link_target(change.target)))
    resolved = change.target.resolve(strict=False)
    expected = change.source.resolve()
    recognized_raw = raw == expected or any(
        _under(raw, root)
        for root in (adapter.home / ".cc-switch/skills", adapter.home / ".gemini/skills")
    )
    return resolved == expected and recognized_raw


def apply_plan(plan: ChangePlan, adapters: Mapping[str, TargetAdapter]) -> BatchResult:
    results: list[OperationResult] = []
    for change in plan.changes:
        if change.action in {"no-op", "unavailable"}:
            results.append(OperationResult(True, change.action, change.slug, change.adapter_key, change.target, change.reason))
            continue
        if change.action in {"blocked", "requires-adopt"}:
            results.append(OperationResult(False, change.action, change.slug, change.adapter_key, change.target, change.reason))
            continue
        if snapshot_path(change.target) != change.expected:
            results.append(OperationResult(False, "state-changed", change.slug, change.adapter_key, change.target, "target changed after planning"))
            continue
        adapter = adapters[change.adapter_key]
        if change.action == "remove" and not _safe_managed_link(change, adapter):
            results.append(OperationResult(False, "target-conflict", change.slug, change.adapter_key, change.target, "target is not a recognized managed link"))
            continue
        try:
            if change.action == "create":
                _install_link(change.source, change.target)
                verified = change.target.is_symlink() and change.target.resolve() == change.source.resolve()
            else:
                _remove_link(change.target)
                verified = not _lexists(change.target)
            if not verified:
                raise OSError("post-operation verification failed")
            results.append(OperationResult(True, "applied", change.slug, change.adapter_key, change.target, change.reason))
        except PermissionError as exc:
            results.append(OperationResult(False, "permission-denied", change.slug, change.adapter_key, change.target, str(exc)))
        except OSError as exc:
            results.append(OperationResult(False, "verification-failed", change.slug, change.adapter_key, change.target, str(exc)))
    return BatchResult(all(item.ok for item in results), tuple(results))
```

在真正删除前再次调用链接归属校验，而不只依赖旧快照；这样即使计划对象被手工构造，也不能删除普通文件或外部链接。

- [ ] **Step 5: 运行测试和语法检查**

Run:

```bash
uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager_core.py
uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v
```

Expected: 编译成功；全部测试 `OK`。

- [ ] **Step 6: 提交启停核心**

```bash
git add skill_manager_core.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 安全启停受管链接" \
  -m "加入只读计划、状态漂移检测、原子软链替换、归属保护和逐项结果。验证：uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager_core.py；uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 4: cc-switch 与 Copilot 整目录接管

**Files:**
- Modify: `skill_manager_core.py`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: `ManagedState`、`PathSnapshot`、原子链接函数。
- Produces: `ContainerChange`、`AdoptionPlan`、`plan_adoption`、`apply_adoption`、时间戳 JSON 快照。

- [ ] **Step 1: 写旧链接和整目录接管失败测试**

追加两个用例：

```python
from skill_manager_core import apply_adoption, plan_adoption


class AdoptionTests(unittest.TestCase):
    def test_adopts_cc_switch_entry_links_and_writes_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            cc_skill = home / ".cc-switch/skills/docx"
            cc_skill.parent.mkdir(parents=True)
            cc_skill.symlink_to(skill)
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(cc_skill)
            state = build_test_state(repo, home, installed_commands={"claude": "/bin/claude"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")
            result = apply_adoption(plan, {item.key: item for item in state.adapters})

            self.assertTrue(result.ok)
            self.assertEqual(Path(os.readlink(target)), skill.resolve())
            self.assertTrue(plan.snapshot_path.is_file())
            self.assertIn("links", json.loads(plan.snapshot_path.read_text(encoding="utf-8")))

    def test_converts_copilot_whole_directory_link_to_per_skill_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            copilot_root = home / ".copilot/skills"
            copilot_root.parent.mkdir(parents=True)
            copilot_root.symlink_to(repo / "skills")
            state = build_test_state(repo, home, installed_commands={"copilot": "/bin/copilot"})

            result = apply_adoption(
                plan_adoption(state, home / ".local/state/lucas-skills-manager"),
                {item.key: item for item in state.adapters},
            )

            self.assertTrue(result.ok)
            self.assertTrue(copilot_root.is_dir())
            self.assertFalse(copilot_root.is_symlink())
            self.assertEqual((copilot_root / "docx").resolve(), (repo / "skills/docx").resolve())
            self.assertEqual((copilot_root / "pdf").resolve(), (repo / "skills/pdf").resolve())
```

把以下测试辅助函数放在 `write_skill` 下方，后续任务统一复用：

```python
def build_test_state(
    repo: Path,
    home: Path,
    *,
    installed_commands: dict[str, str] | None = None,
    installed_apps: set[str] | None = None,
):
    installed_commands = installed_commands or {}
    installed_apps = installed_apps or set()
    applications = home.parent / "Applications"
    for app_name in installed_apps:
        (applications / app_name).mkdir(parents=True, exist_ok=True)
    adapters = build_adapters(home)
    surfaces = detect_surfaces(
        which=lambda command: installed_commands.get(command),
        applications=applications,
    )
    return scan_managed_state(scan_repository(repo), adapters, surfaces)
```

- [ ] **Step 2: 运行测试确认 adoption 接口缺失**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `ImportError` 指向 `plan_adoption`。

- [ ] **Step 3: 实现 adoption 模型与 JSON 快照**

追加：

```python
import json
from datetime import UTC, datetime


@dataclass(frozen=True)
class ContainerChange:
    adapter_key: str
    root: Path
    expected: PathSnapshot
    links: tuple[tuple[str, Path], ...]
    reason: str


@dataclass(frozen=True)
class BridgeRemoval:
    adapter_key: str
    path: Path
    expected: PathSnapshot
    required_links: tuple[tuple[Path, Path], ...]
    reason: str


@dataclass(frozen=True)
class AdoptionPlan:
    link_changes: tuple[PlannedChange, ...]
    container_changes: tuple[ContainerChange, ...]
    bridge_removals: tuple[BridgeRemoval, ...]
    snapshot_path: Path


def _write_snapshot(plan: AdoptionPlan) -> None:
    plan.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "links": [
            {"path": str(item.target), "kind": item.expected.kind, "link_target": item.expected.link_target}
            for item in plan.link_changes
        ],
        "containers": [
            {"path": str(item.root), "kind": item.expected.kind, "link_target": item.expected.link_target}
            for item in plan.container_changes
        ],
        "bridges": [
            {"path": str(item.path), "kind": item.expected.kind, "link_target": item.expected.link_target}
            for item in plan.bridge_removals
        ],
    }
    plan.snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plan_adoption(state: ManagedState, state_dir: Path) -> AdoptionPlan:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    repository_root = state.repository.skills_root
    sources = {skill.slug: skill.path for skill in state.repository.skills}
    link_changes: list[PlannedChange] = []
    container_changes: list[ContainerChange] = []
    container_adapters: set[str] = set()
    for adapter in state.adapters:
        root_snapshot = snapshot_path(adapter.root)
        if root_snapshot.kind == "symlink" and adapter.root.resolve(strict=False) == repository_root.resolve():
            container_adapters.add(adapter.key)
            container_changes.append(
                ContainerChange(
                    adapter.key,
                    adapter.root,
                    root_snapshot,
                    tuple((skill.slug, skill.path) for skill in state.repository.skills),
                    "whole repository link",
                )
            )
    for target in state.targets:
        if target.adapter_key in container_adapters or target.state != LinkState.LEGACY:
            continue
        link_changes.append(
            PlannedChange(
                "create",
                target.slug,
                target.adapter_key,
                sources[target.slug],
                target.path,
                snapshot_path(target.path),
                "replace legacy link with direct repository link",
            )
        )
    return AdoptionPlan(
        tuple(link_changes),
        tuple(container_changes),
        (),
        state_dir / "snapshots" / f"{timestamp}.json",
    )
```

若 adapter root 本身是指向仓库 `skills/` 的链接，只产生一个 `ContainerChange`，不重复产生 14 个单项。快照名使用 UTC `YYYYMMDDTHHMMSSffffffZ.json`，避免同秒覆盖。

- [ ] **Step 4: 实现整目录转换、逐项替换和回滚**

整目录转换必须使用“三步交换”：构建临时目录 → 把旧 root 改名为 backup → 把临时目录改名为 root。验证失败时删除新 root 并恢复 backup；成功后只删除原来的软链 backup。

```python
def _apply_container_change(change: ContainerChange) -> None:
    if snapshot_path(change.root) != change.expected:
        raise RuntimeError("state-changed")
    temporary = change.root.parent / f".{change.root.name}.lucas-skills-{uuid.uuid4().hex}.tmp"
    backup = change.root.parent / f".{change.root.name}.lucas-skills-{uuid.uuid4().hex}.old"
    temporary.mkdir(parents=True)
    for slug, source in change.links:
        (temporary / slug).symlink_to(source)
    os.replace(change.root, backup)
    try:
        os.replace(temporary, change.root)
        for slug, source in change.links:
            if (change.root / slug).resolve() != source.resolve():
                raise OSError(f"verification failed for {slug}")
        backup.unlink()
    except Exception:
        if change.root.is_dir() and not change.root.is_symlink():
            for child in change.root.iterdir():
                child.unlink()
            change.root.rmdir()
        if _lexists(backup):
            os.replace(backup, change.root)
        raise
    finally:
        if temporary.is_dir():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()


def _apply_bridge_removal(change: BridgeRemoval) -> None:
    if snapshot_path(change.path) != change.expected:
        raise RuntimeError("state-changed")
    for target, source in change.required_links:
        if not target.is_symlink() or Path(os.path.abspath(_absolute_link_target(target))) != source.resolve():
            raise RuntimeError(f"required direct link missing: {target}")
    change.path.unlink()


def apply_adoption(plan: AdoptionPlan, adapters: Mapping[str, TargetAdapter]) -> BatchResult:
    _write_snapshot(plan)
    results: list[OperationResult] = []
    for change in plan.container_changes:
        try:
            _apply_container_change(change)
            results.append(OperationResult(True, "applied", "*", change.adapter_key, change.root, change.reason))
        except (OSError, RuntimeError) as exc:
            results.append(OperationResult(False, "adoption-failed", "*", change.adapter_key, change.root, str(exc)))
    link_plan = ChangePlan(tuple(plan.link_changes))
    results.extend(apply_plan(link_plan, adapters).results)
    for change in plan.bridge_removals:
        try:
            _apply_bridge_removal(change)
            results.append(OperationResult(True, "applied", "*", change.adapter_key, change.path, change.reason))
        except (OSError, RuntimeError) as exc:
            results.append(OperationResult(False, "bridge-removal-failed", "*", change.adapter_key, change.path, str(exc)))
    return BatchResult(all(item.ok for item in results), tuple(results))
```

`_write_snapshot` 保持在任何写操作之前且异常不捕获，因此快照写失败时不得修改任何链接。container 失败不阻止其他独立 adapter 的单项接管，但最终 `BatchResult.ok` 为 false。`BridgeRemoval` 在 Task 4 保持为空，Task 5 用它表达“新直链全部验证通过后才移除旧入口”。

- [ ] **Step 5: 运行接管测试和全量回归**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: 全部测试 `OK`；快照 JSON 能被 `json.loads` 解析；Copilot root 变为真实目录。

- [ ] **Step 6: 提交旧结构接管**

```bash
git add skill_manager_core.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 接管旧软链结构" \
  -m "支持 cc-switch 单项链接和 Copilot 整目录链接的快照、转换、验证与失败回滚。验证：uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 5: Antigravity Desktop 与 CLI 专用结构

**Files:**
- Modify: `skill_manager_core.py`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: `TargetAdapter.manifest_path`、`TargetAdapter.manifest_content`、adoption 模型。
- Produces: CLI 插件准备逻辑、旧 `custom-skills` 安全接管逻辑。

- [ ] **Step 1: 写插件清单与旧容器保护失败测试**

追加：

```python
class AntigravityTests(unittest.TestCase):
    def test_enabling_cli_skill_creates_managed_plugin_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            state = build_test_state(repo, home, installed_commands={"agy": "/bin/agy"})
            plan = plan_set(state, ["pdf"], ["antigravity"], True)

            result = apply_plan(plan, {item.key: item for item in state.adapters})

            manifest = home / ".gemini/antigravity-cli/plugins/lucas-skills/plugin.json"
            self.assertTrue(result.ok)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["name"], "lucas-skills")
            self.assertEqual(
                (home / ".gemini/antigravity-cli/plugins/lucas-skills/skills/pdf").resolve(),
                (repo / "skills/pdf").resolve(),
            )

    def test_refuses_mixed_custom_skills_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            legacy = home / ".gemini/skills"
            legacy.mkdir(parents=True)
            (legacy / "pdf").symlink_to(repo / "skills/pdf")
            write_skill(home / "external", "private", "private")
            (legacy / "private").symlink_to(home / "external/skills/private")
            plugin_skills = home / ".gemini/config/plugins/custom-skills/skills"
            plugin_skills.parent.mkdir(parents=True)
            plugin_skills.symlink_to(legacy)
            state = build_test_state(repo, home, installed_apps={"Antigravity.app"})

            plan = plan_adoption(state, home / ".local/state/lucas-skills-manager")

            self.assertTrue(any(item.action == "blocked" and "mixed" in item.reason for item in plan.link_changes))
            self.assertTrue(plugin_skills.is_symlink())

    def test_adopts_fully_managed_custom_skills_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            legacy = home / ".gemini/skills"
            legacy.mkdir(parents=True)
            (legacy / "pdf").symlink_to(repo / "skills/pdf")
            plugin_root = home / ".gemini/config/plugins/custom-skills"
            plugin_root.mkdir(parents=True)
            (plugin_root / "plugin.json").write_text('{"name":"custom-skills"}\n', encoding="utf-8")
            plugin_skills = plugin_root / "skills"
            plugin_skills.symlink_to(legacy)
            state = build_test_state(repo, home, installed_apps={"Antigravity.app"})

            result = apply_adoption(
                plan_adoption(state, home / ".local/state/lucas-skills-manager"),
                {item.key: item for item in state.adapters},
            )

            desktop_link = home / ".gemini/config/skills/pdf"
            self.assertTrue(result.ok)
            self.assertFalse(os.path.lexists(plugin_skills))
            self.assertTrue((plugin_root / "plugin.json").is_file())
            self.assertTrue(desktop_link.is_symlink())
            self.assertEqual(desktop_link.resolve(), (repo / "skills/pdf").resolve())
```

- [ ] **Step 2: 运行测试确认插件准备尚未发生**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: CLI 用例失败，表现为 `plugin.json` 不存在；混合容器用例失败，表明 adoption 尚未建模。

- [ ] **Step 3: 在 apply 前验证和创建 Antigravity CLI 插件**

实现：

```python
def _prepare_adapter(adapter: TargetAdapter) -> None:
    if adapter.manifest_path is None:
        adapter.root.mkdir(parents=True, exist_ok=True)
        return
    plugin_root = adapter.manifest_path.parent
    if plugin_root.exists() and not plugin_root.is_dir():
        raise OSError("plugin root is not a directory")
    plugin_root.mkdir(parents=True, exist_ok=True)
    if adapter.manifest_path.exists():
        data = json.loads(adapter.manifest_path.read_text(encoding="utf-8"))
        if data.get("name") != "lucas-skills":
            raise OSError("plugin manifest belongs to another owner")
    else:
        temporary = plugin_root / f".plugin-{uuid.uuid4().hex}.tmp"
        temporary.write_text(adapter.manifest_content or "", encoding="utf-8")
        os.replace(temporary, adapter.manifest_path)
    if _lexists(adapter.root) and not adapter.root.is_dir():
        raise OSError("plugin skills path is not a directory")
    adapter.root.mkdir(parents=True, exist_ok=True)
```

`apply_plan` 只在该 adapter 存在实际 `create` 动作时调用 `_prepare_adapter`；`no-op`、`blocked` 和只读计划不得创建插件目录。

- [ ] **Step 4: 实现旧 custom-skills 容器检查**

新增私有函数：

```python
def _inspect_antigravity_legacy_container(home: Path, repository: RepositoryScan) -> tuple[bool, str]:
    plugin_skills = home / ".gemini/config/plugins/custom-skills/skills"
    if not plugin_skills.is_symlink():
        return False, "legacy custom-skills entry not found"
    resolved_root = plugin_skills.resolve(strict=False)
    if not resolved_root.is_dir():
        return False, "legacy custom-skills entry is broken"
    expected = {skill.path.resolve() for skill in repository.skills}
    children = [path for path in resolved_root.iterdir() if not path.name.startswith(".")]
    if not children or any(not path.is_symlink() or path.resolve(strict=False) not in expected for path in children):
        return False, "mixed or unmanaged entries in legacy custom-skills container"
    return True, "safe legacy custom-skills container"


def _plan_antigravity_legacy_bridge(
    state: ManagedState,
) -> tuple[list[PlannedChange], BridgeRemoval | None]:
    home = state.adapters[0].home
    bridge = home / ".gemini/config/plugins/custom-skills/skills"
    if not _lexists(bridge):
        return [], None
    safe, reason = _inspect_antigravity_legacy_container(home, state.repository)
    desktop = next(adapter for adapter in state.adapters if adapter.key == "antigravity-desktop")
    if not safe:
        blocked = PlannedChange(
            "blocked",
            "*",
            desktop.key,
            state.repository.skills_root,
            bridge,
            snapshot_path(bridge),
            reason,
        )
        return [blocked], None
    changes: list[PlannedChange] = []
    required: list[tuple[Path, Path]] = []
    for skill in state.repository.skills:
        target = desktop.root / skill.slug
        current = snapshot_path(target)
        if current.kind == "missing":
            action, message = "create", "move Antigravity skill to official user root"
        elif target.is_symlink() and target.resolve(strict=False) == skill.path.resolve():
            action, message = "no-op", "official user-root link already resolves to repository"
        else:
            action, message = "blocked", "official Antigravity target is occupied"
        changes.append(PlannedChange(action, skill.slug, desktop.key, skill.path, target, current, message))
        required.append((target, skill.path))
    removal = BridgeRemoval(desktop.key, bridge, snapshot_path(bridge), tuple(required), "remove verified legacy custom-skills bridge")
    return changes, removal
```

把 `plan_adoption` 的 return 前逻辑扩展为：

```python
bridge_changes, bridge_removal = _plan_antigravity_legacy_bridge(state)
link_changes.extend(bridge_changes)
bridge_removals = () if bridge_removal is None else (bridge_removal,)
return AdoptionPlan(
    tuple(link_changes),
    tuple(container_changes),
    bridge_removals,
    state_dir / "snapshots" / f"{timestamp}.json",
)
```

因此安全容器先创建 Desktop 官方目录逐项直链，全部验证后只删除 `custom-skills/skills` 软链；`custom-skills/plugin.json` 和未知文件保持不变。混合容器只生成 `blocked` 结果。

- [ ] **Step 5: 运行 Antigravity 测试和全量回归**

Run:

```bash
uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager_core.py
uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v
```

Expected: 全部测试 `OK`。

- [ ] **Step 6: 提交 Antigravity 适配**

```bash
git add skill_manager_core.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 适配 Antigravity Skills" \
  -m "为 Desktop 使用官方全局目录，为 agy 创建受管插件，并安全识别旧 custom-skills 容器。验证：uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager_core.py；uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 6: 只读全局 Skill 概览与重名检测

**Files:**
- Modify: `skill_manager_core.py`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: `ManagedState`、工具适配器、frontmatter 解析器。
- Produces: `InventorySource`、`InventoryRecord`、`scan_inventory`、Codex 已启用插件解析。

- [ ] **Step 1: 写外部、本地、内置、损坏和重复名称失败测试**

在临时 HOME 构造以下来源并断言分类：

```python
class InventoryTests(unittest.TestCase):
    def test_lists_unmanaged_and_duplicate_skills_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(home / "external", "review", "review")
            claude_root = home / ".claude/skills"
            claude_root.mkdir(parents=True)
            (claude_root / "review").symlink_to(home / "external/skills/review")
            review_copy = claude_root / "review-copy"
            review_copy.mkdir()
            (review_copy / "SKILL.md").write_text(
                "---\nname: review\ndescription: local review copy\n---\n",
                encoding="utf-8",
            )
            broken = home / ".copilot/skills/broken"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.symlink_to(home / "missing")
            built_in_root = home / "Library/Application Support/com.github.githubapp/app-skills"
            built_in = built_in_root / "builtin"
            built_in.mkdir(parents=True)
            (built_in / "SKILL.md").write_text(
                "---\nname: builtin\ndescription: built in\n---\n",
                encoding="utf-8",
            )
            enabled_root = home / ".codex/plugins/cache/market/enabled/1.0.0"
            disabled_root = home / ".codex/plugins/cache/market/disabled/1.0.0"
            for plugin_root, slug in ((enabled_root, "enabled-skill"), (disabled_root, "disabled-skill")):
                manifest = plugin_root / ".codex-plugin/plugin.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text('{"skills":"skills"}\n', encoding="utf-8")
                write_skill(plugin_root, slug, slug)
            config = home / ".codex/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text(
                '[plugins]\n"enabled@market" = { enabled = true }\n"disabled@market" = { enabled = false }\n',
                encoding="utf-8",
            )

            state = build_test_state(repo, home, installed_commands={"claude": "/bin/claude", "copilot": "/bin/copilot"})
            records = scan_inventory(state, home)

            self.assertTrue(any(record.slug == "review" and record.source_type == "external-link" for record in records))
            self.assertTrue(any(record.slug == "review-copy" and record.source_type == "local-copy" for record in records))
            self.assertTrue(any(record.slug == "broken" and record.source_type == "broken" for record in records))
            self.assertTrue(any(record.slug == "builtin" and record.source_type == "built-in" for record in records))
            self.assertTrue(any(record.slug == "enabled-skill" and record.source_type == "plugin" for record in records))
            self.assertFalse(any(record.slug == "disabled-skill" for record in records))
            self.assertTrue(any("duplicate-name" in record.flags for record in records if record.name == "review"))
            self.assertTrue(any(record.slug == "review" and record.raw_target == home / "external/skills/review" for record in records))
            self.assertTrue((claude_root / "review").is_symlink())
```

- [ ] **Step 2: 运行测试确认 inventory 接口缺失**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `ImportError` 指向 `scan_inventory`。

- [ ] **Step 3: 实现库存模型和固定来源发现**

追加：

```python
import tomllib


@dataclass(frozen=True)
class InventorySource:
    root: Path
    tools: tuple[str, ...]
    surfaces: tuple[str, ...]
    source_type: str
    flat_markdown: bool = False


@dataclass(frozen=True)
class InventoryRecord:
    slug: str
    name: str
    description: str
    path: Path
    raw_target: Path | None
    resolved_target: Path | None
    tools: tuple[str, ...]
    surfaces: tuple[str, ...]
    source_type: str
    flags: tuple[str, ...]


def _fixed_inventory_sources(home: Path) -> list[InventorySource]:
    return [
        InventorySource(home / ".claude/skills", ("claude",), ("claude-desktop", "claude-cli"), "user-root"),
        InventorySource(home / ".codex/skills", ("codex",), ("codex-desktop", "codex-cli"), "user-root"),
        InventorySource(home / ".codex/skills/.system", ("codex",), ("codex-desktop", "codex-cli"), "built-in"),
        InventorySource(home / ".copilot/skills", ("copilot",), ("copilot-desktop", "copilot-cli"), "user-root"),
        InventorySource(home / ".agents/skills", ("copilot",), ("copilot-desktop", "copilot-cli"), "shared-user-root"),
        InventorySource(home / ".gemini/config/skills", ("antigravity",), ("antigravity-desktop",), "user-root"),
        InventorySource(home / ".gemini/antigravity-cli/skills", ("antigravity",), ("antigravity-cli",), "user-root", True),
        InventorySource(
            home / "Library/Application Support/com.github.githubapp/app-skills",
            ("copilot",),
            ("copilot-desktop",),
            "built-in",
        ),
    ]
```

扫描时跳过普通用户 root 下的隐藏目录；`.system` 由独立 source 扫描。目录型 Skill 读取 `SKILL.md`；`flat_markdown=True` 同时接受 `*.md` 和目录型 Skill。损坏软链在读取前判定为 `broken`。

- [ ] **Step 4: 实现插件来源发现与活跃 Codex 插件解析**

Antigravity 插件来源来自：

```python
home.glob(".gemini/config/plugins/*/skills")
home.glob(".gemini/antigravity-cli/plugins/*/skills")
```

Codex 逻辑：用 `tomllib` 读取 `~/.codex/config.toml` 的 `[plugins]`；只处理 `enabled = true`。对键 `<plugin>@<marketplace>`：

1. 若 `cache/<marketplace>-remote/<plugin>/.codex-remote-plugin-install.json` 存在，优先该根；
2. 否则使用 `cache/<marketplace>/<plugin>`；
3. 在版本子目录查找 `.codex-plugin/plugin.json` 或 `.claude-plugin/plugin.json`；
4. 多版本时选择 manifest `mtime_ns` 最大者；
5. 读取 manifest 的 `skills` 相对路径，缺省为 `skills`；
6. 无可解析 manifest 时生成 inventory warning，不把原始缓存标为已加载。

实现入口：

```python
def _enabled_codex_plugin_sources(home: Path) -> tuple[list[InventorySource], list[ScanIssue]]:
    config_path = home / ".codex/config.toml"
    if not config_path.is_file():
        return [], []
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    plugins = config.get("plugins", {})
    sources: list[InventorySource] = []
    issues: list[ScanIssue] = []
    for key, settings in plugins.items():
        if not isinstance(settings, dict) or settings.get("enabled") is not True or "@" not in key:
            continue
        plugin, marketplace = key.rsplit("@", 1)
        cache = home / ".codex/plugins/cache"
        remote = cache / f"{marketplace}-remote" / plugin
        regular = cache / marketplace / plugin
        plugin_root = remote if (remote / ".codex-remote-plugin-install.json").is_file() else regular
        manifests = list(plugin_root.glob("*/.codex-plugin/plugin.json")) + list(plugin_root.glob("*/.claude-plugin/plugin.json"))
        if not manifests:
            issues.append(ScanIssue("plugin-manifest-missing", plugin_root, f"enabled plugin has no manifest: {key}"))
            continue
        manifest_path = max(manifests, key=lambda path: path.stat().st_mtime_ns)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        skills_rel = manifest.get("skills", "skills")
        skills_root = manifest_path.parent.parent / skills_rel
        sources.append(InventorySource(skills_root, ("codex",), ("codex-desktop", "codex-cli"), "plugin"))
    return sources, issues


def _scan_inventory_source(source: InventorySource, managed_paths: set[Path]) -> list[InventoryRecord]:
    if not source.root.is_dir():
        return []
    candidates = list(source.root.glob("*.md")) if source.flat_markdown else []
    candidates.extend(path for path in source.root.iterdir() if path.is_dir() or path.is_symlink())
    records: list[InventoryRecord] = []
    for candidate in sorted(candidates, key=lambda path: path.name):
        if candidate.name.startswith("."):
            continue
        metadata_path = candidate if candidate.suffix == ".md" else candidate / "SKILL.md"
        slug = candidate.stem if candidate.suffix == ".md" else candidate.name
        raw_target = Path(os.readlink(candidate)) if candidate.is_symlink() else None
        resolved = candidate.resolve(strict=False)
        source_type = source.source_type
        flags: list[str] = []
        if candidate.is_symlink() and not candidate.exists():
            records.append(InventoryRecord(slug, slug, "", candidate, raw_target, resolved, source.tools, source.surfaces, "broken", ("broken-link",)))
            continue
        if resolved in managed_paths:
            source_type = "managed"
        elif candidate.is_symlink():
            source_type = "external-link"
        elif source.source_type not in {"built-in", "plugin"}:
            source_type = "local-copy"
        try:
            metadata = _read_frontmatter(metadata_path)
            name = str(metadata.get("name", "")).strip()
            description = str(metadata.get("description", "")).strip()
            if not name:
                raise ValueError("missing frontmatter name")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            name, description, source_type = slug, "", "broken"
            flags.append(f"invalid-skill:{exc}")
        records.append(
            InventoryRecord(
                slug,
                name,
                description,
                candidate,
                raw_target,
                resolved,
                source.tools,
                source.surfaces,
                source_type,
                tuple(flags),
            )
        )
    return records


def scan_inventory(state: ManagedState, home: Path) -> tuple[InventoryRecord, ...]:
    plugin_sources = [
        InventorySource(path, ("antigravity",), ("antigravity-desktop",), "plugin")
        for path in home.glob(".gemini/config/plugins/*/skills")
    ]
    plugin_sources.extend(
        InventorySource(path, ("antigravity",), ("antigravity-cli",), "plugin")
        for path in home.glob(".gemini/antigravity-cli/plugins/*/skills")
    )
    codex_sources, _issues = _enabled_codex_plugin_sources(home)
    managed_paths = {skill.path.resolve() for skill in state.repository.skills}
    records = [
        record
        for source in [*_fixed_inventory_sources(home), *plugin_sources, *codex_sources]
        for record in _scan_inventory_source(source, managed_paths)
    ]
    duplicate_keys = {
        (surface, record.name)
        for record in records
        for surface in record.surfaces
        if sum(record.name == other.name and surface in other.surfaces for other in records) > 1
    }
    return tuple(
        InventoryRecord(
            record.slug,
            record.name,
            record.description,
            record.path,
            record.raw_target,
            record.resolved_target,
            record.tools,
            record.surfaces,
            record.source_type,
            record.flags + (("duplicate-name",) if any((surface, record.name) in duplicate_keys for surface in record.surfaces) else ()),
        )
        for record in records
    )
```

`scan_inventory` 暂不把 `_enabled_codex_plugin_sources` 的 `ScanIssue` 伪装成 Skill；`doctor` 通过独立 `issues` 字段输出这些扫描告警。解析后的路径等于当前仓库某个 `SkillRecord.path` 时，类型统一为 `managed`。

- [ ] **Step 5: 运行库存测试和只读性检查**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: 全部测试 `OK`；disabled Codex 插件不出现在 inventory；测试前后临时 HOME 的非受管路径快照相同。

- [ ] **Step 6: 提交全局概览**

```bash
git add skill_manager_core.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 汇总全局 Skill 库存" \
  -m "只读枚举用户目录、内置目录和已启用插件，区分来源并检测损坏与重名。验证：uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 7: CLI 契约与 JSON 输出

**Files:**
- Create: `skill_manager.py`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: 核心公开函数和 dataclass 结果。
- Produces: `main(argv, home, repo_root, stdout) -> int`，命令 `status`、`doctor`、`set`、`adopt`、`serve`。

- [ ] **Step 1: 写 CLI 默认只读和 JSON 失败测试**

追加：

```python
import io

from skill_manager import main


class CliTests(unittest.TestCase):
    def test_set_without_apply_only_prints_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            output = io.StringIO()

            code = main(
                ["set", "docx", "--tool", "claude", "--on", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["mode"], "plan")
            self.assertFalse(os.path.lexists(home / ".claude/skills/docx"))

    def test_status_json_contains_tools_surfaces_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            output = io.StringIO()
            code = main(["status", "--json"], home=home, repo_root=repo, stdout=output, which=lambda _: None, applications=root / "Applications")
            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["skills"][0]["slug"], "pdf")
            self.assertEqual(len(payload["adapters"]), 5)
            self.assertEqual(len(payload["surfaces"]), 8)

    def test_batch_partial_failure_returns_one_with_per_item_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            write_skill(repo, "pdf", "pdf")
            occupied = home / ".claude/skills/pdf"
            occupied.mkdir(parents=True)
            output = io.StringIO()

            code = main(
                ["set", "--all", "--tool", "claude", "--on", "--apply", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/claude" if command == "claude" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["code"], "partial-failure")
            self.assertEqual({item["code"] for item in payload["results"]}, {"applied", "blocked"})
            self.assertTrue((home / ".claude/skills/docx").is_symlink())
            self.assertTrue(occupied.is_dir())

    def test_unavailable_surface_does_not_make_cli_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "pdf", "pdf")
            output = io.StringIO()

            code = main(
                ["set", "pdf", "--tool", "antigravity", "--on", "--apply", "--json"],
                home=home,
                repo_root=repo,
                stdout=output,
                which=lambda command: "/bin/agy" if command == "agy" else None,
                applications=root / "Applications",
            )

            payload = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertIn("unavailable", {item["code"] for item in payload["results"]})
```

- [ ] **Step 2: 运行测试确认入口模块不存在**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `ModuleNotFoundError: No module named 'skill_manager'`。

- [ ] **Step 3: 实现 argparse 和依赖可注入的 main**

`main` 签名固定为：

```python
def main(
    argv: Sequence[str] | None = None,
    *,
    home: Path | None = None,
    repo_root: Path | None = None,
    stdout: TextIO | None = None,
    which: Callable[[str], str | None] = shutil.which,
    applications: Path = Path("/Applications"),
) -> int:
```

构建 parser：

```python
parser = argparse.ArgumentParser(prog="skill-manager")
subparsers = parser.add_subparsers(dest="command", required=True)
for name in ("status", "doctor"):
    command = subparsers.add_parser(name)
    command.add_argument("--json", action="store_true")
set_parser = subparsers.add_parser("set")
set_parser.add_argument("skill", nargs="?", default=None)
set_parser.add_argument("--all", action="store_true")
set_parser.add_argument("--tool", choices=("claude", "codex", "copilot", "antigravity", "all"), required=True)
toggle = set_parser.add_mutually_exclusive_group(required=True)
toggle.add_argument("--on", action="store_true")
toggle.add_argument("--off", action="store_true")
set_parser.add_argument("--apply", action="store_true")
set_parser.add_argument("--json", action="store_true")
adopt_parser = subparsers.add_parser("adopt")
adopt_parser.add_argument("--apply", action="store_true")
adopt_parser.add_argument("--json", action="store_true")
serve_parser = subparsers.add_parser("serve")
serve_parser.add_argument("--open", action="store_true")
```

规则：`--all` 与位置参数不能同时出现，也不能同时缺失；`set` 和 `adopt` 默认 plan；只有 `--apply` 写入。`status` 输出受管状态；`doctor` 额外调用 `scan_inventory`。冲突、错误或写入/验证失败返回 `1`；只有 `unavailable` 时仍返回 `0`；成功或纯计划返回 `0`；argparse 错误保持 `2`。

- [ ] **Step 4: 实现稳定 JSON 序列化和文本摘要**

添加递归序列化器，保证 `Path`、`Enum`、dataclass、tuple 可编码：

```python
def to_jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value
```

JSON 顶层必须带 `mode: status|doctor|plan|apply`、`ok`、`repo_root`、`skills`、`adapters`、`surfaces`、`targets`；doctor 增加 `inventory` 和扫描 `issues`，变更命令增加 `changes` 或 `results`。批次同时包含成功和失败项时顶层 `code` 固定为 `partial-failure`；全部失败时使用第一个失败项的 code。文本模式至少输出总数、每工具启用数、冲突数和下一步命令，不打印 Skill 正文。

- [ ] **Step 5: 运行 CLI 测试和手工只读 smoke test**

Run:

```bash
uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager.py skill_manager_core.py
uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py status --json
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py doctor --json
```

Expected: 编译和测试通过；两个真实 HOME 命令只输出 JSON，不修改 `git status`，也不改变任何软链。

- [ ] **Step 6: 提交 CLI**

```bash
git add skill_manager.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 提供只读优先的 CLI" \
  -m "实现 status、doctor、set、adopt 命令，写操作默认只生成计划并支持稳定 JSON 输出。验证：uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager.py skill_manager_core.py；uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 8: 按需本地 HTTP 服务与写接口保护

**Files:**
- Modify: `skill_manager.py`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: CLI 构建状态和执行变更的内部函数。
- Produces: `create_server(repo_root, home, token, applications, which)`、`serve` 命令、五个 API。

- [ ] **Step 1: 写 localhost、令牌和同源失败测试**

使用临时 HOME 启动随机端口服务：

```python
import threading
import urllib.error
import urllib.request

from skill_manager import create_server


class HttpServerTests(unittest.TestCase):
    def test_write_requires_token_and_same_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            server = create_server(
                repo_root=repo,
                home=home,
                token="test-token",
                applications=root / "Applications",
                which=lambda command: "/bin/claude" if command == "claude" else None,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            url = f"http://{host}:{port}/api/set"
            body = json.dumps({"skill": "docx", "tool": "claude", "enabled": True, "apply": True}).encode()
            try:
                bad = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(bad)
                self.assertEqual(error.exception.code, 403)

                good = urllib.request.Request(
                    url,
                    data=body,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://{host}:{port}",
                        "X-Skill-Manager-Token": "test-token",
                    },
                )
                response = json.loads(urllib.request.urlopen(good).read())
                self.assertTrue(response["ok"])
                self.assertEqual((home / ".claude/skills/docx").resolve(), (repo / "skills/docx").resolve())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_rejects_path_traversal_as_invalid_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            write_skill(repo, "docx", "docx")
            server = create_server(repo, home, "test-token", root / "Applications", lambda _: "/bin/claude")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            request = urllib.request.Request(
                f"http://{host}:{port}/api/set",
                data=json.dumps({"skill": "../evil", "tool": "claude", "enabled": True, "apply": True}).encode(),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://{host}:{port}",
                    "X-Skill-Manager-Token": "test-token",
                },
            )
            try:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(json.loads(error.exception.read())["code"], "invalid-skill")
                self.assertFalse(os.path.lexists(home / ".claude/evil"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_server_restart_recovers_identical_filesystem_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            repo, home = root / "repo", root / "home"
            skill = write_skill(repo, "docx", "docx")
            target = home / ".claude/skills/docx"
            target.parent.mkdir(parents=True)
            target.symlink_to(skill)

            def read_status() -> dict[str, object]:
                server = create_server(repo, home, "test-token", root / "Applications", lambda _: "/bin/claude")
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                host, port = server.server_address
                try:
                    return json.loads(urllib.request.urlopen(f"http://{host}:{port}/api/status").read())
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)

            first = read_status()
            second = read_status()

            self.assertEqual(first["targets"], second["targets"])
            self.assertTrue(target.is_symlink())
```

另加：只绑定 `127.0.0.1`、错误 Origin 返回 403、`GET /api/status` 只读、`POST /api/shutdown` 能停止服务的用例。

- [ ] **Step 2: 运行测试确认 `create_server` 缺失**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `ImportError` 指向 `create_server`。

- [ ] **Step 3: 实现服务工厂和只读 API**

使用 `ThreadingHTTPServer(("127.0.0.1", 0), Handler)`。Handler 只接受：

- `GET /`：读取 `skill_manager_web/index.html`，把固定占位符 `__SKILL_MANAGER_TOKEN__` 替换为 `json.dumps(token)`；
- `GET /api/status`；
- `GET /api/inventory`；
- 其他 GET 返回 404。

所有 JSON 响应设置：

```text
Content-Type: application/json; charset=utf-8
Cache-Control: no-store
X-Content-Type-Options: nosniff
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:
```

不要设置 `Access-Control-Allow-Origin`。

- [ ] **Step 4: 实现写保护、set、adopt 和 shutdown**

写请求必须同时满足：

```python
expected_origin = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"
token_ok = secrets.compare_digest(self.headers.get("X-Skill-Manager-Token", ""), self.server.token)
origin_ok = self.headers.get("Origin") == expected_origin
```

任何一个不满足都返回 403。body 最大 64 KiB，超过返回 413；JSON 非对象返回 400。`/api/set` 接受 `{skill, tool, enabled, apply}` 或 `{all: true, tool, enabled, apply}`：单项页面请求传 `apply: true`，批量先传 `apply: false` 预览、确认后传 `apply: true`；`/api/adopt` 同样使用 `{"apply": false}` 预览、`{"apply": true}` 执行；`/api/shutdown` 在独立线程调用 `server.shutdown()`，先返回 200。

业务异常必须映射为结构化响应：`ValueError`（未知 slug、`../` 等非法输入）→ HTTP 400 / `invalid-skill`；受管 manifest 归属冲突和目标占用 → HTTP 409 / `target-conflict`；权限错误 → HTTP 403 / `permission-denied`；未分类内部异常 → HTTP 500 / `internal-error`。任何错误都不得回显 traceback。

`serve --open` 使用 `secrets.token_urlsafe(32)`，打印 URL；只有用户传 `--open` 时调用 `webbrowser.open(url)`。服务退出后不留 pid、端口或令牌文件。

- [ ] **Step 5: 运行服务测试与端口检查**

Run:

```bash
uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager.py
uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v
```

Expected: 全部测试 `OK`；测试 server address 第一项严格为 `127.0.0.1`。

- [ ] **Step 6: 提交本地服务**

```bash
git add skill_manager.py tests/test_skill_manager.py
git commit -m "feat(skill-manager): 提供按需本地服务" \
  -m "加入 localhost 随机端口、临时令牌、同源校验、受保护写 API 和显式关闭。验证：uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager.py；uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 9: 桌面管理页面

**Files:**
- Create: `skill_manager_web/index.html`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: `/api/status`、`/api/inventory`、`/api/set`、`/api/adopt`、`/api/shutdown`。
- Produces: 单页双视图 UI，无外部资源和构建步骤。

- [ ] **Step 1: 写静态页面契约失败测试**

追加：

```python
class WebPageTests(unittest.TestCase):
    def test_page_contains_required_views_and_no_external_assets(self) -> None:
        page = Path("skill_manager_web/index.html").read_text(encoding="utf-8")
        for element_id in (
            "summary",
            "managed-view",
            "inventory-view",
            "managed-table",
            "inventory-table",
            "rescan-button",
            "adopt-button",
            "shutdown-button",
            "managed-search",
            "managed-filter",
            "inventory-search",
            "inventory-filter",
            "enable-all-button",
            "disable-all-button",
        ):
            self.assertIn(f'id="{element_id}"', page)
        self.assertIn("__SKILL_MANAGER_TOKEN__", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("innerHTML", page)
```

- [ ] **Step 2: 运行测试确认页面不存在**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `FileNotFoundError: skill_manager_web/index.html`。

- [ ] **Step 3: 创建页面骨架、样式和两个视图**

创建 `skill_manager_web/index.html`，必须包含：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Skills 管理</title>
  <style>
    :root { color-scheme: light; --bg: #f6f7f9; --panel: #fff; --text: #17191c; --muted: #69707a; --line: #e2e5e9; --accent: #2563eb; --danger: #b42318; }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { width: min(1440px, calc(100% - 48px)); margin: 32px auto; }
    header, .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; }
    header { padding: 20px 24px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
    .toolbar, .tabs, #summary { display: flex; gap: 10px; flex-wrap: wrap; }
    button, input, select { font: inherit; }
    button { border: 1px solid var(--line); border-radius: 10px; background: #fff; padding: 8px 12px; cursor: pointer; }
    button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
    .panel { margin-top: 16px; overflow: hidden; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    .muted { color: var(--muted); }
    .hidden { display: none; }
    .state-enabled { color: #08783e; }
    .state-error, .state-conflict { color: var(--danger); }
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>Skills 管理</h1><div id="repo-path" class="muted"></div></div>
      <div class="toolbar">
        <button id="rescan-button">重新扫描</button>
        <button id="adopt-button">迁移旧链接</button>
        <button id="shutdown-button">关闭服务</button>
      </div>
    </header>
    <section id="summary" aria-label="统计"></section>
    <nav class="tabs" aria-label="视图切换">
      <button data-view="managed-view" class="primary">仓库 Skills</button>
      <button data-view="inventory-view">全局概览</button>
    </nav>
    <section id="managed-view" class="panel">
      <div class="toolbar filters">
        <input id="managed-search" type="search" placeholder="搜索仓库 Skill" aria-label="搜索仓库 Skill">
        <select id="managed-filter" aria-label="筛选仓库状态"><option value="all">全部状态</option><option value="enabled">已启用</option><option value="disabled">未启用</option><option value="mixed">部分启用</option><option value="conflict">冲突</option><option value="error">异常</option></select>
        <button id="enable-all-button">全部启用</button><button id="disable-all-button">全部停用</button>
      </div>
      <table id="managed-table"></table>
    </section>
    <section id="inventory-view" class="panel hidden">
      <div class="toolbar filters">
        <input id="inventory-search" type="search" placeholder="搜索全局 Skill" aria-label="搜索全局 Skill">
        <select id="inventory-filter" aria-label="筛选来源"><option value="all">全部来源</option><option value="managed">当前仓库</option><option value="external-link">外部软链</option><option value="local-copy">本地副本</option><option value="built-in">内置</option><option value="plugin">插件</option><option value="broken">损坏</option><option value="duplicate-name">重名</option></select>
      </div>
      <table id="inventory-table"></table>
    </section>
    <dialog id="confirm-dialog"><form method="dialog"><h2 id="confirm-title"></h2><pre id="confirm-body"></pre><button value="cancel">取消</button><button id="confirm-apply" value="confirm" class="primary">确认</button></form></dialog>
    <div id="message" role="status" aria-live="polite"></div>
  </main>
  <script>window.SKILL_MANAGER_TOKEN = __SKILL_MANAGER_TOKEN__;</script>
  <script>
    "use strict";
    const state = { status: null, inventory: null };
  </script>
</body>
</html>
```

页面不使用 emoji 作为唯一状态表达；状态同时有文本和 CSS class。所有来自 API 的字符串通过 `textContent` 或 `document.createTextNode` 写入。

- [ ] **Step 4: 实现 API 调用、矩阵、筛选、确认和反馈**

在第二个 script 中实现这些确定函数：

```javascript
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Skill-Manager-Token": window.SKILL_MANAGER_TOKEN,
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || `HTTP ${response.status}`);
  return payload;
}

async function loadStatus() {
  state.status = await api("/api/status");
  renderSummary(state.status);
  renderManaged(state.status);
}

async function loadInventory() {
  state.inventory = await api("/api/inventory");
  renderInventory(state.inventory);
}

async function setSkill(slug, tool, enabled) {
  await api("/api/set", { method: "POST", body: JSON.stringify({ skill: slug, tool, enabled, apply: true }) });
  await Promise.all([loadStatus(), loadInventory()]);
}

async function setAll(enabled) {
  const request = { all: true, tool: "all", enabled };
  const preview = await api("/api/set", { method: "POST", body: JSON.stringify({ ...request, apply: false }) });
  if (!await confirmPlan(enabled ? "全部启用" : "全部停用", preview)) return;
  await api("/api/set", { method: "POST", body: JSON.stringify({ ...request, apply: true }) });
  await Promise.all([loadStatus(), loadInventory()]);
}

async function previewAdoption() {
  const preview = await api("/api/adopt", { method: "POST", body: JSON.stringify({ apply: false }) });
  const confirmed = await confirmPlan("迁移旧链接", preview);
  if (!confirmed) return;
  await api("/api/adopt", { method: "POST", body: JSON.stringify({ apply: true }) });
  await Promise.all([loadStatus(), loadInventory()]);
}

async function shutdown() {
  await api("/api/shutdown", { method: "POST", body: "{}" });
  document.getElementById("message").textContent = "服务已关闭，可以关闭此页面。";
}
```

状态聚合和 DOM 更新使用以下固定映射与函数；不拼接 HTML：

```javascript
const TOOL_ADAPTERS = {
  claude: ["claude-shared"],
  codex: ["codex-shared"],
  copilot: ["copilot-shared"],
  antigravity: ["antigravity-desktop", "antigravity-cli"],
};
const TOOLS = Object.keys(TOOL_ADAPTERS);

function element(tag, text = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function clear(node) { node.replaceChildren(); }

function targetMap(payload, slug) {
  return new Map(payload.targets.filter((item) => item.slug === slug).map((item) => [item.adapter_key, item]));
}

function toolState(payload, slug, tool) {
  const targets = targetMap(payload, slug);
  const states = TOOL_ADAPTERS[tool].map((key) => targets.get(key)?.state || "unavailable");
  if (states.some((value) => value === "conflict")) return "conflict";
  if (states.some((value) => value === "error")) return "error";
  const active = states.filter((value) => value !== "unavailable");
  if (active.length === 0) return "unavailable";
  if (active.every((value) => value === "enabled")) return "enabled";
  if (active.every((value) => value === "disabled")) return "disabled";
  return "mixed";
}

function renderSummary(payload) {
  const summary = document.getElementById("summary");
  clear(summary);
  summary.append(element("span", `仓库 ${payload.skills.length}`));
  for (const tool of TOOLS) {
    const count = payload.skills.filter((skill) => toolState(payload, skill.slug, tool) === "enabled").length;
    summary.append(element("span", `${tool} ${count}`));
  }
  const states = payload.skills.flatMap((skill) => TOOLS.map((tool) => toolState(payload, skill.slug, tool)));
  summary.append(element("span", `冲突 ${states.filter((value) => value === "conflict").length}`));
  summary.append(element("span", `异常 ${states.filter((value) => value === "error").length}`));
  document.getElementById("repo-path").textContent = payload.repo_root;
}

function renderManaged(payload) {
  const query = document.getElementById("managed-search").value.trim().toLowerCase();
  const filter = document.getElementById("managed-filter").value;
  const table = document.getElementById("managed-table");
  clear(table);
  const head = element("tr");
  for (const label of ["Skill", "Claude", "Codex", "Copilot", "Antigravity"]) head.append(element("th", label));
  table.append(head);
  for (const skill of payload.skills) {
    const states = Object.fromEntries(TOOLS.map((tool) => [tool, toolState(payload, skill.slug, tool)]));
    if (query && !`${skill.slug} ${skill.name} ${skill.description}`.toLowerCase().includes(query)) continue;
    if (filter !== "all" && !Object.values(states).includes(filter)) continue;
    const row = element("tr");
    const identity = element("td");
    identity.append(element("strong", skill.name), element("div", skill.description, "muted"));
    row.append(identity);
    for (const tool of TOOLS) {
      const cell = element("td");
      const button = element("button", states[tool], `state-${states[tool]}`);
      const details = TOOL_ADAPTERS[tool].map((key) => targetMap(payload, skill.slug).get(key)).filter(Boolean);
      button.title = details.map((item) => `${item.adapter_key}: ${item.state} (${item.message})`).join("\n");
      button.disabled = ["unavailable", "conflict", "error"].includes(states[tool]) || details.some((item) => item.state === "legacy");
      button.addEventListener("click", () => setSkill(skill.slug, tool, states[tool] !== "enabled").catch(showError));
      cell.append(button);
      if (details.length === 2) cell.append(element("div", `D:${details[0].state} C:${details[1].state}`, "muted"));
      row.append(cell);
    }
    table.append(row);
  }
}

function renderInventory(payload) {
  const records = payload.inventory || [];
  const query = document.getElementById("inventory-search").value.trim().toLowerCase();
  const filter = document.getElementById("inventory-filter").value;
  const table = document.getElementById("inventory-table");
  clear(table);
  const head = element("tr");
  for (const label of ["名称", "来源", "工具", "路径", "原始链接", "解析目标", "状态"]) head.append(element("th", label));
  table.append(head);
  for (const record of records) {
    const flags = record.flags || [];
    if (query && !`${record.slug} ${record.name} ${record.description}`.toLowerCase().includes(query)) continue;
    if (filter !== "all" && filter !== record.source_type && !flags.includes(filter)) continue;
    const row = element("tr");
    for (const value of [record.name, record.source_type, record.tools.join(", "), record.path, record.raw_target || "-", record.resolved_target || "-", flags.join(", ") || "正常"]) {
      row.append(element("td", value));
    }
    table.append(row);
  }
}

function switchView(viewId) {
  for (const id of ["managed-view", "inventory-view"]) document.getElementById(id).classList.toggle("hidden", id !== viewId);
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("primary", button.dataset.view === viewId));
}

function showError(error) { document.getElementById("message").textContent = `操作失败：${error.message}`; }

function confirmPlan(title, payload) {
  const changes = payload.changes || payload.results || [];
  const changed = changes.filter((item) => ["create", "remove", "applied"].includes(item.action || item.code)).length;
  const skipped = changes.filter((item) => ["no-op", "unavailable"].includes(item.action || item.code)).length;
  const conflicts = changes.filter((item) => ["blocked", "conflict", "target-conflict"].includes(item.action || item.code)).length;
  const requiresAdopt = changes.filter((item) => (item.action || item.code) === "requires-adopt").length;
  document.getElementById("confirm-title").textContent = title;
  document.getElementById("confirm-body").textContent = `变更 ${changed}\n跳过 ${skipped}\n冲突 ${conflicts}\n需接管 ${requiresAdopt}`;
  const dialog = document.getElementById("confirm-dialog");
  dialog.showModal();
  return new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true }));
}
```

`GET /api/status` 返回 `{ok, repo_root, skills, adapters, surfaces, targets}`，`GET /api/inventory` 返回 `{ok, inventory, issues}`；页面严格按这两个结构读取。

首屏加载：

```javascript
document.getElementById("rescan-button").addEventListener("click", () => Promise.all([loadStatus(), loadInventory()]).catch(showError));
document.getElementById("adopt-button").addEventListener("click", () => previewAdoption().catch(showError));
document.getElementById("shutdown-button").addEventListener("click", () => shutdown().catch(showError));
document.getElementById("enable-all-button").addEventListener("click", () => setAll(true).catch(showError));
document.getElementById("disable-all-button").addEventListener("click", () => setAll(false).catch(showError));
document.getElementById("managed-search").addEventListener("input", () => renderManaged(state.status));
document.getElementById("managed-filter").addEventListener("change", () => renderManaged(state.status));
document.getElementById("inventory-search").addEventListener("input", () => renderInventory(state.inventory));
document.getElementById("inventory-filter").addEventListener("change", () => renderInventory(state.inventory));
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
Promise.all([loadStatus(), loadInventory()]).catch(showError);
```

- [ ] **Step 5: 运行静态契约、服务回归和人工页面检查**

Run:

```bash
uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py serve
```

Expected: 测试 `OK`；终端打印一个 `http://127.0.0.1:<port>/` URL。人工打开后验证双视图、搜索、筛选、混合状态、冲突详情、adoption 预览和关闭服务；不要在此步骤对真实 HOME 执行写操作。

- [ ] **Step 6: 提交页面**

```bash
git add skill_manager_web/index.html tests/test_skill_manager.py
git commit -m "feat(skill-manager): 添加 Skills 管理页面" \
  -m "提供仓库矩阵、Desktop/CLI 子状态、批量确认和只读全局概览，页面无外部依赖。验证：uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 10: README、完整验证与只读真实环境预检

**Files:**
- Modify: `README.md`
- Modify: `tests/test_skill_manager.py`

**Interfaces:**
- Consumes: 完整 CLI、服务和页面。
- Produces: 用户入口文档、最终验证证据、真实迁移前的只读计划。

- [ ] **Step 1: 写 README 入口契约失败测试**

追加：

```python
class ReadmeTests(unittest.TestCase):
    def test_documents_on_demand_service_and_adoption_gate(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        for text in (
            "uv --version",
            "uv run --python '>=3.11' --with pyyaml python3 skill_manager.py status",
            "uv run --python '>=3.11' --with pyyaml python3 skill_manager.py doctor",
            "uv run --python '>=3.11' --with pyyaml python3 skill_manager.py serve --open",
            "uv run --python '>=3.11' --with pyyaml python3 skill_manager.py adopt --apply",
            "服务不需要后台常驻",
        ):
            self.assertIn(text, readme)
```

- [ ] **Step 2: 运行测试确认 README 尚无入口**

Run: `uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v`

Expected: `FAIL`，缺少 `uv --version`。

- [ ] **Step 3: 更新 README 使用与安全说明**

在现有“快速开始”后增加“全局 Skill 管理器”章节，包含精确命令：

````markdown
## 全局 Skill 管理器

前置条件：本机已安装 `uv`，可用以下命令确认：

```bash
uv --version
```

管理器通过 `uv run --python '>=3.11' --with pyyaml` 使用隔离环境，不需要执行 `pip install pyyaml`。

查看受管状态和全局概览：

```bash
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py status
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py doctor
```

按需打开管理页面：

```bash
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py serve --open
```

预览旧 cc-switch 链接迁移：

```bash
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py adopt
```

只有检查计划并确认后才执行：

```bash
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py adopt --apply
```

服务不需要后台常驻。关闭页面中的服务或在终端按 `Ctrl+C` 后，已创建的软链继续生效。
````

同章列出四工具路径、默认 dry-run、冲突不覆盖、外部 Skill 只读和 Agent 可能需要新会话/重启。

- [ ] **Step 4: 运行完整自动化验证**

Run:

```bash
uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager.py skill_manager_core.py
uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v
git diff --check
```

Expected: 两个模块编译成功；全部测试 `OK`；`git diff --check` 无输出。

- [ ] **Step 5: 运行真实 HOME 只读状态和 doctor**

Run:

```bash
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py status --json
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py doctor --json
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py adopt --json
```

Expected:

- 仓库所有有效顶层 Skill 被识别，设计基线为 14；
- Claude Desktop Code session、ChatGPT Desktop Codex mode、Copilot、Antigravity 及四个 CLI 的已安装表面被检测；
- 当前 cc-switch 单项链接、Copilot 整目录链接和 Antigravity 旧入口出现在 adoption plan；
- 命令执行前后所有软链目标一致；
- 未出现未解释的 `permission-denied` 或解析异常。

保存输出摘要到本次任务记录，不把包含用户绝对路径的扫描 JSON 提交进仓库。

- [ ] **Step 6: 启动页面做真实只读验收**

Run: `uv run --python '>=3.11' --with pyyaml python3 skill_manager.py serve --open`

Expected: 页面显示仓库 Skill 矩阵和全局概览；Claude Desktop Code session、ChatGPT Desktop Codex mode、Copilot、Antigravity 的 Desktop/CLI 子状态与 CLI JSON 一致；点击“迁移旧链接”只查看预览并取消；点击“关闭服务”后端口关闭，软链未变化。

- [ ] **Step 7: 提交 README 和最终测试补充**

```bash
git add README.md tests/test_skill_manager.py
git commit -m "docs(skill-manager): 补充使用与验收说明" \
  -m "记录按需页面、只读检查、迁移确认、安全边界和四工具支持矩阵。验证：uv run --python '>=3.11' --with pyyaml python3 -m py_compile skill_manager.py skill_manager_core.py；uv run --python '>=3.11' --with pyyaml python3 -m unittest discover -s tests -p 'test_skill_manager.py' -v；git diff --check。" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

## 实现完成后的真实迁移门

以下步骤不属于代码提交，执行前必须把 `uv run --python '>=3.11' --with pyyaml python3 skill_manager.py adopt --json` 的摘要交给用户并取得明确确认：

1. 执行 `uv run --python '>=3.11' --with pyyaml python3 skill_manager.py adopt --apply --json`；
2. 再次运行 `status --json`，要求所有启用项最终解析到当前仓库，受管链路中的 `~/.cc-switch/skills` 依赖数为 `0`；
3. 运行 `doctor --json`，要求未管理文件、目录和外部链接的变更数为 `0`；
4. 关闭服务后再次运行 `status --json`，状态必须一致；
5. 在 Claude Desktop Code session、ChatGPT Desktop Codex mode、GitHub Copilot Desktop、Antigravity Desktop 和四个 CLI 的每个已安装表面验证至少一个 Skill 可见；
6. 选一个非关键 Skill 做停用 → 新会话不可见 → 重新启用 → 新会话恢复；
7. 只有以上验证全部通过后，才建议用户自行卸载 cc-switch；管理器不执行卸载或删除 `~/.cc-switch`。

## 计划自检映射

| Spec 要求 | 实施任务 |
| --- | --- |
| 仓库扫描、name mismatch、14 个基线 | Task 1 |
| 四工具族 Desktop/CLI、状态模型 | Task 2 |
| 逐项/批量启停、冲突保护、幂等和漂移检测 | Task 3 |
| cc-switch、Copilot 整目录、快照与回滚 | Task 4 |
| Antigravity Desktop 官方目录和 agy 插件 | Task 5 |
| 全局只读概览、插件、损坏和重名 | Task 6 |
| status/doctor/set/adopt/serve CLI | Task 7 |
| localhost、临时令牌、同源和关闭服务 | Task 8 |
| 双视图桌面页面和操作反馈 | Task 9 |
| README、完整验证、真实只读预检 | Task 10 |
| 用户确认后的真实迁移与四工具验收 | 实现完成后的真实迁移门 |

## 首轮 review findings 修订映射

| Finding | 修订位置 |
| --- | --- |
| P0-01 | 全部运行、测试和 README 命令改为 `uv run --python '>=3.11' --with pyyaml python3 ...`；Task 1 增加 `uv` 预检 |
| P1-01 | 所有 `TemporaryDirectory` 测试根统一使用 `Path(tmp).resolve()` |
| P1-02 | Task 4 删除 `plan_adoption` 中未定义且未使用的 `adapters` 引用 |
| P1-03 | Task 3 将 `unavailable` 定义为成功跳过；Task 7 补 CLI 退出码测试 |
| P1-04 | Task 6 将重名夹具改为同一 Claude 加载表面内的外部链接与本地副本 |
| P2-01 | spec 与 plan 统一 kebab-case 错误码和 `snapshots/` 路径 |
| P2-02 | Task 3/7/8 补批量部分失败、路径穿越和服务重启状态恢复测试 |
| P2-03 | Task 9 确认框单列 `requires-adopt` 数量 |
| P2-04 | Task 8 定义业务异常到 HTTP 状态与结构化错误码的映射 |
| P2-05 | 移除未使用的 `applications`/`adapters` 参数；库存增加 `raw_target` |
| Q-01 | Task 2 优先检测 `ChatGPT.app`，兼容 `Codex.app` |
| Q-02 | 真实验收限定 Claude Desktop Code session，普通 Chat 云端 Skill 不纳入本地软链验收 |
