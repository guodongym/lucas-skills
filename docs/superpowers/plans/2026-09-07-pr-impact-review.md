# PR 影响审查增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已有代码审查与 PR 编排中识别架构冲击、范围越界和无必要能力，并输出证据化定级。

**Architecture:** `code-change-review` 的规则和模板是判断的唯一来源；`review-and-release-pr` 消费结果并保持原有状态与授权边界。复用现有 JSON 评测清单及 unittest，不添加运行器。

**Tech Stack:** Markdown、JSON、Python unittest、现有 PyYAML、独立评测 agent。

**Spec:** `docs/superpowers/specs/2026-09-07-pr-impact-review-design.md`

## Global Constraints

- 不增加独立 skill、评分系统、依赖、自动标签或审批平台。
- 不修改 Agent Manager，不推送、不发布、不激活到用户工具目录。
- 已有审查只读、外部写入授权和 P0/P1/P2 缺陷证据规则保持有效。
- 英文 skill 与评测沿用英文，设计和执行记录使用中文。

## Task 1：代码审查的影响与约束结论

**Files:** 修改 `skills/code-change-review/SKILL.md`、`references/review-rubric.md`、`references/output-template.md`、`evals/evals.json`、`tests/test_code_change_review_skill.py`；在现有 `evals/fixtures/` 增加本设计的 12 个原始案例。

**Interfaces:** 消费固定变更快照与已认可需求；输出 Impact level、Scope/architecture、独立约束问题和现有 Merge readiness。

- [ ] 写入 12 个自包含案例与预期断言。每个只提供该案例材料，不泄露 counterpart、预期答案或其他案例。
- [ ] 新增案例要求单元测试检查 ID 唯一、fixture 存在、安全反例对应真实问题；先运行并观察缺失案例失败。
- [ ] 对核心范围扩张案例以旧版 skill 做 5 次独立运行；保存原始输出并逐条人工判读，记录规则遗漏或证据判断失败。
- [ ] 实施设计定义的八维筛查、变更前可信基线、能力必要性、影响等级和范围结论；模板新增所需字段与合并条件。
- [ ] 以新版 skill 对同案例做 5 次独立运行，再执行其他新增与旧行为案例；按清单断言逐条评估，不把文本匹配当行为通过。
- [ ] 验证：`python3 -m unittest discover -s tests -p 'test_code_change_review_skill.py' -v`。

## Task 2：PR 编排消费结果并完成验证

**Files:** 修改 `skills/review-and-release-pr/SKILL.md`；执行结果追加到本计划，不创建独立报告体系。

**Interfaces:** 消费 Task 1 四种独立判断；沿用 `PASS / FIX / STOP` 与发布前验证。

- [ ] 用旧版 PR skill 对纯越界、批准后的高影响、关键依据缺失三种审查结果做隔离状态判断，记录基线差异。
- [ ] 在 Gate 1 引用同一必要性与约束判断；Phase 3 按 `Conforms / Violates / Needs decision` 映射状态；输出摘要增加影响和范围结论。
- [ ] 用新版复跑三种状态场景，验证越界无 Bug 仍 STOP、高影响符合约束可 PASS、缺证 STOP；不实际读写远端。
- [ ] 独立 reviewer 对照已确认设计检查最终差异；修正有依据的问题，定向重跑受影响检查。
- [ ] 验证：`python3 -m unittest discover -s tests -q`；对两个 skill 运行系统 skill-creator 的 `scripts/quick_validate.py`；`git diff --check`。
- [ ] 记录实际次数、失败原因、修复和覆盖边界；按仓库规范提交本次变更，保留分支供用户审阅。

## 设计与计划复核

已对照当前两个 skill、输出模板和既有 24 个评测条目自检。八维筛查、四种结论、无缺陷的越界阻塞和正常反例均有对应任务。用户已确认聊天设计并授权实施，计划只展开该范围，无新产品或架构决策。
