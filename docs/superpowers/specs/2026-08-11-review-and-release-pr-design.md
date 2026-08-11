# PR 深度评审到发布编排 Skill 设计

- 日期：2026-08-11
- 状态：设计已确认并完成独立复核，待实施
- 结论：新增 Codex 全局薄编排 Skill `review-and-release-pr`，以第一性原理需求门禁作为入口，复用现有方案评审、GitHub 评论处理、代码审查、TDD 修复、完成验证和发布收尾 Skills。运行状态只保留 `PASS / FIX / STOP`；需求不合理、关键证据不足、P0 或需要新决策的修复均停止，修法明确且已有授权的问题可在披露后继续修复。v0.1 只支持 Codex，不激活到其他 Agent 工具。

## 1. 要解决的问题

一次完整 PR 处理通常不只是阅读 diff。实际流程还需要：

1. 在多 PR 场景中先判断依赖和合并顺序；
2. 判断 PR 要解决的问题和验收目标本身是否合理；
3. 复核已有 reviewer 结论与修复是否成立；
4. 独立审查当前实现，而不是沿用旧 review；
5. 对已证实问题选择自动修复或人工决策；
6. 在 main 前进后刷新 PR 现场和验证证据；
7. 只在最终树具备证据时合并和发布；
8. 把 cleanup 与合并、发布授权分开。

现有 Skills 分别覆盖其中一段，但没有统一管理跨阶段状态、证据失效和授权边界。没有编排层时，容易出现以下问题：

- 在需求方向错误或证据不足时直接优化实现；
- 把已有 reviewer 的结论当作独立 review；
- 静默修复严重问题，绕过接口、Schema 或产品语义决策；
- 使用过期的 PR body、base/head、测试数或 review 结论；
- 把“修复所有问题”扩大解释为任意设计变更、合并、发布或清理授权；
- 测试树、最终合并树和发布 tag 不是同一棵树。

新 Skill 只补齐编排缺口，不重新实现各阶段的专业判断和 Git 操作。

## 2. 目标与非目标

### 2.1 目标

1. 第一性原理审查需求先于详细实现审查；门禁不通过时停止后续流程。
2. 将需求审查、已有 review 复核和独立代码 review 保持为三个独立结论。
3. 使用 `PASS / FIX / STOP` 三个状态表达所有阶段，不建设复杂审批系统。
4. 所有 P0/P1 阻止合并；修法明确、范围受控且已有授权的代码问题允许进入 `FIX`。
5. 需要新产品或技术决策时进入 `STOP`，不得用局部补丁替代决策。
6. 在每次 PR head、base、需求或 main 发生实质变化后刷新受影响证据。
7. 复用现有 Skills，保持各自触发、证据和授权契约。
8. PR 评论可追溯且不静默写入；没有写权限时生成草稿并停止外部写入。
9. v0.1 只在 Codex 内跨项目全局可用；运行前确认当前任务具备将要调用的子 Skill 和 GitHub 能力，缺失时 fail-closed。

### 2.2 非目标

- 不替代 GitHub 分支保护、CI、CODEOWNERS 或人工审批。
- 不创建新的代码 review rubric、方案 review rubric 或发布流程。
- 不自动决定产品需求、核心接口、数据库 Schema、依赖或破坏性行为。
- 不把普通代码 review、单独处理 reviewer comments、release-only 或 cleanup-only 请求全部抢进本 Skill。
- 不自动修改 PR body、Issue、spec 或项目计划来使门禁通过。
- 不在首版增加脚本、provider adapter、模板库或持久化状态数据库。
- 不自动执行 `gh auth login`、`gh auth refresh` 或修改 GitHub App 安装范围。
- 不要求每个 `P2` 都修复或阻止合并。
- 不在 v0.1 支持 Claude、GitHub Copilot、Antigravity 或 WorkBuddy，也不为这些工具复制 GitHub 或 Superpowers 插件能力。

## 3. 触发与路由

Skill 名称固定为 `review-and-release-pr`，源码位于：

```text
skills/review-and-release-pr/
```

