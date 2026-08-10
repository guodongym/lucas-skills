# Code Change Review Rubric

Use every dimension as a question set, not as a quota. Follow only the paths made relevant by the change and its real consumers. A checked dimension does not require a finding.

## 1. Observable behavior and requirements

- What user-, caller-, or system-visible behavior changes?
- Does the change satisfy the stated requirement and preserve unrelated behavior?
- Are default, empty, boundary, malformed, stale, duplicate, and reordered inputs handled according to the existing contract?
- Does fallback behavior preserve the same semantics, or silently change them?
- Is new complexity required now, or is it speculative flexibility that creates additional failure paths?

## 2. Data semantics and state transitions

- Track each value's meaning, unit, time basis, ownership, nullability, and lifecycle from input through persistence and output.
- For multi-step writes, list every intermediate state and every failure window.
- Check transactions, commit boundaries, uniqueness, referential integrity, cache invalidation, ledger/source joins, and deletion behavior.
- Check replay, restore, migration, rollback, and mixed old/new data.
- Distinguish missing rows from zero values and unavailable data from empty results.

## 3. Errors, retries, concurrency, and cleanup

- Which exceptions or error values can occur at each call boundary? Are they propagated, translated, retried, or swallowed consistently?
- Can a timeout mean “failed” or “completed but response lost”?
- Are retry identity and idempotency durable across process restarts?
- Check duplicate, concurrent, out-of-order, and delayed execution against the actual synchronization or transaction primitive.
- Check partial success, cancellation, resource cleanup, lock lifetime, and crash recovery.
- Do not claim a race from shared state alone; show an interleaving that reaches the bad state.

## 4. Security and trust boundaries

- Label every value as trusted, authenticated, validated, sanitized, or user-controlled at the point of use.
- Check authentication versus authorization, tenant/account/object binding, privilege changes, and server-side identity re-injection after merges.
- Check injection, path traversal, unsafe deserialization, secret exposure, logging, and error disclosure where the changed data path makes them reachable.
- Check fail-open behavior when policy, identity, or dependency data is missing.
- Security terminology does not determine severity. Use reachable scope, data sensitivity, reversibility, and existing containment.

## 5. Compatibility and migrations

- Identify public APIs, events, schemas, storage formats, configuration keys, command output, and library contracts changed by the diff.
- Read actual consumers. Check field removal/rename, type and default changes, ordering, encoding, and error semantics.
- Model independent deploys, mixed versions, rolling rollback, old data read by new code, and new data read by old code.
- Require a compatibility bridge, version boundary, coordinated cutover, or proved absence of old consumers before confirming safety.
- A consumer test in another repository is unverified until it is run or the direct code path proves the narrow compatibility claim.

## 6. Performance and resource lifetime

Apply this dimension only when the changed path, data volume, frequency, or resource ownership makes it relevant.

- Compare algorithmic complexity and query or network-call count on the real hot path.
- Check unbounded reads, repeated scans, N+1 calls, accidental serialization, and missing backpressure.
- Check memory, file descriptor, connection, subprocess, and temporary-file lifetime.
- Use repository or requirement thresholds when available; do not invent universal limits.

## 7. Tests, observability, containment, and recovery

- Map each changed behavior to its closest unit, integration, contract, migration, or regression test.
- Confirm the test would fail if the suspected bug were present; do not count incidental execution as coverage.
- Check detection signals for high-risk failures: durable receipts, audit records, reconciliation, alerts, or user-visible errors.
- Check whether an operator can stop, isolate, retry, compensate, or roll back the effect without worsening state.
- Missing tests strengthen an evidenced defect's risk assessment but do not alone create a `P1`.

## 8. Maintainability and scope discipline

- Can a future maintainer understand the state machine, trust boundary, ownership, and failure behavior from the code and its tests?
- Does an abstraction remove current duplication or merely predict future variation?
- Are new dependencies, configuration, background work, or public interfaces required by the current change?
- Report maintainability only when it creates a concrete defect, hides a required invariant, or materially prevents safe verification. Pure style preference is not a finding.

## Risk-trigger matrix

| Changed surface | Deepen review for |
| --- | --- |
| Authentication, authorization, secrets, sensitive data | identity override, tenant/object binding, fail-open, disclosure, recovery |
| Writes, deletion, migration, synchronization | partial commit, lost update, replay, rollback, old/new data |
| Queue, retry, transaction, concurrency | duplicate, reorder, timeout ambiguity, crash window, durable idempotency |
| External irreversible effect | request identity, receipt, uncertainty, compensation, rate or account boundary |
| Public API, event, schema, storage | actual consumers, rolling deploy, mixed version, rollback compatibility |
| Shared high-call-volume code | blast radius, default behavior, hot-path cost, containment |
| Local refactor, test, docs, low-risk UI | only the changed invariant and direct tests; do not manufacture adversarial scenarios |

## Candidate-to-finding gate

Before emitting a confirmed finding, answer all six:

1. Which in-scope line introduced or exposed the problem?
2. Which realistic input or event reaches it?
3. Which caller, consumer, state, or external effect is harmed?
4. Which evidence proves the path rather than merely suggesting it?
5. Which current controls apply, and why do they fail to prevent or contain it?
6. Which focused change or test addresses the root cause?

If 1–4 cannot be answered, do not emit a confirmed finding. If 5 shows that the failure is prevented, suppress the hypothetical and report only any directly evidenced residual gap. If a missing answer could change the verdict, emit a question.
