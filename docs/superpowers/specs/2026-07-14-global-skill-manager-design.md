# 全局 Skill 管理器设计

- 日期：2026-07-14
- 状态：已完成首轮 spec/plan 审查并按 findings 修订，待复审
- 结论：在当前仓库内新增一个按需启动的 Skill 管理器，以 Python 核心统一驱动 CLI 与本地网页；`skills/` 是唯一受管 Skill 来源，文件系统软链是唯一真实状态；首版覆盖 Claude Code、Codex、GitHub Copilot、Antigravity 四个工具族的桌面端与 CLI，并提供逐 Skill/逐工具开关、cc-switch 旧结构接管、修复能力和只读全局 Skill 概览。

## 1. 背景与当前事实

当前仓库通过 `vendor.py` 管理上游 Skill 内容，通过 cc-switch 把仓库 Skill 暴露给各 Agent。2026-07-14 的本机只读检查确认：

- 仓库 `skills/` 下有 14 个顶层 Skill；
- `~/.cc-switch/skills` 是指向本仓库 `skills/` 的目录级软链；
- `~/.claude/skills/<name>`、`~/.codex/skills/<name>` 和原 `~/.gemini/skills/<name>` 的受管项多数先指向 `~/.cc-switch/skills/<name>`，再解析到当前仓库；
- `~/.copilot/skills` 已是直接指向本仓库 `skills/` 的整目录软链；
- 原 `/Applications/Codex.app` 已更新为 `/Applications/ChatGPT.app`；当前本机版本 26.707.71524，bundle id 仍为 `com.openai.codex`，应用内包含 Codex mode，Codex CLI 命令仍为 `codex`；
- GitHub Copilot Desktop 为 `/Applications/GitHub Copilot.app`，本机版本 1.0.18；Copilot CLI 命令为 `copilot`；
- Antigravity Desktop 为 `/Applications/Antigravity.app`，本机版本 2.2.1；Antigravity CLI 命令为 `agy`，本机版本 1.0.4；
- 用户使用官方订阅，不再使用 cc-switch 的 Provider、代理、MCP、Prompt、会话等其他功能。完成迁移后，cc-switch 可退出使用。

当前两级软链没有提供不可替代的转换能力。目标结构可直接收敛为：

```text
当前仓库 skills/<name>
        ↓
各工具官方的用户级 Skill 目录
```

## 2. 假设与决策

- 首要运行环境是当前 macOS 主机。
- 四个工具均要求个人全局 Skill，作用于所有项目。
- Desktop 与 CLI 都纳入检测与验收；二者共用官方 Skill 目录时只维护一份链接。
- 每个 Skill 可分别选择启用到哪些工具族，并提供批量全选/同步。
- 管理页面只在需要调整 Skill 时启动，不作为长期后台服务。
- 第一版只管理当前仓库已有 Skill，不负责从 GitHub/ZIP 安装、在线发现、编辑或更新 Skill。
- 第一版对其他来源 Skill 只读展示，不删除、不移动、不接管。
- 上游内容同步继续由 `vendor.py` 负责；本工具不复制该职责。

## 3. 目标与非目标

### 3.1 目标

1. 让当前仓库成为受管 Skill 的唯一来源。
2. 取消 Agent 加载链路对 `~/.cc-switch/skills` 的依赖。
3. 同时支持 Claude Code、Codex、GitHub Copilot、Antigravity 的 Desktop 与 CLI。
4. 支持逐 Skill、逐工具族启停，并准确展示 Desktop/CLI 子状态。
5. 提供幂等的旧结构接管与链接修复能力，而不是一次性迁移脚本。
6. 提供本机全部已发现 Skill 的只读概览，区分当前仓库、外部链接、本地副本、内置/插件、损坏和重名。
7. 所有变更可预览、可验证，不覆盖未管理内容。

### 3.2 非目标

- 不提供 Provider/API 切换、代理、MCP、Prompt、会话或费用管理。
- 不实现 cc-switch 的通用替代品。
- 不删除或自动卸载 cc-switch。
- 不修改、下载、更新或发布 Skill 内容。
- 不删除或接管其他来源 Skill。
- 不提供远程访问、多用户权限或常驻守护进程。
- 不为首版引入 Tauri、Electron、Node 构建链或数据库。
- 不保证仅存在于组织/云端且不投影到本机的远程 Skill 能被枚举。

## 4. 方案选择

### 4.1 选定方案：Python 核心 + 本地网页

