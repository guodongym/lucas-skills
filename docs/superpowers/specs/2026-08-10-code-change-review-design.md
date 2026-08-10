# Code Change Review Skill 设计

状态：设计已完成，待书面 Review

## 结论

新增独立 Skill `code-change-review`，用于对已经实现的代码变更做只读、证据优先的缺陷审查，并判断变更是否具备合并条件。

该 Skill 与 `technical-proposal-review` 共享三条推理规则：第一性原理、风险触发的对抗性审查、证据控制。两者不共享评审对象、详细 rubric、证据来源、严重级别语义或最终裁决：

- `technical-proposal-review` 在编码前判断方案是否完整、合理、可实施，并为人工复审准备重点。
- `code-change-review` 在编码中或合并前判断实际代码是否引入可达缺陷、回归或未受控风险，并给出 merge readiness。

第一版保持最小：不新增脚本、外部依赖、静态分析服务、红队 Agent、自动修复或 GitHub 写操作。

## 要解决的问题

当前已加载的 review 能力分别覆盖审查时机、独立 Agent 委派、评审意见处理、过度工程检查和技术方案审查，但缺少一个可以直接审查 working tree、staged diff、commit range、分支或 PR 的通用代码变更审查 Skill。

没有专用 Skill 时，代码审查容易出现四类不稳定行为：

1. 只复述 diff，没有追踪调用链、状态变化和外部副作用。
2. 使用通用检查清单制造缺少代码证据的建议或严重问题。
3. 混入无关 working-tree WIP，或没有明确 base/head，导致结论范围不可靠。
4. 把未运行、无法访问或仅凭推测的结论写成已验证缺陷。

新 Skill 必须把审查从“泛泛评价代码质量”收紧为“证明当前变更包含可达、具体、有影响的缺陷，或者明确说明未发现此类证据”。

## 目标与非目标

### 目标

1. 支持 working tree、staged changes、commit range、当前分支和 PR 五类常见输入。
2. 在审查前锚定 cwd、branch、HEAD、base/head 和 working-tree 状态。
3. 从变更文件追踪到调用方、数据状态、协议边界、外部副作用和直接测试。
4. 始终使用第一性原理还原基线行为、不变量和新增假设。
5. 对高风险改动执行可达失败链分析，不对所有改动机械运行完整红队流程。
6. 通过统一 evidence gate 校准 `P0/P1/P2/Q`，禁止严重级别膨胀。
7. 默认只读；没有证据时 clean no-op，不为显示工作量制造 findings。
8. 输出结论能直接支持“是否合并、先修什么、哪些仍未验证”的判断。

### 非目标

- 不评审 RFC、PRD 或技术方案正文；这仍由 `technical-proposal-review` 负责。
- 不处理已有 GitHub review threads；这仍由 `gh-address-comments` 负责。
- 不实现修复、不改测试、不发 GitHub 评论、不 resolve thread。
- 不代替 CI、lint、typecheck、静态分析、分支保护或人工审批。
- 不设跨仓库固定覆盖率、圈复杂度、性能或代码行数门槛。
- 不审查整个仓库的存量技术债；只审查用户指定的变更范围及其必要影响面。
- 第一版不维护历史 finding 案例库和用户反馈回流体系；真实使用证明有需要后再设计。

## 与 Technical Proposal Review 的边界

| 维度 | `technical-proposal-review` | `code-change-review` |
| --- | --- | --- |
| 使用阶段 | 编码前 | 编码中或合并前 |
| 必要输入 | 方案、RFC、PRD 等正式文档 | working tree、diff、commit range、分支或 PR |
| 核心问题 | 方案是否完整、合理、可实施 | 实现是否产生可达缺陷或回归 |
| 主要事实来源 | 方案正文、现状说明、历史案例 | 代码、调用链、测试、Git 历史、可复现行为 |
| 第一性原理对象 | 问题、目标、约束、选型、替代方案 | 基线行为、不变量、状态转换、外部副作用 |
| 对抗性审查对象 | 方案是否遗漏失败、检测、止损和恢复设计 | 失败是否能沿当前实现真实发生 |
| `Q` 的含义 | 作者需要补充设计决策或证据 | 需求、范围或运行证据不足，暂时无法确认缺陷 |
| `P0/P1` 的含义 | 方案不适合进入最终人工复审或实施 | 当前实现不应合并 |
| 最终裁决 | 是否准备好进入人工复审 | 是否准备好合并 |
| 主要整改动作 | 补方案、补决策、补验收条件 | 改代码、补测试、修兼容或恢复逻辑 |

