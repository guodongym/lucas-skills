# Agent Manager 重构与全局个人约束管理设计

- 日期：2026-07-16
- 状态：已实现并通过分支验证
- 结论：把现有 `skill-manager` 直接重构为唯一入口 `agent-manager`，在保留 Skill 管理能力的同时，将仓库根 `AGENTS.md` 作为全局个人约束唯一来源，安全管理 Claude、Codex、GitHub Copilot CLI、Antigravity 和通用 Agent 入口；同步重做本地 Web UI，使其成为可快速判断连接健康度并安全执行变更的 Agent 路由控制台。

## 1. 背景与当前事实

当前仓库同时维护两类面向个人 AI 工具的资产：

1. `skills/` 下的 15 个 Skill，由 `skill-manager` 管理到五个本机加载根目录；
2. 根目录 `AGENTS.md`，保存多个 Agent 共用的个人工程约束。

Skill 管理已经完成真实迁移，当前五个适配器共 75 个目标全部直接链接到仓库，cc-switch 已退役。个人约束仍由手工软链维护，2026-07-16 的只读检查确认：

| 入口 | 当前状态 |
| --- | --- |
| `<repo>/AGENTS.md` | Git 受管的权威内容 |
| `~/.agents/AGENTS.md` | 直接链接到仓库 `AGENTS.md` |
| `~/.claude/CLAUDE.md` | 直接链接到仓库 `AGENTS.md` |
| `~/.codex/AGENTS.md` | 独立普通文件，内容落后于仓库两处规则 |
| `~/.copilot/copilot-instructions.md` | 不存在 |
| `~/.gemini/GEMINI.md` | 通过 `~/.agents/AGENTS.md` 两跳链接到仓库 |

同日逐行 diff 确认 `~/.codex/AGENTS.md` 没有仓库源缺失的独有规则：差异来自仓库版新增的量化写作约束和提交历史重写规则，以及对旧“技术导向”措辞的细化。该结论只代表当前快照；真实 replace 授权前仍必须重新 diff，防止其后新增内容被覆盖。

现有 Web UI 能完成管理，但摘要、安装状态、加载路径、操作和表格使用相近的卡片与灰色层级，信息主次不清，更接近工程调试页。新增第二类资源后继续堆叠会进一步降低可读性。

## 2. 目标

1. 用 `agent-manager` 作为本仓库唯一的本机 Agent 配置管理入口。
2. 让 Skills 与全局个人约束成为两个一等资源，共用扫描、计划、安全写入、快照和回滚能力。
3. 让 `<repo>/AGENTS.md` 成为五个文件入口的唯一权威来源，并把受管入口收敛为直接软链。
4. 保留现有四个工具族、Desktop/CLI 检测、Skill 库存和 75 个受管目标的行为。
5. 用新的“Agent 路由控制台”UI 快速表达仓库与各工具之间的真实连接、异常和可执行操作。
6. 所有真实 HOME 变更继续默认 dry-run，显式 `--apply` 后才执行，并支持完整恢复。

## 3. 非目标

- 不保留 `skill-manager` 命令、`tools.skill_manager` Python 包或旧 HTTP API 的兼容层。
- 不批量修改其他仓库的项目级 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 或 Copilot instructions。
- 不自动写入 GitHub Copilot Desktop 的内部数据库或 UI 设置。
- 不把 `upstream-sync` 并入 `agent-manager`。
- 不在本轮管理 MCP、Hooks、Custom Agents、Plugins 或 Prompt 内容。
- 不引入 React、Vue、CSS 框架、图标库、外部字体、CDN 或新的运行依赖。
- 不在实现、测试或合并阶段执行真实 HOME apply。

### 3.1 选型与取舍

本轮采用单一 `agent-manager`，而不是并列保留 `skill-manager` 再新增 `instructions-manager`。原因是两类资源共享仓库身份、工具表面、dry-run/apply、安全写入、HTTP 服务和 UI；两个常驻入口会重复这些边界并让用户在同一工具族上来回切换。代价是本次需要一次性迁移包名、CLI、测试和当前文档，但该工具只有当前仓库使用，用户已明确接受不兼容重构，因此不为旧入口增加长期维护成本。