v0.1 的“全局”特指 Codex 内跨仓库、跨任务可发现，不表示跨 Agent 工具通用。发布时只允许通过 Agent Manager 激活到 `codex` target；不得使用 `--tool all`。Claude、GitHub Copilot、Antigravity 和 WorkBuddy 均为未支持表面，即使它们能够读取仓库中的 `SKILL.md`，也不能据此宣称具备完整流程能力。

### 3.1 正向触发

- “先审需求和已有 review，再独立 review，修好后合并发布这个 PR。”
- “这个 PR 已经有人审过，复核他的结论，再自己审一轮并修复所有问题。”
- “我有多个未合并 PR，先排顺序，然后逐个 review、修复和发布。”
- “按完整 PR 流程处理；需求不合理就在 PR 里评论并停止。”

### 3.2 负向路由

- 只审代码、不要求修复或发布：`code-change-review`。
- 只审正式方案文档：`technical-proposal-review`。
- 只处理已有 GitHub review threads：`gh-address-comments`。
- 只修复一个已知 Bug：调试与 TDD 流程。
- 已完成开发，只需要合并、tag、Release 或清理：`finishing-a-development-release`。
- 只要求盘点多个 PR：GitHub triage；如果用户同时表达后续逐个评审发布意图，再由本 Skill 接管完整流程。

## 4. 现有 Skill 与工具复用契约

`review-and-release-pr` 是编排器。它只决定阶段顺序、状态、证据是否仍有效以及是否已取得对应授权；子 Skill 保留各自的专业规则。

| 现有 Skill / 工具 | 调用条件 | 消费的结果 | 新 Skill 只补充 | 禁止重复实现 |
| --- | --- | --- | --- | --- |
| `github` / `gh` | 解析 PR、Issue、评论、Draft、base/head 和多 PR 现场 | 结构化 PR 元数据、评论及目标仓库权限 | 运行一次能力预检并锁定本轮远端后端 | 不另写通用 GitHub triage，不把仓库 404 直接解释为掉登录 |
| `technical-proposal-review` | PR 引用了正式 PRD、RFC、spec 或技术方案，且需要判断方案合理性 | 独立的 `P0/P1/P2/Q` 方案结论 | 把结论映射到需求门禁 | 不复制其 rubric、历史案例和反馈流程 |
| `gh-address-comments` | PR 存在已有 review threads 或 requested changes | thread 状态、可执行意见和待澄清项 | 保持“已有 review 复核”与独立 review 分离 | 不重新实现 GraphQL thread 解析、回复或 resolve 规则 |
| `receiving-code-review` | 判断已有 reviewer 建议是否正确、完整且适合实施 | 接受、拒绝或需澄清的反馈结论 | 把结论记入当前阶段 | 不盲从 reviewer，也不复制反馈验证流程 |
| `code-change-review` | 完成已有 review 复核后，对当前 immutable base/head 独立审查 | findings、questions、验证与 merge readiness | 将结论映射为 `PASS / FIX / STOP` | 不复制代码审查 rubric、severity 或 evidence gate |
| `systematic-debugging` / `test-driven-development` | 状态为 `FIX` 且已有代码修复授权 | 根因、失败测试、修复和回归结果 | 维持 finding 到修复的追踪关系 | 不复制调试或 RED/GREEN 流程 |
| `verification-before-completion` | 声称修复完成、可合并或发布完成之前 | fresh 验证及对应 tree identity | 判断证据能否跨阶段复用 | 不用旧测试数或口头结论替代验证 |
| `finishing-a-development-release` | 独立 review 重跑通过且用户已授权对应合并/发布动作 | main 集成、tag、Release、回读和 cleanup 门禁 | 传递已验证 tree、授权和遗留风险 | 不复制发布、tag、provider 或本地状态对账流程 |

`skill-creator`、brainstorming、writing-plans 和 writing-skills 只用于开发本 Skill，不是运行期依赖。

运行期依赖按阶段检查，不假设 Skill 激活会自动安装传递依赖：

