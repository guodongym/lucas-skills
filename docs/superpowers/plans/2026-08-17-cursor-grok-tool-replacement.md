# 旧工具支持清理与 Cursor/Grok 兼容复用实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 安全清理本仓库创建的 Antigravity/WorkBuddy 外部链接，并把 Agent Manager 的直接管理范围原子收敛为 Claude、Codex、GitHub Copilot；Cursor/Grok 仅复用工具自身的 Claude 兼容能力。

**Architecture:** 先在 canonical checkout 使用仍存在的旧 adapter 完成真实 HOME 清理，并保留可执行回滚；随后在隔离 worktree 中一次性修改 Python、Web、README 与全部活动测试，避免后端已拒绝旧工具而 Web 仍展示旧入口的中间提交。不新增 Cursor/Grok adapter、写入路径、状态或兼容配置管理。

**Tech Stack:** Python 3.11+、`unittest`、标准库文件系统 API、vanilla HTML/CSS/JavaScript、`uv`、Git。

## Global Constraints

- 批准的设计为 `docs/superpowers/specs/2026-08-17-cursor-grok-tool-replacement-design.md`。
- 真实 HOME 清理必须在旧 adapter 仍存在时从 canonical checkout 执行；代码修改必须在 `feature/agent-manager-tool-cleanup` 隔离 worktree 中执行。
- Skill 工具枚举最终精确为 `claude`、`codex`、`copilot`；surface 精确为六个。
- Instructions 自动目标最终精确为 `shared`、`claude`、`codex`、`copilot`；手工表面只保留 `copilot-desktop`。
- 不创建或管理 `~/.cursor/skills`、`~/.grok/skills`、`~/.grok/AGENTS.md`，不增加 Cursor/Grok CLI/HTTP 参数、Web 列或库存标签。
- 不管理 Cursor/Grok 的 MCP、插件、Hooks、Agents、认证、模型或兼容开关。
- 不保留 `antigravity`、`workbuddy` 的参数别名、隐藏 adapter、旧桥接字段或死代码。
- 真实 HOME 只删除直接指向本仓库的软链，以及内容一致且容器结构精确匹配的 Antigravity `lucas-skills` 插件容器；产品根和外部内容必须保留。
- 清理必须幂等：目标已缺失视为完成；目标存在但 ownership 不匹配时保留现场并停止。
- 不引入新依赖；保留现有 preview、apply、冲突检测、快照、回滚、竞态保护和恢复语义。
- Python、Web、README 和活动测试作为一个 breaking contract 原子提交；该提交包含动机、`验证：`、`BREAKING CHANGE` 和 `Co-authored-by: OpenAI Codex <noreply@openai.com>`。
- feature worktree 不用于验证指向 canonical checkout 的真实受管软链；合并后的真实新运行时 `status/doctor` 需要另行取得合并授权后从 canonical checkout 验收。

---

### Task 1: 在旧 adapter 删除前清理真实 HOME，并保留回滚

**Files:**
- Read: `tools/agent_manager/skills.py`
- Read: `tools/agent_manager/instructions.py`
- External state: `/Users/zhaoguodong/.gemini/config/skills/`
- External state: `/Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills/`
- External state: `/Users/zhaoguodong/.gemini/GEMINI.md`
- External state: `/Users/zhaoguodong/.workbuddy/skills/`

**Interfaces:**
- Consumes: 当前 `main` 上仍包含 `antigravity`、`workbuddy` adapter 的 Agent Manager。
- Produces: 旧受管软链数量为零；专用插件容器删除或已确认缺失；产品根和非本仓库内容原样保留。

- [ ] **Step 1: 重新锚定 canonical checkout，并持久化精确的 pre-cleanup baseline**

Run in one shell; if the shell changes, re-export the printed `CLEANUP_STATE_DIR` exactly before continuing:

```bash
git status --short --branch
ls -ld /Users/zhaoguodong/.cursor/skills /Users/zhaoguodong/.grok/skills /Users/zhaoguodong/.grok/AGENTS.md 2>/dev/null || true

umask 077
export CLEANUP_STATE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/lucas-skills-cleanup.XXXXXX")
chmod 700 "$CLEANUP_STATE_DIR"
printf 'CLEANUP_STATE_DIR=%s\n' "$CLEANUP_STATE_DIR"

uv run agent-manager skills set --all --tool antigravity --off --json > "$CLEANUP_STATE_DIR/antigravity-skills.preview.json"
uv run agent-manager skills set --all --tool workbuddy --off --json > "$CLEANUP_STATE_DIR/workbuddy-skills.preview.json"
uv run agent-manager instructions set --target antigravity --off --json > "$CLEANUP_STATE_DIR/antigravity-instructions.preview.json"

uv run python - <<'PY'
import json
import os
import re
import stat
from pathlib import Path

STATE = Path(os.environ["CLEANUP_STATE_DIR"])
REPOSITORY = Path("/Users/zhaoguodong/Codes/ai-coding/lucas-skills")
ROOTS = {
    "antigravity-desktop": Path("/Users/zhaoguodong/.gemini/config/skills"),
    "antigravity-cli": Path("/Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills/skills"),
    "workbuddy-desktop": Path("/Users/zhaoguodong/.workbuddy/skills"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(name: str) -> dict[str, object]:
    with (STATE / name).open(encoding="utf-8") as stream:
        value = json.load(stream)
    require(isinstance(value, dict), f"{name}: payload must be an object")
    return value


def validate_skills(name: str, adapters: set[str], count: int) -> list[dict[str, object]]:
    payload = load(name)
    require(payload.get("ok") is True, f"{name}: preview is not ok")
    changes = payload.get("changes")
    require(isinstance(changes, list) and len(changes) == count, f"{name}: unexpected change count")
    for change in changes:
        require(isinstance(change, dict), f"{name}: change must be an object")
        adapter = change.get("adapter_key")
        require(adapter in adapters, f"{name}: unexpected adapter {adapter!r}")
        target = Path(str(change.get("target")))
        root = ROOTS[str(adapter)]
        require(target.parent == root, f"{name}: target escaped fixed root: {target}")
        slug = change.get("slug")
        source = Path(str(change.get("source")))
        require(source == REPOSITORY / "skills" / str(slug), f"{name}: source is not the canonical repository Skill")
        expected = change.get("expected")
        require(isinstance(expected, dict), f"{name}: expected snapshot is missing")
        action = change.get("action")
        require(action in {"remove", "no-op"}, f"{name}: unexpected action {action!r}")
        if action == "remove":
            link_target = expected.get("link_target")
            require(expected.get("kind") == "symlink" and isinstance(link_target, str), f"{name}: remove is not an owned symlink")
            raw = Path(link_target)
            absolute = raw if raw.is_absolute() else target.parent / raw
            require(Path(os.path.abspath(absolute)) == source, f"{name}: symlink does not point directly to its source")
        else:
            require(expected.get("kind") == "missing" and expected.get("link_target") is None, f"{name}: no-op target is not missing")
    return changes


state_metadata = STATE.stat(follow_symlinks=False)
require(stat.S_ISDIR(state_metadata.st_mode), "cleanup state is not a directory")
require(stat.S_IMODE(state_metadata.st_mode) == 0o700, "cleanup state mode is not 0700")
require(state_metadata.st_uid == os.geteuid(), "cleanup state owner changed")

skills = [
    *validate_skills("antigravity-skills.preview.json", {"antigravity-desktop", "antigravity-cli"}, 4),
    *validate_skills("workbuddy-skills.preview.json", {"workbuddy-desktop"}, 2),
]

instruction_payload = load("antigravity-instructions.preview.json")
require(instruction_payload.get("ok") is True, "Instructions preview is not ok")
instruction_changes = instruction_payload.get("changes")
require(isinstance(instruction_changes, list) and len(instruction_changes) == 1, "Instructions preview must contain one change")
instruction = instruction_changes[0]
require(isinstance(instruction, dict), "Instructions change must be an object")
require(instruction.get("target") == "/Users/zhaoguodong/.gemini/GEMINI.md", "unexpected Instructions target")
require(instruction.get("source") == str(REPOSITORY / "AGENTS.md"), "unexpected Instructions source")
require(instruction.get("action") in {"remove", "no-op"}, "unexpected Instructions action")
instruction_expected = instruction.get("expected")
require(isinstance(instruction_expected, dict), "Instructions expected snapshot is missing")
if instruction.get("action") == "remove":
    require(
        instruction_expected.get("kind") == "symlink"
        and instruction_expected.get("link_target") == str(REPOSITORY / "AGENTS.md"),
        "Instructions remove is not the canonical managed symlink",
    )
else:
    require(
        instruction_expected.get("kind") == "missing"
        and instruction_expected.get("link_target") is None,
        "Instructions no-op target is not missing",
    )
fingerprint = instruction_payload.get("fingerprint")
require(isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint) is not None, "invalid Instructions fingerprint")

product_roots = []
for product_root in (ROOTS["antigravity-desktop"], ROOTS["workbuddy-desktop"]):
    metadata = product_root.stat(follow_symlinks=False)
    require(stat.S_ISDIR(metadata.st_mode), f"product root is not a real directory: {product_root}")
    product_roots.append({"path": str(product_root), "device": metadata.st_dev, "inode": metadata.st_ino})

baseline = {
    "version": 1,
    "skills": skills,
    "instruction": instruction,
    "instruction_fingerprint": fingerprint,
    "product_roots": product_roots,
}
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
state_fd = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    baseline_fd = os.open("baseline.json", flags, 0o600, dir_fd=state_fd)
    with os.fdopen(baseline_fd, "w", encoding="utf-8") as stream:
        json.dump(baseline, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
finally:
    os.close(state_fd)
print(f"saved exact cleanup baseline: {STATE / 'baseline.json'}")
PY
```

Expected:

- checkout 为干净的 `main`，已包含批准的 spec 与本 plan；
- 状态目录是当前用户持有的 `0700` 真目录，三个原始 preview 和 `0600` `baseline.json` 均在任何 apply 前写入；记录其绝对路径到执行报告；
- Antigravity 恰有 4 个、WorkBuddy 恰有 2 个目标；每项只为 `remove` 的 canonical-repository 直接软链或 `no-op` 的 `missing` 目标；
- Instructions 恰有一个相同语义的目标，并保存当前 fingerprint；两个产品根保存 device/inode；
- 任一数量、目标、动作、link_target、ownership 或权限不符合时停止，不执行 Step 2。

- [ ] **Step 2: 应用 Skill 停用计划，并与保存的 preview 精确比较**

Run:

```bash
test -n "$CLEANUP_STATE_DIR"
uv run agent-manager skills set --all --tool antigravity --off --apply --json > "$CLEANUP_STATE_DIR/antigravity-skills.apply.json"
uv run agent-manager skills set --all --tool workbuddy --off --apply --json > "$CLEANUP_STATE_DIR/workbuddy-skills.apply.json"

uv run python - <<'PY'
import json
import os
from pathlib import Path

STATE = Path(os.environ["CLEANUP_STATE_DIR"])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


for stem in ("antigravity-skills", "workbuddy-skills"):
    with (STATE / f"{stem}.preview.json").open(encoding="utf-8") as stream:
        preview = json.load(stream)
    with (STATE / f"{stem}.apply.json").open(encoding="utf-8") as stream:
        applied = json.load(stream)
    require(applied.get("ok") is True, f"{stem}: apply failed")
    require(applied.get("changes") == preview.get("changes"), f"{stem}: apply did not use the saved target set")
    results = applied.get("results")
    require(isinstance(results, list) and len(results) == len(preview["changes"]), f"{stem}: incomplete results")
    require(all(item.get("ok") is True and item.get("code") in {"applied", "no-op"} for item in results), f"{stem}: unexpected result")
print("Skill apply results exactly match the saved previews")
PY
```

