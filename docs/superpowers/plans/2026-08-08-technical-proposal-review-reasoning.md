# Technical Proposal Review 推理增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用最少规则稳定加入第一性原理和对抗性审查，同时降低强制量化、严重级别膨胀和低风险误报。

**Architecture:** `SKILL.md` 只负责调用三条横切规则和 P0/P1 出口门；规则正文放在 always-on rubric；复用现有 13 个维度和历史风险模式。

## Task 1: RED 与 A/B

- [x] 建立定量选型、定性安全、迁移失败、低风险四类场景。
- [x] A/B 每类各运行 5 个独立样本。
- [x] 记录关键命中率、强制量化率、误造 P0/P1、finding 数和输出长度。
- [x] 针对迁移严重级别膨胀和完整 Skill 低风险 P1 做最小 REFACTOR 并复测。

## Task 2: 最小实现

- [x] 将 `Decision Reasoning Protocol` 替换为第一性原理、对抗性审查、证据控制三条规则。
- [x] 数值阈值仅用于定量决策。
- [x] 增加 P0/P1 出口门，要求证明现有控制和可逆性不足。
- [x] 不新增参考文件、依赖或执行阶段。

## Task 3: 边界修复

- [x] 让 eval 自包含并消除回流表单冲突；补充 3 个回归场景。
- [x] 反馈写盘改为明确授权后执行，并增加脱敏与伪反馈边界。
- [x] 修正 3 个跨领域风险模式的 scope。
- [x] 移除 accepted feedback 中的真实提案 URL。

## Task 4: 验证

- [x] 最终低风险完整回归：5/5 通过，0/5 P0/P1。
- [x] 最终关键风险完整回归：Redis、鉴权、迁移 3/3 保持命中。
- [x] `quick_validate.py`：`Skill is valid!`
- [x] `jq empty` 与 eval ID 唯一性检查通过。
- [x] accepted YAML：5/5 可解析；accepted feedback 无真实 URL。
- [x] 仓库 unittest：275/275。
- [x] `git diff --check`。
