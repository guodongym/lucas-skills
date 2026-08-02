# 开发版本发布收尾 Skill 设计

- 日期：2026-08-02
- 状态：待用户复核
- 结论：新增 `finishing-a-development-release` 编排型 Skill，用一条默认快速路径完成任务分支或 worktree 的文档同步、提交历史整理、main 集成、tag、远端发布与清理；只有出现风险信号时才升级检查。GitHub、Gitee、私有 EZone 等远端按能力分级，平台不支持 Release 页面时允许以可验证的 Portable Release 收口。

## 1. 要解决的问题

个人项目的开发任务通常在独立 worktree 中完成。实现结束后，仍需连续处理多项工作：

1. 同步 CHANGELOG 和受影响文档；
2. 酌情整理任务分支提交历史；
3. 合并到 main 并验证最终代码树；
4. 推送 main、创建 tag 和平台 Release；
5. 在删除 worktree 前保全未提交到 Git 的本地密钥、配置和运行状态；
6. 回读远端结果，避免把半完成状态报告为发布成功。

现有 Skill 分别覆盖其中一段，但没有统一的发布收尾语义：

- `neat-freak` 负责完整知识与规则审计，不适合每次发布都无条件执行；
- `git-history-rewrite` 负责安全整理提交历史；
- `finishing-a-development-branch` 负责分支合并、PR 和基础清理；
- `verification-before-completion` 负责完成声明前的 fresh evidence。

新 Skill 只负责编排、选择快速或升级路径、定义跨平台完成状态，不复制上述 Skill 的详细实现。

## 2. 设计目标与非目标

### 2.1 目标

1. 用一次明确触发完成常见的 worktree 发布收尾，减少重复沟通和漏项。
2. 默认只执行一次最终完整验证、一次远端回读和一次本地状态候选扫描。
3. 根据实际风险决定是否整理历史、执行完整 `neat-freak` 或深度比较本地状态。
4. 同时支持 GitHub、Gitee、私有 EZone 和未知 Git 托管平台。
5. 区分 Full、Portable、Partial、Blocked 四种发布结果，不把 tag 等同于平台 Release。
6. 删除 worktree 前证明有用的 ignored/untracked 本地状态已保留。
7. 对密钥只比较路径、键名、元数据和等价性，不输出值。

### 2.2 非目标

- 不实现通用 CI/CD、制品构建、部署或回滚平台。
- 不为所有代码托管平台预置 API 客户端。
- 不自动发布到所有 remotes。
- 不自动决定版本号或移动已经发布的 tag。
- 不自动解决两边都修改过的私有配置冲突。
- 不把缓存、日志、虚拟环境和依赖目录逐文件扫描。
- 不替代各仓库既有的测试、版本、合并和发布约定。
- 首版不增加通用发布脚本或 provider 插件框架；真实使用证明有必要后再提取。

## 3. 现有 Skill 复用契约

`finishing-a-development-release` 是发布编排器，不是上述 Skill 的合并版。它维护发布阶段、传递验证证据、选择是否升级，并补齐版本、tag、provider Release、本地非 Git 状态和跨平台完成状态。复用分为“直接调用”和“受限阶段复用”；不能完整组合的地方必须显式记录兼容边界，不能口头说复用、实际另写一套流程。

### 3.1 运行期依赖

| 现有 Skill | 复用方式与触发条件 | 复用的职责 | 新 Skill 只补充 | 禁止重复实现 |
| --- | --- | --- | --- | --- |
| `neat-freak` | **条件式直接调用**：用户显式调用，或出现跨项目/跨模块、关键契约、规则/目录/Skill 变化、文档漂移等升级信号 | 完整文档、CHANGELOG、项目知识和 Agent 规则审计 | 默认快速路径只做发布相关文档检查；决定是否升级，并把审计结果作为发布输入 | 不复制完整枚举、知识整理和规则同步流程；不私自给它增加“快速模式” |
| `git-history-rewrite` | **条件式直接调用**：检出 WIP、fixup、重复修复、失序提交，或用户明确要求整理历史 | 选择改写范围、刷新远端、风险判断、备份 ref、历史改写、tree identity 与安全推送规则 | 判断是否需要整理；记录结果与备份 ref；仅在其验证通过后继续发布 | 不复制 rebase/reset/autosquash 操作，不自行定义另一套 force-push 规则 |
| `finishing-a-development-branch` | **受限阶段复用**：任务分支需要合并、PR、保留或清理时，复用其判断和执行合同，但不能按当前版本端到端原样运行 | 环境与 base 确认、用户决定集成方式、合并结果验证、分支/worktree 所有权安全和基础清理 | 接受用户已给出的集成选择；按 tree 等价性消除重复测试；把 cleanup 延后到 provider 发布和本地状态门禁之后 | 不发明第四种集成选项，不改变 base/所有权/删除授权规则，不把延后 cleanup 变成跳过 cleanup 检查 |
| `verification-before-completion` | **必需直接调用**：声称合并、验证、发布或清理完成之前；远端写入前需取得最终 tree 的 fresh evidence | 证据先于声明、验证命令与结论严格对应 | 复用等价 tree 的同一份证据；把证据映射到 Full/Portable/Partial/Blocked 状态 | 不另建一套“凭经验视为通过”的完成标准，不用旧日志代替 fresh evidence |