方案或 plan 可以作为 `code-change-review` 的可选需求依据，但不能成为强制输入。没有正式方案时，应从用户要求、现有行为、测试、接口契约和仓库规则还原基线。

混合输入按“被裁决对象”路由：

- 用户要判断方案是否完整、合理或可实施时，使用 `technical-proposal-review`。
- 用户要判断代码是否正确或可以合并时，使用 `code-change-review`，方案只作为需求依据。
- 用户明确要求同时评审方案和实现时，分别运行两个 Skill，输出两个独立结论，不用一套严重级别同时裁决两类对象。

两个 Skill 各自保留一份简短的三条推理规则，不建立跨 Skill 文件依赖。这样可保持独立安装、独立演进和明确触发。

## 触发契约

Skill 名称固定为 `code-change-review`。实现时 frontmatter `description` 应覆盖下列语义：

> Use when the user asks to review implemented code changes in a working tree, staged diff, commit range, branch, or pull request for defects, regressions, risk, test gaps, or merge readiness. Perform a read-only, repository-grounded review with file/line evidence and verified-versus-unverified conclusions. Skip proposal/RFC/PRD review, handling existing reviewer comments, debugging without a change scope, whole-repository audits, and implementation or fixes.

正向触发示例：

- “Review 一下当前分支，看看是否有 bug。”
- “深度 review 这个 PR，重点看数据语义和负面风险。”
- “检查 staged changes 是否可以合并。”
- “Review `base..head` 这几个提交。”
- “看看这个 diff 是否破坏兼容性，给出 file/line 证据。”

负向触发示例：

- “初审这份技术方案。” → `technical-proposal-review`
- “修复 PR 上所有 reviewer comments。” → `gh-address-comments`
- “排查生产环境为什么超时。” → 调试流程
- “审计整个仓库有没有过度工程。” → whole-repo 或专项 audit
- “按这个 plan 开始实现。” → 实现流程

## 输入和范围解析

### 输入优先级

1. 用户显式给出的 base/head、commit range、PR 或文件范围。
2. 用户明确指定的 staged、unstaged 或 working-tree changes。
3. 当前分支相对其明确基线的变更。
4. 仍无法唯一确定时，先完成所有安全的只读解析，再询问一个会改变审查结论的范围问题。

不得静默选择一个可能改变结论的基线。不得把当前工作区的无关 WIP 自动并入已提交变更的结论。

### 五类输入的确定性快照

| 用户输入 | 默认包含 | 默认排除 | base/head 或快照规则 |
| --- | --- | --- | --- |
| `staged` | index 中的 tracked 变更 | unstaged、untracked、ignored | `HEAD` 对 index |
| `unstaged` | working tree 中相对 index 的 tracked 变更 | staged、untracked、ignored | index 对 working tree |
| `working tree` / “全部未提交改动” | staged、unstaged、非 ignored 的 untracked 文件 | ignored 文件 | `HEAD` 对当前未提交快照；分别标明三类来源 |
| commit range | 用户给出的两个端点及其间变更 | range 外提交和全部未提交改动 | 使用解析后的不可变 commit SHA；双点/三点语义按用户原表达保留 |
| 当前分支 | 从分支基线到当前 `HEAD` 的已提交变更 | 全部未提交改动 | 显式 base 优先；其次使用已解析 PR base；再次使用远端默认分支的 merge-base；仍不唯一则询问 |
| PR | 现场读取的 PR base/head SHA 和对应 diff | 本地未提交改动、PR head 之后的新提交 | 以远端 PR 元数据为准；本地对象只有在 SHA 一致时才作为证据 |

显式文件范围用于收窄上述快照，取“版本范围与文件范围的交集”，不能把范围外代码写进 finding。为理解调用链可以只读范围外代码，但它只作为上下文，除非缺陷由本次范围内变更引入，否则不形成当前审查 finding。