Web UI 继续采用无构建步骤的原生 HTML/CSS/JS，而不引入前端框架。当前页面只有一个本地用户、四个页面和有限状态交互，框架不会降低运行风险，反而会增加依赖、构建和供应链维护面。UI 通过拆分 `index.html`、`app.css`、`app.js` 解决现有单文件可维护性问题。

## 4. 命名与 CLI 契约

`agent-manager` 是唯一推荐且唯一实际存在的管理入口：

```bash
uv run agent-manager status
uv run agent-manager doctor
uv run agent-manager serve --open

uv run agent-manager skills status
uv run agent-manager skills set docx --tool codex --on --json
uv run agent-manager skills set docx --tool codex --on --apply --json
uv run agent-manager skills adopt --json

uv run agent-manager instructions status
uv run agent-manager instructions set --target codex --on --json
uv run agent-manager instructions set --target codex --on --apply --expect-fingerprint <reviewed-sha256> --json
uv run agent-manager instructions adopt --json
uv run agent-manager instructions adopt --replace-existing --json
uv run agent-manager instructions adopt --apply --replace-existing --expect-fingerprint <reviewed-sha256> --json
```

规则如下：

- `agent-manager status` 汇总 Skills、Instructions、工具表面和异常数量。
- `agent-manager doctor` 对两类资源做完整诊断，并附加全局 Skill 只读库存。
- `skills` 下保留现有 `status`、`set`、`adopt` 语义；命令默认 dry-run。
- `instructions` 下提供 `status`、`set`、`adopt`；命令同样默认 dry-run。
- target key 固定为 `shared`、`claude`、`codex`、`copilot`、`antigravity` 或 `all`。
- `--replace-existing` 只对 Instructions adopt 中的冲突普通文件、外部链接或断链生效；不带 `--apply` 时生成完整 replace preview，带 `--apply` 时执行同一计划。目录永不自动接管。
- 所有 Instructions apply 必须携带 preview 返回的 64 位小写十六进制 `--expect-fingerprint`；服务端重扫生成的指纹不一致时返回 `state-changed`，零写入。Skill 命令保持现有 apply 契约。
- 删除旧 console script，不提供 alias、wrapper、shim 或弃用提示。
- `upstream-sync` 继续作为独立入口，职责与行为不变。

退出码延续现有约定：健康的只读命令、无冲突 preview 和成功 apply 返回 `0`；仓库扫描问题、`conflict`、`broken`、源文件无效、被阻塞的 preview、apply 或回滚失败返回 `1`；命令行参数错误由 `argparse` 返回 `2`。`missing` 和 `matching-copy` 是可行动状态，本身不使 `status` 失败；`doctor` 仍会在只读库存存在 broken/duplicate flags 时返回 `1`。

域级 `skills status --json` 和 `instructions status --json` 使用与聚合 status 相同的 `mode`、`ok`、`code`、`message`、`repo_root`、`scanned_at` 顶层信封，并分别原样返回聚合 payload 中的 `skills` 或 `instructions` 容器；不另造第二套字段名。

README、`pyproject.toml`、测试和当前活跃文档全部使用新命令。已完成的历史 spec/plan 保留原命令，作为当时执行事实，不进行追溯改写。

## 5. 组件和文件结构

```text
tools/
├── agent_manager/
│   ├── __init__.py
│   ├── cli.py
│   ├── server.py
│   ├── core.py
│   ├── skills.py
│   ├── instructions.py
│   └── web/
│       ├── index.html
│       ├── app.css
│       └── app.js
└── upstream_sync/
```

边界如下：

- `cli.py`：命令解析、文本摘要、JSON 输出和退出码；不实现文件系统业务逻辑。
- `server.py`：localhost HTTP 服务、静态资源读取、请求验证和鉴权；不复制计划逻辑。
- `core.py`：共享状态类型、计划指纹、快照、原子替换、FD/软链安全原语和回滚协调。
- `skills.py`：现有 Skill 适配器、扫描、库存、set/adopt 计划和应用。
- `instructions.py`：个人约束适配器、状态分类、set/adopt 计划和应用。
- `web/`：无构建步骤的 HTML/CSS/JS；业务真实状态全部来自服务端。