- Python 负责扫描、分类、计划、变更、回滚和验证。
- CLI 与本地 HTTP 服务调用同一套核心逻辑。
- 网页由标准库 HTTP 服务提供，无前端构建步骤。
- 文件系统是唯一真实状态；页面每次操作后重新扫描。
- 使用本机 `uv` 提供 Python 3.11+ 和 PyYAML：统一命令形态为 `uv run --python '>=3.11' --with pyyaml python3 ...`，不向全局 Python 安装包，也不新增项目构建链。

### 4.2 未选方案

| 方案 | 不采用原因 |
| --- | --- |
| 纯 CLI + 只读 HTML | 无法提供用户确认需要的点击管理体验 |
| 独立桌面应用 | 引入新的打包、升级和依赖维护链，对当前规模过重 |
| 复制 Skill 到各工具目录 | 产生内容漂移、重复占用和更新不一致 |
| 单个整目录软链 | 无法支持逐 Skill、逐工具开关 |

## 5. 文件结构与组件边界

```text
lucas-skills/
├── skills/                         # 唯一受管 Skill 来源
├── skill_manager.py                # CLI 与本地服务入口
├── skill_manager_core.py           # 扫描、状态、计划、软链与回滚
├── skill_manager_web/
│   └── index.html                  # 单文件 HTML/CSS/JS 管理页面
└── tests/
    └── test_skill_manager.py       # 临时 HOME 下的自动化测试
```

边界如下：

- `skill_manager_core.py` 不依赖 HTTP 或浏览器，所有路径通过参数或适配器提供，可在临时 HOME 测试。
- `skill_manager.py` 只解析命令、启动服务、把请求映射到核心操作。
- `index.html` 不保存业务状态，只展示服务端扫描结果并提交显式操作。
- 目标适配器首版直接定义在核心模块中，不增加可配置插件体系。

## 6. 工具适配矩阵

| 工具族 | 用户级受管目标 | Desktop/CLI 关系 | 检测方式 |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/<skill>` | CLI 与 Claude Desktop 的 Code session 共用 | Desktop 检查 `Claude.app`，CLI 检查 `claude`；普通 Chat 的云端上传 Skill 不作为本地文件系统表面 |
| Codex | `~/.codex/skills/<skill>` | CLI 与 ChatGPT Desktop 的 Codex mode 共用 | Desktop 优先检查 `ChatGPT.app`，兼容过渡期 `Codex.app`；CLI 检查 `codex` |
| GitHub Copilot | `~/.copilot/skills/<skill>` | 作为个人全局 Skill；两端分别验收 | Desktop 检查 `com.github.githubapp`，CLI 检查 `copilot` |
| Antigravity Desktop | `~/.gemini/config/skills/<skill>` | Desktop 独立目标 | 检查 `com.google.antigravity` |
| Antigravity CLI | `~/.gemini/antigravity-cli/plugins/lucas-skills/skills/<skill>` | CLI 独立插件目标 | 检查 `agy` |

GitHub Copilot 的 `~/.copilot/skills` 是官方个人全局目录。管理器不修改 Copilot Desktop 的内置目录：

```text
~/Library/Application Support/com.github.githubapp/app-skills
```

Antigravity Desktop 使用官方全局目录 `~/.gemini/config/skills/`。Antigravity CLI 采用插件而不是扁平 Markdown 目录，以完整保留 Skill 中的脚本、模板和 references：

```text
~/.gemini/antigravity-cli/plugins/lucas-skills/
├── plugin.json
└── skills/
    ├── docx -> <repo>/skills/docx
    ├── pdf  -> <repo>/skills/pdf
    └── ...
