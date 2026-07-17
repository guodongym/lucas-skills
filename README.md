# lucas-skills

私有 skill 仓库，部分内容来源于公开仓库。通过 `upstream-sync` 追踪上游变更并按需同步，通过 GitHub Actions 实现每周自动检测。

## 目录结构

```
lucas-skills/
├── .github/
│   └── workflows/
│       └── sync-upstream.yml  # 自动检测 & 开 PR 的 Actions workflow
├── docs/                 # 设计与实施文档
├── skills/               # 本地 skill 文件
├── tests/                # 自动化测试
├── tools/
│   ├── agent_manager/    # Agent 配置 CLI、领域逻辑与 Web 控制台
│   │   └── web/          # index.html、app.css、app.js
│   └── upstream_sync/    # 上游同步工具及配置
├── pyproject.toml        # Python 项目与两个 CLI 入口
└── uv.lock               # 锁定依赖版本
```

## 方案设计

### 核心思路

- `tools/upstream_sync/upstream.yml` 声明每个上游仓库的地址和需要同步的路径映射
- `tools/upstream_sync/upstream.lock.yml` 记录每个上游上次同步时的 commit hash，作为"基准线"
- `uv run upstream-sync check` 用 `git ls-remote` 快速对比远端最新 commit 与 lock 文件，**无需 clone**，秒级完成
- `uv run upstream-sync sync` 执行 sparse clone/fetch（只拉取映射的路径），将变更覆写到本地，更新 lock 文件
- 删除策略：上游删除的文件**不会自动删除**本地文件，只打印 `[WARN]` 提示，由你手动决定

方案选型对比详见 [docs/upstream-sync.md](docs/upstream-sync.md)。

## 快速开始

### 安装依赖

```bash
uv sync
```

### 检测上游是否有更新（只读，无需 clone）

```bash
uv run upstream-sync check
```

输出示例：

```
[UPDATE] anthropics-skills: 有更新  abc12345 -> def67890
[OK]     my-other-upstream: 已是最新 (ff001122)
```

### 查看具体变更内容

```bash
uv run upstream-sync diff
```

输出示例：

```
=== anthropics-skills ===
  skills/skill-creator -> skills/skill-creator:
    + new-file.md
    ~ SKILL.md
    - old-file.md  [上游已删除，本地保留]
```

### 执行同步

```bash
# 同步所有上游
uv run upstream-sync sync

# 只同步指定上游
uv run upstream-sync sync --upstream anthropics-skills
```

## Agent Manager

Agent Manager 以本仓库 `skills/` 和 `AGENTS.md` 为唯一受管源，统一管理 Skills 与个人约束。它覆盖 Claude、Codex、GitHub Copilot、Antigravity 四个工具族、八个检测表面；前置条件是本机已安装 `uv`：

```bash
uv --version
```

管理器通过仓库级 `pyproject.toml` 和 `uv.lock` 使用隔离环境，无需单独安装 PyYAML。
运行时分别位于 `tools/agent_manager/` 和 `tools/upstream_sync/`。

### 命令层级、状态与诊断

聚合状态和诊断位于顶层，两个资源域分别位于 `skills` 与 `instructions`：

```bash
uv run agent-manager status --json
uv run agent-manager doctor --json

uv run agent-manager skills status --json
uv run agent-manager skills set docx --tool codex --on --json
uv run agent-manager skills adopt --json

uv run agent-manager instructions status --json
uv run agent-manager instructions set --target codex --on --json
uv run agent-manager instructions adopt --json
```

不带 `--json` 时，文本输出仅提供摘要。查看完整字段时使用 `--json`：`status` 返回完整 `surfaces`、Skills 和 Instructions targets，`doctor` 返回完整 `inventory`，写操作返回 `changes`、fingerprint 和 `results`。inventory 是只读视图，不会修改或接管仓库之外的 Skill。

Skills 常见状态为 `enabled`、`disabled`、`conflict` 和 `broken`。Instructions 使用 `enabled`、`missing`、`indirect-link`、`matching-copy`、`conflict`、`broken` 和 `manual`；其中 missing 和 matching-copy 是可处理状态，conflict、broken 或源文件异常会阻止写入。

### 工具表面与受管路径

Desktop 和 CLI 分别检测，共四个工具族、八个检测表面。Skills 共使用五个 Skill 根目录：

| 工具 | Desktop 检测 | CLI 检测 | Skill 加载位置 |
| --- | --- | --- | --- |
| Claude | `Claude.app` 或 `Claude Code.app` | `claude` | `~/.claude/skills/<skill>` |
| Codex | 优先 `ChatGPT.app`，兼容 `Codex.app` fallback | `codex` | `~/.codex/skills/<skill>` |
| GitHub Copilot | `GitHub Copilot.app` | `copilot` | `~/.copilot/skills/<skill>` |
| Antigravity | `Antigravity.app` | `agy` | Desktop：`~/.gemini/config/skills/<skill>`；CLI：`~/.gemini/antigravity-cli/plugins/lucas-skills/skills/<skill>` |

Antigravity CLI 的受管插件清单位于 `~/.gemini/antigravity-cli/plugins/lucas-skills/plugin.json`。`doctor` 还会只读扫描 `~/.agents/skills`、Codex 内置及已启用插件目录、Antigravity CLI 用户目录和 Copilot Desktop 内置目录；这些库存来源不因此变为受管目标。

Instructions 共使用五个 Instructions 文件入口，全部以仓库 `AGENTS.md` 为来源：

