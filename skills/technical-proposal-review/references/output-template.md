# Output Template

Use this structure for every first-pass review.

## 初审结论

结论：`通过` / `需补充后再审` / `阻塞` / `建议转人工重点审`

理由：用 1-3 句话说明最核心判断。不要写泛泛总结。

## 输入范围

- 评审对象：
- 方案正文来源：
- 已有评审意见：无 / 已作为参考 / 已在盲测中排除。
- 本次输出边界：区分“已有意见复核”和“本次新增发现”。

## 阻塞问题

| ID | 问题 | 证据 | 为什么重要 | 建议补充 |
|---|---|---|---|---|

Use this section only for `P0 阻塞` issues.

## 重要问题

| ID | 问题 | 证据 | 影响 | 建议补充 |
|---|---|---|---|---|

Use this section for `P1 重要` issues.

## 建议优化

| ID | 建议 | 证据 | 价值 | 建议调整 |
|---|---|---|---|---|

Use this section for `P2 建议` items. Omit when there are no useful `P2` items.

## 追问清单

| ID | 问题 | 为什么需要回答 |
|---|---|---|

Use this section for `Q 追问`.

## 通用架构检查

Summarize global rubric coverage. Prefer concise status lines:

- 已覆盖：
- 仍缺口：

## 历史相似案例

List matched cases only when the analogy helps explain the issue:

- `CASE-xxx`: 相似点；可借鉴的评审规则。

## 人工复审重点

List 2-5 items that require human judgment.

## 回流表单

Include the complete YAML block from `feedback-loop.md`. Do not replace it with a prose table.
