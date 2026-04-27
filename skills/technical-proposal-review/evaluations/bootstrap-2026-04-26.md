# Bootstrap Blind Replay Evaluation

Date: 2026-04-26
Skill draft: `technical-proposal-review`

## Purpose

Evaluate whether the first skill draft can rediscover core human review concerns without seeing the historical `评审意见` sections as input.

## Method

For each historical case:

1. Prepare a proposal input that hides the original `评审意见` section.
2. Run the skill review using the proposal body only.
3. Compare skill findings with the original human review comments.
4. Record hits, missed issues, false positives, severity mismatches, and output preference feedback.

## Acceptance Criteria

- Core human concern hit rate is at least 70%.
- No dangerous severity miss for rollback, migration, security model changes, community fork risk, consistency, or external capacity promises.
- Most findings include concrete proposal evidence or missing evidence.
- Each case includes useful human review focus.

## Results Table

| Case | Hidden Human Comments | Core Human Concerns | Skill Hits | Misses | False Positives | Severity Issues | Preference Notes | Result |
|---|---|---|---|---|---|---|---|---|
| CASE-001 | yes | OAuth2 feasibility; login-state authority | Hit OAuth2/OIDC feasibility; hit authoritative login-state/session mismatch; also found token/key lifecycle and first-login side-effect risks. | No core miss. | Extra K8s namespace transaction concern is useful but needs human confirmation. | Possible over-severity on K8s namespace side effect if existing compensation exists. | Keep concrete identity-source wording; avoid turning OAuth2/OIDC into mandatory replacement without checking external platform capability. | pass |
| CASE-002 | yes | future gateway migration; human attribution for background tasks | Hit future gateway migration conflict; hit background task identity attribution; also found fail-open, forged header, token lifecycle risks. | No core miss. | Extra fail-open/header trust comments are useful general architecture findings. | P0 fail-open is acceptable if auth boundary is hard requirement; otherwise may be P1 with guardrails. | Preserve strong fail-open and trusted-header checks for gateway auth proposals. | pass |
| CASE-003 | yes | community fork risk from plugin source modification | Found fail-open matchRule, global consumer isolation, rollback, and concurrent CRD write risks. | Missed the human core concern: modifying plugin source creates community fork and upgrade-maintenance risk. | Some extra security findings are useful but do not replace the fork-risk review. | Dangerous severity miss: RP-004 should have been P0/P1. | Strengthen RP-004 trigger and force plugin/source-change proposals to check fork governance. | needs calibration |
| CASE-004 | yes | reuse existing async mechanism; current-state proof; MVP; coverage matrix | Hit current-state proof; hit existing mechanism reuse boundary; hit queue consistency; hit button/API coverage matrix; hit identity/tenant metadata. | Missed explicit MVP-first decision path and operation-category refinement; SDK integration guidance only partially covered. | Extra sensitive-field and tenant metadata comments are useful. | No dangerous severity miss. | Add a more explicit MVP-first and operation taxonomy check for platform capability proposals. | pass with calibration |
| CASE-005 | yes | rollover index mode; naming; required log framework; representative rollout | Hit fixed alias/rollover versus service-day index conflict; hit component-specific naming risk; hit required `logFramework` metadata; hit migration/rollback. | Representative Java/Python/Go rollout was only partially covered through coverage matrix, not called out directly. | Extra Filebeat field-path concern is useful but needs actual event sample confirmation. | No dangerous severity miss. | Require representative end-to-end rollout examples when logging/observability standards are proposed. | pass with calibration |
| CASE-006 | yes | queue stacking; decoupled HPA; read/write isolation; spec control points | Hit all four core concerns: spec-to-control mapping, multi-layer queue state risk, decoupled HPA/backpressure, read/write model isolation. | No core miss. | Extra PgBouncer/PG read replica compatibility concern is useful but depends on actual SQL behavior. | No dangerous severity miss. | Preserve spec-to-control matrix as P0 when proposal promises external tenant packages. | pass |

## Bootstrap Summary

- Cases reviewed: 6
- Exact core concern hit rate: 14/17
- Hit rate including partial matches: 15/17
- Dangerous severity misses: 1, `CASE-003` missed community fork/source patch risk.
- Overall result: pass threshold; bootstrap calibration feedback has been reviewed by the human reviewer and folded into skill references.

## Calibration Notes

- Strengthen `RP-004` so any proposal that modifies community, gateway, plugin, Wasm, CRD controller, or third-party source code must explicitly review fork governance, upgrade path, alternatives, rollback, and ownership.
- Add an MVP-first check that triggers on platform-wide capabilities with broad scope, fallback design, SDK rollout, or new queue/collector design.
- Add representative rollout examples for logging, audit, authentication, and gateway standards; the skill should ask for at least one real end-to-end service per major stack or domain.
- Keep strong general findings from blind replay, especially fail-open behavior, trusted identity headers, token/key lifecycle, queue state ownership, and spec-to-control matrices.

## Human-Approved Calibration Feedback

Accepted bootstrap feedback was written to:

- `technical-proposal-review/feedback/accepted/bootstrap-feedback-2026-04-27.yaml`
- `technical-proposal-review/feedback/accepted/bootstrap-output-preferences-2026-04-27.yaml`

Current pending feedback status:

- No pending bootstrap feedback remains.
