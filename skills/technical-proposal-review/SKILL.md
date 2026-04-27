---
name: technical-proposal-review
description: Use when the user asks to review, 初审, 复审, 校准, or improve technical方案/architecture proposals or评审意见, especially auth, gateways, logging, audit, multi-tenant capacity, migration, reliability, security, rollout, or maintainability. Use even for casual prompts like “帮我看看方案” or “给点评审意见”; returns first-pass findings and feedback fields, not final approval.
---

# Technical Proposal Review

## Purpose

Perform first-pass technical proposal review before human final review.

This skill should:

1. Identify blocking and important risks.
2. Combine general architecture review with the user's historical review preferences.
3. Produce actionable findings backed by proposal evidence.
4. Preserve human review authority by clearly listing final review focus.
5. Include feedback fields so future runs improve review accuracy and output style.

This skill should not approve a proposal as final. It only decides whether the proposal is ready for human review and what the human reviewer should focus on.

## Core Workflow

1. Read the proposal or proposal path supplied by the user.
2. If the input includes existing `评审意见`, use them as reviewer context, not as proposal-body evidence. Separate inherited human comments from new skill findings.
3. Load `references/review-rubric.md` for always-on review dimensions.
4. Load `references/output-template.md` before drafting the response.
5. Identify all applicable domain tags; tags add scrutiny and never narrow review scope.
6. Load `references/risk-patterns.md` and match concrete patterns against proposal evidence.
7. Load `references/case-bank.md` only when historical analogies help explain or prioritize findings.
8. Load `references/industry-frameworks.md` when checking broad architecture quality attributes.
9. Load `references/output-preferences.md` before finalizing wording and priority.
10. Output findings with IDs, severity, evidence, impact, and requested remediation.
11. End with the feedback block defined in `references/feedback-loop.md`.

## Review Scope Rule

Never classify a proposal into a single exclusive category and skip other checks.

Always run the global rubric. Domain tags such as `auth`, `gateway`, `logging-observability`, `audit`, `multi-tenant-capacity`, `migration`, `security`, and `maintainability` only add specialized checks.

## Finding Requirements

Each finding must include:

- stable ID such as `P0-01`, `P1-02`, `P2-03`, or `Q-01`
- severity
- concrete evidence or missing evidence from the proposal
- why the issue matters
- what the author should add, change, or decide
- matched risk pattern or historical case when useful

Avoid generic advice. Do not write "consider reliability" or "consider security" unless the response explains what is missing, where it appears in the proposal, why it matters, and what the author should do.

## Severity

- `P0 阻塞`: not ready for final human review until addressed.
- `P1 重要`: materially affects implementation risk or review quality.
- `P2 建议`: improves clarity, completeness, or execution quality.
- `Q 追问`: evidence is insufficient and the proposal author must answer.

## Historical Materials

Use `materials/historical-reviews/index.md` as the public source index for historical proposals and review comments. Do not load full historical files by default. Load only the cases needed for similarity or rule explanation.

Private source files and exact local path mappings are optional local calibration data. If `materials/private/historical-reviews/index.local.md` exists, use it only when source-level traceability is needed. If private materials are absent, continue the review using `references/`, accepted feedback, and the distilled case bank; treat this as reduced traceability, not a skill failure. Do not request, expose, or reconstruct private source material unless the user explicitly provides it in the local workspace.

When a historical source includes both proposal content and prior review comments, keep their roles distinct. Use proposal content as evidence for new findings; use prior review comments as calibration, comparison, or reviewer context.

## Feedback

Always include a feedback block. The user can mark missed issues, false positives, severity changes, liked comments, disliked comments, and wording preferences. These signals are later folded into `references/risk-patterns.md`, `references/case-bank.md`, and `references/output-preferences.md`.

## Evaluation

Use `evals/evals.json` when testing or improving this skill. For blind replay evals, use externally prepared masked inputs so reliance on prior human comments is testable. This masking is an eval harness concern, not a normal review requirement.
