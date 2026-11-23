# Code Change Review Rubric

Use the [nine surfaces in the entry](../SKILL.md#screen-the-change) to screen the complete change before applying the relevant checks below. Include indirect callers, generated contracts, externally deployed consumers and runtime configuration. An unchanged signature, empty migration directory or rename alone cannot establish unchanged behavior.

## Risk checks

Find the real hot path or failure window. Routine refactors, test/doc edits and copy or token-only UI changes need the changed invariant and direct checks. Apply the checks for each changed path.

| Changed path | Questions to resolve |
| --- | --- |
| Ordinary behavior and fallbacks | What changes for users, callers and systems? Check unrelated behavior and expected default, empty, boundary, malformed, stale, duplicate and reordered inputs. Compare fallback semantics. |
| Writes, deletion, migration, synchronization | Track meaning, units, time basis, owner, nullability and lifecycle from input through persistence to output. Distinguish missing rows from zero and unavailable data from empty results. List intermediate states and failures. Inspect transactions, lost updates, uniqueness, referential integrity, invalidation, ledger/source joins, replay, old/new data, restore and rollback. |
| Queue, retry, transactions, concurrency | Check error propagation, translation and swallowed failures, timeout ambiguity, durable request identity/idempotency after restart, duplicate/reordered/concurrent/delayed work, cancellation, partial success, lock lifetime, cleanup and crash recovery. A race needs an interleaving reaching bad state. |
| External irreversible effects | Check request identity, receipt, uncertainty after response loss, compensation, rate and account boundaries. |
| Authentication, authorization, secrets, sensitive data | Label input trust and validation at use. Trace authentication and authorization, tenant/account/object binding, privileges and server claims after merges. Check reachable injection, traversal, unsafe deserialization, logging and disclosure, fail-open behavior and recovery. |
| Public API, event, schema, storage, CLI or configuration | Apply [Compatibility](#compatibility) to consumers, deploy order, the mixed-version window and rollback. |
| Dependencies and operating burden | Check provenance, lockfile changes, install hooks, egress, permissions and bounded cost. Inspect suspect scripts before execution. |
| Shared or high-volume code | Trace default changes and blast radius. Where call rate, data volume or resource ownership matters, compare complexity and query/network counts, unbounded reads, scans, N+1 calls, serialization and backpressure. Check memory, descriptors, connections, subprocesses and temporary files. Use repository or requirement limits. |
| New or restructured user-visible UI | Apply [UI review](ui-review.md) to rendered state, raw values, actions, layout, forms and reused components. |
| A changed invariant or high-risk failure | Map behavior to direct unit, integration, contract, migration or regression tests. Check whether the test would fail with the bug. Trace detection through receipts, audit, reconciliation, alerts or visible errors, then the operator’s ability to stop, isolate, retry, compensate or roll back. |

## Changed governance and boundaries

Check before/after responsibilities, write ownership, source of truth and deployment boundaries for cross-module writes, multiple configuration/state authorities or bypassed shared services. A new writer alone does not prove ownership transfer or broad impact. If missing responsibility or consumer facts decide impact, give the known exposure with Undetermined. Mandatory repository rules, including UI reuse and pre-merge walkthroughs, are constraints. Confirm a documented convention is mandatory before enforcing it.

For changed verification, compare the old invariant, new assertion and actual CI path. An approved contract can warrant a different assertion. A weakened required gate needs equivalent replacement coverage or separate approval.

Check whether abstractions remove current duplication and whether tests/code make state, trust, ownership and failure behavior legible. Added dependencies, configuration, background work and interfaces need approved use or acceptance now. An approved new capability needs an expected use path. Adoption can follow. Weigh existing or platform alternatives and maintenance obligations. File counts, speculative value, green tests and general practices cannot override approved tradeoffs. Maintainability is a defect only when there is a concrete failure, required invariant hidden, or safe verification materially prevented. Apply the entry's scope/architecture judgment for a mandatory boundary.

## Compatibility

Trace actual API, event, schema, storage, configuration, command and library consumers through removed/renamed fields, types, defaults, ordering, encoding, permissions and errors. Check independent deployment, mixed versions, rolling rollback, new readers with old data and old readers with new data. Establish migration and recovery through a bridge, version boundary, coordinated cutover or proved absence of old consumers. An approved joint cutover with all consumers accounted for can suffice. A known old consumer needs a working migration path. An incomplete material inventory leaves a question, and an external consumer test stays unverified until run or proved for the specific code path.

## UI removals and list search

For UI simplification, trace removed controls to the user's task, metrics and comparison context. Another page or raw-data view is equivalent when it preserves that task. Include lost history or evidence and added orchestration in the comparison.

For search, trace API/storage scope → returned dataset → filtering → count → pagination → URL state. Assess dataset completeness and scale suitability separately. Complete results avoid page-only omissions. Loading the full list still needs evidence at relevant volumes. Bounded or offline data may justify local filtering. Treat missing capacity evidence as a question only when material to acceptance. A performance defect or mandatory backend-search requirement needs separate evidence.
