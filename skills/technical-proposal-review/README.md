# 技术方案评审 Skill

这个 skill 用于在人工正式评审前，对技术方案做第一轮初审。它会结合通用架构评审维度、业界成熟评审框架、历史人工评审沉淀出来的风险模式，以及持续回流机制，帮助更早发现方案里的重要风险。

它只负责初审，不负责最终拍板。最终是否通过仍然以人工评审为准。

## 适用场景

适合用在以下场景：

- 评审技术方案、架构设计、改造方案、迁移方案
- 复核已有 `评审意见` 是否完整、是否有遗漏
- 沉淀一次新的人工评审反馈，让 skill 后续更贴近你的评审偏好
- 校准某类方案的常见风险，比如认证、网关、审计、日志、多租户、容量、迁移、回滚、安全、可维护性

典型方案类型包括：

- 认证、授权、网关、身份透传
- 日志、审计、可观测性、平台能力推广
- 迁移、回滚、可靠性、容量、多租户隔离
- 开源组件改造、源码 patch、社区分叉风险、未来架构兼容性

如果输入方案里已经带有人工 `评审意见`，skill 可以把这些意见作为评审上下文或校准材料，但不能把已有评审意见当成方案正文证据来生成新问题。

## 输出内容

一次初审输出通常包含：

- 初审结论：`通过`、`需补充后再审`、`阻塞`、`建议转人工重点审`
- 输入范围：说明评审对象、正文来源、已有评审意见是否参与
- `P0`、`P1`、`P2`、`Q` 分级问题
- 每条问题的证据、影响、建议补充内容
- 通用架构检查覆盖情况
- 必要时引用历史相似案例
- 人工复审重点
- 用于后续回流的结构化反馈块

## 文件结构

```text
technical-proposal-review/
├── SKILL.md
├── README.md
├── evals/
│   └── evals.json
├── evaluations/
│   └── bootstrap-2026-04-26.md
├── feedback/
│   ├── accepted/
│   ├── pending/
│   └── rejected/
├── materials/
│   ├── historical-reviews/
│   │   └── index.md
│   └── private/
└── references/
    ├── case-bank.md
    ├── feedback-loop.md
    ├── industry-frameworks.md
    ├── output-preferences.md
    ├── output-template.md
    ├── review-rubric.md
    └── risk-patterns.md
```

## 文件职责

`SKILL.md` 是 skill 的真正入口文件。它定义触发条件、核心执行流程、评审范围、问题分级、历史材料使用方式、反馈回流要求和评测说明。

`README.md` 是给人看的维护说明。它解释目录结构和维护方式，但不应该变成第二套执行规则。真正影响评审行为的规则应该放在 `SKILL.md` 或 `references/` 里。

`references/review-rubric.md` 是每次评审都要覆盖的通用检查维度，包括背景目标、现状复用、方案选型、架构边界、迁移回滚、失败处理、安全、可观测性、容量、成本、可维护性、上线验证和文档完整性。

`references/risk-patterns.md` 存放从历史评审中沉淀出来的高频风险模式。它用于帮助识别具体问题，但不能在缺少方案证据时硬套结论。

`references/case-bank.md` 存放脱敏后的历史案例索引和可复用评审规则。这里应该只放通用模式、评审关注点和建议补充项，不放原始方案正文。

`references/industry-frameworks.md` 存放业界成熟评审框架的浓缩版，例如 Well-Architected、ATAM、SRE 等，用来补充历史案例没有覆盖到的通用架构质量维度。

`references/output-template.md` 定义初审报告的输出结构。

`references/output-preferences.md` 记录你偏好的表达方式、优先级判断方式和不喜欢的输出风格。

`references/feedback-loop.md` 定义回流用的 YAML 表单，以及反馈如何进入 `pending`、`accepted`、`rejected`。

`feedback/accepted/` 存放你已经确认采纳的反馈。这些反馈可以影响后续 skill 行为，也可以进一步沉淀到 `references/` 里。

`feedback/pending/` 存放还没经过你确认的反馈，比如模型自评、评测过程、其他 agent 提出的改进建议。这里的内容不能直接改写 skill 行为。