Expected: 两个 payload 均为 `ok: true`，且 apply 返回的 `changes` 与对应 raw preview 逐字段相同；结果只包含 `applied` 或幂等 `no-op`。Skill set 没有 fingerprint 参数，由 apply 内部隔离并复核每个软链；比较失败时立即停止并按 Step 5 使用 baseline 补偿。

- [ ] **Step 3: 按保存的 fingerprint 清理 Instructions，并隔离删除专用插件容器**

Run:

```bash
test -n "$CLEANUP_STATE_DIR"
cleanup_instruction_action=$(uv run python -c 'import json, os; from pathlib import Path; print(json.loads((Path(os.environ["CLEANUP_STATE_DIR"]) / "baseline.json").read_text())["instruction"]["action"])')
cleanup_instruction_fingerprint=$(uv run python -c 'import json, os; from pathlib import Path; print(json.loads((Path(os.environ["CLEANUP_STATE_DIR"]) / "baseline.json").read_text())["instruction_fingerprint"])')
if [[ "$cleanup_instruction_action" == "remove" ]]; then
  uv run agent-manager instructions set --target antigravity --off --apply --expect-fingerprint "$cleanup_instruction_fingerprint" --json > "$CLEANUP_STATE_DIR/antigravity-instructions.apply.json"
else
  uv run python -c 'import os; raise SystemExit(1 if os.path.lexists("/Users/zhaoguodong/.gemini/GEMINI.md") else 0)'
fi

uv run python - <<'PY'
import json
import os
from pathlib import Path

STATE = Path(os.environ["CLEANUP_STATE_DIR"])
with (STATE / "baseline.json").open(encoding="utf-8") as stream:
    baseline = json.load(stream)
if baseline["instruction"]["action"] == "remove":
    with (STATE / "antigravity-instructions.preview.json").open(encoding="utf-8") as stream:
        preview = json.load(stream)
    with (STATE / "antigravity-instructions.apply.json").open(encoding="utf-8") as stream:
        applied = json.load(stream)
    if applied.get("ok") is not True:
        raise RuntimeError("Instructions apply failed")
    if applied.get("changes") != preview.get("changes") or applied.get("fingerprint") != baseline["instruction_fingerprint"]:
        raise RuntimeError("Instructions apply did not use the saved baseline")
    results = applied.get("results")
    if not isinstance(results, list) or len(results) != 1 or results[0].get("code") not in {"applied", "no-op"}:
        raise RuntimeError("Instructions apply returned an unexpected result")
print("Instructions cleanup matches the saved baseline")
PY

uv run python - <<'PY'
import os
import stat
import uuid
from pathlib import Path
from tools.agent_manager.skills import ANTIGRAVITY_MANIFEST

PARENT = Path("/Users/zhaoguodong/.gemini/antigravity-cli/plugins")
CONTAINER = "lucas-skills"
ISOLATED = "container"
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def read_bytes(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def close_fd(fd: int | None) -> None:
    if fd is not None:
        os.close(fd)


try:
    parent_fd = os.open(PARENT, DIRECTORY_FLAGS)
except FileNotFoundError:
    print("plugin container already absent (plugin parent missing)")
    raise SystemExit(0)
container_fd = None
manifest_fd = None
skills_fd = None
quarantine_fd = None
isolated_fd = None
quarantine_name = None
quarantine_identity = None
moved = False
deletion_started = False
try:
    parent_metadata = os.fstat(parent_fd)
    require(stat.S_ISDIR(parent_metadata.st_mode), "plugin parent is not a directory")
    parent_identity = identity(parent_metadata)
    named_parent = os.stat(PARENT, follow_symlinks=False)
    require(identity(named_parent) == parent_identity, "plugin parent identity changed after opening")
    try:
        container_fd = os.open(CONTAINER, DIRECTORY_FLAGS, dir_fd=parent_fd)
    except FileNotFoundError:
        print("plugin container already absent")
    if container_fd is not None:
        container_metadata = os.fstat(container_fd)
        require(stat.S_ISDIR(container_metadata.st_mode), "plugin container is not a directory")
        container_identity = identity(container_metadata)

        manifest_fd = os.open("plugin.json", FILE_FLAGS, dir_fd=container_fd)
        manifest_metadata = os.fstat(manifest_fd)
        require(stat.S_ISREG(manifest_metadata.st_mode), "plugin manifest is not a regular file")
        manifest_identity = identity(manifest_metadata)
        expected_manifest = ANTIGRAVITY_MANIFEST.encode("utf-8")
        require(manifest_metadata.st_size == len(expected_manifest), "plugin manifest size changed")
        require(read_bytes(manifest_fd) == expected_manifest, "plugin manifest content changed")

        skills_fd = os.open("skills", DIRECTORY_FLAGS, dir_fd=container_fd)
        skills_metadata = os.fstat(skills_fd)
        require(stat.S_ISDIR(skills_metadata.st_mode), "plugin skills entry is not a directory")
        skills_identity = identity(skills_metadata)
        require(sorted(os.listdir(container_fd)) == ["plugin.json", "skills"], "plugin container has external entries")
        require(os.listdir(skills_fd) == [], "plugin skills directory is not empty")

        quarantine_name = f".lucas-skills-quarantine-{uuid.uuid4().hex}"
        os.mkdir(quarantine_name, 0o700, dir_fd=parent_fd)
        quarantine_fd = os.open(quarantine_name, DIRECTORY_FLAGS, dir_fd=parent_fd)
        quarantine_metadata = os.fstat(quarantine_fd)
        quarantine_identity = identity(quarantine_metadata)
        require(stat.S_ISDIR(quarantine_metadata.st_mode), "quarantine is not a directory")
        require(stat.S_IMODE(quarantine_metadata.st_mode) == 0o700, "quarantine mode is not 0700")
        require(quarantine_metadata.st_uid == os.geteuid(), "quarantine owner changed")
        named_quarantine = os.stat(quarantine_name, dir_fd=parent_fd, follow_symlinks=False)
        require(identity(named_quarantine) == quarantine_identity, "quarantine identity changed after creation")
        named_container = os.stat(CONTAINER, dir_fd=parent_fd, follow_symlinks=False)
        require(identity(named_container) == container_identity, "plugin container changed before isolation")

        os.rename(CONTAINER, ISOLATED, src_dir_fd=parent_fd, dst_dir_fd=quarantine_fd)
        moved = True
        isolated_fd = os.open(ISOLATED, DIRECTORY_FLAGS, dir_fd=quarantine_fd)
        require(identity(os.fstat(isolated_fd)) == container_identity, "isolated container identity changed")
        require(sorted(os.listdir(isolated_fd)) == ["plugin.json", "skills"], "isolated container entries changed")

        check_manifest_fd = os.open("plugin.json", FILE_FLAGS, dir_fd=isolated_fd)
        try:
            check_manifest_metadata = os.fstat(check_manifest_fd)
            require(stat.S_ISREG(check_manifest_metadata.st_mode), "isolated manifest type changed")
            require(identity(check_manifest_metadata) == manifest_identity, "isolated manifest identity changed")
            require(read_bytes(check_manifest_fd) == expected_manifest, "isolated manifest content changed")
        finally:
            os.close(check_manifest_fd)

        check_skills_fd = os.open("skills", DIRECTORY_FLAGS, dir_fd=isolated_fd)
        try:
            check_skills_metadata = os.fstat(check_skills_fd)
            require(identity(check_skills_metadata) == skills_identity, "isolated skills identity changed")
            require(os.listdir(check_skills_fd) == [], "isolated skills directory changed")
        finally:
            os.close(check_skills_fd)

        close_fd(manifest_fd)
        manifest_fd = None
        close_fd(skills_fd)
        skills_fd = None
        deletion_started = True
        os.unlink("plugin.json", dir_fd=isolated_fd)
        os.rmdir("skills", dir_fd=isolated_fd)
        require(os.listdir(isolated_fd) == [], "isolated container is not empty after entry deletion")
        close_fd(isolated_fd)
        isolated_fd = None
        close_fd(container_fd)
        container_fd = None
        os.rmdir(ISOLATED, dir_fd=quarantine_fd)
        moved = False
        named_quarantine = os.stat(quarantine_name, dir_fd=parent_fd, follow_symlinks=False)
        require(identity(named_quarantine) == quarantine_identity, "quarantine identity changed before removal")
        os.rmdir(quarantine_name, dir_fd=parent_fd)
        quarantine_name = None
        print("removed isolated manager-owned plugin container")
except BaseException:
    if moved and not deletion_started and quarantine_fd is not None:
        try:
            os.stat(CONTAINER, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            try:
                os.rename(ISOLATED, CONTAINER, src_dir_fd=quarantine_fd, dst_dir_fd=parent_fd)
            except OSError:
                pass
            else:
                moved = False
    if moved and quarantine_name is not None:
        print(f"plugin container retained without deletion at {PARENT / quarantine_name / ISOLATED}")
    raise
finally:
    close_fd(isolated_fd)
    close_fd(skills_fd)
    close_fd(manifest_fd)
    close_fd(container_fd)
    close_fd(quarantine_fd)
    if quarantine_name is not None and not moved:
        try:
            named_quarantine = os.stat(quarantine_name, dir_fd=parent_fd, follow_symlinks=False)
            if quarantine_identity is not None and identity(named_quarantine) == quarantine_identity:
                os.rmdir(quarantine_name, dir_fd=parent_fd)
        except (FileNotFoundError, OSError):
            pass
    os.close(parent_fd)
PY
```