`pyproject.toml` 改为：

```toml
[project.scripts]
agent-manager = "tools.agent_manager.cli:main"
upstream-sync = "tools.upstream_sync.vendor:main"
```

发行包仍沿用仓库级项目名称 `lucas-skills-tools`，不因 CLI 改名引入包发布迁移。

## 6. 全局个人约束适配矩阵

唯一来源固定为 `<repo>/AGENTS.md`，五个自动管理目标均直接链接到该文件：

| target key | 受管路径 | 覆盖范围 |
| --- | --- | --- |
| `shared` | `~/.agents/AGENTS.md` | 采用通用 Agent 约定的工具 |
| `claude` | `~/.claude/CLAUDE.md` | Claude Code CLI 与 Desktop Code session |
| `codex` | `~/.codex/AGENTS.md` | Codex CLI 与 ChatGPT Desktop Codex mode |
| `copilot` | `~/.copilot/copilot-instructions.md` | GitHub Copilot CLI |
| `antigravity` | `~/.gemini/GEMINI.md` | Antigravity Desktop 与 `agy` CLI 的全局规则 |

GitHub Copilot Desktop 的全局规则由应用 Settings 管理。页面将它作为 `manual` 表面展示，提供“复制规则内容”和操作说明，但不把它伪装成文件系统受管目标。

依据：

- GitHub Copilot CLI 用户级 instructions：<https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference>
- GitHub Copilot Desktop 自定义入口：<https://docs.github.com/en/copilot/how-tos/github-copilot-app/customize-github-copilot-app>
- Antigravity CLI context 迁移规则：<https://antigravity.google/docs/gcli-migration>
- Antigravity CLI workspace rules：<https://antigravity.google/docs/cli-best-practices>

## 7. Instructions 状态模型

每个文件目标使用以下互斥状态：

| 状态 | 判定 |
| --- | --- |
| `enabled` | 目标是直接链接到当前仓库 `AGENTS.md` 的软链 |
| `missing` | 目标不存在 |
| `indirect-link` | 目标通过一个或多个软链最终解析到当前仓库源文件 |
| `matching-copy` | 目标是普通文件，字节内容与源文件完全一致 |
| `conflict` | 目标是不同内容的普通文件、目录或指向其他来源的有效软链 |
| `broken` | 目标是断链或解析链中断 |
| `manual` | 表面仅支持人工设置，不对应自动写入目标 |

仓库源文件固定为本次进程解析出的 `repo_root / "AGENTS.md"`。`repo_root` 必须是包含 `pyproject.toml`、`skills/` 和 `AGENTS.md` 的仓库根；源文件必须是不跟随软链打开后仍位于该根目录、可读且能严格解码为 UTF-8 的普通 Markdown 文件。源文件缺失、为软链、路径逃逸、编码无效或扫描失败时，全部 Instructions 写操作 fail closed。实现和测试可以从隔离 worktree 加临时 HOME 运行；只有合并后的 canonical `main` checkout 可以获准写真实 HOME。

## 8. Instructions 操作语义

### 8.1 set

- `--on`：目标为 `missing` 时创建直接软链；`enabled` 时 no-op；其他状态拒绝。
- `--off`：只删除当前管理器确认的直接仓库软链；其他类型拒绝删除。
- `--target all` 展开为五个文件目标，不包含 Copilot Desktop manual 表面。
- 所有计划记录扫描状态、源文件哈希、目标类型和原始软链值。

### 8.2 adopt