- Phase 0 必须具备 `code-change-review`、`verification-before-completion`、`finishing-a-development-release`，以及 Connector 或 `gh` 中至少一种满足目标 PR 读取要求的 GitHub 后端。
- PR 引用正式方案时，进入 Gate 1 前必须具备 `technical-proposal-review`。
- PR 存在已有 review 时，进入 Phase 2 前必须具备 `gh-address-comments` 和 `receiving-code-review`；如果只是主后端缺少 thread-aware 读取能力，仍按 4.1 节允许的受控只读补充执行。
- 状态进入 `FIX` 前必须具备 `systematic-debugging` 和 `test-driven-development`。
- 缺少当前阶段的必需子 Skill 时进入 `STOP`，列出缺失能力并请求用户修复环境；不得现场复制子 Skill rubric、跳过阶段或把通用推理冒充为已完成的专业流程。

这些检查只验证能力存在，不激活、安装、更新或修改任何 Skill、插件与认证状态。

### 4.1 GitHub 能力预检与后端锁定

Connector 与本机 `gh` 使用不同认证和仓库授权，不能假设一边登录成功就代表另一边能访问目标仓库。Phase 0 对目标 PR 只做一次能力预检：

```text
Connector 读取身份和目标仓库
├─ 所需 PR 读取能力均成功：github_backend=connector
└─ 目标仓库 404、NOT_FOUND 或缺少所需读取能力
   → gh auth status + 目标仓库只读查询
      ├─ 成功：github_backend=gh
      └─ 失败：STOP
```

规则如下：

- Connector 身份成功但目标私有仓库返回 404/NOT_FOUND 时，记录 `connector_scope_gap`，不得误报为未登录。
- 能力预检至少覆盖目标仓库和核心 PR 元数据；进入已有 review 复核前，再确认普通评论和 review threads 的必要读取能力。
- 后端一旦选定，它就是本轮目标 PR 的主事实来源和全部 GitHub 写操作入口，避免在不同权限和刷新时点之间来回切换。
- 专项 Skill 明确要求的只读能力补充可以使用另一后端，例如 `gh-address-comments` 的 thread-aware GraphQL；使用前必须核对同一 repository、PR number 和 head SHA，不得据此切换主后端或扩大写权限。
- 本地 Git 仍负责代码对象、diff 和 tree identity，不受远端元数据后端选择影响。
- 两个后端都失败时进入 `STOP`，报告失败层和原始错误；不得自动登录、刷新凭据或修改 GitHub App 安装。
- 后端选择只证明能力可用，不授予评论、resolve、push、合并或其他写权限。

## 5. 最小状态模型

所有阶段只使用三种状态：

| 状态 | 含义 | 允许的下一步 |
| --- | --- | --- |
| `PASS` | 当前门禁已满足 | 进入下一阶段 |
| `FIX` | 已证实代码问题，修法明确、范围受控且已有修复授权 | 披露 finding 后按 TDD 修复，再重跑独立 review |
| `STOP` | 需求、证据、风险或修复需要人工决策 | 评论 PR 或生成评论草稿，停止后续动作 |

不增加 `BLOCKED`、`DECISION_REQUIRED`、`REJECTED` 等持久状态。停止原因写入状态摘要即可。

整体流程为：

```text
锚定 PR 与授权
→ 第一性原理需求门禁
   ├─ STOP：评论或起草评论，停止
   └─ PASS：继续
→ 复核已有 review
→ 独立代码 review
   ├─ PASS：继续最终验证
   ├─ FIX：披露 → TDD 修复 → 重新独立 review
   └─ STOP：评论或起草评论，停止
→ 最终验证
→ 按授权合并和发布
→ 另行授权后 cleanup
```

## 6. Phase 0：锚定现场和授权

开始任何判断前记录：