Expected: Instructions 仅在 baseline action 为 `remove` 时使用保存的 fingerprint apply；原始 `no-op` 保持缺失。插件容器缺失时幂等通过；存在时，父目录、容器、manifest、`skills/` 均通过 `O_NOFOLLOW`/`O_DIRECTORY` 与 `fstat` 绑定，容器原子移入唯一 `0700` 同级隔离目录并二次核对后，内部条目才通过 `dir_fd` 删除。任一 identity 或内容变化时不删除：能恢复则恢复，不能恢复则保留隔离现场并停止。整个流程不依赖优化模式会移除的检查语句。

- [ ] **Step 4: 读回清理结果并确认产品根 identity 不变**

Run:

```bash
uv run agent-manager skills status --json
uv run agent-manager instructions status --json

uv run python - <<'PY'
import json
import os
import stat
from pathlib import Path

STATE = Path(os.environ["CLEANUP_STATE_DIR"])
with (STATE / "baseline.json").open(encoding="utf-8") as stream:
    baseline = json.load(stream)
if os.path.lexists("/Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills"):
    raise RuntimeError("plugin container still exists")
for expected in baseline["product_roots"]:
    metadata = os.stat(expected["path"], follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode):
        raise RuntimeError(f"product root changed type: {expected['path']}")
    if (metadata.st_dev, metadata.st_ino) != (expected["device"], expected["inode"]):
        raise RuntimeError(f"product root identity changed: {expected['path']}")
print("product root identities match the saved baseline")
PY

git status --short --branch
```

Expected: Antigravity/WorkBuddy target 不再有 `enabled` 或 `legacy`；Antigravity Instructions 为 `missing`；插件目录不存在；两个产品根的 device/inode 与 baseline 相同；仓库仍干净。保留状态目录直至实现成功且不再需要补偿。

- [ ] **Step 5: 仅在实现中止时按 baseline 精确恢复旧状态**

