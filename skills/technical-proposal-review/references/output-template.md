# Output Template

Use the user's language. Lead with the decision and concrete reasons. A small review can be short prose; a larger one can use the structure below. Include each conclusion once and omit empty sections.

## 结论与范围

结论：`通过` / `需补充后再审` / `阻塞` / `建议转人工重点审`。

Explain the reason in 1–3 sentences, then identify the proposal/version, full or delta scope and relevant evidence boundary. A pass is review readiness, not final approval or completed implementation.

## 目标与方案判断

State the approved current-stage outcome, how a user/caller reaches it, what existing capability is reused and whether the additional behavior is necessary. Give a simpler alternative only when it has a concrete benefit; state any lost capability or changed business meaning. Use short prose or a compact table rather than repeating the proposal inventory.

## 发现与建议

List only supported P0/P1/P2/Q entries, most consequential first. Each contains:

- ID and priority.
- Proposal location or missing fact, separated from inherited reviewer claims.
- Reachable scenario and concrete effect; for P0/P1, why the existing controls do not contain it.
- Smallest correction or decision. For a question, name the affected conclusion/gate and the smallest evidence needed.

A table is useful for short entries; use paragraphs when a scenario needs explanation. Do not fragment one root cause across sections or inflate an uncertainty into a confirmed defect.

## 复审变化（有前轮时）

Close, retain or revise prior finding IDs. Explain whether a new issue was missed before, introduced by a revision, exposed by the baseline or caused by changed requirements. Describe actual independent review separately from self-review.

## 验证与待决定事项

Report only sources inspected or checks actually run; distinguish author claims, static reasoning, synthetic reproduction and real-system evidence. Name material coverage gaps and their stage: preflight, implementation, deployment or business acceptance. State which conclusion each gap affects.

Ask only decisions that cannot be resolved from available evidence and would change scope, acceptance or material consequences. Historical analogies appear only when useful. A clean review needs no empty P/Q tables, mandatory human-review list or calibration footer. End when the requested review is complete.