读取 untracked 文件前先遵循仓库的 ignore、秘密信息和本地配置规则；不得为了审查读取已忽略的凭据或私有配置。若非 ignored untracked 文件仍无法安全分类，列为排除项并说明覆盖缺口。

PR 审查不得默认执行 `git fetch`。优先使用只读的 GitHub/API/`gh pr diff` 数据；如果本地缺少与远端 SHA 一致的代码对象，导致调用链或测试无法验证，明确标记未验证。需要 fetch、临时 clone 或其他持久化本地数据时，先说明必要性并取得授权。

### 审查锚点

开始审查时记录并在输出中概括：

- repository/cwd
- 当前 branch 或 detached HEAD
- 当前 HEAD
- base/head 或 staged/unstaged 范围
- working tree 是否包含范围外变更
- 需求、方案或 plan 是否存在及其使用方式

PR 元数据、远端状态、CI 状态和生产行为属于易变信息；需要使用时必须现场读取。无法读取时标记未验证，不能由本地 diff 推断远端或生产结论。

## 核心工作流

### 1. 锚定范围并保持只读

确认审查对象、基线和排除项。使用 `git status`、`git diff`、`git log`、`git show`、`git merge-base` 等只读命令。默认不得修改 working tree、index、HEAD、branch、PR、issue 或外部系统。

这里的只读指被审查代码、Git index/refs 和外部系统状态保持不变。验证命令只有通过以下安全门才可执行：

1. 先记录 `HEAD`、refs 和 staged/unstaged/non-ignored-untracked 状态。
2. 命令是仓库已有且已知不会格式化代码、安装或升级依赖、执行迁移、发布、发送消息或写生产/共享服务。
3. 预期写入仅限工具产生的 ignored 缓存、构建产物或操作系统临时目录。
4. 命令结束后回读 source/index/ref 状态；除允许的 ignored 临时产物外必须与基线一致。

不得清理审查前已经存在的 ignored/untracked 内容。无法确认副作用的测试、需要启动或修改外部资源的检查、`git fetch` 和其他 Git 写操作均跳过并标记未验证；不要为了满足验证要求越过只读边界。

### 2. 还原需求和基线行为

按可信度使用以下来源：

1. 用户明确要求和已批准的方案/plan。
2. 仓库内 `AGENTS.md`、接口契约、schema、迁移约束和现有测试。
3. 变更前代码和 Git 历史表达的现有行为。
4. 命名、注释和惯例只能作为线索，不能单独证明需求。

如果需求证据互相冲突，输出 `Q` 或范围限制，不自行选择更方便的解释。

### 3. 从 diff 追踪实际影响

先读完整 diff 和变更统计，再按风险追踪必要上下文：

- 变更函数、类型、字段或配置的调用方和消费者。
- 输入、状态转换、持久化、缓存、队列、网络调用和用户可见输出。
- 公共 API、事件、序列化、存储格式、迁移和混合版本兼容边界。
- 错误处理、重试、幂等、事务、并发、超时、取消和清理路径。
- 与改动直接对应的单元、集成、契约或回归测试。

影响面由真实引用和行为决定，不由文件数量决定。高调用量共享代码和窄范围不可逆副作用都可以是高风险改动。

### 4. 应用三条横切推理规则

#### 第一性原理：始终执行

对每个实质改动回答：

- 变更前的可观察行为是什么？
- 哪些不变量必须继续成立？
- 变更引入了什么新假设？
- 从输入到状态或外部副作用的实际路径是什么？
- 什么代码、测试或反例能够推翻“实现正确”的判断？
- 新增复杂度是否由明确需求产生？

第一性原理用于还原事实和约束，不要求所有定性问题提供伪造的数值门槛。

#### 对抗性审查：按风险加深

以下改动默认进入深度对抗性审查：

- 鉴权、权限、密钥和敏感数据。
- 数据写入、删除、迁移、同步和一致性。
- 并发、事务、队列、重试、幂等和崩溃恢复。
- 外部调用、支付、发布等不可轻易撤销的副作用。
- 公共 API、协议、事件、schema、存储格式和兼容性。
- 高调用量或高爆炸半径的共享代码。

为候选问题追踪：

```text
前置条件
→ 触发事件
→ 实际代码路径
→ 错误状态或副作用
→ 用户、数据或系统影响
→ 检测方式
→ 止损与恢复
```