- repository、PR number/URL、base branch、base SHA、head SHA；
- `github_backend`、目标仓库访问结果和必要 PR 读取能力；
- 当前 main、PR Draft/mergeable/checks/review 状态；
- PR body、关联 Issue、spec/plan 和验收标准；
- 本地 worktree、branch、HEAD、脏文件及排除范围；
- 用户已授权的动作：只读 review、代码修复、PR 评论、push、合并、tag/Release、生产操作、cleanup。
- 当前 Codex 任务所需的运行期子 Skill 可用性；缺失项和对应停止阶段。

授权按动作解释：

- “修复所有确认的问题”授权 `FIX` 中的范围内代码和测试修复，不授权核心接口、Schema、新依赖、产品语义或跨模块扩张。
- “没问题就合并发布”只在全部门禁通过后授权普通合并和项目既有正式发布流程，不授权 force-push、移动 tag、生产安全变更或 cleanup。
- “需求不合理就在 PR 评论”授权该次运行发布需求门禁评论；没有同类表达时只生成评论草稿。
- 已取得的明确授权不重复询问；不能从一个动作推断另一个动作。

多个 PR 排序是可选的 Phase 0 子流程。排序只使用现场依赖、重叠文件、Draft、base/head、冲突和风险证据；每合并一个 PR 后，剩余 PR 必须重新锚定，旧顺序仅作为候选。

## 7. Gate 1：第一性原理需求审查

Gate 1 在详细实现 review 之前运行。允许为判断需求读取必要的现有行为、契约和仓库上下文，但不得先研究如何修好当前实现，再反向合理化需求。

### 7.1 需求证据优先级

1. 用户明确需求或已批准的方案/plan。
2. PR body 链接的 Issue、PRD、RFC、spec 和验收标准。
3. 仓库规则、现有公共契约、真实调用方和可观察基线行为。
4. PR 标题、提交信息和代码命名只能作为线索。

证据相互冲突时不得自行选择更方便实现的一边。

### 7.2 审查问题

至少回答：

- 要解决的问题是否真实存在，受影响对象和当前基线是什么？
- 目标是否与项目方向、公共契约和已有不变量兼容？
- 验收条件是否明确、可验证且不互相矛盾？
- PR 是否解决了声明的问题，还是把范围替换成另一件事？
- 新增复杂度、迁移和行为风险是否由当前需求产生？
- 什么事实或反例可以推翻“该需求合理”的结论？

### 7.3 门禁结果

`PASS` 需要同时满足：目标合理、关键证据充分、约束和验收可执行。Gate 1 不负责宣布技术方案已经完美，只证明可以进入实现审查。

以下任一条件进入 `STOP`：

- 问题不存在或现有机制已经满足目标；
- 目标与核心约束或公共契约冲突；
- 验收条件不可验证或互相矛盾；
- 关键证据缺失，答案可能改变需求、范围或方案；
- PR 实际解决对象与声明需求错位；
- 收益无法支持新增复杂度、迁移或不可逆风险。

证据不足使用 `Q`，不得假装已经证明需求错误。`Q` 同样是硬门禁：获得明确回答并形成可验证需求后，必须重新读取最新需求证据并重跑 Gate 1。

### 7.4 PR 评论

Gate 1 的 `STOP` 评论包含：

1. 结论：需求审查已停止；
2. 使用的 PR head 和需求来源；
3. 已证实的不合理点，或 blocking `Q`；
4. 对范围、实现或用户的具体影响；
5. 作者需要回答或修改的内容；
6. 明确说明 Gate 1 通过前不进入实现 review。

有评论授权时使用本轮锁定的 GitHub 后端发布并回读；无授权时输出同内容草稿。作者更新需求后不能从后续阶段续跑，必须从 Phase 0 和 Gate 1 重新开始。

## 8. Phase 2：复核已有 review

1. 读取 thread-aware review 状态，区分 unresolved、resolved、outdated、informational 和 duplicate。
2. 对每条结论检查证据、可达路径、影响、现有控制和修复是否覆盖根因。
3. 分别记录：成立且已正确修复、成立但修复不完整、不成立、证据不足、已过期。
4. 不把已有 reviewer 的结论并入独立 review finding 数量，也不因评论已 resolved 就认定修复正确。
5. PR 没有可找到的 review 证据时明确标记覆盖缺口，不从提交名称猜测评论原文。

