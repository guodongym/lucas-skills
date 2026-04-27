# Risk Patterns

Use these patterns to identify issues that recur in the user's historical reviews. Match patterns against concrete proposal evidence. If evidence is weak, output a `Q`追问 instead of overstating the issue.

## 通用前置检查

Before firing any pattern, check whether the proposal has already addressed the concern that would trigger it. If the proposal provides a reasonable contextual explanation — such as confirming a fork is the only viable path, stating that metering precision is not required, or noting that a field is technically unavailable — downgrade the finding to a `Q` or close it rather than outputting a P1 or P2.

This pre-check does not remove pattern-specific requirements. It only prevents firing a finding when the proposal has already resolved the trigger condition.

---

## RP-001 New Mechanism Without Reuse Boundary

Scope: global

Trigger:

- Proposal introduces a new queue, collector, plugin, service, SDK, or protocol path.
- Existing mechanism is present but not evaluated deeply.

Why it matters:

- New mechanisms increase state, operations, migration, and maintenance cost.

Expected review:

- Ask whether existing capability can be extended.
- Require current-state limitations, measured bottlenecks, or failure cases.
- Require a clear delta between old and new behavior.

Historical source:

- Operation audit review: questioned adding a new queue instead of reusing the existing async event mechanism.

## RP-002 Solution Before Current-State Proof

Scope: global

Trigger:

- Proposal describes final architecture before explaining existing behavior and concrete problems.
- Proposal uses broad goals without evidence.

Expected review:

- Require current path, known bottlenecks, baseline data, and precise problem statement.

Historical source:

- Operation audit review: "先把现有方案说清楚，再说新的方案改变了哪里".

## RP-003 Optimization Before MVP

Scope: global

Trigger:

- Proposal designs fallback, complex scheduling, or full optimization before a representative path is proven.
- Proposal covers a broad platform capability but does not define a narrow end-to-end MVP and follow-up learning path.

Expected review:

- Require MVP path, exposed problems from MVP, then optimization sequence.
- Require at least one representative end-to-end rollout before broad optimization or platform-wide rollout.

Historical source:

- Operation audit review: first run a process MVP, then analyze issues, then optimize.

## RP-004 Community Fork Or Source Patch Without Governance

Scope: gateway

Trigger:

- Proposal modifies community or third-party plugin source.
- Upgrade and fork strategy are not explicit.
- Proposal changes open source gateway, plugin, Wasm, CRD controller, SDK, or vendored dependency code instead of using documented extension points.

Expected review:

- Require upgrade ownership, patch rebase path, trigger conditions for tracking upstream releases, and a plan for merging back if the community eventually supports the capability.
- Identify whether the affected component is open source. For open source components, the maintenance strategy should stay close to upstream and avoid hard-to-merge divergence from community code.
- If the proposal has not yet established whether non-fork alternatives are feasible, also require evaluation of extension points, configuration, composition, sidecar, or upstream contribution before accepting source modification.
- Treat as at least `P1`; use `P0` when the source patch changes authentication, authorization, routing, security defaults, or migration-critical behavior and no governance is provided.
- Do not let route-level or configuration-level findings hide the fork and upgrade-maintenance risk.

Historical source:

- API Key plugin merge review: source modification creates community fork risk.

## RP-005 Migration And Rollback Under-Specified

Scope: migration

Trigger:

- Proposal changes data location, CRD shape, plugin responsibility, or gateway behavior.
- Migration is mentioned but lacks freeze window, validation, rollback, or dual-write plan.
- Proposal synchronously creates external resources such as namespaces, storage, indexes, or cloud resources inside a local DB transaction.

Expected review:

- Require migration sequence, data integrity checks, conflict handling, rollback exercise, and release gates.
- For external resource creation, require idempotency, compensation, explicit failure state, retry, and repair path. Use `P0` only when synchronous external creation has no such controls; otherwise use `P1` or `Q`.

Historical source:

- API Key merge proposal and inner gateway authentication review.

## RP-006 Future Architecture Collision

Scope: global

Trigger:

- Proposal works for current state but may conflict with known migration or consolidation plans.

Expected review:

- Require current mode, target future mode, overlap period, compatibility path, and repeated-work avoidance.

Historical source:

- Inner authentication review: consider future business API gateway migration into model gateway.

## RP-007 Identity Without Human Accountability

Scope: auth

Trigger:

- Background service, scheduled task, or internal request uses service identity without a real user or owner.

Expected review:

- Require operator, creator, updater, or responsible-user semantics.
- Define no-user fallback explicitly.

Historical source:

- Inner authentication review: evaluation business lacks operator but has creator/updater.

## RP-008 Login State Or Identity Source Ambiguity

Scope: auth

Trigger:

- SSO or third-party login proposal has multiple identity states or local sessions.

Expected review:

- Require authoritative identity source, token lifetime, logout behavior, session mismatch handling, and standard protocol evaluation.

Historical source:

- Cloud SSO review: ask for OAuth2/OIDC or equivalent standard protocol support and whether the external login state can be authoritative.

## RP-009 External Spec Promise Without Control Points

Scope: multi-tenant-capacity

Trigger:

- Proposal promises tenant package, SLA, RPM, QPS, TPM, document count, or concurrency.
- Control points are not mapped to gateway, app, worker, model, or storage layers.