优先尝试重复、乱序、过期、恶意或边界输入，并检查并发执行、部分成功、依赖超时、进程崩溃、数据消失、混合版本和回滚后的状态。

只有前置条件和代码路径可达时，失败链才成为 finding。合理但尚无证据的风险写为 `Q` 或未验证范围。低风险 UI、测试、文档和局部重构只检查相关不变量，不机械生成攻击场景。

#### 证据控制：统一出口

候选 finding 必须经过同一个 evidence gate：

- 是否有具体代码、测试、历史或可复现行为支持？
- 失败路径是否在本次变更和现实输入下可达？
- 影响是否具体，而不是抽象的“可能有风险”？
- 现有校验、隔离、测试、回滚或降级能否控制影响？
- 修复是否直接针对根因？

同根因 findings 合并。证据不足使用 `Q`；已有控制且影响窄、可独立回滚时降级为 `P2` 或不输出。

### 5. 运行针对性验证

先识别仓库现有的测试、lint、typecheck 和构建入口，再运行能够证实或推翻候选结论的最小检查。遵循仓库既有命令，不为使测试通过而修改依赖或环境。

验证结果区分：

- `已验证`：本轮实际运行或由直接代码证据完整证明。
- `未验证`：受环境、权限、外部服务或时间限制，未完成必要验证。
- `不适用`：该结论不依赖对应验证面。

测试通过不能单独证明没有业务缺陷；测试无法运行也不能自动证明产品有缺陷。

### 6. 校准严重级别

- `P0 阻塞`：当前变更包含已证实、可达且影响严重的安全、数据损坏、不可恢复副作用或广泛不可用风险，现有控制和可逆性不足，禁止合并。
- `P1 重要`：当前变更包含已证实或由完整代码路径证明的功能回归、协议破坏或错误状态，会造成实质影响，应在合并前修复。缺少测试只能作为风险控制不足的证据，不能单独构成 `P1`。
- `P2 建议`：问题真实但影响受控、范围窄、可独立回滚，或属于与本次变更直接相关的质量缺口；不得把纯个人风格偏好写成 `P2`。
- `Q 追问`：需求、范围、环境或运行证据不足，必须补充信息才能判断是否存在缺陷或如何定级。

任何 `P0/P1` 都必须说明失败路径、实际影响，以及为什么现有控制和可逆性不能充分控制该影响。无法说明时降级为 `P2/Q`。

### 7. 给出 merge readiness

`Q` 不属于已确认 finding。将问题分为：

- `blocking Q`：答案可能改变审查范围、需求基线或产生 `P0/P1`，在回答前不能可靠判断是否合并。
- `non-blocking Q`：答案只影响 `P2`、后续优化或已明确不在本次合并门内的范围。

必要验证是指：缺少该验证时，无法确认一个候选 `P0/P1` 是否成立，或无法确认关键行为/契约是否被保持。与当前合并判断无关的完整测试矩阵、生产观察和长期指标不属于必要验证，但必须列入覆盖边界。

按下表给出四种结论之一：

| 条件 | Merge readiness |
| --- | --- |
| 存在 `P0/P1` | `Not ready` |
| 不存在 `P0/P1`，但存在 blocking Q、范围不唯一或必要验证未完成 | `Unable to determine` |
| 不存在 `P0/P1` 和 blocking Q，必要验证完成，只有 `P2`、non-blocking Q 或不影响合并的覆盖缺口 | `Ready with non-blocking follow-ups` |
| 不存在 confirmed findings 或未决问题，必要验证完成 | `Ready` |

结论只覆盖已声明的审查范围，不代表整个仓库、所有运行环境或生产状态都已验证。

## 输出契约

输出以结论和 findings 为主，不要求先写优点，也不输出泛化代码质量建议。

每条 confirmed finding（`P0/P1/P2`）必须包含：

- 稳定 ID：`P0-01`、`P1-01` 或 `P2-01`
- 精确位置：文件和行号；无法给行号时说明原因
- 当前行为或缺失证据
- 可达或可复现路径
- 实际影响
- 现有控制和可逆性判断
- 直接整改建议
- 验证状态

每条 `Q` 单独包含：

