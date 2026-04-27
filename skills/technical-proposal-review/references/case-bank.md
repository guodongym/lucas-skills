# Case Bank

Use this file for structured historical analogies. Do not quote large sections of source proposals. Load source files from `materials/historical-reviews/index.md` only when more context is needed.

## CASE-001 Cloud SSO

Source:

- Private source key `CASE-001`

Domain tags:

- `auth`
- `security`
- `maintainability`

Scenario:

- Single-direction SSO from an external cloud platform to an internal platform.
- Proposal uses same-domain Header/Cookie token extraction and local verification.
- Local user mapping, first-login account creation, default roles, special admin mapping, and space strategy are included.

Human review concerns:

- Ask whether the external platform can provide OAuth2/OIDC or an equivalent standard protocol for looser coupling.
- If current approach remains, consider using the external platform login state as authoritative to avoid duplicate login and inconsistent sessions.

Reusable rules:

- Evaluate standard identity protocols before custom token bridging.
- Define authoritative identity source, token lifetime, logout behavior, and mismatch handling.
- Separate core integration goals from optional role or space optimization.

Expected supplement:

- Token format, verification method, key rotation, logout semantics, concurrent first-login behavior, and final decision on OAuth2 feasibility.

## CASE-002 Inner Gateway Authentication

Source:

- Private source key `CASE-002`

Domain tags:

- `auth`
- `gateway`
- `observability`
- `migration`

Scenario:

- Internal model and MCP domains lack authentication and user/client observability dimensions.
- Proposal reuses a gateway `jwt-auth` plugin with claims-to-headers.

Human review concerns:

- Consider future business API gateway migration into the model gateway to avoid conflicting or duplicate work.
- Background operations should simulate or preserve a human identity; evaluation lacks operator but has creator/updater.

Reusable rules:

- Gateway proposals must describe compatibility with current and future gateway modes.
- Service calls should not erase human accountability.
- Built-in plugin reuse still requires version, order, and failure-mode validation.

Expected supplement:

- Gateway migration timeline, overlap mode, actor attribution rules, and failure behavior such as `FAIL_OPEN` implications.

## CASE-003 API Key Authentication Merge

Source:

- Private source key `CASE-003`

Domain tags:

- `gateway`
- `auth`
- `migration`
- `security`
- `maintainability`

Scenario:

- Proposal merges API key authentication and authorization responsibilities into one plugin to eliminate CRD double writes.
- It changes plugin configuration, match rule semantics, and data migration.

Human review concern:

- Modifying plugin source creates community fork risk and future upgrade difficulty; evaluate better alternatives.

Reusable rules:

- Community source modification requires alternatives, governance, upgrade strategy, rollback, and patch ownership.
- Plugin responsibility changes require security model diff, route/domain priority tests, and migration validation.

Expected supplement:

- Non-fork alternatives, fork governance, real CRD samples, current key/consumer/route counts, rollback execution, and dual-write or reverse migration plan.

## CASE-004 Platform Operation Audit

Source:

- Private source key `CASE-004`

Domain tags:

- `audit`
- `observability`
- `maintainability`

Scenario:

- Proposal extends operation audit from Java backend to heterogeneous services through SDK and centralized audit collector.
- It discusses async, batch insert, retry, and coverage.

Human review concerns:

- Reuse the current async event mechanism before adding a new queue.
- Explain existing problems before new design.
- Do not over-design local fallback before measuring loss scenarios and loss rate.
- Provide button-level coverage matrix.
- Refine operation categories such as task start and stop.
- Clarify SDK integration guidance.
- Use MVP first, then analyze exposed issues, then optimize.

Reusable rules:

- Platform capability extensions need current-state proof and coverage matrix.
- Retry and fallback must be justified by measured failure modes.
- MVP-first progression is required when scope is broad.

Expected supplement:

- Measured latency, loss rate, failure categories, MVP scope, SDK contract, button/API coverage table, and acceptance criteria.

## CASE-005 Service Log Collection

Source:

- Private source key `CASE-005`

Domain tags:

- `logging-observability`
- `operations`
- `capacity`

Scenario:

- Proposal standardizes Filebeat routing, labels, language log format, ILM, index naming, and service adaptation work.

Human review concerns:

- Adopt fixed index alias plus rollover, with Filebeat write and OpsCenter read separation.
- Avoid component-specific legacy naming; prefer business type or a governed unified job index.
- Decide whether Go should standardize on one framework such as `zap`, with fallback for hard-to-adapt components.
- If framework-specific parsing is required, make `app.kubernetes.io/logFramework` mandatory.
- First sprint should run representative Java, Python, and Go components end to end.

Reusable rules:

- Logging designs must balance query isolation with shard and lifecycle cost.
- Mandatory metadata should match downstream parser and query dependency.
- Representative end-to-end rollout should precede full migration.

Expected supplement:

- Final index naming decision, representative component list, validation queries, owner list, and capacity baseline.

## CASE-006 Knowledge Base Multi-Tenant Isolation

Source:

- Private source key `CASE-006`

Domain tags:

- `multi-tenant-capacity`
- `reliability`
- `operations`
- `cost`

Scenario:

- Proposal addresses tenant fairness, rate limiting, queue scheduling, HPA, model read/write traffic, and package specs.

Human review concerns:

- Queue stacking adds state consistency risk.
- Cross-layer cascading scale logic is too idealized; prefer decoupled HPA, backpressure, and HTTP 429.
- Model read traffic has higher priority and may need separate inference instances.
- Tenant specification config must sync from the authoritative package source and propagate to gateway and application layers.
- Promised specs must be proven achievable and limited explicitly.

Reusable rules:

- Tenant promises require enforcement points and observable metrics.
- Multi-layer queues require single source of truth and idempotency.
- HPA should be decoupled per component.
- Read/write traffic isolation should be assessed for resource-heavy paths.

Expected supplement:

- Spec-to-control mapping, current bottleneck baselines, queue and model metrics, 429 semantics, retry guidance, and authoritative package config sync design.

## CASE-007 Operation Audit V2 With Author Responses

Source:

- Private source key `CASE-007`

Domain tags:

- `audit`
- `sdk`
- `cross-service`
- `maintainability`

Scenario:

- Operation audit proposal extends existing Java/System audit write path to heterogeneous services.
- The document includes prior reviewer questions and author answers, plus a current architecture and a future event/batch-write optimization path.
- A linked button/project matrix exists, but the proposal still needs a clear acceptance baseline.

Human review concerns:

- Treat prior reviewer questions as reviewer context, and treat author answers as proposal evidence.
- When a diagram shows Go/Python SDK HTTP paths but text says heterogeneous services lack audit capability, require current/target boundary clarification.
- SDK/API contract gaps can be more actionable than generic reliability comments when architecture already exists.
- Event plus batch write is acceptable as a future optimization only if this-phase scope and trigger conditions are explicit.

Reusable rules:

- For cross-service platform capabilities, prioritize executable SDK/API contracts: required fields, actor and tenant source, timeout, retry, error codes, idempotency, and compatibility.
- Require each diagram path to be labeled current, this-phase target, future target, or out of scope when text and diagram appear inconsistent.
- Separate current MVP/reuse path from future optimization path, with trigger metrics and decision gates.
- For platform audit coverage, a linked matrix should be reviewable as an acceptance baseline, not just a scope inventory.

Expected supplement:

- SDK/API schema, current-vs-target boundary, this-phase scope, future batch-write trigger conditions, audit failure semantics, field-overflow strategy, and acceptance matrix.