- `indirect-link`：可在普通 apply 中转换为直接软链。
- `matching-copy`：保存原文件后转换为直接软链。
- `missing`：仅当固定一级父目录已存在且为真实目录时创建直接软链；`enabled`：no-op。父目录缺失时 preview 返回 `blocked` / `parent-missing` 且无快照、无写入，用户须先人工执行对应的 `mkdir -m 700 ~/.agents`、`~/.claude`、`~/.codex`、`~/.copilot` 或 `~/.gemini`，再重新 preview 和 apply。
- 不同内容普通文件、外部有效软链或 `broken`：preview 完整展示，但普通 apply 拒绝。
- 只有显式 `--replace-existing` 才能把上述冲突规划为 `replace`。不带 `--apply` 时只返回原对象指纹、replace 动作和拟写入的快照路径，不创建快照或修改目标；加上 `--apply` 后复用同一计划语义，并必须先成功写入可恢复快照。
- 目录始终返回 `unsupported-target`，即使指定 `--replace-existing` 也不重命名或删除。
- 当前 `~/.codex/AGENTS.md` 将按 `conflict` 处理；当前 `~/.gemini/GEMINI.md` 将按 `indirect-link` 处理。

### 8.3 原子性与恢复

一次请求选中的 Instructions 目标视为一个原子批次：单目标 `set` 只包含该目标，`--target all` 和全量 `adopt` 包含五个文件目标。

1. apply 前全量重扫并比对计划指纹；
2. 快照普通文件的原始字节、permission mode、类型和 SHA-256，记录软链的 raw target；JSON 中的任意字节使用 Base64，禁止按文本解码后再保存；
3. 通过同目录临时名和原子 rename/replace 完成目标替换；
4. 任一项失败时按逆序恢复全部已变更目标；
5. 恢复路径被竞争者占用时不覆盖竞争者，保留隔离文件并返回可行动路径；
6. 回滚或快照失败必须体现在顶层错误码和逐项结果中。
7. 计划阶段对每个目标记录一级父目录的 kind、device 和 inode。父目录缺失返回 `blocked` / `parent-missing`；父目录为普通文件、软链或 special file 返回 `blocked` / `parent-not-directory`。apply 不创建或删除一级父目录，只从已打开的 HOME fd 以 `O_DIRECTORY | O_NOFOLLOW` 打开计划中已审查的目录，并在打开前、打开后及提交屏障复核完全相同的 device/inode；身份变化返回 `state-changed`，不得写入 leaf。macOS/Python 不提供绑定已打开目录 FD/inode 的安全创建发布原语，因此不通过 `ctypes` 或新依赖绕过该边界。

计划指纹由 repo/source identity、源 SHA-256、replace flag、选中 target、动作、目标完整快照以及父目录 kind/device/inode 规范化计算；快照文件名固定为 `instructions-<fingerprint>.json`。因此同一文件系统状态下，replace preview 与 apply 返回相同 changes、指纹和快照路径。apply 若发现该路径已存在，不覆盖已有 prepared/committed 记录，而是返回 `incomplete-transaction` 或 `snapshot-conflict` 供用户先审查。

原子批次保证覆盖进程内可捕获失败，不宣称跨五个目录具备断电级文件系统事务。快照先以 `prepared` 状态持久化，每个目标只通过同目录原子 rename/replace 从旧状态切到新状态；批次全部验证后再原子标记 `committed`。进程被强杀或断电时，目标可能停在部分已应用状态，但每个目标必须是完整旧对象或完整新链接，原始文件字节仍在 `prepared` 快照或隔离备份中。后续 `status`/`doctor` 只读报告 `incomplete-transaction` 和恢复路径，不自动修改 HOME，也拒绝覆盖同指纹记录；用户必须先审查快照、按记录人工恢复或确认现状，再将已处置记录移出活动 snapshots 目录，之后才能重新 apply。

新状态目录固定为：

```text
~/.local/state/lucas-agent-manager/snapshots/
```

现有 `~/.local/state/lucas-skills-manager/` 快照不由运行时兼容读取。真实迁移阶段经单独确认后，将旧目录原样移动到 `~/.local/state/lucas-agent-manager/legacy-skill-manager/`：目标必须预先不存在，移动前后核对相对路径、文件数和 SHA-256，全部一致后才删除旧路径；新运行时不会把该归档目录当作新格式快照读取。

## 9. HTTP API 与安全边界

API 统一按资源命名：

