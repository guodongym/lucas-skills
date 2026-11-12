# lucas-skills

私有 skill 仓库，部分内容来源于公开仓库。通过 `upstream-sync` 追踪上游 Git 仓库或官方发布 ZIP 的变更并按需同步，通过 GitHub Actions 实现每周自动检测。

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

Agent Manager 以本仓库 `skills/` 和 `AGENTS.md` 为唯一受管源，统一管理 Claude、Codex、GitHub Copilot 三个工具族、六个检测表面。前置条件是本机已安装 `uv`：

```bash
uv --version
```

管理器通过仓库级 `pyproject.toml` 和 `uv.lock` 使用隔离环境，无需单独安装 PyYAML。运行时分别位于 `tools/agent_manager/` 和 `tools/upstream_sync/`。

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

Desktop 和 CLI 分别检测，共三个工具族、六个检测表面。Skills 共使用三个 Skill 根目录：

| 工具 | Desktop 检测 | CLI 检测 | Skill 加载位置 |
| --- | --- | --- | --- |
| Claude | `Claude.app` 或 `Claude Code.app` | `claude` | `~/.claude/skills/<skill>` |
| Codex | 优先 `ChatGPT.app`，兼容 `Codex.app` fallback | `codex` | `~/.codex/skills/<skill>` |
| GitHub Copilot | `GitHub Copilot.app` | `copilot` | `~/.copilot/skills/<skill>` |

`doctor` 还会只读扫描 `~/.agents/skills`、Codex 内置及已启用插件目录，以及 Copilot Desktop 内置目录；这些库存来源不因此变为受管目标。

Instructions 共使用四个 Instructions 文件入口，全部以仓库 `AGENTS.md` 为来源：

| target | Instructions 目标路径 | 覆盖范围 |
| --- | --- | --- |
| `shared` | `~/.agents/AGENTS.md` | 通用 Agent 约束 |
| `claude` | `~/.claude/CLAUDE.md` | Claude CLI 与 Desktop Code session |
| `codex` | `~/.codex/AGENTS.md` | Codex CLI 与 ChatGPT Desktop Codex mode |
| `copilot` | `~/.copilot/copilot-instructions.md` | GitHub Copilot CLI |

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

Skills `adopt` 识别 cc-switch 单项链接和 Copilot 整目录链接；Instructions `adopt` 识别间接链接、同内容副本、缺失目标和冲突目标。两者都必须先 preview，并且不会卸载 cc-switch 或删除 `~/.cc-switch`。

```bash
uv run agent-manager skills adopt --json
uv run agent-manager instructions adopt --json
```

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

## WPS 365 官方套件

[WPS 365](skills/wps365/README.md) 将官方 CLI 安装包和 15 个 Skill 集中存放在 `skills/wps365/`，通过单一入口激活到 Codex。来源和逐文件校验值见该目录的 `upstream.json`。

WPS 使用 `type: release-zip` 来源，按官方版本索引定位发布包；配置、版本锁和校验记录与 Git 来源一同进入现有自动检查。详见 [发布 ZIP 来源](docs/upstream-sync.md#发布-zip-来源)。

## Ezone 随包 CLI

[Ezone Skill](skills/ezone/SKILL.md) 提供仓库、PR、意见与原生通知、CI／门禁、合并、代码标签说明和 raw 制品资源命令。复制整个 `skills/ezone/`（含 `scripts/`、`references/`、`agents/`），无需安装 lucas-skills 包或全局 CLI；Python 3.11+ 标准库即可启动，本地开发及推送另需 Git。

项目根目录 `.ezone.json` 保存实例地址、显式 repoKey 和企业；每个人通过 `auth login` 隐藏输入自己的令牌，保存到项目外 `~/.config/ezone/credentials.json`，按 HTTPS 平台地址隔离。CI 可用机密变量 `EZONE_TOKEN` 覆盖，并须同时设置可信 `EZONE_HOST` 或显式 `--host` 绑定发送目标；上下文也保留 `EZONE_HOST`、`EZONE_REPO`、`EZONE_COMPANY` 和全局参数。需可信 HTTPS 网络及相应业务权限；不自动获取令牌、改保护规则或调整权限。参数、退出码及网络边界见 [命令与环境](skills/ezone/references/commands.md)，真实写入和回读步骤见 [PR 与发布](skills/ezone/references/pr-release.md)。GitHub 评审路径继续使用原有 connector／gh，Ezone 后端由此 Skill 提供。

```sh
python3 /absolute/path/to/ezone/scripts/ezone.py --version
python3 /absolute/path/to/ezone/scripts/ezone.py --help
python3 /absolute/path/to/ezone/scripts/ezone.py --json doctor
python3 /absolute/path/to/ezone/scripts/ezone.py --json pr view 2
```

源码来源是本仓库 `skills/ezone/scripts/`，随包版本为 `0.2.0`，复制后仍可用 `--version` 回读，不依赖 `.git`。Agent Manager 沿用现有扫描能力，先在包含新 Skill 的任务工作区预览：

```sh
uv run agent-manager skills set ezone --tool codex --on --json
```

核对 source 是否指向当前任务 worktree；canonical checkout 尚无该 Skill 时不能宣称已安装。以上只做 preview，不用 `--apply`，不修改真实 HOME。正式消费宜在集成后的固定主工作区按已有授权核对具体计划，再新建会话确认发现来源。

项目内消费可将完整 Skill 安装到 `<project>/.agents/skills/ezone/` 并随项目代码提交，已有同名目录先核对来源。[Codex 官方说明](https://learn.chatgpt.com/docs/build-skills)将此列为仓库级技能路径。项目自行维护多个 Skill 的选择、来源版本清单与同步规则；本公开仓库不管理消费项目的安装与升级。首次配置、登录退出和 CI 接入见[命令与环境](skills/ezone/references/commands.md#首次使用)，验收范围见[验收记录](docs/ezone-validation.md)。

| 边界 | 内容 |
| --- | --- |
| 本期实现 | repo／branch／commit 读取与显式分支创建、PR 到代码标签／raw 制品命令；独立审查与发布工作流的平台适配 |
| 后续 | 文件树／内容／搜索／blame／归档、项目／卡片与卡片关联、产品版本、更多包协议、交付关联及部署恢复 |
| 不纳入 | 仓库删除及管理侧修改、成员／权限／保护规则管理、镜像／GC、外部消息渠道、全局短命令安装 |

普通合并评审（MR）用 `pr create`；直接提交评审（DCR）沿用向保护分支 Git push 的原生路径，不假设有普通源分支。读取／意见／合并只有在评审对象和明确提交可核实时复用，本期未真实验收 DCR。

实现、离线检查和真实验收分开报告，详见 [验收记录](docs/ezone-validation.md)。完整历史能力调查见 [能力盘点](docs/ezone-capability-inventory.md)，其中拟议接口不替代当前 CLI 帮助。
