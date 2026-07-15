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
│   ├── skill_manager/    # 全局 Skill 管理器
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

## 全局 Skill 管理器

全局 Skill 管理器以本仓库 `skills/` 为受管源，为四种 AI 工具创建逐项软链，并汇总本机已有的 Skill 库存。前置条件是本机已安装 `uv`，可用以下命令确认：

```bash
uv --version
```

管理器通过仓库级 `pyproject.toml` 和 `uv.lock` 使用隔离环境，无需单独安装 PyYAML。

### 状态、诊断与库存

快速查看受管状态和全局概览：

```bash
uv run skill-manager status
uv run skill-manager doctor
```

不带 `--json` 时，文本输出仅提供摘要，包括仓库 Skill 数量、各工具启用数量、冲突数和下一步命令，不展开逐项记录。`status` 的完整 `surfaces` 和 `targets`、`doctor` 的完整 `inventory`，以及写操作计划/结果的完整 `changes` 和 `results` 都必须使用 `--json` 查看。inventory 是只读视图，不会修改或接管仓库之外的 Skill。

无论供脚本读取还是人工验收，查看完整字段时都使用：

```bash
uv run skill-manager status --json
uv run skill-manager doctor --json
```

### Desktop 与 CLI 支持矩阵

Desktop 和 CLI 是否可用会分别检测；同一行共用目标目录的工具只需管理一次软链。

| 工具 | Desktop 检测 | CLI 检测 | 受管路径 |
| --- | --- | --- | --- |
| Claude | `Claude.app` 或 `Claude Code.app` | `claude` | `~/.claude/skills/<skill>` |
| Codex | 优先 `ChatGPT.app`，兼容 `Codex.app` fallback | `codex` | `~/.codex/skills/<skill>` |
| GitHub Copilot | `GitHub Copilot.app` | `copilot` | `~/.copilot/skills/<skill>` |
| Antigravity | `Antigravity.app` | `agy` | Desktop：`~/.gemini/config/skills/<skill>`；CLI：`~/.gemini/antigravity-cli/plugins/lucas-skills/skills/<skill>` |

Antigravity CLI 的受管插件清单位于 `~/.gemini/antigravity-cli/plugins/lucas-skills/plugin.json`。`doctor` 还会只读扫描 `~/.agents/skills`、Codex 内置及已启用插件目录、Antigravity CLI 用户目录和 Copilot Desktop 内置目录；这些库存来源不因此变为受管目标。

### 预览与执行

管理命令默认是 dry-run。人工执行 apply 前必须使用 `--json` 审查完整 `changes`；例如，预览为 Codex 启用一个 Skill：

```bash
uv run skill-manager set docx --tool codex --on --json
```

确认计划中的目标、动作、冲突和跳过项符合预期后，才在同一命令中增加 `--apply`；保留 `--json` 以检查完整 `results`：

```bash
uv run skill-manager set docx --tool codex --on --apply --json
```

也可以使用 `--all` 批量操作仓库 Skill，或用 `--off` 停用。管理器采用 fail-closed 策略：只要仓库扫描发现任一扫描问题，就拒绝全部 `set` 和 `adopt`（包括 preview），并在错误中列出问题代码和路径；先修复或移出无效候选后再重新预览。执行阶段还会重新校验计划和文件系统状态；目标已被普通文件、目录或其他来源软链占用时会报告冲突，不覆盖现有内容。管理器只写入上述受管目标及必要的 Antigravity CLI 插件清单，不改写外部 Skill 内容。

按需打开管理页面：

```bash
uv run skill-manager serve --open
```

页面中的“Skill 加载位置”会汇总仓库来源和五个受管根目录，并可复制完整绝对路径。服务只绑定本机回环地址，写操作需要当前服务生成的临时令牌。服务不需要后台常驻。关闭页面中的服务或在终端按 `Ctrl+C` 后，已创建的软链继续生效。启停 Skill 后，已运行的 Agent 可能仍使用启动时的缓存；请新建会话，必要时重启对应 Desktop 或 CLI。

### 从 cc-switch 等旧链接迁移

`adopt` 用于把已识别的 cc-switch 单项链接、Copilot 整目录链接和 Antigravity 旧入口转换为本仓库的逐项直连。人工审查必须使用 JSON preview：

```bash
uv run skill-manager adopt --json
```

只有检查完整 `changes` 并取得明确确认后，才增加 `--apply`：

```bash
uv run skill-manager adopt --apply --json
```

真实环境的 `adopt --apply` 不属于常规安装或文档验收：必须先把 `adopt --json` 摘要交给用户，并另行取得明确确认。迁移会在 `~/.local/state/lucas-skills-manager/snapshots/` 保存原软链元数据；管理器不会卸载 cc-switch，也不会删除 `~/.cc-switch`。

迁移完成并逐一验证四种 Desktop 与四个 CLI 的已安装表面后，管理器可以统一提供状态矩阵、逐项启停、冲突保护和全局 inventory，cc-switch 不再承担这些 Skill 软链的运行时依赖。只有确认受管链路不再依赖 `~/.cc-switch/skills`，且新会话中的停用与恢复都正常，才建议用户自行退出或卸载 cc-switch。

迁移逻辑仍会保留：它用于识别尚未迁移的旧机器、后续恢复的备份或重新出现的旧链接，并在改写前持续提供可审计的预览与冲突检查；这不表示迁移需要重复执行。

### 集成后验收门

feature worktree 与真实软链指向的 canonical checkout 路径不同，因此不能在 worktree 内完成真实环境验收。代码合并或切回 canonical checkout 后，必须先执行以下 post-integration acceptance gate；本次 feature 实现不声称这些步骤已经完成：

```bash
uv run skill-manager status --json
uv run skill-manager doctor --json
uv run skill-manager adopt --json
uv run skill-manager serve --open
```

验收时核对完整 `surfaces`、`targets`、`inventory` 和 adoption `changes`，并确认只读命令前后软链目标不变。页面只完成 preview / cancel / port shutdown：预览迁移后取消，关闭服务并确认端口已停止，不能点击或调用真实 apply。

post-integration acceptance gate 仍不得执行 `adopt --apply`。真实迁移必须另开确认步骤，把 canonical checkout 上的 `adopt --json` 摘要交给用户并取得明确授权。

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