```text
GET  /api/status
GET  /api/inventory
POST /api/skills/set
POST /api/skills/adopt
POST /api/instructions/set
POST /api/instructions/adopt
POST /api/shutdown
```

`GET /api/status` 返回：

```json
{
  "repo_root": "/absolute/repo",
  "skills": {},
  "instructions": {},
  "surfaces": [],
  "summary": {},
  "scanned_at": "2026-07-16T00:00:00Z"
}
```

`skills`、`instructions`、`surfaces` 和 `summary` 都是完整对象，不由浏览器补全。Skill target 至少包含 `slug`、`adapter_key`、`tool`、`state`、`path`、`raw_target`、`resolved_target`、`message`；`instructions` 对象包含只读 `source`、`source_sha256`、`source_text`、五个 `targets` 和 manual surfaces，供页面展示与复制当前规则；每个 Instruction target 至少包含 `key`、`state`、`path`、`source`、`raw_target`、`resolved_target`、`source_sha256`、`target_sha256`、`message`；summary 至少包含两类资源的 enabled/total、冲突数和异常数。源无效时 `source_text` 为 `null`，并通过 issues 和失败状态表达，浏览器不得自行读取本机文件。

Instructions set/adopt 的 preview 与 apply response 在公共信封之外固定包含顶层 `changes`、`fingerprint` 和 `snapshot_path`；preview 后两者用于人工审查和 apply 的 `expected_fingerprint`，apply response 保留原计划三字段并另附逐项 `results`。无写入计划时 `snapshot_path` 为 `null`。

写请求只接受以下精确 JSON 对象：

```json
POST /api/skills/set          {"skill":"docx","all":false,"tool":"codex","on":true,"apply":false}
POST /api/skills/set          {"skill":null,"all":true,"tool":"all","on":true,"apply":false}
POST /api/skills/adopt        {"apply":false}
POST /api/instructions/set    {"target":"codex","on":true,"apply":false,"expected_fingerprint":null}
POST /api/instructions/adopt  {"apply":false,"replace_existing":false,"expected_fingerprint":null}
POST /api/instructions/adopt  {"apply":false,"replace_existing":true,"expected_fingerprint":null}
POST /api/instructions/adopt  {"apply":true,"replace_existing":true,"expected_fingerprint":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
POST /api/shutdown            {}
```

`skills/set` 始终使用同一组五个字段：单项时 `skill` 为 slug 且 `all:false`，全量时 `skill:null` 且 `all:true`。`replace_existing` 仅允许出现在 Instructions adopt，`apply:false|true` 均合法；相同状态下两者的 changes、计划指纹和由指纹派生的快照目标必须一致，区别只在是否落盘执行。Instructions preview 的 `expected_fingerprint` 必须为 `null`；apply 必须回传 preview response 中的 64 位小写十六进制 fingerprint，服务端重扫并常量时间比较后才允许写入。未知字段、缺失字段、错误类型和多余字段均返回 `400 invalid-request`。preview 即使包含被阻塞项也返回 `200` 并用顶层 `ok:false`、稳定 `code` 和逐项 changes 表达；apply 的冲突返回 `409`，权限失败返回 `403`，内部或回滚失败返回 `500`。CLI 与 HTTP 共享业务错误码和逐项结果结构。

`index.html` 包含唯一占位符 `__AGENT_MANAGER_TOKEN__`。服务端只在返回该文件时将占位符替换为 HTML-attribute escaped token；`app.js` 从 `<meta name="agent-manager-token">` 读取后立即移除该 DOM 节点，并只通过 `X-Agent-Manager-Token` 发送写请求。`app.css` 和 `app.js` 按原始字节返回，不注入内容。页面不使用内联 script/style，因此 CSP 收紧为 `script-src 'self'; style-src 'self'`，不保留 `unsafe-inline`。

安全边界不得弱化：