运行期编排顺序为：本地状态候选快照 → 轻量文档检查或 `neat-freak` → 历史检查或 `git-history-rewrite` → 复用 `finishing-a-development-branch` 的集成阶段并暂停 cleanup → 本地状态对账 → `verification-before-completion` 取得最终证据 → push/tag/provider Release 与回读 → 通过本地状态门禁后复用其 cleanup 合同。

这不是要求每次依次执行四个 Skill。没有升级信号时 `neat-freak` 和 `git-history-rewrite` 应 no-op；没有分支集成或清理任务时不调用 `finishing-a-development-branch`。`verification-before-completion` 的门禁始终保留，但相同 tree 的等价证据可以复用，避免重复测试。

未来的 `SKILL.md` 对完整调用使用明确的 `REQUIRED SUB-SKILL` 标记，对 `finishing-a-development-branch` 使用 `REUSED CONTRACT` 标记并逐条列出仅有的三个兼容点：已有选择不重复询问、等价 tree 不重复测试、cleanup 延后但不取消。除此之外只引用 Skill 名称，不摘抄其内部操作步骤。若安全规则冲突，以更严格的规则为准。

### 3.2 必要的最小兼容调整

首版实现同时处理两个现有触发/顺序冲突：

1. `neat-freak` 当前把裸“收尾”视为强触发。应在其 description 中补充路由边界：明确的“发布收尾/合并 main/tag/push”由 `finishing-a-development-release` 接管，只有用户点名 `$neat-freak` 或编排器检出升级信号时才运行完整审计。
2. `finishing-a-development-branch` 当前 Option 1 会在本地合并验证后立即 cleanup。发布编排只复用其集成和清理合同，并将 cleanup 延后；不直接修改插件缓存中的 Skill，也不声称完整调用了未完整执行的流程。

这两项属于组合适配，不引入新的发布能力。若未来 `finishing-a-development-branch` 提供正式的 deferred-cleanup 接口，新 Skill 应改为直接调用并删除本地兼容描述。

### 3.3 仅用于开发本 Skill 的工具

`skill-creator` 和 `superpowers:writing-skills` 用于设计、实现和 RED/GREEN 验证 `finishing-a-development-release` 本身，不是用户发布项目时的运行期依赖，也不应出现在快速发布动作链中。

## 4. 触发与授权边界

Skill 名称：`finishing-a-development-release`。

触发场景包括：

- “发布收尾”“这个版本可以发了”；
- “合并 main、打 tag、push”；
- “开发完成，整理提交历史后发布”；
- “创建 GitHub/Gitee Release”；
- “历史 tag 没有 Release”“Release notes 显示不全”；
- “发布后清理 worktree/任务分支”。

授权解释：

- 用户明确要求“合并 main、tag、push、发布”时，授权对 main 当前选定的发布 remote 执行对应 branch、tag 和该平台原生 Release 写入；不授权其他 remotes。
- 用户只要求“合并”时，不推送、不打 tag、不创建平台 Release。
- 仅说“发布”不自动授权删除 worktree 或分支；用户同时说“收尾/清理 worktree”，或仓库规则明确把清理包含在该命令中，才执行清理。
- force push、移动现有 tag、覆盖私有配置、删除未合并分支始终需要单独明确授权。

## 5. 核心原则：快速路径，按风险升级

标准发布的目标动作量是：

- 1 次提交范围分析；
- 1 次相关文档检查；
- 1 次最终完整验证；
- 1 次 push；
- 1 次远端状态回读；
- 1 次本地状态候选扫描。

同一代码树的 fresh evidence 可以复用：

