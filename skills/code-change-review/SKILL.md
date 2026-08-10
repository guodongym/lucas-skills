---
name: code-change-review
description: Use when the user asks to review implemented code changes in a working tree, staged diff, commit range, branch, or pull request for defects, regressions, test gaps, risk, or merge readiness. Skip proposal/RFC/PRD review, handling existing reviewer comments, debugging without a change scope, whole-repository audits, and implementation or fixes.
---

# Code Change Review

## Overview

Review implemented changes, not design intent alone. Prove reachable defects from repository evidence, assess existing controls before assigning severity, and say plainly when no supported defect exists.

Default to read-only work. Do not implement fixes, modify tests, mutate Git state, publish comments, resolve threads, or write external systems unless the user separately authorizes that work.

Before reviewing, read:

- [references/review-rubric.md](references/review-rubric.md) for the detailed review dimensions and risk triggers.
- [references/output-template.md](references/output-template.md) for finding fields, question handling, severity, and merge-readiness rules.

## Routing boundary

Use this Skill when the object being judged is implemented code and the decision is whether that implementation is correct or ready to merge. A proposal, RFC, PRD, or plan may be supporting requirement evidence, but is not required.

Route by the object being judged:

- Proposal completeness, feasibility, or implementation readiness: use `technical-proposal-review`.
- Existing GitHub reviewer comments or threads: use the comment-addressing workflow.
- Production symptoms without a defined change range: use systematic debugging.
- Whole-repository debt or over-engineering: use an audit workflow.
- Requested implementation or fixes: use an implementation workflow.
- Explicit request to review both proposal and code: run two independent reviews and return two independent verdicts.

## 1. Anchor the review scope

Record repository/cwd, branch or detached HEAD, current HEAD, base/head or working snapshot, excluded changes, and the requirement sources used.

### Input precedence

1. User-specified PR, immutable base/head, commit range, or file range.
2. User-specified staged, unstaged, or working-tree changes.
3. Current branch relative to a uniquely resolved baseline.
4. If multiple remaining choices would change the verdict, finish safe read-only discovery and ask one scope question.

Never silently choose an ambiguous baseline. Never merge unrelated local WIP into a committed-range or PR verdict.

### Deterministic snapshots

| Input | Include | Exclude | Compare |
| --- | --- | --- | --- |
| `staged` | tracked index changes | unstaged, untracked, ignored | `HEAD` to index |
| `unstaged` | tracked working-tree changes | staged, untracked, ignored | index to working tree |
| `working tree` or all uncommitted work | staged, unstaged, non-ignored untracked files | ignored files | `HEAD` to current uncommitted snapshot; label each source |
| commit range | the user-named endpoints and range | all other commits and uncommitted work | resolved immutable SHAs; preserve the user's two-dot or three-dot semantics |
| current branch | committed changes from baseline to `HEAD` | all uncommitted work | explicit base, else PR base, else remote-default merge-base; ask if still ambiguous |
| PR | live PR base/head SHAs and diff | local WIP and commits after PR head | remote PR metadata; use local objects only when SHAs match |

An explicit file range intersects the selected version snapshot. Read outside that intersection only for caller or consumer context; do not report an out-of-range line unless an in-range change introduced the defect.

For untracked files, obey ignore, secret, and local-configuration rules. Do not inspect ignored credentials or private configuration. If a non-ignored file cannot be classified safely, exclude it and state the coverage gap.

For PRs, prefer live API or `gh pr diff` evidence. Do not fetch by default. If required objects are unavailable, mark the call-chain or test conclusion unverified; request authorization before fetch, clone, or other persistent Git writes.

## 2. Establish the baseline

Use evidence in this order:

1. The user's requirement and approved proposal or plan.
2. Repository instructions, public contracts, schemas, migrations, and existing tests.
3. Pre-change behavior and relevant Git history.
4. Names, comments, and conventions only as leads.

Conflicting or missing requirements become a question or coverage boundary. Do not choose the interpretation that makes a candidate finding easier to claim.

