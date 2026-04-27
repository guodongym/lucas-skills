# Review Rubric

Use every section for every proposal. Domain tags can add checks but cannot remove any global dimension.

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

- Only one option is presented.
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

- Does the proposal explain compatibility with current systems and known future migration paths?
- Does it define migration scope, data transformation, write freeze or dual-write period, and validation?
- Does it describe rollback steps and triggers?

Risk signals:

- Migration is described as a phase but lacks commands, sequence, data checks, or rollback.
- Future gateway or platform migration is mentioned but not reconciled with the proposal.

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

- Can future teams extend the solution without rewriting core pieces?
- Are custom patches, custom protocols, and special cases minimized?
- Is the design compatible with expected future architecture direction?

Risk signals:

- The design solves the immediate problem by adding a hard-to-upgrade fork.
- A temporary bridge becomes a permanent dual-maintenance path.

## 12. Rollout And Validation

Check:

- Is there an MVP path before broad rollout?
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