Trigger: Task 1 已完成，但隔离 worktree 无法建立、实现被明确放弃，或后续任务无法继续且用户要求恢复原状。正常实现路径跳过本步骤。必须使用 Step 1 保存的同一个 `CLEANUP_STATE_DIR`；只恢复原 action 为 `remove` 的 target/link_target，原始 `no-op`/`missing` 不创建。

Run from the same canonical checkout:

```bash
test -n "$CLEANUP_STATE_DIR"

uv run python - <<'PY'
import json
import os
import stat
from collections import defaultdict
from pathlib import Path
from tools.agent_manager.skills import ANTIGRAVITY_MANIFEST

STATE = Path(os.environ["CLEANUP_STATE_DIR"])
ROOTS = {
    "antigravity-desktop": Path("/Users/zhaoguodong/.gemini/config/skills"),
    "antigravity-cli": Path("/Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills/skills"),
    "workbuddy-desktop": Path("/Users/zhaoguodong/.workbuddy/skills"),
}
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def readlink_or_missing(target: Path) -> str | None:
    try:
        metadata = target.stat(follow_symlinks=False)
    except FileNotFoundError:
        return None
    require(stat.S_ISLNK(metadata.st_mode), f"target is not a symlink: {target}")
    return os.readlink(target)


with (STATE / "baseline.json").open(encoding="utf-8") as stream:
    baseline = json.load(stream)
require(baseline.get("version") == 1, "unsupported cleanup baseline")
changes = baseline.get("skills")
require(isinstance(changes, list), "cleanup baseline has no Skill changes")
removals = [change for change in changes if change.get("action") == "remove"]
product_identities = {
    item["path"]: (item["device"], item["inode"])
    for item in baseline["product_roots"]
}

cli_removals = [change for change in removals if change.get("adapter_key") == "antigravity-cli"]
if cli_removals:
    plugin_parent = Path("/Users/zhaoguodong/.gemini/antigravity-cli/plugins")
    parent_fd = os.open(plugin_parent, DIRECTORY_FLAGS)
    try:
        try:
            os.mkdir("lucas-skills", 0o755, dir_fd=parent_fd)
        except FileExistsError:
            pass
        container_fd = os.open("lucas-skills", DIRECTORY_FLAGS, dir_fd=parent_fd)
        try:
            allowed = {"plugin.json", "skills"}
            require(set(os.listdir(container_fd)).issubset(allowed), "plugin container has external entries")
            expected_manifest = ANTIGRAVITY_MANIFEST.encode("utf-8")
            try:
                manifest_fd = os.open("plugin.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=container_fd)
            except FileNotFoundError:
                manifest_fd = os.open("plugin.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=container_fd)
                with os.fdopen(manifest_fd, "wb") as stream:
                    stream.write(expected_manifest)
                manifest_fd = os.open("plugin.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=container_fd)
            try:
                metadata = os.fstat(manifest_fd)
                require(stat.S_ISREG(metadata.st_mode), "plugin manifest is not a regular file")
                require(metadata.st_size == len(expected_manifest), "plugin manifest size differs")
                require(os.read(manifest_fd, len(expected_manifest) + 1) == expected_manifest, "plugin manifest content differs")
            finally:
                os.close(manifest_fd)
            try:
                os.mkdir("skills", 0o755, dir_fd=container_fd)
            except FileExistsError:
                pass
            skills_fd = os.open("skills", DIRECTORY_FLAGS, dir_fd=container_fd)
            try:
                expected_names = {Path(str(change["target"])).name for change in cli_removals}
                require(set(os.listdir(skills_fd)).issubset(expected_names), "plugin skills directory has external entries")
            finally:
                os.close(skills_fd)
        finally:
            os.close(container_fd)
    finally:
        os.close(parent_fd)

by_adapter: dict[str, list[dict[str, object]]] = defaultdict(list)
for change in removals:
    adapter = str(change.get("adapter_key"))
    require(adapter in ROOTS, f"unexpected adapter in baseline: {adapter}")
    by_adapter[adapter].append(change)

for adapter, adapter_changes in by_adapter.items():
    root = ROOTS[adapter]
    root_fd = os.open(root, DIRECTORY_FLAGS)
    try:
        root_metadata = os.fstat(root_fd)
        if str(root) in product_identities:
            require(
                (root_metadata.st_dev, root_metadata.st_ino) == product_identities[str(root)],
                f"product root identity changed before rollback: {root}",
            )
        for change in adapter_changes:
            target = Path(str(change.get("target")))
            require(target.parent == root, f"target escaped fixed root: {target}")
            expected = change.get("expected")
            require(isinstance(expected, dict), f"missing expected snapshot: {target}")
            link_target = expected.get("link_target")
            require(expected.get("kind") == "symlink" and isinstance(link_target, str), f"baseline target was not a symlink: {target}")
            source = Path(str(change.get("source")))
            raw = Path(link_target)
            absolute = raw if raw.is_absolute() else target.parent / raw
            require(Path(os.path.abspath(absolute)) == source, f"baseline ownership changed: {target}")
            current = readlink_or_missing(target)
            if current is None:
                os.symlink(link_target, target.name, dir_fd=root_fd)
                current = os.readlink(target.name, dir_fd=root_fd)
            require(current == link_target, f"refused to overwrite changed target: {target}")
    finally:
        os.close(root_fd)

for change in changes:
    target = Path(str(change["target"]))
    expected_link = change["expected"]["link_target"] if change["action"] == "remove" else None
    require(readlink_or_missing(target) == expected_link, f"Skill target differs from baseline: {target}")
print(f"restored exactly {len(removals)} Skill links; preserved {len(changes) - len(removals)} missing targets")
PY

rollback_instruction_action=$(uv run python -c 'import json, os; from pathlib import Path; print(json.loads((Path(os.environ["CLEANUP_STATE_DIR"]) / "baseline.json").read_text())["instruction"]["action"])')
if [[ "$rollback_instruction_action" == "remove" ]]; then
  uv run agent-manager instructions set --target antigravity --on --json > "$CLEANUP_STATE_DIR/antigravity-instructions.rollback-preview.json"
  rollback_instruction_fingerprint=$(uv run python - <<'PY'
import json
import os
from pathlib import Path

state = Path(os.environ["CLEANUP_STATE_DIR"])
baseline = json.loads((state / "baseline.json").read_text())
preview = json.loads((state / "antigravity-instructions.rollback-preview.json").read_text())
changes = preview.get("changes")
if preview.get("ok") is not True or not isinstance(changes, list) or len(changes) != 1:
    raise RuntimeError("invalid Instructions rollback preview")
change = changes[0]
original = baseline["instruction"]
if change.get("action") != "create" or change.get("target") != original["target"] or change.get("source") != original["expected"]["link_target"]:
    raise RuntimeError("Instructions rollback preview does not restore the exact baseline link")
print(preview["fingerprint"])
PY
  )
  uv run agent-manager instructions set --target antigravity --on --apply --expect-fingerprint "$rollback_instruction_fingerprint" --json > "$CLEANUP_STATE_DIR/antigravity-instructions.rollback-apply.json"
else
  uv run python -c 'import os; raise SystemExit(1 if os.path.lexists("/Users/zhaoguodong/.gemini/GEMINI.md") else 0)'
fi

uv run python - <<'PY'
import json
import os
import stat
from pathlib import Path

STATE = Path(os.environ["CLEANUP_STATE_DIR"])
with (STATE / "baseline.json").open(encoding="utf-8") as stream:
    baseline = json.load(stream)


def actual_link(target: str) -> str | None:
    path = Path(target)
    try:
        metadata = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISLNK(metadata.st_mode):
        raise RuntimeError(f"restored target is not a symlink: {target}")
    return os.readlink(path)


expected_pairs = sorted(
    (change["target"], change["expected"]["link_target"] if change["action"] == "remove" else None)
    for change in baseline["skills"]
)
actual_pairs = sorted((target, actual_link(target)) for target, _link in expected_pairs)
if actual_pairs != expected_pairs:
    raise RuntimeError(f"Skill target/link set differs from baseline: expected={expected_pairs!r}, actual={actual_pairs!r}")

instruction = baseline["instruction"]
expected_instruction = instruction["expected"]["link_target"] if instruction["action"] == "remove" else None
actual_instruction = actual_link(instruction["target"])
if actual_instruction != expected_instruction:
    raise RuntimeError("Instructions target/link differs from baseline")

for expected in baseline["product_roots"]:
    metadata = os.stat(expected["path"], follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or (metadata.st_dev, metadata.st_ino) != (expected["device"], expected["inode"]):
        raise RuntimeError(f"product root differs from baseline: {expected['path']}")

cli_links = [change for change in baseline["skills"] if change["adapter_key"] == "antigravity-cli" and change["action"] == "remove"]
container = Path("/Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills")
if cli_links and not container.is_dir():
    raise RuntimeError("required manager-owned CLI plugin container was not restored")
if not cli_links and os.path.lexists(container):
    raise RuntimeError("CLI plugin container was recreated without an original remove target")
print("rollback target/link set exactly matches the saved baseline")
PY

uv run agent-manager status --json
```