该阶段发现需求或方案问题时返回 Gate 1；发现需要人工选择的 reviewer 建议时进入 `STOP`；其余已授权问题可作为后续独立 review 的输入，但不能替代独立 review。

## 9. Phase 3：独立代码 review 与修复门

使用 `code-change-review` 对当前 immutable base/head 独立审查。严重度和 merge readiness 完全沿用该 Skill：

- `P0/P1` 均阻止合并；
- blocking `Q` 或必要验证缺失时不能判断可以合并；
- `P2` 默认不阻止合并。

将结论映射为三种状态：

### 9.1 `PASS`

- 没有 `P0/P1` 或 blocking `Q`；
- 必要验证已完成；
- 只有 `P2`、non-blocking `Q` 或明确不影响本次合并的覆盖边界。

`P2` 是否修复取决于用户要求和修复成本；不为了形式上的零 finding 扩大范围。

### 9.2 `FIX`

同时满足以下条件时允许进入 `FIX`：

- finding 已由代码证据或可复现行为证明；
- 根因和直接修法明确；
- 修改仍在已批准需求和原 PR 范围内；
- 不改变核心接口、数据库 Schema、依赖或产品语义；
- 不产生新的跨模块或不可逆外部行为；
- 用户已经授权修复所有确认问题或该 finding。

进入 `FIX` 前必须先披露 finding ID、影响、根因、修复范围和验证方式。随后使用调试与 TDD 流程；完成后重新锚定 head 并重跑独立 review，不能直接进入发布。

### 9.3 `STOP`

以下情况进入 `STOP`：

- 任一 `P0`；
- blocking `Q` 或必要证据缺失；
- 核心接口、Schema、新依赖、产品语义、跨模块扩张或破坏性行为需要决策；
- 存在多种合理修法且长期行为不同；
- 修复明显超出原 PR；
- 实现暴露出需求或方案本身错误，此时回到 Gate 1，而不是给错误需求打补丁。

`STOP` 时使用本轮锁定的 GitHub 后端评论 finding、证据、影响、建议选项和需要的决定；没有评论授权时生成草稿。不得修改代码、push、合并或发布。

### 9.4 防止静默修复

- `FIX`：修复前在会话中披露；修复后在有评论授权时发布一条汇总，记录 finding、修复提交和验证结果。
- `STOP`：在有评论授权时立即评论并停止。
- 所有修复在最终报告中保持 finding → commit/diff → test 的追踪关系。

## 10. 最终验证、合并、发布和清理

只有最新一次独立 review 为 `PASS` 才能进入最终验证。进入发布前确认：

1. PR body、base/head、已有 review 和 checks 已重新读取；
2. PR 已基于所需的最新 main 解决冲突；
3. 针对性测试和仓库要求的完整门禁通过；
4. 测试时的 Git tree 与待合并 tree 相同，或存在可验证的 tree identity；
5. 没有未解决的 `P0/P1`、blocking `Q` 或必要验证缺口；
6. 用户已经授权对应 push、合并和发布动作。

随后调用 `finishing-a-development-release`。新 Skill 不另建 tag、Release、provider 回读或 cleanup 规则。

合并前 main 或 PR head 发生变化时，至少重新执行：Phase 0 现场锚定、变更范围影响判断、受影响的 review 与必要验证。需求或方案发生变化时必须从 Gate 1 重跑。

cleanup 始终使用独立授权。成功合并和发布不自动授权删除 worktree、本地分支、远端分支或备份 ref。

## 11. 状态摘要与恢复

不建设持久化状态数据库。每次阶段结束只维护一份简短摘要：

```text
PR / base SHA / head SHA
GitHub backend and capability result
Current phase
State: PASS | FIX | STOP
Requirement sources
Review findings and questions
Evidence and verification tree
Granted actions
Stop reason or next action
```

恢复旧会话时先现场回读。任何 SHA、需求、评论、checks 或 main 状态变化都可能使旧摘要失效；摘要只能用于定位，不是当前事实来源。