- 历史改写后 tree identity 未变，不重复完整测试；
- main fast-forward 后 tree 与已验证 tree 相同，不重复完整测试；
- pre-push hook 已覆盖相同门禁且本轮输出可核实时，不重复执行相同命令；
- tag 和平台 Release 不改变代码树，不触发代码测试。

以下信号使流程升级：

- main 在开发期间新增提交，合并或 rebase 改变最终 tree；
- 工作区存在相关脏文件、未分类本地状态或私有配置冲突；
- 版本号、tag、发布 remote 或 CHANGELOG 章节不明确；
- API、环境变量、数据库、部署方式、规则文件或跨项目契约发生变化；
- 测试、push、tag 或平台 Release 创建/回读失败；
- 用户显式调用 `$neat-freak`。

## 6. 快速发布流程

### 6.1 现场锚定

1. 确认 repo、worktree、branch、HEAD、工作区和 git common dir。
2. 确认目标 base branch；默认采用任务来源或当前约定的 `main`，不凭名称猜测。
3. 刷新选定 remote 的 branch/tag 引用，确认 ahead/behind、是否已经推送、是否存在同名 tag。
4. 识别 main 的 push upstream；多个候选发布 remotes 无法唯一判断时停止询问。
5. 在流程开始时记录本地状态候选快照，供清理前复核。

### 6.2 轻量文档同步

默认只检查：

- CHANGELOG 当前版本章节；
- README 中与本次变更直接相关的内容；
- changed files 指向的相关 docs；
- 本次新增或修改的 API、环境变量、部署命令和运行约束；
- AGENTS/CLAUDE 是否被本次变更直接影响。

以下情况调用完整 `neat-freak`：用户显式点名、跨项目/跨模块发布、关键契约变化、发现文档漂移，或规则/目录/Skill 本身发生变化。新 Skill 不向 `neat-freak` 添加隐式“快速模式”。

### 6.3 提交历史

1. 检查任务范围内是否存在 WIP、fixup、重复修复或失序提交。
2. 历史已经清晰时 no-op，不为形式改写。
3. 需要改写时必须调用 `git-history-rewrite`，遵守远端刷新、备份 ref、tree identity 和 `--force-with-lease` 规则。
4. 文档/CHANGELOG 收尾提交可折入对应功能提交或保留为独立发布边界，按仓库历史和审阅价值判断。

### 6.4 main 集成、本地状态对账与最终验证

1. 在 canonical main checkout 或受管主工作区更新 main。
2. 按仓库约定 fast-forward、merge 或合入；不擅自改变项目合并策略。
3. 对 main 最终验证需要的私有配置执行本地状态阶段 B 对账；不依赖这些配置的候选可延后到清理门处理。
4. 在最终发布 tree 上取得一次完整、fresh 的仓库验证证据。
5. 如果最终 tree 与此前已验证 tree 字节一致，复用证据并记录等价关系。
6. 验证失败时停止在本地，不 push、tag 或清理。

### 6.5 推送、tag 与平台发布

远端顺序固定为：

1. push main；
2. 回读远端 main SHA；
3. 创建并推送 annotated tag；
4. 用 `git ls-remote` 回读 tag 对象和 peeled tag；
5. 能力允许时创建平台 Release；
6. 回读平台 Release 的 tag、标题、正文、状态和 URL。

禁止先把 tag 推到远端而让 main 留在旧提交。若仓库明确采用受支持的 atomic push，可一次推 main/tag，但仍需逐项回读。

### 6.6 本地状态对账与清理

清理前重新读取全部候选状态；若与初始快照不同，重新分类。完成其余必要迁移和验证后，才按授权清理 worktree、任务分支或备份 ref。

## 7. 远端能力与发布状态

### 7.1 远端识别

以 main upstream 对应 remote 的 push URL 为准，不依赖 remote 必须名为 `origin`：

- `github.com`：GitHub adapter；
- `gitee.com`：Gitee adapter；
- 私有 EZone host：只使用仓库文档或已配置的内部 CLI/API；
- 其他 host：未知 provider。

一个仓库存在多个 remotes 时，默认只发布到 main upstream 对应 remote。不同步其他 mirror；用户明确指定多个发布目标时分别执行并分别报告状态。

### 7.2 四级状态

| 状态 | 完成条件 | 清理策略 |
| --- | --- | --- |
| `Full Release` | 远端 main + annotated tag + 原生平台 Release + 全部回读通过 | 可按授权清理 |
| `Portable Release` | 平台无可用 Release 能力；远端 main + annotated tag + 版本化 CHANGELOG + Git 回读通过 | 可按授权清理 |
| `Partial Release` | 平台预期支持 Release，但鉴权、接口或网络失败；main/tag 已发布 | 报告可重试来源；保留备份 ref，未完成本地状态对账时不清理 |
| `Blocked` | main/tag 推送失败，或版本、notes、remote 无法确定 | 不清理 |