Expected: 只恢复 baseline 中原 action 为 `remove` 的精确链接；原始 `no-op`/`missing` 保持缺失。仅当存在 Antigravity CLI `remove` 时，创建内容固定的 manager-owned manifest、`skills/` 与那些精确链接。Instructions 仅在原 action 为 `remove` 时执行单目标 fingerprint apply。最终比较的 Skill 与 Instructions target/link_target 集合和两个产品根 identity 与 baseline 完全一致。本 Task 不创建 Git 提交。

---

### Task 2: 端到端原子删除旧工具支持

**Files:**
- Modify: `tools/agent_manager/skills.py`
- Modify: `tools/agent_manager/instructions.py`
- Modify: `tools/agent_manager/cli.py`
- Modify: `tools/agent_manager/server.py`
- Modify: `tools/agent_manager/web/index.html`
- Modify: `tools/agent_manager/web/app.js`
- Modify: `README.md`
- Modify: `tests/test_agent_manager.py`
- Modify: `tests/test_agent_manager_instructions.py`
- Modify: `tests/test_agent_manager_http.py`
- Modify: `tests/test_agent_manager_web.py`

**Interfaces:**
- Consumes: Task 1 已清理的真实 HOME；现有 generic Skill/Instructions 状态机。
- Produces: 三个 adapter、六个 surface、四个 Instructions target、三条 Web 路由、四列 Skills 表，以及不含旧字段的统一 CLI/HTTP/Web/README 合同。

- [ ] **Step 1: 创建隔离 worktree**

Invoke `superpowers:using-git-worktrees`, then create `feature/agent-manager-tool-cleanup` from the commit containing this plan.

Verify:

```bash
git status --short --branch
git log -2 --oneline
```

Expected: 当前分支为 `feature/agent-manager-tool-cleanup`，工作区干净，spec 和 plan 均在历史中。

- [ ] **Step 2: 一次性把活动测试改为最终合同**

Add/import exact allow-list contracts:

```python
self.assertEqual(agent_manager_cli.TOOLS, ("claude", "codex", "copilot"))
self.assertEqual(
    agent_manager_cli.INSTRUCTION_TARGETS,
    ("shared", "claude", "codex", "copilot"),
)
self.assertEqual(agent_manager_server.TOOLS, agent_manager_cli.TOOLS)
self.assertEqual(
    agent_manager_server.INSTRUCTION_TARGETS,
    agent_manager_cli.INSTRUCTION_TARGETS,
)
```

Update adapter/surface expectations:

```python
self.assertEqual(
    set(adapters),
    {"claude-shared", "codex-shared", "copilot-shared"},
)
self.assertEqual(
    set(surfaces),
    {
        "claude-desktop", "codex-desktop", "copilot-desktop",
        "claude-cli", "codex-cli", "copilot-cli",
    },
)
```

Replace old inventory cases with the exact fixed-source contract:

```python
self.assertEqual(
    [source.path for source in _fixed_inventory_sources(home)],
    [
        home / ".claude/skills",
        home / ".codex/skills",
        home / ".codex/skills/.system",
        home / ".copilot/skills",
        home / ".agents/skills",
        home / "Library/Application Support/com.github.githubapp/app-skills",
    ],
)
```

Update Instructions and adoption schema expectations:

```python
self.assertEqual(
    [target.key for target in build_instruction_targets(home)],
    ["shared", "claude", "codex", "copilot"],
)
self.assertEqual(
    set(payload["changes"]),
    {"link_changes", "container_changes", "snapshot_path"},
)
```

Update Web and README contracts:

```python
self.assertEqual(
    [route["tool"] for route in topology],
    ["claude", "codex", "copilot"],
)
self.assertIn('id="skills-body"><tr><td colspan="4"', self.html)
self.assertIn('cell.setAttribute("colspan", "4")', self.javascript)
```

```python
self.assertIn("三个工具族、六个检测表面", manager_docs)
self.assertIn("Cursor/Grok 兼容消费", manager_docs)
self.assertIn("`~/.cursor/skills`", manager_docs)
self.assertIn("`~/.grok/skills`", manager_docs)
```

`manager_docs` is the README slice from `## Agent Manager` up to `## 添加新的上游来源`. Delete all tests whose only contract is old-tool enablement, manifest creation, bridge migration, Web fallback or tool-specific HTTP apply. Keep generic preview/apply、rollback、conflict、race、recovery tests and adapt their fixtures to retained tools. Active tests must not retain removed names as negative fixtures; exact allow-list assertions and the final static scan cover that boundary.

- [ ] **Step 3: 运行全量测试并确认最终合同失败**

Run:

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -q
```

Expected: FAIL，至少包含 adapter/surface/Instructions 数量、adoption schema、Web 路由/列数和 README 管理范围不匹配；不得以只删测试的方式得到绿灯。

- [ ] **Step 4: 删除 Python 旧 adapter、库存、Instructions 和 bridge schema**

Implement exact runtime constants:

```python
TOOLS = ("claude", "codex", "copilot")
INSTRUCTION_TARGETS = ("shared", "claude", "codex", "copilot")
```

```python
def build_adapters(home: Path) -> tuple[TargetAdapter, ...]:
    return (
        TargetAdapter("claude-shared", "claude", home, home / ".claude/skills", ("claude-desktop", "claude-cli")),
        TargetAdapter("codex-shared", "codex", home, home / ".codex/skills", ("codex-desktop", "codex-cli")),
        TargetAdapter("copilot-shared", "copilot", home, home / ".copilot/skills", ("copilot-desktop", "copilot-cli")),
    )
```

```python
app_candidates = {
    "claude-desktop": (applications / "Claude.app", applications / "Claude Code.app"),
    "codex-desktop": (applications / "ChatGPT.app", applications / "Codex.app"),
    "copilot-desktop": (applications / "GitHub Copilot.app",),
}
cli_commands = {
    "claude-cli": "claude",
    "codex-cli": "codex",
    "copilot-cli": "copilot",
}
```

Use this exact Instructions topology:

```python
_TARGETS = (
    (
        "shared",
        ".agents/AGENTS.md",
        (
            "claude-desktop", "claude-cli", "codex-desktop",
            "codex-cli", "copilot-cli",
        ),
    ),
    ("claude", ".claude/CLAUDE.md", ("claude-desktop", "claude-cli")),
    ("codex", ".codex/AGENTS.md", ("codex-desktop", "codex-cli")),
    ("copilot", ".copilot/copilot-instructions.md", ("copilot-cli",)),
)
```

Reduce `TargetAdapter` to `key/tool/home/root/surfaces`, and reduce `AdoptionPlan` to `link_changes/container_changes/snapshot_path/repository`. Delete these old-only symbols and every reference:

```text
BridgeRemoval
ANTIGRAVITY_MANIFEST
_inspect_antigravity_legacy_container
_plan_antigravity_legacy_bridge
_apply_bridge_removal
bridge_removals
```

`_fixed_inventory_sources()` retains only the six paths asserted by tests; `scan_inventory()` combines them only with enabled Codex plugin sources. `_write_snapshot()` emits only `links`/`containers`; `plan_adoption()` and `apply_adoption()` have no bridge phase; `_prepare_adapter()` only creates `adapter.root`. Update CLI empty/adoption payload and text change counting to the same three-field adoption schema. HTTP validation inherits the exact constants.

- [ ] **Step 5: 同步删除 Web 与 README 旧合同**

Use this exact family list:

```javascript
const TOOL_FAMILIES = [
  { key: "claude", label: "Claude" },
  { key: "codex", label: "Codex" },
  { key: "copilot", label: "Copilot" },
];
```

Delete the tool-specific manual fallback in `buildTopology()` and use actual instruction targets/manual surfaces only. `flattenedChanges()` concatenates only `link_changes` and `container_changes`. Remove old options/headers from both selects and the Skills table; set only Skills loading/empty rows to `colspan="4"`, leaving inventory `colspan="6"` unchanged.

Rewrite the README Agent Manager section to three tools/six surfaces/four Instructions targets, remove manifest/bridge/custom-instructions guidance, and add:

```markdown
### Cursor/Grok 兼容消费

Cursor 和 Grok 不是 Agent Manager 的受管工具。Agent Manager 不写入
`~/.cursor/skills`、`~/.grok/skills` 或 `~/.grok/AGENTS.md`，也不管理二者的
MCP、插件、Hooks、Agents 或兼容开关。