- 稳定 ID：`Q-01`
- 需要回答的问题
- 当前缺失的证据
- 该答案会影响的范围、严重级别或 readiness 判断
- 获取答案或完成验证的方式
- `blocking` / `non-blocking`

报告固定包含：

1. 结论与 merge readiness。
2. 审查范围：repo、branch、HEAD、base/head、排除项。
3. 按严重级别排序的 confirmed findings。
4. 与 findings 分开的 questions。
5. 验证：实际运行的命令和结果。
6. 覆盖边界：未检查或无法验证的部分。

没有 confirmed finding 时，明确输出：

> 结论：未发现有代码证据支持的缺陷。

随后仍列出 questions、审查范围、已完成验证和未验证边界。不得为了填满模板制造测试建议、重构建议或假设性问题。

## 与现有能力的组合

- `requesting-code-review` 决定何时委派独立 reviewer；被委派 reviewer 使用本 Skill 的审查契约。
- `receiving-code-review` 用于验证并处理本 Skill 已产生的反馈。
- `gh-address-comments` 用于读取和处理 GitHub 上已有 review threads。
- `ponytail-review` 可作为只检查过度工程的独立补充，不混入正确性 findings。
- `technical-proposal-review` 评审实现前方案，并可为本 Skill 提供可选的需求和验收依据。

各能力保持独立触发。`code-change-review` 不依赖另一个 Skill 必须同时加载。

## Skill 文件结构

```text
skills/code-change-review/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── review-rubric.md
│   └── output-template.md
└── evals/
    ├── evals.json
    └── fixtures/
```

- `SKILL.md`：触发边界、只读约束、范围解析、核心工作流和三条横切规则。
- `agents/openai.yaml`：只包含 display name、short description 和 default prompt；不声明新工具或依赖。
- `review-rubric.md`：正确性、数据语义、错误处理、并发、安全、兼容性、性能、测试和运维影响等详细维度。
- `output-template.md`：finding 字段、严重级别、merge readiness、clean no-op 和覆盖边界格式。
- `evals.json`：自包含的触发和行为评测及其断言。
- `fixtures/`：仅包含评测需要的最小源文件、diff、需求和预期基线，不包含真实仓库秘密、完整项目副本或嵌套 `.git`。

第一版不创建 `scripts/`、`assets/`、README、案例库、反馈目录或独立 Agent。只有重复出现且需要确定性执行的机械步骤，才在后续版本考虑脚本。

## 验证设计

### 触发评测

固定覆盖 10 个单一意图提示：5 个正向、5 个负向。另增加 2 个混合输入路由提示，不计入“无重叠”断言。验收要求：

- 正向提示全部触发 `code-change-review`。
- 方案评审、反馈处理、调试、实现和 whole-repo audit 提示均不触发。
- 10 个单一意图提示与 `technical-proposal-review` 的触发结果无重叠。
- 2 个混合提示按“被裁决对象”路由；明确要求双审时产生两个独立任务和结论。

### 行为评测

`evals/evals.json` 固定包含 12 个 behavior cases：4 个真实缺陷、与其一一配对的 4 个安全反例，以及 4 个范围/证据控制案例。

真实缺陷及其安全反例覆盖：

1. 双写或多步骤状态变更：定位崩溃窗口、数据影响和恢复缺口。
2. 鉴权或身份边界：定位可达绕过路径，不依赖安全关键词定级。
3. 公共 API、事件或存储格式变更：发现真实消费者兼容性回归。
4. 重试、并发或乱序：追踪重复副作用或状态覆盖的实际代码路径。

4 个范围/证据控制案例覆盖：

1. 空提交窗口：输出 clean no-op，不制造 finding。
2. 低风险可回滚重构：识别现有控制，产生 0 个 `P0/P1`。
3. 范围外 WIP：明确排除，不能污染 commit-range 结论。
4. 外部环境不可用：保持代码结论与运行结论分离，将后者标记未验证或 `Q`。

安全反例与对应缺陷只改变一个关键控制，例如事务边界、身份重注入、兼容别名或幂等键，用于证明 Skill 会评估现有控制而不是命中关键词。