平台明确不支持 Release 是可接受的 Portable Release，不等同于失败。平台本应支持但本次执行失败，不能静默降级为成功。

### 7.3 Provider 策略

**GitHub**

- 使用现有远端 annotated tag 创建 GitHub Release；使用 `--verify-tag` 防止隐式创建错误 tag。
- 完整正文来自 CHANGELOG 对应版本章节；tag annotation 只保留版本与短摘要。
- 稳定版本可标记 Latest；RC/beta 等标记 Prerelease。
- 使用机器可读输出回验 tag、name、body、draft/prerelease 状态和 URL。
- 默认不使用自动生成 notes 代替人工维护的 CHANGELOG。

**Gitee**

- 运行时从 Gitee 当前官方 API/CLI 文档确认 Release 创建、读取、鉴权和字段契约，再决定是否执行 Full Release。
- 不在 Skill 中硬编码可能漂移的 endpoint 或 token 名。
- 预检阶段没有发现可用 adapter 或已配置凭据时，选择 Portable Release；不要求用户在聊天中粘贴 token。
- 预检已选择 Full Release，但实际创建、鉴权或回读失败时，结果是 Partial Release，不能临时改报 Portable Release。

**私有 EZone/未知平台**

- 先读取仓库规则、内部运行手册和已有 CLI/API 配置。
- 没有明确契约时不猜 endpoint、不拼接未验证 URL、不写私有远端。
- 使用通用 Git main/tag + CHANGELOG 形成 Portable Release。

### 7.4 历史 tag 修复模式

当用户要求补齐历史 Release：

1. 找出用户指定范围内“远端 tag 已存在、平台 Release 不存在”的版本；
2. 从各自 CHANGELOG 章节构造 notes；
3. 不修改、不移动、不重写原 tag；
4. 只有最新稳定版本可标记 Latest；
5. 缺少明确版本章节时停止该版本，不编造 notes；
6. 每个版本创建后单独回读并报告。

历史修复不自动作为每次正常发布的一部分。

## 8. 非 Git 本地状态对账

### 8.1 两阶段模型

**阶段 A：初始候选快照**

- 枚举 feature worktree 和 main checkout 的 ignored/untracked 候选；
- 只展开 `.env*`、`*.local`、私有配置、证书、Cookie、部署/smoke 配置、持久化数据库和运行状态等高价值路径；
- `node_modules`、`.venv`、构建缓存和普通日志只按目录分类，不深扫；
- 记录路径、类型、大小、权限、mtime 和必要时的 SHA-256；
- `.env` 只记录 key 集合、缺失关系和值是否相等，不输出值；
- 符号链接只记录 link 和 target，不跟随复制外部目标。

**阶段 B：main 对账**

| 差异 | 动作 |
| --- | --- |
| worktree 新增、main 缺失 | 判断是否有用；有用则复制到 main 本地状态 |
| 两边内容等价 | no-op |
| worktree 更新、main 未修改 | 更新 main 并验证来源/目标等价 |
| 两边都修改且不同 | 冲突，停止自动处理 |
| 明确可重建 | 不迁移，标记可丢弃 |
| 用途不明 | 未分类，保留 worktree |

### 8.2 安全约束

- 不输出、提交、上传或写入日志的密钥值。
- 不通过 `git add -f` 暂存 ignored 私有文件。
- `.env` 优先按 key 合并，不整文件盲目覆盖。
- 同一 key 两边值不同必须视为冲突，不按 mtime 自动选边。
- 复制后保留或收紧权限，并用哈希或结构化等价检查验证。
- 需要私有配置的最终测试，应在 main 本地状态完成对账后执行。
- 未分类或冲突数量大于 0 时，worktree cleanup 必须暂停。

### 8.3 清理判据

删除 worktree 前必须满足：

- 代码已经合入目标 main；
- main/tag 已按当前发布等级完成远端回读；
- 有用本地状态已迁移并验证；
- 本地状态冲突为 0；
- 未分类候选为 0；
- 删除范围和授权明确。

`Partial Release` 中，只要 notes 已固化在远端 main、main/tag 可恢复且本地状态已对账，可以删除 worktree；历史改写 backup ref 保留到平台 Release 补建成功。若任一可恢复条件不成立，不清理。

