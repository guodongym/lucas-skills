# 旧工具清理与 Cursor/Grok 兼容复用设计

## 1. 结论

Agent Manager 删除 Antigravity Desktop/CLI 与 WorkBuddy Desktop 的直接管理，不新增 Cursor Desktop/CLI 或 Grok Build CLI 的写入 adapter。Cursor 可兼容发现或导入 Claude 配置，Grok 默认兼容扫描 Claude 配置；用户不需要工具级独立启停，因此继续把同一批 Skill 链接到 `~/.cursor/skills`、`~/.grok/skills` 只会制造重复来源和维护成本。

Agent Manager 的直接管理边界收敛为 Claude、Codex、GitHub Copilot。Cursor/Grok 只在 README 中作为现有 Claude 配置的兼容消费者说明，不进入工具枚举、状态矩阵、HTTP 参数、Web 列、库存工具标签或 Instructions 目标。MCP、插件、Hooks、Agents、兼容开关继续由各工具自身管理。

旧 adapter 删除前的一次性真实 HOME 清理已经完成：只移除了可证明属于本仓库的 Antigravity、WorkBuddy Skill 链接、Antigravity Instructions 链接，以及 ownership、manifest 内容和目录结构均通过检查的专用插件容器；产品根与外部内容保持不变。该迁移只作为已完成证据保留，不能从当前或未来 HEAD 重放。

## 2. 已验证事实

### 2.1 当前实现

当前 Agent Manager 有六个 Skill adapter：Claude、Codex、Copilot 各一个，Antigravity 两个，WorkBuddy 一个；检测九个 surface。Instructions 有 `shared`、`claude`、`codex`、`copilot`、`antigravity` 五个自动文件目标和一个 Copilot Desktop 手工表面。

Antigravity 还带有插件 manifest、插件库存扫描和旧目录桥接；WorkBuddy 有独立 Skill 根与 Web 手工 Instructions 特例。删除两者必须覆盖 CLI、HTTP、Web、README、库存与测试，不能只改枚举。

### 2.2 Cursor 兼容行为

- Cursor 从 `~/.cursor/skills/` 与 `~/.agents/skills/` 加载用户级 Skill，并可通过兼容发现或第三方导入读取 Claude、Codex Skill 目录；该能力由 Cursor 自身设置控制。
- Cursor 的第三方配置导入可带入 Claude 的 Skills、Rules、Plugins 与 MCP，但 Desktop 与 CLI 的插件/兼容发现存在版本和功能差异，不能从一端成功推断另一端成功。
- Cursor CLI 读取项目级 `.cursor/rules/`、`AGENTS.md` 和 `CLAUDE.md`；这不等于它会继承 Desktop User Rules 或全部已导入插件能力。
- Cursor User Rules 由 Cursor 设置保存，不是 Agent Manager 可安全链接的独立文件。
- Cursor 对跨目录同名 Skill 和全局软链发现的行为有版本差异，不能把重复写入当成稳定去重方案。

因此本期不向 Cursor 原生目录写入，也不声称能独立启停或读取 Cursor 的兼容开关；Desktop 与 CLI 的 Claude Skill 可见性必须分别验收。

官方依据：

- <https://cursor.com/cn/docs/skills>
- <https://cursor.com/cn/docs/rules>
- <https://cursor.com/cn/docs/cli/using>
- <https://docs.cursor.com/context/model-context-protocol>

### 2.3 Grok Build 兼容行为

- Grok 默认扫描 `~/.claude/skills/`、`~/.cursor/skills/` 与 `~/.agents/skills/`，vendor 兼容开关可以关闭。
- 同名原生 Skill 按优先级处理；与内置命令或插件冲突时可保留限定名称，因此库存中仍可能出现重名定义。
- Grok 默认兼容读取 Claude/Cursor 的规则与 MCP。MCP 同名时按来源优先级覆盖；不同名称指向同一服务时仍可能形成两份服务。
- 当前真实 `grok inspect` 已发现本机 Claude 用户 Skills；`~/.claude/CLAUDE.md` 与项目 `AGENTS.md` 指向同一真实文件时只报告一个 Instructions 来源。

因此本期不创建 `~/.grok/skills` 或 `~/.grok/AGENTS.md` 链接，也不管理 Grok 的 MCP 或兼容配置。

官方依据：

- <https://docs.x.ai/build/overview>
- <https://docs.x.ai/build/features/skills-plugins-marketplaces>
- <https://docs.x.ai/build/cli/reference>
- Grok CLI 随附文档：`~/.grok/docs/user-guide/07-mcp-servers.md`、`08-skills.md`、`12-project-rules.md`

## 3. 目标与非目标

### 3.1 目标