`evals.json` 沿用仓库现有结构：顶层 `skill_name` 和 `evals`；每个条目包含稳定 `id`、`kind`（`trigger` 或 `behavior`）、`prompt`、`expected_output`、`files` 和可逐条判定的 `assertions`。触发和行为条目放在同一文件，fixture 由 `files` 引用。

### Finding 契约评测

自动或人工断言：

- 每个 `P0/P1` 都包含位置、可达路径、实际影响、控制/可逆性和整改建议。
- 不输出没有代码或测试证据的确定性缺陷。
- 不把纯风格、泛化最佳实践或固定指标写成阻塞问题。
- 未运行的测试不写成通过；环境失败不写成产品缺陷。
- 没有 finding 时结论明确，并保留验证和覆盖边界。
- 所有评测运行保持只读，不修改被审查仓库。

### 验证流程

实现阶段按以下顺序执行：

1. RED：在 Skill 缺失或最小骨架下运行 4 个缺陷案例及对应安全反例，保存未命中或误报证据。
2. GREEN：实现最小规则，使全部 12 个 behavior cases 通过逐条 assertions。
3. 触发测试：使用不显式点名 Skill 的新鲜上下文运行 12 个 trigger cases；从工具/Skill 加载记录判断实际路由，不能只根据最终措辞猜测是否触发。
4. 行为测试：使用显式 Skill 路径和新鲜上下文运行每个 behavior case；grader 只接收原始输出和 assertions，逐条记录 pass/fail，不接收预期 finding 的解释。
5. 只读测试：在一次性临时 fixture 中记录执行前后的 `HEAD`、refs、index、tracked 和 non-ignored-untracked 状态；除 case 明确允许的 ignored 缓存外必须一致。生产仓库和用户真实 WIP 不作为评测 fixture。
6. 回归：运行 Skill `quick_validate.py`、JSON/fixture 引用校验、仓库单元测试和 `git diff --check`。
7. Forward test：使用新鲜上下文审查至少一个真实但脱敏的 commit range，只提供原始代码范围和需求，不泄露预期 finding。
8. 复核 forward-test 输出是否满足只读、证据、严重级别和 clean no-op 契约。

本版本不新增持久化 eval runner；runner 采用 Skill Creator 的 fresh-context/subagent forward-test 流程，`evals.json` 是 case 和 oracle 的唯一来源。每次评测记录模型、Skill 版本、case ID、逐条 assertions 和原始输出路径，使结果可复核。若手工编排在实现中已经重复或无法可靠检查只读状态，再单独提议确定性 runner，不在本设计中预先增加脚本。

Forward test 只审查一次性 fixture 或脱敏材料，不访问生产系统，不修改用户真实仓库。若需要额外权限、长时间运行或外部写操作，必须先单独请示。

## 实施边界

实现应作为新增 Skill 完成，不修改 `technical-proposal-review` 的 rubric、案例库、反馈或输出语义。允许的相邻修改仅包括：

- 仓库级 Skill 索引或发现清单需要登记新 Skill。
- 新 Skill 所需的 eval 和结构校验。
- 为证明触发互斥而增加的最小测试夹具。

如果实现过程中发现必须引入依赖、修改 Agent Manager 核心接口、改变其他 Skill 的触发描述或建立跨 Skill 共享模块，应停止并重新评审设计，不在实现计划中默认扩张范围。

## 完成标准

只有同时满足以下条件，才可宣称 `code-change-review` 实现完成：

1. Skill 可被发现且 frontmatter 校验通过。
2. 10 个单一意图正向/负向提示不与 `technical-proposal-review` 重叠；混合提示符合“被裁决对象”路由规则。
3. 12 个 behavior cases 覆盖 4 个真实缺陷、4 个配对安全反例和 4 个范围/证据控制场景。
4. 所有 `P0/P1` 满足 evidence gate。
5. 低风险反例和空范围均产生 0 个 `P0/P1`。
6. 只读契约得到验证：被审查 source、index、refs 和外部状态不变；只有设计明确允许的 ignored 临时产物可以出现。
7. 仓库既有测试、结构化数据校验和 `git diff --check` 通过。
8. 至少一次 fresh-context forward test 通过，且未依赖泄露的预期答案。

设计文档获用户书面 Review 后，下一步使用 `writing-plans` 生成实施计划；在计划获批前不创建 Skill 文件。