Read the complete diff and change statistics before following the necessary callers, consumers, state transitions, persistence, queues, network calls, user-visible outputs, compatibility boundaries, failure paths, and directly related tests. Impact follows behavior and references, not file count.

## 3. Apply the reasoning rules

### First principles — always

For each material change, reconstruct:

- the prior observable behavior;
- the invariants that must still hold;
- the new assumptions introduced;
- the actual path from input to state or external side effect;
- the code, test, or counterexample that could disprove correctness;
- whether new complexity follows from a stated requirement.

Do not invent numeric thresholds for qualitative decisions.

### Adversarial review — deepen by risk

Deepen review for authentication, authorization, secrets, sensitive data, writes, deletion, migration, consistency, concurrency, transaction, queue, retry, idempotency, crash recovery, irreversible external effects, public contracts, mixed versions, or high-blast-radius shared code.

Trace a candidate through:

```text
precondition
→ trigger
→ actual code path
→ bad state or side effect
→ concrete impact
→ detection
→ containment and recovery
```

Try duplicate, reordered, stale, malicious, and boundary inputs where relevant. Also test partial success, dependency timeout, process crash, missing data, mixed versions, and rollback state. Low-risk UI, test, documentation, and local refactors receive only the checks relevant to their invariants.

### Evidence gate — every candidate

A confirmed finding requires all of these:

1. Specific code, test, history, or reproducible-behavior evidence.
2. A reachable path under realistic inputs within this change scope.
3. A concrete impact.
4. An assessment of existing validation, isolation, tests, rollback, degradation, and reversibility.
5. A remediation that addresses the demonstrated root cause.

Merge findings with one root cause. If a missing fact decides reachability or severity, emit `Q`, not a confirmed finding. If the shown control prevents the failure, do not restate the hypothetical as `P0/P1`; at most report a directly evidenced non-blocking gap.

## 4. Read-only safety gate

Use read-only Git inspection such as `status`, `diff`, `log`, `show`, and `merge-base`. Run a validation command only when every condition holds:

1. Record HEAD, refs, staged/unstaged state, and non-ignored untracked state first.
2. Use an existing repository command known not to format source, install or upgrade dependencies, migrate data, publish, send messages, or write production/shared services.
3. Limit expected writes to ignored tool caches, ignored build outputs, or operating-system temporary paths.
4. Re-read source, index, refs, and non-ignored untracked state afterward; they must match the baseline.

Do not remove pre-existing ignored or untracked content. Skip tests with uncertain side effects, external-resource writes, Git writes, or unavailable prerequisites and mark the affected conclusion unverified.

## 5. Verify the smallest decisive surface

Identify repository-standard tests, lint, typecheck, and build commands. Run only the smallest safe checks that can confirm or refute candidate defects, then expand when risk or repository rules require it.

Classify evidence as:

- `Verified`: run now or completely demonstrated by direct code evidence.
- `Unverified`: necessary evidence was blocked by environment, permission, external service, or safety constraints.
- `Not applicable`: the conclusion does not depend on that validation surface.

A passing test suite does not prove business correctness. A test environment failure does not prove a product defect.

## 6. Calibrate and report

Apply severity and Merge readiness exactly as defined in the output template. `P0/P1` must explain the reachable path, impact, and why existing controls or reversibility are insufficient. A missing test alone is not `P1`.

Lead with the verdict and confirmed findings. Keep `Questions` separate. Include actual commands and results, plus unchecked or unverified boundaries.

When no confirmed finding exists, state exactly:

> 结论：未发现有代码证据支持的缺陷。

Do not manufacture style advice, test suggestions, refactors, or speculative risks to fill the report.

## Common review failures

| Failure | Correction |
| --- | --- |
| Restating the diff | Trace callers, state, side effects, and consumers. |
| Treating a keyword as a defect | Prove reachability and concrete impact. |
| Ignoring a shown control | Re-run the failure chain through that control. |
| Promoting missing evidence to `P1` | Ask a blocking or non-blocking `Q`. |
| Calling an environment failure a product bug | Separate code evidence from runtime evidence. |
| Adding unrelated cleanup advice | Keep findings attributable to this change. |
