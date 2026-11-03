# Code Change Review Rubric

Use every dimension as a question set, not as a quota. Follow only the paths made relevant by the change and its real consumers. A checked dimension does not require a finding.

## Change-impact screening

Screen all nine surfaces; use the detailed checks below only where relevant. Include behavior and runtime configuration, not just declarations or filenames. Follow indirect callers, generated contracts and externally deployed consumers when necessary to establish impact. A rename, empty migration directory or unchanged signature does not prove unchanged semantics.

| Surface | Establish from the baseline and change |
| --- | --- |
| Requirement and scope | Map material additions/removals to approved goals and exclusions; identify bundled unrelated behavior. |
| Capability and complexity | Current use/acceptance, reuse of existing code or installed/native facilities, deletion test, added contracts/state/services/maintenance. Do not demand a formal proposal for routine bounded changes. |
| Architecture boundaries | Before/after module responsibility, dependency direction, write ownership, source of truth, trust and deployment boundaries. Look for direct cross-module writes, parallel config/state authorities and bypasses of shared services. |
| Interfaces and compatibility | Added/changed/removed API, event, CLI, configuration and storage contracts; parameters, return values, errors, defaults, permissions and mixed-version consumers. |
| Data and consistency | Added/changed/removed tables and fields, types/defaults/nullability, indexes/constraints and write paths; old data, migration order, rollback and restore. |
| Existing functions and failure propagation | User flows, shared callers, defaults, side effects, retries and partial failure; scope of outage or degradation. Intended changes still have impact. |
| Security and operating burden | Privileges, tenant boundaries, egress, irreversible actions, new dependencies/lock changes/install hooks, provenance, unbounded tasks and resource/cost growth. Inspect suspect scripts before considering safe execution. |
| Verification and constraint integrity | Deleted/skipped tests, relaxed assertions, changed acceptance, disabled CI/architecture checks and modified rule files; establish equivalent replacement coverage or independent approval. |
| User-visible UI | Added/changed pages, flows, forms, dialogs, action groups and states; the repository's UI rules and shared components compared with the closest existing feature; formats feeding reused renderers; runtime walkthrough evidence. Use [User-visible UI](#user-visible-ui). |

A documented pattern is not automatically mandatory; a repository rule stated as mandatory (for example "must reuse" or "must provide a walkthrough before merge") is an approved constraint, not a style preference. Historical code and green CI do not establish correctness. Compare changed paths with approved pre-change boundaries and separately traceable exceptions.

For capability necessity, ask whether deleting the addition still satisfies current acceptance. Apply the reverse test to removals: whether a real user task still has an equivalent path, history and evidence. Fewer controls with more background orchestration can increase complexity; preserving an internal mechanism is justified by its invariant, not its familiarity. Identify the smallest existing alternative and any unjustified behavior or maintenance obligation. File count and personal preference are not evidence; approved new capabilities need not have existing adopters.

For changed validation, compare the old invariant, new assertion and actual CI path. Updating an assertion for an approved contract can be valid; weakening a required gate without equivalent coverage can be a constraint issue despite functioning runtime code.

## 1. Observable behavior and requirements

- What user-, caller-, or system-visible behavior changes?
- Does the change satisfy the stated requirement and preserve unrelated behavior?
- Are default, empty, boundary, malformed, stale, duplicate, and reordered inputs handled according to the existing contract?
- Does fallback behavior preserve the same semantics, or silently change them?
- Is new complexity required now, or is it speculative flexibility that creates additional failure paths?

### UI removals and list search

For UI simplification, trace removed controls to user tasks, metrics and comparison context. Another page or raw-data view is equivalent only if it preserves the relevant task.

For search, trace API/storage scope → returned dataset → filtering → count → pagination → URL state. Separate **dataset completeness** from **scale suitability**: filtering a complete response avoids page-only omissions but does not prove full-list loading fits the expected volume. Bounded/offline data can justify local filtering. Missing capacity evidence is a question only when material to acceptance; it is not a measured performance defect, a universal backend-search requirement or an automatic merge blocker.

### User-visible UI

Apply when the change adds or restructures a page, flow, form, dialog, action group, layout or interaction state. A copy-only or style-token change on an existing page needs only the changed text/style checked; it does not require a walkthrough unless a repository rule says so.

First read the repository's UI rules, shared-component guide and the closest existing feature that does the same job. Then check each changed page along its main task path (enter → judge → act → result → back):

- **States**: loading keeps the page structure and never shows empty-state copy; empty, error (with recovery), success, disabled and permission-denied states are distinct.
- **Raw values**: no enums, ISO/UTC timestamps, internal error objects, IDs instead of names, or markup from a renderer that expects another format reach the user. Trace the producer's output format into any reused renderer.
- **Actions**: primary, secondary and destructive actions are distinguishable, grouped and aligned as the rules require; destructive actions confirm; no control looks actionable but does nothing.
- **Forms and dialogs**: label position, width, control type (date/time/select versus free text), field count, and cancel/submit placement follow the rules.
- **Layout**: no overlap, overflow or unintended stretching at the repository's target viewports.
- **Reuse**: list the shared components the closest feature uses; a new page that hand-builds an equivalent instead of using a mandated component, or adds a parallel layout class, violates the rule unless the PR records an approved reason.

Runtime walkthrough: when a safe isolated preview exists (documented mock or synthetic-data mode, a static server over an extracted copy, or isolated temporary storage), render the changed pages, walk the main path and its states at the target viewports, and record screenshots or measured boxes. Static reading cannot establish overlap, alignment, width or state timing. When no safe preview exists, record the walkthrough as unverified and name the gate it affects; a repository rule requiring author walkthrough evidence before merge makes missing evidence a constraint or blocking question.

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
- Report maintainability as a defect only when it creates a concrete defect, hides a required invariant, or materially prevents safe verification. Proven scope/architecture violations, including breaches of mandatory repository UI or component rules, go in constraint issues even without a defect; unclear necessity goes in Questions. Pure style preference is neither.

## Risk-trigger matrix

| Changed surface | Deepen review for |
| --- | --- |
| Authentication, authorization, secrets, sensitive data | identity override, tenant/object binding, fail-open, disclosure, recovery |
| Writes, deletion, migration, synchronization | partial commit, lost update, replay, rollback, old/new data |
| Queue, retry, transaction, concurrency | duplicate, reorder, timeout ambiguity, crash window, durable idempotency |
| External irreversible effect | request identity, receipt, uncertainty, compensation, rate or account boundary |
| Public API, event, schema, storage | actual consumers, rolling deploy, mixed version, rollback compatibility |
| Shared high-call-volume code | blast radius, default behavior, hot-path cost, containment |
| New or restructured user-visible page, flow, form, dialog or shared UI component | states, raw values, action hierarchy, layout at target viewports, reuse against the closest feature and repository UI rules, runtime walkthrough |
| Local refactor, test, docs, copy-only or style-token UI change | only the changed invariant and direct tests; do not manufacture adversarial scenarios |

## Candidate-to-finding gate

Apply the [Skill’s evidence gate](../SKILL.md#evidence-gate--every-candidate): an in-scope cause, reachable path, concrete impact, evaluated controls and root-cause remedy. Unknown decisive facts become questions; prevented failures are not confirmed defects.