- 仅绑定 `127.0.0.1` 随机端口；
- 使用新命名的临时 token 和 `X-Agent-Manager-Token`；
- 严格验证 Host、Origin、Content-Type、body size、method 和 path；
- 使用常量时间 token 比较；
- 静态文件只允许 `index.html`、`app.css`、`app.js` 三个精确路径；
- 每个目录组件使用 `O_DIRECTORY | O_NOFOLLOW`，叶文件必须是普通文件；
- 不实现通用静态目录服务器、路径拼接 fallback 或目录索引。

## 10. Web UI：Agent 路由控制台

### 10.1 页面职责

页面的唯一任务是：让用户快速判断仓库配置是否正确连接到各 Agent，并安全执行必要变更。它不是通用监控台，也不展示与操作无关的装饰性数据。

### 10.2 信息架构

桌面端采用左侧导航和右侧内容区：

- 总览
- Skills
- 个人约束
- 全局库存

顶栏只保留仓库身份、重新扫描和关闭服务。批量操作随当前页面和选择上下文出现，不常驻堆叠。

### 10.3 总览

- 首屏摘要展示 Skills enabled/total、Instructions enabled/total、冲突和异常。
- 中央拓扑以 `lucas-skills` 仓库为源节点，连接 Claude、Codex、Copilot、Antigravity。
- Skills 与 Instructions 使用不同线型；正常、缺失、冲突同时用线型、图标和文字表达，不仅依赖颜色。
- “需要处理”区域只展示异常及可行动入口；健康时明确显示无异常。
- 加载路径、完整 raw target 和哈希收进可展开区域或详情抽屉。

### 10.4 Skills

- 保留工具矩阵，使用 sticky 表头和 sticky Skill 名称。
- 单元格只显示状态图标和短标签；完整原因、路径和原始目标在右侧详情抽屉展示。
- 搜索、状态筛选和批量选择位于内容区顶部。
- 只有存在选择时才显示启用、停用、接管批量操作。

### 10.5 个人约束

- 五个文件入口按工具展示目标路径、Desktop/CLI 覆盖、状态和当前来源。
- 点击行打开详情抽屉，展示完整软链链路、源/目标哈希和计划入口。
- Copilot Desktop 显示 `manual`，提供复制仓库规则内容和清晰的 Settings 操作步骤。
- 冲突替换先在抽屉中展示 preview，最终 apply 使用明确的危险操作确认框。

### 10.6 视觉系统

视觉主题为“Agent 路由控制台”，连接拓扑是唯一高识别度元素，其余界面保持安静：

| token | 值 | 用途 |
| --- | --- | --- |
| Canvas | `#F4F6F8` | 页面背景 |
| Ink | `#171A1F` | 主文本 |
| Muted | `#69717D` | 次级信息 |
| Route | `#2563EB` | 当前选中和连接 |
| Healthy | `#16825D` | 正常状态 |
| Attention | `#B86B12` | 待处理状态 |

- 标题使用本机 Avenir Next，正文使用系统 UI 字体，路径使用 SF Mono fallback。
- 不使用大面积渐变、毛玻璃、泛滥阴影或每块内容一个卡片的布局。
- 主要依靠空间、分组、细线、字号和字重建立层级。
- 内联 SVG 图标由语义组件生成；装饰图形设置 `aria-hidden`。

### 10.7 反馈、响应式与可访问性

- 普通成功使用短暂通知；错误固定显示在对应行或“需要处理”区域，并给出下一步。
- 批量 preview 使用侧边抽屉；只有危险 apply 使用 modal。
- 展示最近扫描时间，不做自动轮询。
- apply 后全量重扫，并提示新会话或重启后生效。
- 小屏幕把侧栏变为顶部导航，拓扑改为纵向路由；矩阵提供明确的横向滚动提示。
- 全部操作可通过键盘完成，焦点清晰，状态不只依赖颜色。
- 唯一常规动画是约 180ms 的连接状态过渡；`prefers-reduced-motion` 下禁用。

## 11. 真实数据流

```text
扫描仓库和 HOME
→ 构建 Skills 与 Instructions 统一状态
→ 生成 preview 和计划指纹
→ 用户确认 apply
→ apply 回传已审 fingerprint，服务端重扫并核对
→ 写快照
→ 原子变更
→ 失败则逆序回滚
→ 全量重扫
→ CLI/UI 展示最终真实状态
```