Expected review:

- Require spec-to-control mapping, observable metrics, enforcement point, failure response, and known limits.

Historical source:

- Knowledge base multi-tenant review: ask whether promised specs can really be achieved.

## RP-010 Multi-Layer Queue Stack With State Risk

Scope: multi-tenant-capacity

Trigger:

- Proposal adds multiple queues, dispatchers, retry layers, or cross-queue coordination.

Expected review:

- Require single source of truth, idempotency, retry and DLQ ownership, outbox or transactional delivery, and traceability.
- Prefer local autonomy and backpressure when possible.

Historical source:

- Knowledge base multi-tenant review: queue stacking adds state consistency risk.

## RP-011 Tightly Coupled Cross-Layer Scaling

Scope: multi-tenant-capacity

Trigger:

- Proposal requires upper and lower layers to scale in a strict sequence or coordinate through complex rules.

Expected review:

- Prefer independent HPA per component, local metrics, backpressure, and HTTP 429.

Historical source:

- Knowledge base multi-tenant review: keep component HPA decoupled.

## RP-012 Read And Write Traffic Not Separated

Scope: multi-tenant-capacity

Trigger:

- Proposal uses shared model, index, DB, or path for read and write workloads with different latency priorities.

Expected review:

- Require read/write isolation assessment, fallback if isolation is not feasible, and prioritization rules.

Historical source:

- Knowledge base multi-tenant review: model read priority is higher and may need separate inference instances.

## RP-013 Log Or Index Naming Driven By Historical Component Names

Scope: logging-observability

Trigger:

- Log index names are based on historical component names rather than query, lifecycle, or business dimensions.

Expected review:

- Require naming based on business type, query path, lifecycle, and long-term governance.

Historical source:

- Service logging review: avoid component-specific legacy markers; prefer business type or a governed unified job index.

## RP-014 Mandatory Metadata Not Enforced

Scope: logging-observability

Trigger:

- Labels, fields, headers, or config are required by routing, parsing, querying, or operations but marked optional.

Expected review:

- Make metadata mandatory or define fallback behavior with limitations.

Historical source:

- Service logging review: `app.kubernetes.io/logFramework` should be required if framework-specific parsing is expected.

## RP-015 Coverage Matrix Missing For Platform Capability

Scope: audit

Trigger:

- Proposal adds a platform-wide capability such as audit, logging, or authentication but lacks coverage inventory.
- Proposal defines a standard across languages, gateways, services, jobs, routes, or UI operations without representative end-to-end examples.

Expected review:

- Require button, API, route, service, domain, or component-level matrix with priority, owner, and current coverage.
- Require representative rollout samples for each major stack, domain, or traffic type before broad rollout.
- For Filebeat, Kubernetes labels, or collector field-path concerns, ask for real event samples and keep low-confidence parser details as `Q` or human review focus unless evidence is direct.

Historical source:

- Operation audit review: require button-level list and completion state.

## RP-016 Cross-Service Contract Missing

Scope: audit

Trigger:

- Proposal adds or standardizes a platform capability across services, languages, SDKs, gateways, or protocols.
- Architecture shows SDK/API/RPC/HTTP integration points but the request contract, response semantics, authentication boundary, timeout/retry behavior, idempotency, or required fields are not specified.

Expected review:

- Treat missing SDK/API contract as high priority when it affects implementation ownership or cross-service consistency.
- Require concrete request/response schema, required metadata, actor and tenant source, error codes, timeout and retry rules, idempotency key, and compatibility expectations.
- Prefer this finding before generic reliability comments when the proposal already has a high-level architecture but lacks an executable integration contract.

Historical source:

- Operation audit review feedback: SDK/API contract gap was the most actionable review point for a cross-language audit capability.

## RP-017 Architecture Text Boundary Mismatch

Scope: global

Trigger:

- Architecture diagram shows components, SDKs, protocols, or capabilities that the proposal text describes as missing, future, or unsupported.
- The proposal does not say whether a component in the diagram is current state, target state, or illustrative design.

Expected review:

- Require the author to mark each diagram component and path as current, this-phase target, future target, or out of scope.
- Ask for an explicit delta between current behavior and proposed behavior before reviewing implementation details.
- Raise as `P1` when the mismatch changes development scope, ownership, or review readiness.

Historical source:

- Operation audit review feedback: text said heterogeneous services lacked audit capability while the architecture diagram already showed Go/Python SDK HTTP paths.

## RP-018 Phase Scope Mixed With Future Optimization

Scope: global

Trigger:

- Proposal presents current architecture and future optimization architecture together without a phase boundary.
- A future optimization such as batching, queueing, fallback, or new storage appears next to the current MVP path without trigger conditions.

Expected review:

- Require a clear this-phase scope, future-phase scope, trigger metrics, and decision gates.
- Ask whether the MVP reuses existing mechanisms first, and defer optimization until representative rollout exposes measured pressure or failure modes.
- Treat as high priority when mixed scope could expand implementation or confuse acceptance criteria.

Historical source:

- Operation audit review feedback: event plus batch write was acceptable as a future QPS optimization, but needed explicit boundary and trigger conditions separate from the current SDK access path.