1. Skill 工具枚举收敛为 `claude`、`codex`、`copilot`。
2. 删除 Antigravity、WorkBuddy 的 adapter、surface、Instructions、库存、专用桥接、UI、文档与活动测试合同。
3. 固化删除旧实现前已完成的真实 HOME 一次性清理证据，并禁止从删除 adapter 后的 HEAD 重放旧迁移。
4. README 说明 Cursor/Grok 可复用 Claude Skills，其他配置遵循各工具自身的兼容或导入设置；Cursor Desktop/CLI 的实际可见性分别验证，但二者都不属于 Agent Manager 的直接管理目标。
5. 保持当前受管工具的 preview、fingerprint、apply、冲突检测、快照与回滚语义。

### 3.2 非目标

- 不新增 Cursor/Grok adapter、surface、CLI/HTTP 工具参数或 Web 工具列。
- 不创建或管理 `~/.cursor/skills`、`~/.grok/skills`、`~/.grok/AGENTS.md`。
- 不自动写 Cursor User Rules、应用数据库、设置文件或云端状态。
- 不管理 Cursor/Grok 的 MCP、插件、Hooks、Agents、认证、模型或兼容开关。
- 不把 Cursor/Grok 的兼容发现包装成独立启停状态，也不读取其配置来推断实时有效性。
- 不迁移或删除 Antigravity、WorkBuddy 的普通文件、普通目录、外部链接或产品自有资产。
- 不保留 Antigravity、WorkBuddy 的 CLI 参数兼容别名或隐藏 adapter。
- 不引入新依赖。

## 4. 方案选择

### 4.1 采用：删除旧支持，复用现有 Claude 配置

Cursor/Grok 继续通过各自的兼容发现或导入能力复用 Agent Manager 已管理的 Claude Skills；规则、MCP 等其他配置遵循工具自身设置。Manager 不复制同一来源，不增加状态类型，也不承担第三方兼容配置的生命周期。

这是当前需求的最小闭环：用户只需要这些工具能使用同一批能力，不需要“Claude 开、Cursor 关、Grok 开”一类独立控制。

### 4.2 不采用：为 Cursor/Grok 建立原生写入 adapter

原生 adapter 能提供独立启停，但会与默认 Claude 兼容扫描形成重复来源。Cursor 缺少稳定的跨目录去重保证；Grok 即使能处理同名定义，也会增加限定名称、库存噪声和验收复杂度。用户已确认不需要该能力。

### 4.3 不采用：统一管理 MCP 或 vendor 兼容开关

MCP 包含认证、进程启动、OAuth 和工具级开关，风险与 Skill 软链不同。Cursor/Grok 已提供自己的导入、优先级与开关，Agent Manager 不重复实现。

## 5. 行为设计

### 5.1 清理后的直接管理拓扑

| tool | adapter | surfaces | Skill 根 |
| --- | --- | --- | --- |
| `claude` | `claude-shared` | Desktop、CLI | `~/.claude/skills` |
| `codex` | `codex-shared` | Desktop、CLI | `~/.codex/skills` |
| `copilot` | `copilot-shared` | Desktop、CLI | `~/.copilot/skills` |

Cursor/Grok 不出现在该表中。它们发现或导入 Claude Skills 是工具自身的兼容行为，不是 Agent Manager 生成的受管目标。

### 5.2 Instructions

自动目标从五个收敛为四个：

| target | 路径 | surfaces |
| --- | --- | --- |
| `shared` | `~/.agents/AGENTS.md` | Claude Desktop/CLI、Codex Desktop/CLI、Copilot CLI |
| `claude` | `~/.claude/CLAUDE.md` | Claude Desktop/CLI |
| `codex` | `~/.codex/AGENTS.md` | Codex Desktop/CLI |
| `copilot` | `~/.copilot/copilot-instructions.md` | Copilot CLI |

手工表面只保留 `copilot-desktop`。README 可以提示 Cursor User Rules 和 Grok 原生规则是兼容层关闭后的工具内备用方案，但 Agent Manager 不展示虚假的手工状态或写入入口。

### 5.3 旧支持清理

该一次性迁移已在旧 adapter 仍可识别 ownership 时执行完成。执行时仓库共有 18 个 Skill，观察结果为：

- Antigravity Skill preview 36 项：32 `remove`、4 `no-op`；apply 与读回成功。
- WorkBuddy Skill preview 18 项：16 `remove`、2 `no-op`；apply 与读回成功。
- Antigravity Instructions preview 1 项：1 `remove`；fingerprint apply 与读回成功。
- manager-owned `lucas-skills` 插件容器在 ownership、manifest 内容和“仅含 manifest 与空 `skills/`”结构检查通过后删除。
- `~/.gemini/config/skills`、`~/.workbuddy/skills` 产品根保留；Cursor/Grok 三个原生路径清理前后均 absent；canonical checkout 保持 clean。

当时的 rollback Step 5 未触发。旧 adapter 删除后，本仓库不再保留可重放的 HOME 清理或恢复算法，也不得从当前或未来 HEAD 重跑该迁移。未来若需恢复或修复外部状态，必须以已记录的精确 removed set（Antigravity 32、WorkBuddy 16、Instructions 1）和届时现场为输入，重新设计并 review 一个独立 migration；不得批量启用或补建原 `no-op`/missing 目标。

