# 旧工具支持清理与 Cursor/Grok 兼容复用实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 安全清理本仓库创建的 Antigravity/WorkBuddy 外部链接，并把 Agent Manager 的直接管理范围原子收敛为 Claude、Codex、GitHub Copilot；Cursor/Grok 仅复用工具自身的 Claude 兼容能力。

**Architecture:** 真实 HOME 的一次性清理已在旧 adapter 删除前从 canonical checkout 完成；Task 1 只保留审计证据，不保留可重放脚本。随后在隔离 worktree 中一次性修改 Python、Web、README 与全部活动测试，避免后端已拒绝旧工具而 Web 仍展示旧入口的中间提交。不新增 Cursor/Grok adapter、写入路径、状态或兼容配置管理。

**Tech Stack:** Python 3.11+、`unittest`、标准库文件系统 API、vanilla HTML/CSS/JavaScript、`uv`、Git。

## Global Constraints

- 批准的设计为 `docs/superpowers/specs/2026-08-17-cursor-grok-tool-replacement-design.md`。
- 真实 HOME 清理已在旧 adapter 仍存在时从 canonical checkout 完成；不得从当前或未来 HEAD 重跑。代码修改在 `feature/agent-manager-tool-cleanup` 隔离 worktree 中执行。
- Skill 工具枚举最终精确为 `claude`、`codex`、`copilot`；surface 精确为六个。
- Instructions 自动目标最终精确为 `shared`、`claude`、`codex`、`copilot`；手工表面只保留 `copilot-desktop`。
- 不创建或管理 `~/.cursor/skills`、`~/.grok/skills`、`~/.grok/AGENTS.md`，不增加 Cursor/Grok CLI/HTTP 参数、Web 列或库存标签。
- 不管理 Cursor/Grok 的 MCP、插件、Hooks、Agents、认证、模型或兼容开关。
- 不保留 `antigravity`、`workbuddy` 的参数别名、隐藏 adapter、旧桥接字段或死代码。
- 已完成的真实 HOME 清理只删除了直接指向本仓库的软链，以及 ownership、内容和结构校验通过的 Antigravity `lucas-skills` 插件容器；产品根和外部内容已保留。
- 不引入新依赖；保留当前受管工具的 preview、apply、冲突检测、快照、回滚、竞态保护和恢复语义。
- Python、Web、README 和活动测试作为一个 breaking contract 原子提交；该提交包含动机、`验证：`、`BREAKING CHANGE` 和 `Co-authored-by: OpenAI Codex <noreply@openai.com>`。
- feature worktree 不用于验证指向 canonical checkout 的真实受管软链；合并后的真实新运行时 `status/doctor` 需要另行取得合并授权后从 canonical checkout 验收。

---

### Task 1: 已完成的一次性旧工具清理（不可重放）

**状态：** COMPLETED。该迁移已在旧 adapter 删除前从 canonical checkout 执行成功。本节只保留审计证据，不再提供可执行命令。

> **禁止重跑：** 不得从当前或未来 HEAD 重跑 Task 1。当前实现已删除 Antigravity/WorkBuddy adapter，旧命令和旧 ownership 识别能力不再构成有效迁移工具。

#### 已观察的执行证据

执行时仓库共有 18 个 Skill，preview 与 apply 结果如下：

| domain | preview 总数 | `remove` | `no-op` | 结果 |
| --- | ---: | ---: | ---: | --- |
| Antigravity Skills（2 个 adapter） | 36 | 32 | 4 | apply 成功；读回无已启用或 legacy 目标 |
| WorkBuddy Skills（1 个 adapter） | 18 | 16 | 2 | apply 成功；读回无已启用或 legacy 目标 |
| Antigravity Instructions | 1 | 1 | 0 | fingerprint apply 成功；读回为 missing |

同时观察到：

- manager-owned Antigravity `lucas-skills` 插件容器在 ownership、manifest 内容和“仅含 manifest 与空 `skills/`”结构检查通过后删除；
- `/Users/zhaoguodong/.gemini/config/skills` 与 `/Users/zhaoguodong/.workbuddy/skills` 产品根保留；
- `/Users/zhaoguodong/.cursor/skills`、`/Users/zhaoguodong/.grok/skills`、`/Users/zhaoguodong/.grok/AGENTS.md` 在清理前后均保持 absent；
- canonical checkout 的 Git 状态在执行后保持 clean。

#### 回滚记录与后续门禁

Step 5 rollback 未触发。旧 adapter 随 Task 2 删除后，原回滚路径已失效，本仓库不保留可重放的 HOME 清理或恢复算法。

若未来需要恢复或修复外部状态，必须作为新的 reviewed migration 处理：以本节记录的精确 removed set（Antigravity 32、WorkBuddy 16、Instructions 1）和当时的实际文件状态重新设计、review、preview 与授权。不得通过批量启用推断或补建原 `no-op`/missing 目标。

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
