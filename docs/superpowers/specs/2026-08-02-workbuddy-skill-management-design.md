# WorkBuddy Skill 纳管设计

## 1. 结论

Agent Manager 增加第五个工具族 `workbuddy`，只管理 WorkBuddy Desktop 的用户级 Skills。仓库 `skills/` 继续作为唯一受管来源，每个启用项直接软链到 `~/.workbuddy/skills/<skill>`。

本期不管理 WorkBuddy 的“自定义指令”、身份、记忆、插件、连接器或真实 HOME 中已有的非仓库 Skill，也不把 CodeBuddy 的规则加载契约外推到 WorkBuddy。

## 2. 背景与已验证事实

当前 Agent Manager 覆盖 Claude、Codex、GitHub Copilot、Antigravity 四个工具族。Skills 采用逐项软链和显式状态模型；Instructions 以仓库根目录 `AGENTS.md` 为唯一来源，并通过各工具已有的稳定文件入口部署。

本机 WorkBuddy 5.3.8 的只读调查确认：

- Desktop 应用位于 `/Applications/WorkBuddy.app`，bundle id 为 `com.workbuddy.workbuddy`；
- 用户级 Skill 根目录为 `~/.workbuddy/skills/`，Skill 使用 `<name>/SKILL.md` 结构；
- 该目录当前有 15 个普通目录，仓库当前也有 15 个顶层 Skill，目录名交集为 0；
- WorkBuddy 内置 CodeBuddy Agent CLI，但 Desktop 启动路径显式关闭 CodeBuddy 的 Markdown system-reminder 注入，不能据此承诺自动加载用户级或项目级 `AGENTS.md`；
- WorkBuddy UI 的“自定义指令”会影响所有对话，但当前没有稳定、公开的文件或 API 契约，且内容上限为 1500 字符。

因此，Skills 有稳定且可验证的文件系统目标；Instructions 暂无满足 Agent Manager 安全边界的自动化目标。

## 3. 目标与非目标

### 3.1 目标

1. 在 CLI、HTTP API、Web 控制台和状态输出中把 WorkBuddy 展示为第五个工具族。
2. 支持逐 Skill 查看、启用和停用 WorkBuddy 目标。
3. 保留 `status`、`set`、`adopt` 的 dry-run、冲突检测、计划应用和回滚语义。
4. 将 WorkBuddy 自有 Skill 纳入只读库存，但不自动接管或删除。
5. 通过测试和 README 说明 WorkBuddy 的能力边界及验收方式。

### 3.2 非目标

- 不新增 WorkBuddy Instructions target。
- 不读写 WorkBuddy 的“自定义指令”设置、SQLite、Local Storage 或云同步状态。
- 不创建或管理 WorkBuddy 插件。
- 不把 `~/.workbuddy/skills` 整目录替换为软链。
- 不迁移、覆盖或删除 WorkBuddy 已有 Skill。
- 不修改真实 HOME；真实启用另行使用现有 preview/apply 授权流程。

## 4. 方案选择

### 4.1 采用：逐 Skill 直接软链

为 WorkBuddy 增加一个 adapter：

| 字段 | 值 |
| --- | --- |
| tool | `workbuddy` |
| adapter key | `workbuddy-desktop` |
| surface | `workbuddy-desktop` |
| 检测方式 | `/Applications/WorkBuddy.app` 是否存在 |
| 目标根目录 | `~/.workbuddy/skills` |
| 目标条目 | `~/.workbuddy/skills/<skill>` |

该方案复用现有 per-Skill 状态机，不需要 WorkBuddy 专用 manifest，也不影响同目录中的产品内置、市场或用户自建 Skill。

### 4.2 不采用：整目录软链

WorkBuddy 已在目标目录保存自有 Skill。整目录替换会扩大所有权边界，并可能破坏 WorkBuddy 的安装、升级和 SkillHub 管理行为。

### 4.3 不采用：受管插件

插件可以封装 Skills，但会额外引入 manifest、启用状态和插件生命周期，无法为当前的逐 Skill 开关提供更小或更稳定的实现。

## 5. 行为设计

### 5.1 检测与可用性

`detect_surfaces` 增加 `workbuddy-desktop`。检测到 `/Applications/WorkBuddy.app` 时 adapter 可用；未检测到时目标状态为 `unavailable`，写操作保持 no-op/拒绝语义，不创建 `~/.workbuddy` 或目标目录。

WorkBuddy 当前没有纳入管理范围的 CLI 表面，因此不增加虚构的命令检测项。

### 5.2 状态与写操作

WorkBuddy 复用现有链接状态：