| target | Instructions 目标路径 | 覆盖范围 |
| --- | --- | --- |
| `shared` | `~/.agents/AGENTS.md` | 通用 Agent 约束 |
| `claude` | `~/.claude/CLAUDE.md` | Claude CLI 与 Desktop Code session |
| `codex` | `~/.codex/AGENTS.md` | Codex CLI 与 ChatGPT Desktop Codex mode |
| `copilot` | `~/.copilot/copilot-instructions.md` | GitHub Copilot CLI |
| `antigravity` | `~/.gemini/GEMINI.md` | Antigravity Desktop 与 CLI |

Copilot Desktop 的全局 instructions 由应用 Settings 管理，是手工边界；管理器只显示 manual 状态、复制规则内容和操作说明，不写应用内部数据。

### Preview、apply 与安全门

所有写命令默认 preview。Skills 启用预览示例：

```bash
uv run agent-manager skills set docx --tool codex --on --json
```

Skill 接管同样先看完整计划：

```bash
uv run agent-manager skills adopt --json
```

Instructions 替换现有文件时，必须先审查 replace preview：

```bash
uv run agent-manager instructions adopt --replace-existing --json
```

确认 `changes` 后，把该 preview 返回的 64 位 fingerprint 原样绑定到 apply：

```bash
uv run agent-manager instructions adopt --apply --replace-existing --expect-fingerprint <reviewed-sha256> --json
```

真实 HOME apply 不属于文档或分支验收。无论 Skills 还是 Instructions，都必须把 preview 摘要交给用户并单独取得明确授权；授权一个 preview 不自动授权另一类写入。管理器采用 fail-closed 策略：只要仓库扫描发现任一扫描问题，就拒绝全部 `set` 和 `adopt`（包括 preview），并在错误中列出问题代码和路径。Instructions apply 还会复核 source、目标、父目录身份和 fingerprint，失败时按批次回滚；目录不会被自动接管。

旧状态归档也需要独立授权。只有在真实迁移验收完成后，才可另行审查把 `~/.local/state/lucas-skills-manager/` 原样归档到 `~/.local/state/lucas-agent-manager/legacy-skill-manager/`；Agent Manager 不会自动移动或删除旧状态。

### Web 控制台与生命周期

按需启动本机控制台：

```bash
uv run agent-manager serve --open
```

`serve --open` 只在需要查看或操作时启动，不是后台服务。页面同时显示 Skills 的“Skill 加载位置”和 Instructions 目标路径，可复制完整绝对路径；服务只绑定 `127.0.0.1` 随机端口，写操作需要当前进程生成的临时 token。点击页面“关闭服务”或在终端按 `Ctrl+C` 即停止，服务不需要后台常驻，已创建的软链不受影响。写入后请新建会话，必要时重启对应 Desktop 或 CLI，使其重新加载配置。

### 从旧链接迁移

Skills `adopt` 识别 cc-switch 单项链接、Copilot 整目录链接和 Antigravity 旧入口；Instructions `adopt` 识别间接链接、同内容副本、缺失目标和冲突目标。两者都必须先 preview，并且不会卸载 cc-switch 或删除 `~/.cc-switch`。

```bash
uv run agent-manager skills adopt --json
uv run agent-manager instructions adopt --json
```

### 集成后验收门

feature worktree 与真实软链指向的 canonical checkout 路径不同，不能在 worktree 内完成真实环境验收。合并或切回 canonical checkout 后，先运行只读命令和页面 preview：

```bash
uv run agent-manager status --json
uv run agent-manager doctor --json
uv run agent-manager skills adopt --json
uv run agent-manager instructions adopt --json
uv run agent-manager instructions adopt --replace-existing --json
uv run agent-manager serve --open
```

验收时核对完整 `surfaces`、targets、`inventory` 和 adoption `changes`，并确认只读命令前后目标不变。页面只完成 preview / cancel / port shutdown：预览后取消，关闭服务并确认端口停止，不执行真实 apply。真实迁移和旧状态归档分别进入前述独立授权门。

## 添加新的上游来源

编辑 `tools/upstream_sync/upstream.yml`，在 `upstreams` 列表中追加一项：

```yaml
upstreams:
  - name: my-upstream          # 自定义名称，唯一标识
    repo: https://github.com/user/repo
    branch: main
    mappings:
      - src: path/in/upstream  # 上游仓库中的目录路径
        dst: skills/local-name # 本地目标路径
      - src: another/path
        dst: skills/another
```

然后执行 `uv run upstream-sync sync` 完成首次同步。

## GitHub Actions 自动化

`.github/workflows/sync-upstream.yml` 会在每周一 09:00 UTC 自动运行：

1. 执行 `uv run upstream-sync check` 检测是否有上游更新
2. 如有更新，自动运行 `uv run upstream-sync sync`
3. 将变更提交到新分支 `upstream-sync/YYYY-MM-DD`
4. 自动开 PR，PR body 中包含同步详情和所有 `[WARN]` 提示

也可以在 Actions 页面手动触发（`workflow_dispatch`）。

> **注意**：首次使用需在仓库 Settings → Actions → General → Workflow permissions 中开启 "Read and write permissions"，Actions 才能创建分支和 PR。

## 文件说明

| 文件 | 说明 |
|------|------|
| `tools/upstream_sync/upstream.yml` | 上游配置，手动维护 |
| `tools/upstream_sync/upstream.lock.yml` | 同步状态，自动生成，**建议提交到 git** |
| `tools/upstream_sync/vendor.py` | 上游同步实现，依赖 `pyyaml` + `git` |
| `pyproject.toml` | Python 项目配置与 CLI 入口 |
| `uv.lock` | 锁定 Python 依赖版本 |
| `~/.cache/upstream-sync/` | clone 缓存目录，可安全删除，下次 sync 自动重建 |