`feedback/rejected/` 存放你明确不采纳的反馈。保留它是为了避免后续重复采纳同类错误建议。

`materials/historical-reviews/index.md` 是公开、脱敏后的历史材料索引，只保留 case ID、领域标签和摘要说明。

`materials/private/` 是本地私有目录，已经被 git 忽略。这里可以放原始历史方案、本地文件映射、私有评测工作区等材料。别人没有这个目录时，skill 仍然应该可以正常使用，只是少了源材料级追溯。

`evals/evals.json` 存放评测用例和期望，用来验证 skill 是否真的改善了评审行为。

`evaluations/bootstrap-2026-04-26.md` 记录第一次盲测回放评估摘要。它应该保持脱敏，只保留评测结论和可公开的校准信息。

## 反馈回流流程

1. skill 每次评审后输出结构化反馈块。
2. 你可以标记漏判、误判、优先级调整、喜欢的评论、不喜欢的评论和措辞偏好。
3. 未经确认的反馈先进入 `feedback/pending/`。
4. 你确认采纳后，反馈进入 `feedback/accepted/`。
5. 你明确不采纳的反馈进入 `feedback/rejected/`。
6. 已采纳反馈可以继续沉淀到 `references/risk-patterns.md`、`references/case-bank.md` 或 `references/output-preferences.md`。

原则：模型、评测脚本或其他 agent 生成的反馈，必须先经过人工确认，不能直接改进 skill 行为。

## 隐私边界

可以提交：

- `SKILL.md`
- `README.md`
- 脱敏后的 `references/`
- 脱敏后的 `materials/historical-reviews/index.md`
- 只包含抽象规则的 `feedback/accepted/`
- `feedback/pending/.gitkeep` 和 `feedback/rejected/.gitkeep`
- `evals/evals.json`
- `evaluations/` 下脱敏后的评测摘要

不要提交：

- 原始方案正文
- 内部真实文件名和本地路径映射
- 可能包含方案细节的私有评测输出
- 租户名、内部域名、凭证、客户敏感信息
- `materials/private/` 下的任何文件

## 规则维护节奏

每 **5 次评审**（即 `feedback/accepted/` 新增 5 个文件后）做一次小整理，不需要重写，只做归并和标注。

### 需要检查的三件事

**1. `references/output-preferences.md` — Avoid 列表归并**

如果出现 3 条以上可以抽象为同一原则的具体条目，将它们合并为一条通用规则加括号示例，避免 Avoid 列表无限增长。

判断标准：这几条条目是否都在说"先检查 X 再决定是否输出"，只是 X 不同？如果是，归并。

**2. `references/risk-patterns.md` — 给新增模式补 Scope 标注**

每条新增模式在 `Trigger:` 前加一行：

```markdown
Scope: global | gateway | auth | logging-observability | multi-tenant-capacity | audit | migration
```

`global` 表示对所有方案适用；其他值表示只在对应领域标签匹配时激活。

**3. `references/risk-patterns.md` — 检查是否有分支逻辑可以外移**

若某条模式的 `Expected review` 出现了"若 A 则要求 X，若 B 则要求 Y"的条件分支，判断这个分支是否已被顶部的"通用前置检查"覆盖。若是，简化该模式，保留核心要求即可。

### 不需要在每次整理时做的事

- 不需要重写 `references/review-rubric.md`，它的 13 个维度基本稳定。
- 不需要清理 `feedback/accepted/`，历史归档保留用于追溯。
- 不需要更新 `references/case-bank.md`，案例追加即可，不用归并。

## 维护检查

更新后提交前建议运行：

```bash
python3 skills/skill-creator/scripts/quick_validate.py skills/technical-proposal-review
jq empty skills/technical-proposal-review/evals/evals.json
git diff --check
git status --short --ignored
```

还需要检查公开文件里是否误放了内部标识、原始文件名、密钥或敏感内容。源材料级追溯留在 `materials/private/`，可复用规则沉淀到可提交的 `references/`。