- Cursor 可通过自身的兼容发现或第三方导入复用 Claude Skills；Desktop 与 CLI
  需要分别新建会话确认，不能从一端成功推断另一端成功。
- Grok 默认兼容扫描 Claude Skills 与规则；可用 `grok inspect --json` 检查实际来源。

不要再把同一仓库 Skill 链接到 Cursor/Grok 原生目录，否则可能新增重复来源。

官方参考：

- Cursor Skills：<https://cursor.com/cn/docs/skills>
- Cursor Rules：<https://cursor.com/cn/docs/rules>
- Cursor CLI：<https://cursor.com/cn/docs/cli/using>
- Grok Skills/Plugins：<https://docs.x.ai/build/features/skills-plugins-marketplaces>
- Grok CLI：<https://docs.x.ai/build/cli/reference>
```

- [ ] **Step 6: 运行全量回归和零残留检查**

Run:

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -q
if rg -n 'antigravity|workbuddy|Antigravity|WorkBuddy' README.md tools tests; then
  exit 1
fi
if rg -n 'bridge_removals|BridgeRemoval|ANTIGRAVITY_MANIFEST' tools tests; then
  exit 1
fi
if rg -n '\.cursor/skills|\.grok/skills|\.grok/AGENTS\.md' tools; then
  exit 1
fi
uv lock --check
git diff --check
```

Expected: tests PASS；三次 `rg` 均无输出；lock 与 diff 检查通过。运行时、README 和活动测试不含旧支持，运行时代码不含 Cursor/Grok 原生写入路径。

- [ ] **Step 7: 提交一个端到端 breaking contract**

```bash
git add README.md tools/agent_manager tests/test_agent_manager.py tests/test_agent_manager_instructions.py tests/test_agent_manager_http.py tests/test_agent_manager_web.py
git commit \
  -m 'refactor(agent-manager)!: 删除旧工具支持' \
  -m 'Agent Manager 端到端收敛为 Claude、Codex、Copilot，原子删除 Antigravity/WorkBuddy adapter、Instructions、库存、bridge schema、Web 和 README 合同。Cursor/Grok 继续通过工具自身能力兼容 Claude Skills，不增加重复写入路径。' \
  -m '验证：
- uv run python -m unittest discover -s tests -p '"'"'test_*.py'"'"' -q
- uv lock --check
- git diff --check
- active runtime/docs/tests residue scan 0' \
  -m 'BREAKING CHANGE: CLI 和 HTTP 不再接受 antigravity 或 workbuddy 工具及 antigravity Instructions target。' \
  -m 'Co-authored-by: OpenAI Codex <noreply@openai.com>'
```

---

### Task 3: 完成外部兼容 smoke、review 与交付边界

**Files:**
- Verify: `README.md`
- Verify: `tools/agent_manager/`
- Verify: `tests/`
- Verify: real HOME cleanup from Task 1

**Interfaces:**
- Consumes: Task 1 的外部清理和 Task 2 的原子实现提交。
- Produces: 可 review 的 feature branch；本次变更未新增 Cursor/Grok manager-owned 状态；真实新运行时验收明确等待合并授权。

- [ ] **Step 1: 重新运行确定性验证**

Run:

```bash
uv run python -m unittest discover -s tests -p 'test_*.py' -q
uv lock --check
git diff --check
git status --short --branch
```

Expected: tests/lock/diff 全部通过，feature worktree 干净，只有一个端到端实现提交位于 plan commit 之后。

- [ ] **Step 2: 只读检查 Grok 与 Cursor 的独立兼容结果**

Run:

```bash
grok inspect --json
ls -ld /Users/zhaoguodong/.cursor/skills /Users/zhaoguodong/.grok/skills /Users/zhaoguodong/.grok/AGENTS.md 2>/dev/null || true
```

Expected:

- 在当前未关闭兼容的环境中，Grok 输出仍包含 Claude 来源的 Skills/Instructions；
- 三个原生路径的状态与 Task 1 基线一致，Agent Manager 没有新建或改写它们；
- 分别新建 Cursor Desktop 和 Cursor CLI 会话，确认至少一个来自 `~/.claude/skills` 的已知 Skill 可见；
- 任一工具因兼容开关或版本能力不可见时，记录为外部环境限制，不写 Cursor/Grok 原生目录兜底，也不把未完成的 smoke 写成“已支持”。

- [ ] **Step 3: 从 canonical checkout 复核旧外部状态**

Run:

```bash
test ! -e /Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills
test -d /Users/zhaoguodong/.gemini/config/skills
test -d /Users/zhaoguodong/.workbuddy/skills
git status --short --branch
```

Expected: manager-owned 插件容器不存在，两个产品根仍在，canonical checkout 没有因 Task 1 产生仓库文件变化。

- [ ] **Step 4: 使用 review 和完成前验证工作流**

Invoke `superpowers:requesting-code-review` against the approved spec and this plan. Resolve only concrete in-scope findings with failing-test-first discipline, then invoke `superpowers:verification-before-completion` and rerun Steps 1-3.

Expected: review 无未解决的阻塞 finding；feature branch 干净；不要从 feature worktree 声称真实受管软链已通过新运行时 `status/doctor`。

- [ ] **Step 5: 明确后续授权边界**

Do not push、merge、tag、release、删除 worktree，或在 canonical checkout 运行合并后新版本的真实 `status/doctor`，除非用户另行授权。获得合并授权后，按 `superpowers:finishing-a-development-branch` 集成；随后从 canonical checkout 运行：

```bash
uv run agent-manager status --json
uv run agent-manager doctor --json
```

Expected after authorized integration: adapters 精确为 3、surfaces 精确为 6、Instructions targets 精确为 4、manual surface 精确为 1，且 `conflicts=0`、`issues=0`。该 post-integration gate 不属于未合并 feature branch 的完成声明。
