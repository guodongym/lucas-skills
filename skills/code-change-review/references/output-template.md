# Code Change Review Output Template

Use the [entry’s report contract and verdicts](../SKILL.md#report-and-verdict). Order every report as verdict line, briefing, attention and full verdict, five answers, findings, then verification/coverage. Explain each fact or finding once and cross-reference by section or C/P/Q IDs elsewhere. For a bounded review with a finding, keep the briefing short and give actionable disposition. For an expanded report, use sections for each part and skip empty ones. Preliminary reviews explicitly mark answers they could not assess.

## Change briefing

Keep the briefing detailed and self-contained on facts so a reader new to the change can follow the full story (problem, main path, before/after architecture, diagrams, groups and new-concept inventory), but leave critiques, root causes and remedies for later sections.

```markdown
**改动导读**
- 业务问题：… （来源：声称 PR 描述 / 推断 / 未说明）
- 实现方式：入口 → 处理 → 存储或输出（3–5 步）
- 架构处理：前后对比，或“无架构变化”
- 改动分组：| 组 | 目的 | 文件 / 手写行数 | 能否单独交付 |
- 新概念清单（只列事实，覆盖变动涉及的类别：数据/状态、机制、角色/权限、流程/入口、界面用词、共享依赖；质疑与简化方案写在后文“方案”）：| 类别 | 概念 | 来源（已确认 / 仅作者） |
- PR 适配：合适 / 建议拆分（不阻塞）/ 违反仓库强制规则（C），附决定性理由
```

Write the labels in the user’s language. Diagrams show verified facts only: use real module or function names, draw an untraced call as a dashed edge labelled unverified, and mark each new, modified or removed node; unchanged nodes are context. Keep one question per diagram, about 12 nodes, at most two diagrams in a routine review and three in a large one. The text must still stand without them. Use `flowchart` for paths and deploy order, before/after `subgraph`s for architecture, `sequenceDiagram` for async or cross-service calls and `stateDiagram-v2` for state changes. When publishing to a platform not confirmed to render Mermaid, replace it with indented text arrows.

## Concise later sections

- **Special attention**: one line per item (before → after contract, schema, architecture, existing-function change or unchecked gap); cite C/P/Q IDs without repeating causes or remedies.
- **Five questions**: judgment-only, 2–3 sentences per question (for multi-group PRs, cover shared points once and add group notes only where groups differ). Cite the briefing and C/P/Q IDs; consolidate the new-concept challenges and keep/simplify/split/remove recommendations once inside Approach. Do not repeat the briefing or finding details.
- **Nine surfaces & verification**: group unchanged surfaces on one line; for changed surfaces write only `no issue` or the matching C/P/Q IDs instead of re-summarizing findings; explain gaps only for unverified surfaces.

## Scope and verification

Give repository/cwd, branch or detached HEAD and SHA, immutable endpoints or local snapshot, requirements used and exclusions. Disclose material sampling, unavailable consumers/environments and the smallest missing evidence for the affected acceptance gate. For commands actually run, give the command, passed/failed/blocked and the decisive result or count. Give direct code evidence separately. Environment failure alone establishes no product defect.

## Evidence entries

Report one issue per cause. Use stable IDs and list P0 before P1 before P2.

- **C-01** — approved baseline and source/version (with owner adoption for inherited suggestions), changed location and conflict, affected ownership/function/maintenance, smallest alignment or specific decision and actual evidence/verification limits. Evaluate approval already supplied.
- **P0-01 / P1-01 / P2-01** — changed causal location, current behavior, reachable path, user/data/protocol/system impact, controls and reversibility, smallest root-cause remedy, verification status and evidence. Keep unrelated historical debt out of the review.
- **Q-01** — missing evidence, affected conclusion and gate (merge, deployment or business acceptance), smallest resolution, and blocking/non-blocking status. Apply the entry’s blocking criterion.

### Location

Cite the smallest causal changed line(s) in target-file coordinates. Verify text with a numbered target-file readback. For diff-only evidence, start at the `+` hunk number and number each context/added line before incrementing. Deleted lines and hunk headers neither receive nor advance the new-side number. Use the resulting target-file line numbers for the causal code.