- `enabled`：目标是直接指向当前仓库 Skill 的软链；
- `disabled`：目标不存在；
- `legacy`：最终解析到当前仓库 Skill，但不是直接链接；
- `conflict`：目标为普通目录、普通文件或指向其他来源的链接；
- `unavailable`：WorkBuddy Desktop 未安装；
- `error`：扫描失败。

`skills set <skill> --tool workbuddy --on` 只在目标缺失且固定父目录符合现有安全前提时创建直接软链；`--off` 只删除管理器确认的直接仓库软链。现有普通目录即使内容相同也视为冲突，不做目录级内容比较或接管。

`skills adopt` 沿用通用链接接管逻辑，不增加 WorkBuddy 普通目录迁移特例。这样可以避免把 WorkBuddy 自建或市场安装的 Skill 误判为仓库副本。

### 5.3 库存

只读 inventory 增加 `~/.workbuddy/skills` 来源，并映射到 `workbuddy` / `workbuddy-desktop`。当前仓库直接链接标记为 `managed`；其他有效 Skill 标记为 `external`；断链、无效 frontmatter 和同一表面重名继续使用现有 flags。

库存扫描不改变文件系统，也不把外部 WorkBuddy Skill 变成受管对象。

### 5.4 CLI、HTTP 与 Web

- CLI 的工具枚举增加 `workbuddy`，从而支持 `--tool workbuddy` 和 `--tool all`。
- HTTP 请求校验与状态响应接受、返回 `workbuddy`。
- Web 控制台 Skills 拓扑增加 WorkBuddy 一列，并显示 Desktop 安装状态、目标路径和逐 Skill 状态。
- Instructions 区域不增加 WorkBuddy target；可在说明文本中明确“WorkBuddy 自定义指令需在应用内手工维护”。

### 5.5 文档

README 的支持矩阵增加 WorkBuddy Desktop：

- 应用检测：`WorkBuddy.app`；
- CLI：无受管表面；
- Skill 路径：`~/.workbuddy/skills/<skill>`；
- Instructions：不自动管理，使用 WorkBuddy 设置中的“个性化 → 自定义指令”。

文档同时说明启用后应新建 WorkBuddy 任务进行发现性验证，不承诺当前会话热加载。

## 6. 测试与验证

实现采用 TDD，先补失败测试，再修改生产代码。覆盖：

1. adapter 路径、tool key 和 surface 映射；
2. `WorkBuddy.app` 存在/缺失时的检测结果；
3. WorkBuddy 目标的 enabled、disabled、conflict、unavailable 状态；
4. `set --on`、`set --off`、`--tool all` 的计划与应用；
5. inventory 对受管链接、外部目录和异常条目的分类；
6. CLI 参数、JSON 输出和退出码；
7. HTTP 请求校验及响应；
8. Web 工具列、路径、安装状态和汇总展示；
9. README 契约断言与项目现有完整测试集。

最终验证至少包括：

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

真实 HOME 验收不在自动测试中执行。后续经独立授权后，使用现有 dry-run/apply 流程启用一个无冲突 Skill，再新建 WorkBuddy 任务确认其可被发现；验证完成后可按相同流程停用测试项。

## 7. 风险与控制

| 风险 | 控制 |
| --- | --- |
| WorkBuddy 升级改变 Skill 路径 | README 标注已验证版本；adapter 路径测试与真实新任务验收共同发现漂移 |
| 覆盖 WorkBuddy 自有 Skill | 普通目录始终为 conflict；不提供自动替换 |
| `--tool all` 意外扩大写入 | 复用 preview/fingerprint/apply 契约和逐目标计划 |
| 把 CodeBuddy 规则能力误报为 WorkBuddy 能力 | 本期不新增 Instructions target，文档明确仅 UI 手工配置 |
| Skill 创建后当前任务不可见 | 验收固定使用新建 WorkBuddy 任务，不承诺热加载 |

## 8. 验收标准

1. Agent Manager 的 Skills 域完整展示五个工具族，WorkBuddy 只包含 Desktop 表面。
2. WorkBuddy 已安装时，仓库 Skill 可被逐项规划为 `~/.workbuddy/skills/<skill>` 直接软链。
3. WorkBuddy 未安装或目标冲突时，不创建、覆盖或删除任何目标。
4. WorkBuddy 已有普通目录保持原样，并在 inventory 中可见。
5. Instructions 域保持原有五个 target，不出现虚假的 WorkBuddy 自动管理状态。
6. 项目完整测试全部通过，README 与 CLI/HTTP/Web 行为一致。