浏览器不缓存或推断受管状态。刷新、操作成功和部分失败后都以服务端重扫结果为准。

## 12. 迁移策略

代码迁移不保留旧入口：

1. 将 `tools/skill_manager/` 重构为 `tools/agent_manager/`；
2. 拆分 CLI、HTTP、Skills、Instructions 和静态资源；
3. 将 console script 改为 `agent-manager`；
4. 更新当前 README、测试、package data 和活跃文档；
5. 扫描非历史文档，确保没有旧包和旧命令残留；
6. 保持 `upstream-sync` 行为不变。

实现与合并期间只使用临时 HOME。合并后在 canonical checkout 执行只读验收：

```bash
uv run agent-manager status --json
uv run agent-manager doctor --json
uv run agent-manager instructions adopt --json
uv run agent-manager instructions adopt --replace-existing --json
```

先审查 replace preview 中的动作、原对象指纹、计划 fingerprint 和拟写入快照路径；再对每个冲突普通文件与仓库源执行独立只读 diff，确认没有需要回收的独有规则。真实 apply 必须再次取得用户确认：

```bash
uv run agent-manager instructions adopt --apply --replace-existing --expect-fingerprint <reviewed-sha256> --json
```

apply 后新建四个工具的会话验证规则加载。Copilot Desktop 单独按页面说明手动同步。

## 13. 测试与验收

### 13.1 自动化测试

1. 迁移现有 106 项测试，保持原 Skill 行为、安全边界和回滚断言。
2. 验证 `tools.skill_manager` 和 `skill-manager` 均不存在。
3. 验证 `agent-manager` console script、help、JSON 和退出码。
4. 覆盖五种 Instructions 文件状态、两跳解析、断链和源文件 fail-closed。
5. 覆盖 set/adopt dry-run、显式 apply、冲突拒绝和 `--replace-existing`。
6. 覆盖普通文件字节/mode 恢复、快照失败、竞争者占位、权限失败和多目标原子回滚。
7. 覆盖新 HTTP 路由、请求 schema、token、Host、Origin、body size 和 method/path 拒绝。
8. 对三个静态文件逐组件复现 leaf 与中间目录软链攻击，确认外部内容零泄漏。
9. 用 Node 执行真实 `app.js` 中可分离的纯函数，覆盖拓扑数据、筛选、路径缩写、复制降级和计划摘要。
10. 验证 wheel 恰好包含 `index.html`、`app.css`、`app.js` 以及 upstream-sync 数据文件。

### 13.2 人工浏览器验收

- `1440×900` 桌面布局；
- `390×844` 小屏布局；
- 总览健康、缺失、冲突、加载、空状态和错误状态；
- 键盘导航、可见焦点和 screen-reader label；
- `prefers-reduced-motion`；
- preview、侧边抽屉、危险确认、复制和新会话提示；
- 页面不产生 console error，不请求外部资源。

### 13.3 工程验收

```bash
git diff --check
uv lock --check
uv run python -m unittest discover -s tests -p 'test_*.py'
uv run python -m py_compile tools/agent_manager/*.py tools/upstream_sync/vendor.py
uv build
uv run agent-manager --help
uv run upstream-sync --help
```

## 14. 完成标准

满足以下全部条件才算完成：

1. 代码、README 和当前命令中只存在 `agent-manager`，无运行时兼容层。
2. 现有 75 个 Skill 目标在临时 HOME 与真实只读验收中保持正常。
3. 五个 Instructions 目标能够准确分类并生成可审计计划。
4. 冲突文件只有在显式 replace apply 下才会被接管，且可完整恢复。
5. Web UI 能在总览中快速表达仓库到四个工具族的真实连接状态。
6. Skills、个人约束和全局库存各自有明确页面和上下文操作。
7. 自动化测试、构建、静态资源安全测试和人工视觉验收全部通过。
8. 真实 HOME 在独立确认前零写入；确认后五个文件入口均为仓库直链。
9. Copilot Desktop 明确保留人工同步边界，不误报为自动受管。
