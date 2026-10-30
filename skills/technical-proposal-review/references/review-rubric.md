# Review Rubric

Screen all dimensions for applicability; deepen only paths relevant to the proposal, its stage and real consumers. Domain tags add checks without excluding other dimensions. Do not turn the question set into a quota of findings, documents or infrastructure.

## Cross-Cutting Reasoning Rules

### First principles — start from the task

Reconstruct latest confirmed goal → current-stage usable outcome → user/caller path → necessary invariants → existing capability → proposed difference. Separate source facts, assumptions, owner decisions and the reviewer's suggestions. An approved plan is evidence of scope, not proof that its design remains suitable; a scope-changing alternative stays a proposal until authorized.

For each material addition, ask what current acceptance would fail without it and whether an existing mechanism suffices. For each removal or simplification, trace the user task it supported, the replacement and any semantic or operational loss. Consider keeping the existing behavior as an alternative. Table, menu, file and switch counts are clues, not evidence of necessity. Do not add background orchestration just to hide controls or remove useful history just to reduce objects.

Explain the smallest sufficient approach and its tradeoffs. Require metrics, comparison baselines and numeric thresholds for actual quantitative promises, not qualitative choices. Do not manufacture alternative designs or future phases when one approach already satisfies the approved goal.

### Adversarial review — try to falsify the conclusion

Check ordinary use first: can the approved user task complete with the proposed inputs, outputs and access path? Then choose realistic counterexamples from the changed assumptions and failure boundaries, including partial success, concurrency, retries, stale state or denied access where relevant. Challenge the preferred design, a simplification and inherited findings equally; adversarial review is not a search for reasons to add machinery.

Trace precondition → trigger → proposed/actual path → bad state → user impact → detection/containment/recovery. Follow shared services, wrappers and transaction boundaries before claiming a missing control. State what evidence would refute the candidate; close it when a shown control prevents the failure. Use a minimal sample, code readback or safe reproduction when decisive. Label a proposal-level counterexample as reasoning, not an executed test. No counterexample quota applies to low-risk paths.

### Evidence and stage control

Create a finding only for an evidenced gap affecting the outcome or a material decision. Use Q for unresolved facts, assess impact against existing controls and reversibility, and merge shared root causes. Security labels, checklist omissions and general best practices do not establish priority or override an accepted tradeoff. When a failure depends on an unverified external capability or behavior, keep that premise as Q and name the decisive evidence; a hypothetical serious consequence does not establish P0/P1. An optional behavior absent from the goal is a simplification candidate, not automatically a violation of an approved exclusion.

Preflight resolves uncertainties that can change the design, such as permissions, external data semantics or representative model feasibility. Implementation tests check built behavior; deployment and business acceptance check their declared later gates. Do not require a completed product to prove it can enter development, and do not defer an absent required adapter, entry point or usable result as merely an untested production environment. Keep an approved foundational stage distinct from delivery of the whole roadmap.

## 1. Background And Goals

Check:

- Does the proposal explain the current state before proposing a new design?
- Does it separate goals from non-goals?
- Does it explain why the problem matters now?
- Does it include enough context for a reviewer who did not attend prior meetings?

Risk signals:

- Solution appears before problem analysis.
- Goals mix must-have delivery with optional optimization.
- Claims rely on meeting context or external links without summarizing decisions.

## 2. Current Capability Reuse

Check:

- Does the proposal evaluate existing mechanisms, standard protocols, built-in plugins, existing queues, existing SDKs, or current operational paths?
- Does it explain why reuse is insufficient when introducing new components?
- Does it distinguish extension, replacement, and parallel operation?

Risk signals:

- New queue, plugin, service, or SDK is introduced without proving existing capability boundaries.
- Existing behavior is described inaccurately or too shallowly to support the proposed change.

## 3. Option Selection

Check:

- Are meaningful alternatives compared?
- Does the selected option show tradeoffs rather than only benefits?
- Are rejected options rejected for concrete reasons?

Risk signals:

- A materially simpler viable option is omitted without explanation.
- The proposal says "lowest risk" without evidence.
- Cost, migration, maintenance, or operational complexity are absent from comparison.

## 4. Architecture Boundaries

Check:

- Are responsibilities clear between frontend, backend, gateway, plugins, DB, queue, external systems, and operations?
- Are protocol boundaries and ownership boundaries explicit?
- Can each component be understood independently?

Risk signals:

- Multiple components write the same state without ownership rules.
- A component handles policy, execution, retry, and observability in one unclear block.

## 5. Compatibility And Migration

Check:

- Does the proposal account for actual consumers, deployed versions, preserved data and approved cutover boundaries?
- Does it define migration scope, data transformation, write freeze or dual-write period, and validation?
- Does it describe rollback steps and triggers?

Risk signals:

- Migration is described as a phase but lacks commands, sequence, data checks, or rollback.
- A known consumer or required recovery path is broken; speculative future consumers alone do not require a compatibility layer.

## 6. Consistency And Failure Handling

Check:

- Are retries, idempotency, duplicate delivery, partial failure, concurrency conflict, and crash windows addressed?
- Is there a single source of truth for state?
- Are compensation and recovery paths explicit?

Risk signals:

- Multi-layer queue design lacks state ownership.
- DB write and downstream delivery can diverge.
- Kubernetes CRD full replacement is used without conflict retry.

## 7. Security And Permissions

Check:

- Does the proposal define identity source, authentication boundary, authorization boundary, token lifetime, key rotation, and privilege escalation path?
- Does it explain fail-open or fail-closed behavior?
- Does it identify security model changes?

Risk signals:

- Service identity hides the real human operator.
- Global visibility replaces domain isolation without explicit risk analysis.
- Token or key behavior is assumed but not specified.

## 8. Observability

Check:

- Are metrics, logs, traces, dimensions, dashboards, and alert conditions specified?
- Can operators diagnose the proposed system after rollout?
- Are business dimensions such as tenant, user, client type, model, domain, or route captured when relevant?

Risk signals:

- Observability is only named as a goal.
- New async flows lack queue depth, failure count, retry count, and latency metrics.

## 9. Capacity And Performance

Check:

- Does the proposal include baseline data and expected load?
- Are rate limits, queue depth, concurrency, token limits, shard count, storage growth, or HPA metrics connected to the design?
- Are external promises mapped to enforceable control points?

Risk signals:

- SLA or package specs are promised without gateway, application, worker, model, and storage controls.
- Index or queue growth is not bounded.

## 10. Cost And Operations

Check:

- Does the proposal identify ongoing operational cost, upgrade cost, fork maintenance, on-call impact, and manual procedures?
- Does it prefer local autonomy and standard operational primitives where possible?

Risk signals:

- Community source is modified without upgrade governance.
- Cross-layer orchestration creates hidden operational coupling.

## 11. Maintainability And Evolvability

Check:

- Can the approved extension be maintained without speculative framework or configuration work?
- Are custom patches, custom protocols, and special cases minimized?
- Is the design compatible with expected future architecture direction?

Risk signals:

- The design solves the immediate problem by adding a hard-to-upgrade fork.
- A temporary bridge becomes a permanent dual-maintenance path.

## 12. Rollout And Validation

Check:

- Is the current-stage user path usable, with later work separated from its acceptance?
- Are representative end-to-end cases identified?
- Are tests, validation queries, migration checks, and acceptance criteria explicit?
- For platform standards, are representative stacks, services, languages, or domains selected before full rollout?

Risk signals:

- Full-scale rollout appears before a representative path is proven.
- The plan has work estimates but no acceptance criteria.
- A logging, audit, auth, or gateway standard has a service list but no real end-to-end sample per major stack or traffic type.

## 13. Documentation Completeness

Check:

- Are API, field, config, label, operation, button, or route inventories included where needed?
- Are responsibilities and owners listed for cross-team work?
- Are unresolved questions separated from accepted decisions?

Risk signals:

- A platform capability proposal lacks a coverage matrix.
- Configuration examples exist but no ownership or lifecycle rules are defined.