```

`plugin.json` 是管理器拥有的固定清单，名称为 `lucas-skills`。若同名位置已存在且不是管理器创建的兼容结构，状态为冲突，拒绝覆盖。

参考资料：

- OpenAI 新 ChatGPT Desktop 与 Codex 迁移：<https://help.openai.com/en/articles/20001276-moving-to-the-new-chatgpt-desktop-app>
- GitHub Copilot personal Agent Skills：<https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills>
- GitHub Copilot CLI Skill locations：<https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#skills-reference>
- Antigravity Desktop global Skills：<https://www.antigravity.google/docs/skills?app=antigravity-ide>
- Antigravity Desktop plugins：<https://www.antigravity.google/docs/plugins>
- Antigravity CLI plugins and Skills：<https://antigravity.google/docs/cli-plugins>

## 7. 状态模型

每个仓库 Skill × 受管目标的状态只能是以下之一：

| 状态 | 定义 | 是否自动处理 |
| --- | --- | --- |
| `enabled` | 直接链接到当前仓库对应 Skill | 无需变更 |
| `disabled` | 目标不存在 | 可启用 |
| `legacy` | 经 cc-switch 或旧适配路径最终解析到当前仓库 | 可在确认后接管 |
| `conflict` | 普通文件、真实目录或指向其他来源的软链 | 不处理 |
| `unavailable` | 对应 Desktop/CLI 未安装或无法识别 | 不创建目录 |
| `error` | 损坏链接、非法 Skill 或验证失败 | 不处理，报告原因 |

工具族主状态由子目标聚合：

- 所有可用子目标启用：`enabled`；
- 所有可用子目标停用：`disabled`；
- Desktop/CLI 不一致：`mixed`；
- 任一子目标冲突或错误：主状态展示告警，并保留各子状态。

`unavailable` 是正常跳过状态：不创建目录、不计入批次失败，也不导致 CLI 非零退出。只有 `conflict`、`error`、执行漂移、权限或验证失败才使批次失败。

路径比较使用规范化后的绝对路径。目录名是部署与链接标识；只有最终解析到 `<repo>/skills/<directory-slug>` 的链接才视为当前仓库受管或可接管链接。

## 8. 仓库 Skill 扫描

只扫描 `skills/` 的一级子目录。一个目录成为受管 Skill 必须满足：

1. 存在常规文件 `SKILL.md`；
2. YAML frontmatter 可解析；
3. `name` 非空并符合 Skill 命名约束；
4. 目录名本身符合可安全用作软链名称的 slug 约束；
5. 顶层受管 Skill 之间不存在重复目录名或重复 frontmatter `name`。

目录名是管理器的稳定部署标识，frontmatter `name` 用于触发语义、展示和重名检测。两者不一致时显示 `name-mismatch` 告警，但不阻止管理；这是为了兼容当前 `skills/wps365/` 目录与 `name: wps365-skills` 的既有结构。

不递归把 `skills/wps365/skills/*` 等子 Skill 当成独立顶层受管项；它们属于父 Skill 的资源。

扫描提取 `name`、`description` 和源路径供 UI 使用。正文不默认渲染。

## 9. 全局 Skill 概览

概览扫描四个工具官方或已注册的本地加载位置，并按实际加载关系归属到 Desktop/CLI。对 Codex 等存在插件缓存的工具，只把系统目录和已启用插件来源标为“已加载”；不把未启用的原始缓存误报为运行时 Skill。

来源分类：

| 分类 | 定义 |
| --- | --- |
| `managed` | 来自当前仓库 |
| `external-link` | 软链到当前仓库之外 |
| `local-copy` | 加载目录中的真实 Skill 目录 |
| `built-in` | 工具内置、系统或已启用插件提供 |
| `broken` | 损坏链接、缺少 `SKILL.md` 或元数据无效 |
| `duplicate-name` | 同一加载目标中不同来源具有相同 frontmatter `name` |

每项至少展示：

- Skill 名称与描述；
- 来源分类；
- 实际路径与软链目标；
- 被哪些工具族和 Desktop/CLI 加载；
- `SKILL.md` 验证结果；
- 是否与当前仓库或同一工具中的其他 Skill 重名。

`~/.agents/skills` 等共享目录只扫描一次，再按官方支持关系映射到消费者。仅存在于组织或云端、未投影到本机的 Skill 不属于文件系统完整性承诺；只有目标 CLI 提供稳定、只读、可机器解析的清单时才附加展示，并明确标为“运行时报告”。

第一版概览严格只读，不提供删除、移动、禁用或接管外部 Skill 的操作。

## 10. 操作语义与安全边界

### 10.1 启用

- 目标不存在：创建指向当前仓库对应 Skill 的软链。
- 已正确链接：返回 `no-op`。
- 目标为 `legacy`：普通启用不静默接管；由接管操作替换。
- 目标为其他文件、目录或链接：返回 `target-conflict`。

### 10.2 停用

只允许删除：

- 直接指向当前仓库对应 Skill 的软链；
- 经已识别旧结构最终解析到当前仓库对应 Skill 的软链。

不删除普通文件、真实目录、工具内置 Skill、其他来源软链或名称相同但路径不匹配的内容。

### 10.3 批量操作

- 单项开关本身就是明确授权，执行后立即回读验证。
- “全部启用”“全部停用”和接管必须先展示变更数、跳过项和冲突，再二次确认。
- 安全项可继续执行；失败与冲突逐项报告。
- 任一批次存在冲突、错误或写入/验证失败时，CLI 返回非零退出码，页面显示部分成功；`unavailable` 只计入跳过项。

### 10.4 竞争与回滚

- 执行前重新读取目标状态；若与计划时不同，停止该项，返回 `state-changed`。
- 新链接先在同一父目录创建临时软链，再用原子替换落位。
- 整目录形态转换先构造同级临时目录，验证后替换；失败时恢复原链接。
- 操作后必须重新解析链接并验证最终目标。
- 页面或进程中断后，下一次扫描从文件系统恢复真实状态。

## 11. 接管与修复

不创建独立的一次性迁移脚本。旧结构处理作为管理器的通用 `adopt`/`doctor` 能力保留：

- 首次使用：接管 cc-switch 旧链接、Copilot 整目录链接和 Antigravity 旧 `custom-skills` 转接结构；
- 后续使用：检测链接漂移、损坏链接、新电脑初始化和重新 clone 后的缺失状态；
- 无遗留项时：只报告无需接管，不产生变更。

Antigravity 旧 `custom-skills` 插件只在其 `skills` 入口最终包含的每个非隐藏项都解析到当前仓库、且不存在外部或本地副本时才可自动接管。接管时只移除这个旧 `skills` 入口并切换到官方全局目录；`plugin.json` 和其他未知文件保持不动。只要容器中混有一个非本仓库项，整个旧入口标记为冲突，必须人工处理。

接管流程：

1. 验证仓库 Skill；
2. 检测工具与目标路径；
3. 生成替换、保留、跳过和冲突清单；
4. 在 `~/.local/state/lucas-skills-manager/snapshots/` 保存只含路径与原链接目标的时间戳 JSON 快照；
5. 用户确认后逐项接管；
6. 重新扫描并验证；
7. 输出结果与快照位置。

快照不是业务状态或数据库，只用于人工审计和故障恢复。管理器不删除 `~/.cc-switch`，不卸载 cc-switch；所有受管链接验证为直连仓库后，用户可自行卸载。

## 12. CLI 契约

```text
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py status [--json]
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py doctor [--json]
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py set <skill> --tool <tool> --on|--off [--apply]
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py set --all --tool <tool|all> --on|--off [--apply]
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py adopt [--apply]
uv run --python '>=3.11' --with pyyaml python3 skill_manager.py serve [--open]
```

- `status`：扫描仓库 Skill、工具状态和受管链接。
- `doctor`：额外扫描全局 Skill、重复名称、损坏项和旧结构，只读。
- `set`：未提供 `--apply` 时只输出计划；提供后执行。
- `adopt`：未提供 `--apply` 时只输出迁移计划；提供后执行并保存快照。
- `serve --open`：绑定本机随机端口并打开浏览器。

工具枚举固定为 `claude`、`codex`、`copilot`、`antigravity`。CLI 与页面使用相同状态和错误码。

## 13. 本地服务与安全

- 仅绑定 `127.0.0.1`，端口使用操作系统分配的可用端口。
- 启动时生成高熵临时令牌；所有写请求必须提供令牌。
- 写接口同时校验 HTTP 方法与同源请求。
- 服务停止后令牌失效。
- 不配置开机启动，不创建 LaunchAgent，不监听局域网。
- 页面提供“关闭服务”，终端可使用 `Ctrl+C`。
- 服务关闭不影响 Skill；工具直接读取持久化软链。
- 日志只输出当前终端的操作摘要，不记录 Skill 正文或敏感配置。
- 页面展示的文件内容全部做 HTML 转义。

最小 API：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/status` | 仓库 Skill 与工具状态 |
| `GET` | `/api/inventory` | 全局只读概览 |
| `POST` | `/api/set` | 单项或批量启停 |
| `POST` | `/api/adopt` | 预览或执行旧结构接管 |
| `POST` | `/api/shutdown` | 关闭当前服务 |

## 14. 页面设计

页面面向桌面浏览器，采用单页、双视图结构。

### 14.1 顶部与统计

展示仓库路径、扫描时间、“重新扫描”“迁移旧链接”“关闭服务”，以及：

- 仓库 Skill 总数；
- 四个工具族启用数；
- Desktop/CLI 可用状态；
- 冲突数与异常数。

### 14.2 仓库 Skills 视图

行是仓库 Skill，列是 Claude Code、Codex、GitHub Copilot、Antigravity。

- `●`：全部启用；
- `○`：全部停用；
- `◐`：Desktop/CLI 混合状态；
- `!`：冲突或错误；
- `D/C`：Desktop/CLI 子状态。

支持逐项开关、单行全部启用、批量选择、全部启用/停用、名称搜索和状态筛选。详情区展示描述、源路径、各目标路径、链接解析结果和验证结果。

### 14.3 全局概览视图

展示名称、来源、加载工具、实际路径、软链目标、验证状态和重名情况。支持按当前仓库、外部软链、本地副本、内置/插件、损坏、重名筛选。所有外部项只读。

### 14.4 反馈

- 单项操作后原地重新扫描；
- 批量操作先显示计划与数量；
- 冲突显示路径和拒绝修改原因；
- 工具需重启或新建会话时显示提示；
- 服务端结果始终覆盖页面临时状态。

## 15. 错误模型

核心和 HTTP 层使用一致的结构化错误：

```json
{
  "ok": false,
  "code": "target-conflict",
  "path": "/Users/example/.codex/skills/example",
  "message": "目标是普通目录，未执行覆盖"
}
```

至少覆盖：

- `invalid-skill`
- `unavailable`
- `target-conflict`
- `broken-link`
- `permission-denied`
- `state-changed`
- `verification-failed`
- `invalid-token`
- `partial-failure`
- `requires-adopt`
- `adoption-failed`
- `bridge-removal-failed`
- `internal-error`

目标目录无写权限时只报告具体路径和处理建议，不在工具内自动提权。

## 16. 测试设计

自动化测试使用标准库 `unittest`、临时仓库和临时 HOME，不触碰真实用户目录；测试和编译统一通过 `uv run --python '>=3.11' --with pyyaml python3 ...` 执行。

覆盖：

1. 合法与非法 Skill 扫描；
2. 直接链接、旧链接、外部链接、真实目录和损坏链接分类；
3. 启用、停用与重复执行的幂等性；
4. 冲突拒绝和失败回滚；
5. Copilot 整目录链接接管；
6. Antigravity CLI 插件清单与逐 Skill 链接；
7. 全局概览与 frontmatter 名称重复检测；
8. 路径穿越和非仓库目标保护；
9. 执行前状态变化检测；
10. HTTP 写接口令牌与同源验证；
11. 批量操作部分失败；
12. 服务重启后从文件系统恢复相同状态。

不把 Playwright、浏览器驱动或目标 Agent CLI 设为单元测试依赖。页面走人工浏览器验证，真实工具加载走本机集成验证。

## 17. 本机验收

真实迁移前先运行只读计划；用户确认后才写入用户目录。

验收条件：

1. 仓库所有有效顶层 Skill 全部被识别（设计时基线为 14 个）；
2. 四个工具族及本机已安装的 Desktop/CLI 全部被检测；
3. 所有启用项最终解析到当前仓库 `skills/<name>`；
4. 受管加载链路中对 `~/.cc-switch/skills` 的依赖数为 `0`；
5. 未管理文件、目录和外部链接的变更数为 `0`；
6. 服务关闭并重新启动后状态一致；
7. Claude Desktop Code session、ChatGPT Desktop Codex mode、Copilot Desktop、Antigravity Desktop，以及四个 CLI 的每个已安装表面至少验证一个启用 Skill 可见；普通 Claude Chat 的云端 Skill 列表不属于本地软链验收；
8. 停用一个测试项后，新会话中不可见；重新启用后恢复；
9. 页面单项、批量、冲突、接管和全局概览行为符合设计；
10. 自动化测试全部通过，真实接管无未解释失败。

工具是否立即重新加载 Skill 由各自运行时决定。管理器完成软链验证后提示新建会话或重启目标工具，不自动操作进程。

## 18. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 新版 Desktop 与 CLI 的 Skill 发现规则变化 | 适配器隔离路径规则；文件系统验证与实际表面验收分开 |
| 名称相同但来源不同 | 以 frontmatter `name` 检测重复，概览明确展示路径和加载目标 |
| 误删用户自有 Skill | 只删除最终解析到当前仓库同名 Skill 的软链 |
| 批量操作部分成功 | 逐项计划、逐项验证；仅冲突、错误或写入/验证失败导致非零退出，`unavailable` 正常跳过 |
| 页面与文件系统状态漂移 | 不缓存业务状态，每次操作后重新扫描 |
| 本地网页被其他页面调用 | localhost、随机端口、临时令牌、同源校验 |
| 一次性迁移逻辑变成死代码 | 收敛为通用 `adopt`/`doctor`，持续用于初始化与修复 |
| 原始插件缓存被误报为已加载 | 只按官方目录和启用元数据归属；原始缓存不等同于活跃 Skill |

## 19. 实施边界

本设计批准后，下一阶段只编写实现计划，不直接实现。实现阶段按 TDD 推进：先用临时 HOME 写失败用例，再实现扫描与软链核心，最后接 CLI、HTTP 和页面。真实用户目录迁移属于单独验收步骤，必须先展示只读计划并取得确认。