## 9. 错误处理与恢复

- 测试失败：停在本地，保留 worktree 和分支。
- main push 失败：不创建或推送 tag。
- tag push/回读失败：报告 main 已发布、tag 未完成，不创建平台 Release。
- 平台 Release 失败：报告 Partial Release、错误类型和从 CHANGELOG 重试的方法；不重写 tag。
- local-state 冲突：发布可以保持已完成等级，但清理暂停；只报告路径、key 名和差异类型。
- cleanup 失败：不使用强制删除绕过；报告仍存在的 worktree/branch/ref。
- 远端并发更新、force-with-lease 拒绝或同名 tag 指向不同提交：立即停止，不覆盖远端。

## 10. Skill 结构

首版保持最小结构，并只对一个现有 Skill 做触发路由修正：

```text
skills/finishing-a-development-release/
├── SKILL.md
└── agents/
    └── openai.yaml

skills/neat-freak/SKILL.md       # 仅调整 description 的发布收尾路由边界
```

不新增脚本、provider adapter 或 reference 文件。SKILL.md 只保留：

- 快速路径与升级条件；
- 四级发布状态；
- provider 选择规则；
- 本地状态对账与清理门禁；
- 必须调用的现有 sub-skills；
- 紧凑的最终报告模板。

若首轮真实使用反复出现泄密风险或候选扫描命令漂移，再单独设计只读 `inspect-local-state` 脚本；首版不提前承担该复杂度。

## 11. 验证策略

实现前先按 skill-writing 的 RED/GREEN 流程验证真实增量。场景至少覆盖：

1. GitHub worktree 正常发布，预期 Full Release；
2. Gitee 或未知 EZone 无已验证 Release API，预期 Portable Release；
3. GitHub Release 创建鉴权失败，预期 Partial Release；
4. worktree/main 的 `.env` 同 key 不同值，预期停止清理且不输出值；
5. 历史已经清晰、tree identity 未变，预期不重写历史、不重复完整测试；
6. 用户只要求合并，预期不 push/tag/Release；
7. 历史 tag 缺 Release，预期补建 Release 且不移动 tag；
8. 缓存目录很多但私有候选无差异，预期快速 no-op 而非深扫。
9. 用户明确说“发布收尾”但没有升级信号，预期进入新 Skill 且不运行完整 `neat-freak`；
10. 用户已经选择合并 main，预期不重复询问、不重复测试，并在发布与本地状态门禁通过前保留 worktree。

验收条件：

- frontmatter 只含 `name` 和 `description`，名称和目录一致；
- description 覆盖中英文触发语，不摘要完整流程；
- SKILL.md 不复制现有 sub-skills 的详细步骤；
- 每个运行期 sub-skill 都明确触发条件、消费的输出和禁止重复实现的边界；
- `SKILL.md` 用 `REQUIRED SUB-SKILL` 标记完整调用，用 `REUSED CONTRACT` 标记分支 Skill 的受限阶段复用；
- 三个分支兼容点仅限已有选择、等价证据和延后 cleanup，不复制整个 `finishing-a-development-branch`；
- `neat-freak` 的触发路由已消除“发布收尾必然执行完整审计”的冲突；
- `skill-creator` 与 `superpowers:writing-skills` 只用于本 Skill 的开发验证，不进入发布运行期；
- 所有 destructive/remote 写入都有可观察的授权条件；
- Partial、Blocked 或本地状态冲突不会被报告为 Full Release；
- fast-path 场景只要求一次最终完整验证；
- secret 场景的输出不包含任何值；
- `quick_validate.py`、仓库全量 unittest 和 `git diff --check` 通过。

多 Agent forward-test 只有在当前环境允许且用户授权时执行；环境不允许时，保留场景清单和基线输出，使用新的独立会话完成后续验证，不绕过 RED/GREEN 要求。

## 12. 最终报告合同

最终报告保持一屏优先，只包含可行动事实：

```text
Release: Full | Portable | Partial | Blocked
Version/tag: <version>
Main: <local sha> == <remote sha>
Tag: <tag object>; peeled -> <sha>
Platform release: <url | unavailable | failed>
Verification: <fresh commands and counts>
History: <unchanged | rewritten, backup ref>
Local state: <merged/equal/discardable/conflict/unclassified counts>
Cleanup: <completed | preserved, reason>
Residual risk: <none | concise blocker>
```

不能用“发布完成”掩盖 Partial/Blocked 状态，也不能把 tag 页面当成平台 Release 页面。