### 5.4 CLI、HTTP、Web、库存与文档

- `TOOLS` 只包含 `claude`、`codex`、`copilot`；`--tool all` 只展开三者。
- `INSTRUCTION_TARGETS` 只包含 `shared`、`claude`、`codex`、`copilot`。
- Web Skills 表从六列缩为四列：Skill 身份加三个受管工具。
- Web 删除 Antigravity/WorkBuddy 路由与 WorkBuddy 手工 Instructions fallback；保留 Copilot Desktop 手工行。
- inventory 删除 `.gemini`、`.workbuddy` 与 Antigravity 插件来源，不新增 Cursor/Grok 来源或工具标签。
- README 把 Cursor/Grok 放在“兼容消费方”说明中，不放入 Agent Manager 受管工具表。
- 历史 CHANGELOG 与已完成历史 spec/plan 保留当时事实；当前实施 plan 必须按本设计重写，旧版本不得执行。

## 6. 错误处理与安全边界

- Task 1 是已完成的一次性 migration 记录，不是当前 HEAD 的操作手册；不得复制或重跑其中的旧命令。
- 已观察结果只证明当时精确的 32+16+1 个 remove 与 4+2 个 no-op/missing；不推导当前 HOME 状态，也不提供通用 rollback 能力。
- 未来任何外部状态恢复或修复都必须重新盘点现场并走独立 review/preview/授权；不得批量启用旧工具或补建当时缺失的目标。
- 普通文件、目录、外部链接、产品根和 ownership 不明确的对象继续属于保留边界。
- 删除旧代码后不再扫描 `.gemini`、`.workbuddy` 或 Antigravity 插件路径。
- Cursor/Grok 未发现 Claude Skills 时，只在文档中指导用户检查各工具兼容或导入设置；Agent Manager 不替其修复设置。
- MCP 同名覆盖、重名 Skill、OAuth 或重复进程由工具自身诊断；README 指向 Cursor 设置和 `grok inspect`，Manager 不声称已解决。

## 7. 测试与验证

实现采用 TDD，最小覆盖包括：

1. adapter 精确为三个，surface 精确为六个；
2. CLI/HTTP 工具参数精确为 `claude`、`codex`、`copilot`；
3. Instructions 自动目标精确为四个，手工表面精确为 Copilot Desktop 一个；
4. `--tool all`、状态汇总、冲突、回滚、竞态与恢复合同保持有效；
5. Web 表头、筛选、拓扑和空状态使用三工具布局；
6. inventory 不再扫描 Antigravity/WorkBuddy 路径；
7. README 区分“受管工具”和“兼容消费方”；
8. 当前运行时代码、README 与活动测试没有旧工具支持残留；
9. 已完成的一次性真实 HOME 清理证据与不可重放门禁记录；
10. `grok inspect --json` 继续能发现 Claude 来源；Cursor Desktop 与 Cursor CLI 分别在新会话中确认 Claude Skills 可见，不创建新链接。若工具兼容开关关闭或版本能力不足，记录为外部环境限制，不增加 Agent Manager 写入兜底。

最终验证至少包括：

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
uv lock --check
git diff --check
rg -n "antigravity|workbuddy|Antigravity|WorkBuddy" README.md tools tests
```

实现分支的自动验证使用临时 HOME 和 Applications fixture。真实受管软链指向 canonical checkout，不能从 feature worktree 用新代码声称真实 `status/doctor` 已通过；该验收必须等待获批合并后，从 canonical checkout 运行并读回。

## 8. 验收标准

1. Agent Manager 只展示并写入 Claude、Codex、GitHub Copilot。
2. Antigravity、WorkBuddy 的当前运行时、UI、库存、README 与活动测试支持全部移除。
3. Instructions 只保留四个自动目标和 Copilot Desktop 手工表面。
4. 本次变更不为 Cursor/Grok 新增目录、软链、状态或额外 Skill 来源；既有第三方导入造成的重名/重复由工具自身诊断。README 准确说明其兼容依赖与关闭开关后的限制。
5. 一次性真实 HOME 清理结果已记录：Antigravity 32、WorkBuddy 16、Instructions 1 个受管链接完成移除，4+2 个 missing 目标未创建；经 ownership/content/shape 检查的 Antigravity 插件容器已删除，产品根与非本仓库对象保持原样。该记录不可从当前或未来 HEAD 重放。
6. 全量自动测试通过；获批集成后从 canonical checkout 读回 Agent Manager 冲突与问题数为零。Grok 在当前兼容配置下仍能从 Claude 来源发现 Skills/Instructions，Cursor Desktop 与 CLI 分别完成 Claude Skill 可见性 smoke。环境兼容关闭时允许记录为外部限制，但不得把未验证状态写成已支持。
