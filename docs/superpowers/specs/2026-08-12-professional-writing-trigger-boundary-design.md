# professional-writing 触发边界设计

- 日期：2026-08-12
- 状态：用户已确认，自审通过（2026-08-12；无阻塞或重要问题）
- 基线：`main@4dae340`
- 范围：只校准 `professional-writing` 的触发职责，不改变正文写作流程

## 1. 问题与结论

当前 `description` 同时覆盖“方案与决策文档”和 `design doc`。当软件设计流程也会生成设计文档时，Agent 可能仅根据产物名称加载 `professional-writing`，让写作流程抢占本应由 Superpowers 承担的设计工作。

不能用“设计文档一律不触发”解决这个问题。`professional-writing` 的核心职责本来就包括从零撰写技术方案；把它降级为润色或校验工具，会破坏独立技术写作场景。

触发判断改为看用户当前的首要任务：

- 首要目标是产出、重写或完善给人阅读的正式技术文档时，使用 `professional-writing`，包括从零撰写技术方案。
- 首要目标是探索产品或软件行为、确定需求、架构与实现取舍时，使用相应设计工作流；不能仅因为该流程会生成 `spec`、`plan` 或 `design doc` 而加载 `professional-writing`。
- 用户显式指定 Skill 或执行顺序时，按用户指定的职责和顺序执行。

## 2. 第一性原理职责

`professional-writing` 的交付物是帮助读者理解、判断或行动的专业文档，而不是单纯经过润色的文字。因此它继续负责：

1. 明确读者、阅读目标和中心主张；
2. 从材料中区分事实、判断、推测与未知；
3. 组织方案、取舍、依据、条件与范围边界；
4. 从零起草、重写并复核正式文档；
5. 材料不足时追问、收窄结论或披露待确认项，不补造技术事实。

它不因为文档中包含技术判断就失去写作职责，也不因为其他流程会输出文档就自动取得该流程的设计职责。

## 3. 路由边界

| 用户的首要任务 | 路由 |
| --- | --- |
| “根据这些约束写一份数据库迁移技术方案，给架构委员会评审” | `professional-writing` |
| “帮我从零写一份技术方案；资料不够可以先问我” | `professional-writing` |
| “把这份已有技术方案改得更清楚、适合决策者阅读” | `professional-writing` |
| “一起设计帖子趋势功能，确定数据模型和实现路径” | `superpowers:brainstorming` |
| “按 Superpowers 流程完成设计并形成 spec” | `superpowers:brainstorming`；只有用户要求时再由 `professional-writing` 校验 |
| “评审这份已有技术方案是否合理、能否开发” | `technical-proposal-review` |
| “用 Superpowers 写，用 professional-writing 验证” | 严格按该顺序组合两个 Skill |

边界依据是用户要完成的工作，不是文档名称、是否存在未决问题或是否出现 `方案`、`spec`、`design doc` 等关键词。

## 4. description 调整原则

保留现有正向范围：

- 总结与汇报；
- 技术解释与专业文章；
- 方案与决策文档，包括从零撰写技术方案；
- 教程与操作指南；
- 已有正式文档的诊断与重写。

增加两个可观察边界：

1. 只有正式文档本身是当前主要交付物时，才因文档写作意图触发。
2. 其他设计、开发或治理流程仅把文档作为中间产物时，不因此触发；显式点名或显式编排除外。

不把 `professional-writing` 描述为仅用于“润色”“验证”或“设计完成后的最后一步”。

## 5. 验证设计

在现有内容评测之外增加触发路由评测，正向与近邻反例同时覆盖：

- 正向：从零技术方案、给定材料成稿、资料不足但明确要求正式方案、已有文档重写；
- 负向：软件功能设计、实现计划、已有方案评审、代码实现，以及仅在流程中顺带生成文档；
- 组合：用户显式要求 Superpowers 起草并由 `professional-writing` 验证；
- 关键词对照：正反用例都包含“技术方案”“设计文档”或 `design doc`，证明路由依据是任务意图而非关键词。

验证遵循 RED → GREEN：先用当前 `description` 记录截图场景和近邻用例的基线，再修改 `description`，随后重跑同一组用例。基础校验至少包括 `quick_validate.py`、评测清单结构检查、仓库测试和 `git diff --check`。

## 6. 变更范围

实施阶段只允许修改：

- `skills/professional-writing/SKILL.md` 的 frontmatter `description`；
- `skills/professional-writing/evals/` 下的触发路由评测；
- 验证评测结构所需的最小测试文件。

不修改正文写作流程、references、现有六个内容评测 fixture，也不新增依赖或运行时编排器。

## 7. 验收标准

1. 单独要求从零撰写技术方案时，`professional-writing` 仍应触发并走完整写作流程。
2. 只要求设计软件功能并形成 spec 时，不因文档产物误触发 `professional-writing`。
3. 显式要求“Superpowers 写、professional-writing 验证”时，两个 Skill 按指定顺序执行。
4. 评审已有技术方案继续路由到 `technical-proposal-review`。
5. `description` 保持触发条件导向，不摘要或复制正文工作流。
6. 现有内容写作能力和六个内容评测合同保持不变。
