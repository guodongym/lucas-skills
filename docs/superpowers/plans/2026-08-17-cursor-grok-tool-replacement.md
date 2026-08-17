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

- [ ] **Step 1: 重新锚定 canonical checkout、记录原生路径基线并刷新 preview**

Run:

```bash
git status --short --branch
ls -ld /Users/zhaoguodong/.cursor/skills /Users/zhaoguodong/.grok/skills /Users/zhaoguodong/.grok/AGENTS.md 2>/dev/null || true
uv run agent-manager skills set --all --tool antigravity --off --json
uv run agent-manager skills set --all --tool workbuddy --off --json
uv run agent-manager instructions set --target antigravity --off --json
```

Expected:

- checkout 为干净的 `main`，已包含批准的 spec 与本 plan；
- 记录 Cursor/Grok 三个原生路径在实现前是否存在及当前类型，后续只允许状态不变；
- 两个 Skill preview 的 `ok` 均为 `true`，`changes` 只包含 `remove` 或 `no-op`；
- Antigravity 目标只位于 `/Users/zhaoguodong/.gemini/config/skills/` 或 `/Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills/skills/`；
- WorkBuddy 目标只位于 `/Users/zhaoguodong/.workbuddy/skills/`；
- Instructions preview 只有 `/Users/zhaoguodong/.gemini/GEMINI.md` 一个 `remove` 或 `no-op`；`remove` 时 `expected.kind` 必须为 `symlink` 且指向本仓库 `AGENTS.md`；
- 任一目标、动作或 ownership 不符合以上条件时停止。

- [ ] **Step 2: 应用两个已审查的 Skill 停用计划**

Run:

```bash
uv run agent-manager skills set --all --tool antigravity --off --apply --json
uv run agent-manager skills set --all --tool workbuddy --off --apply --json
```

Expected: 两个 payload 均为 `ok: true`；结果只包含 `applied` 或幂等 `no-op`，没有普通文件、普通目录或外部链接被删除。Skill set 没有 fingerprint 参数，由 apply 内部复核目标快照，执行后必须继续完成 Step 4 读回。

- [ ] **Step 3: 幂等清理 Antigravity Instructions 和专用插件容器**

Run:

```bash
cleanup_instruction_preview=$(uv run agent-manager instructions set --target antigravity --off --json)
cleanup_instruction_action=$(
  printf '%s' "$cleanup_instruction_preview" |
  uv run python -c 'import json, sys; payload=json.load(sys.stdin); changes=payload["changes"]; assert payload["ok"] is True; assert len(changes) == 1; change=changes[0]; assert change["action"] in {"remove", "no-op"}; assert change["target"] == "/Users/zhaoguodong/.gemini/GEMINI.md"; expected=change["expected"]; assert change["action"] == "no-op" or (expected["kind"] == "symlink" and expected["link_target"] == "/Users/zhaoguodong/Codes/ai-coding/lucas-skills/AGENTS.md"); print(change["action"])'
)
if [[ "$cleanup_instruction_action" == "remove" ]]; then
  cleanup_instruction_fingerprint=$(
    printf '%s' "$cleanup_instruction_preview" |
    uv run python -c 'import json, sys; print(json.load(sys.stdin)["fingerprint"])'
  )
  uv run agent-manager instructions set --target antigravity --off --apply --expect-fingerprint "$cleanup_instruction_fingerprint" --json
else
  test ! -e /Users/zhaoguodong/.gemini/GEMINI.md
fi

uv run python - <<'PY'
import os
from pathlib import Path
from tools.agent_manager.skills import ANTIGRAVITY_MANIFEST

root = Path("/Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills")
if not os.path.lexists(root):
    print("plugin container already absent")
else:
    manifest = root / "plugin.json"
    skills = root / "skills"
    assert root.is_dir() and not root.is_symlink()
    assert manifest.is_file() and not manifest.is_symlink()
    assert manifest.read_text(encoding="utf-8") == ANTIGRAVITY_MANIFEST
    assert sorted(item.name for item in root.iterdir()) == ["plugin.json", "skills"]
    assert skills.is_dir() and not skills.is_symlink() and not any(skills.iterdir())
    manifest.unlink()
    skills.rmdir()
    root.rmdir()
    print("removed verified manager-owned plugin container")
PY
```

Expected: Instructions 为一个 `applied` 或已缺失；插件容器打印 `removed verified...` 或 `already absent`。任何 assertion 失败都保留容器并停止。始终保留 `/Users/zhaoguodong/.gemini/config/skills` 与 `/Users/zhaoguodong/.workbuddy/skills` 产品根。

- [ ] **Step 4: 读回清理结果**

Run:

```bash
uv run agent-manager skills status --json
uv run agent-manager instructions status --json
test ! -e /Users/zhaoguodong/.gemini/antigravity-cli/plugins/lucas-skills
test -d /Users/zhaoguodong/.gemini/config/skills
test -d /Users/zhaoguodong/.workbuddy/skills
git status --short --branch
```

Expected: Antigravity/WorkBuddy target 不再有 `enabled` 或 `legacy`；Antigravity Instructions 为 `missing`；插件目录不存在；两个产品根仍在；仓库仍干净。

- [ ] **Step 5: 仅在实现中止时恢复旧支持**

Trigger: Task 1 已完成，但隔离 worktree 无法建立、实现被明确放弃，或后续任务无法继续且用户要求恢复原状。正常实现路径跳过本步骤。

Run from the same canonical checkout after reviewing the fresh `create`/`no-op` previews:

```bash
uv run agent-manager skills set --all --tool antigravity --on --json
uv run agent-manager skills set --all --tool workbuddy --on --json
uv run agent-manager instructions set --target antigravity --on --json
uv run agent-manager skills set --all --tool antigravity --on --apply --json
uv run agent-manager skills set --all --tool workbuddy --on --apply --json

restore_instruction_preview=$(uv run agent-manager instructions set --target antigravity --on --json)
restore_instruction_fingerprint=$(
  printf '%s' "$restore_instruction_preview" |
  uv run python -c 'import json, sys; payload=json.load(sys.stdin); assert payload["ok"] is True; assert all(change["action"] in {"create", "no-op"} for change in payload["changes"]); print(payload["fingerprint"])'
)
uv run agent-manager instructions set --target antigravity --on --apply --expect-fingerprint "$restore_instruction_fingerprint" --json
uv run agent-manager status --json
```

Expected: 旧 Skills/Instructions 恢复为 Task 1 前状态，Antigravity CLI enable 自动重建 manager-owned manifest；报告已执行补偿。本 Task 不创建 Git 提交。

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