## 12. v0.1 文件范围

```text
skills/review-and-release-pr/
├── SKILL.md
└── agents/openai.yaml
tests/
└── test_review_and_release_pr_skill.py
```

- `SKILL.md` 只保留触发、复用契约、核心流程、三状态门禁和授权边界。
- `agents/openai.yaml` 提供 UI 名称、短描述和默认 prompt。
- 契约测试覆盖目录、frontmatter、正反路由和必须出现的编排契约，但不以逐句匹配代替 Agent 行为验证。
- 契约测试明确 v0.1 为 Codex-only、禁止 `--tool all`，并覆盖缺少阶段依赖时进入 `STOP`、不得复制或静默跳过子 Skill。
- 首版不创建 `scripts/`、`references/`、`assets/`、README 或持久化状态文件。

写 `SKILL.md` 前先用不加载本 Skill 的新任务运行压力场景并记录基线缺口；如果现有能力已经稳定满足完整契约，则停止新增重复 Skill。实现后使用新任务重跑相同场景，并在只读、评论草稿模式下连续完成两个真实 PR 前向验证，才能激活到 Codex。前向验证不得修改 PR、代码、Git refs 或发布状态。

连续两个真实 PR 前向验证后，如果仍重复手写相同的 PR 快照采集逻辑，再单独评估脚本；不能预先增加 provider 或状态机框架。

## 13. 验收标准

1. 普通只读 code review、comment-only 和 release-only 请求不会误触发本 Skill。
2. v0.1 只激活到 Codex target；任何交付说明都不宣称支持其他 Agent 工具。
3. 当前阶段的必需子 Skill 缺失时进入 `STOP`，不得现场复制、跳过或替代该 Skill 的专业流程。
4. PR 需求不合理或关键证据不足时，流程停在 Gate 1，并按授权发布评论或生成草稿。
5. Gate 1 未通过时不进入详细代码 review、修复、合并或发布。
6. 已有 review 复核与独立代码 review 输出分开，不能互相替代。
7. 独立 review 的 `P0/P1` 一律阻止合并。
8. 已授权且修法明确的范围内问题可进入 `FIX`；修复前披露，修复后重新独立 review。
9. 核心接口、Schema、新依赖、产品语义或超范围修复进入 `STOP`。
10. `STOP` 后不执行代码或外部状态变更；只有用户解决问题后才从正确阶段重新开始。
11. Connector 能读取身份但无法访问目标私有仓库、而 `gh` 可以访问时，本轮锁定 `gh` 并继续，不误报掉登录。
12. Connector 和 `gh` 都无法访问目标仓库时进入 `STOP`，不得自动改变认证或安装状态。
13. 最终发布复用现有 release Skill，并证明验证 tree、合并 tree 和 tag 目标一致或等价。
14. 合并、发布、PR 评论和 cleanup 授权保持相互独立。
15. 不加载本 Skill 的压力基线至少暴露一个已批准流程缺口；加载后相同场景关闭该缺口，且两个真实 PR 的只读前向验证通过后才允许 Codex 激活。

## 14. 设计取舍

选择独立薄编排 Skill，而不是扩展现有 Skill：

- 扩展 `technical-proposal-review` 会让无正式方案的 PR 无法使用，并混入代码和 GitHub 写操作。
- 扩展 `code-change-review` 会破坏其只读合同。
- 扩展 `finishing-a-development-release` 会让尚未完成的 PR 过早进入发布语义。

选择三状态而不是完整工作流引擎：

- `PASS / FIX / STOP` 足以表达继续、自动修复和人工决策；
- 阻断原因、finding 和授权放在摘要中，不需要为每类原因新增状态；
- 保留复用边界和证据门禁，比增加状态数量更重要。

首版接受的限制：

- 不跨会话持久化状态；
- 只支持 Codex，不承诺跨工具可移植性；
- 不保证所有 Git provider 都能自动评论；
- 不自动识别所有项目的需求文档来源；
- 不将一次真实 PR 成功视为已经覆盖全部触发边界。
