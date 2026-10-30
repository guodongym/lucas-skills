---
name: review-and-release-pr
description: Use when a Codex user requests an end-to-end pull request workflow involving requirement validation, existing review verification, independent review, authorized fixes, and merge or release. Skip isolated code review, proposal-only, comment-only, bugfix-only, release-only, PR-inventory-only, and cleanup-only requests.
---

# Review and Release PR

## Overview

Orchestrate an end-to-end PR decision without replacing specialized Skills. Requirement validity comes before implementation quality. Existing review and independent review are separate evidence sets. Every external write requires authority for that exact action.

## Support boundary

- Codex-only means globally discoverable across Codex projects, not portable across Agent tools.
- Claude, GitHub Copilot, Antigravity, and WorkBuddy are unsupported surfaces in v0.1.
- Do not use --tool all. Deployment may enable only the Codex target.

## Runtime capability gate

Use available `github:github` or local `gh` for PR evidence, `code-change-review` for independent review, and `superpowers:verification-before-completion` for completion evidence. Load `finishing-a-development-release` when authorized work reaches release; a later phase's missing tool does not block earlier independent work.

Use these specialized Skills when available and relevant:

- `technical-proposal-review` when the user requests design review, the PR materially changes the design, or an unresolved design decision needs review. Read an unchanged approved PRD/RFC/spec as requirement evidence; its citation alone does not restart a full proposal review.
- `github:gh-address-comments` and `superpowers:receiving-code-review` when existing review comments, threads, or requested changes exist.
- `superpowers:systematic-debugging` and `superpowers:test-driven-development` before `FIX`.

A missing Skill name is not a missing capability. Use existing equivalent tools or manual review when they preserve the same authority, review independence and evidence requirements; disclose the substitute. In particular, thread-aware `gh`/API data can replace a missing comment Skill only when identity, current head and resolved/outdated thread state can be verified. If no permitted equivalent exists, pause the affected phase and finish independent work. Do not install, authenticate, broaden access or claim an unavailable check passed. Capability presence never grants authority.

## States

| State | Meaning | Next action |
| --- | --- | --- |
| `PASS` | The current gate has sufficient fresh evidence. | Continue. |
| `FIX` | A confirmed bounded defect has a direct repair and existing repair authority. | Disclose, use debugging and TDD, then rerun independent review. |
| `STOP` | Requirement, evidence, capability, risk, or repair needs a decision. | Draft or publish an authorized PR comment and stop. |

P0/P1 always block merge. Proven constraint issues (`Violates`) and blocking Q (`Needs decision`) -> STOP. P2 is non-blocking by default. High impact alone does not block merge.

## Phase 0: Anchor facts, capabilities, and authority

Record repository, PR number, PR URL, base branch, base SHA, head SHA, main, Draft/mergeable/check/review state, requirement sources, local worktree/branch/HEAD/WIP exclusions, selected GitHub backend, and runtime capabilities.

Record authority independently for repair, PR comment, push, merge, tag/Release, production, and cleanup. One explicit request may cover several actions; carry it across phases without asking again. Authority for one action alone does not authorize another.

Probe the connector first. A private-repository 404 or NOT_FOUND with working identity is a connector_scope_gap, not proof of logout. Probe `gh auth status` and the target repository read-only. Lock one main GitHub backend for canonical PR facts and writes. Another backend may supply thread-aware read-only data only after repository, PR number, and head SHA match.

Both GitHub backends unavailable -> pause remote-dependent work. Continue any useful local review, label stale or missing remote evidence, and do not merge/release without the required fresh facts. Preserve original errors; do not log in, refresh credentials, or change GitHub App installation scope.

Screen the anchored diff for the `code-change-review` rubric's Special attention triggers before Gate 1. This preliminary change inventory is not an independent correctness review; mark unchecked architecture, consumers and functions explicitly. Preserve observed changes in the attention report even if Gate 1 stops.

## Gate 1: Review the requirement from first principles

Use approved user requirements, linked Issue/PRD/RFC/spec, repository contracts, real callers, and observable baseline behavior in that order. PR titles, commits, and code names are clues only.

Answer whether the problem exists, the goal fits project contracts, acceptance is verifiable, the PR solves the declared problem, added complexity follows from the requirement, and what evidence would overturn the conclusion.

Apply `code-change-review`'s impact/constraint rules to the approved pre-change baseline: scope, capability necessity and architecture boundaries. PR edits to rules, tests or architecture docs cannot approve themselves. Accept independently traceable prior approval without asking again. A known scope conflict is a constraint issue; missing material approval/consumer evidence is a blocking Q. Do not manufacture a runtime defect to reject an unjustified capability.

PASS only when goal, evidence, constraints, and acceptance are executable. Missing evidence that could change scope is a blocking Q and STOP. An unreasonable, contradictory, already-satisfied, unverifiable, mis-scoped, or unjustifiably risky requirement is STOP. Do not inspect repair details to rationalize a failed requirement. Use code-change-review’s first-principles and adversarial rules to test the current-stage user path and inherited claims, including capability losses from proposed simplification. An absent required production adapter, entry point or usable result is not merely post-deployment acceptance; an approved foundational stage also need not deliver later roadmap features.

On STOP, deliver the gate result and preliminary Special attention through the comment protocol below. Do not continue until an updated requirement passes a fresh Phase 0 and Gate 1.

## Phase 2: Verify existing review independently

When existing review comments, threads, or requested changes exist, use `github:gh-address-comments` for thread-aware state and `superpowers:receiving-code-review` to verify each actionable claim, or the equivalent path established by the runtime capability gate.

Classify unresolved, resolved, outdated, informational, and duplicate threads. For each claim, verify evidence, reachability, impact, controls, root cause, and whether the proposed repair actually closes it. Keep these results separate from independent findings.

When no existing review comments, threads, or requested changes exist, record `no existing review` and the coverage boundary, then proceed directly to Phase 3.

A newly exposed requirement problem returns to Gate 1. A reviewer suggestion requiring a product or technical decision is STOP.

## Phase 3: Run an independent code review

**REQUIRED SUB-SKILL:** Use `code-change-review` against the immutable current base/head. Do not seed it with inherited finding counts or treat resolved threads as proof.

Map the result:

- PASS: Scope/architecture is Conforms, no constraint issue/P0/P1/blocking Q, necessary verification exists, and only P2/non-blocking Q/declared coverage boundaries remain. Approved High-impact changes can pass.
- FIX: Scope/architecture is Conforms, no constraint issue or blocking Q, the defect is confirmed, direct repair is inside the approved requirement and PR, repair authority exists, and it changes no API, Schema, dependency, product semantics, cross-module ownership, or irreversible behavior.
- STOP: any P0, Violates, Needs decision, blocking Q, missing necessary evidence, decision-bearing repair, multiple long-term behaviors, or scope expansion. Do not auto-repair a constraint issue under bounded bug-fix authority or edit requirements to obtain PASS.

Consume the five review answers (need, approach, scope, result, impact), impact level, constraint issues, questions and readiness from the independent review; do not maintain a second scoring rubric. A newly exposed requirement conflict returns to Gate 1. A no-defect verdict cannot erase impact or a constraint issue. Deliver Special attention using the protocol below on PASS, FIX or STOP; it is not reserved for failed reviews.

Before FIX, disclose finding ID, impact, root cause, repair scope, and verification. Use `superpowers:systematic-debugging` and `superpowers:test-driven-development`. Re-anchor the new head and rerun code-change-review over the original base to the final candidate. If this context implemented the candidate or FIX, obtain a separate reviewer/context (use a fresh subagent when available); its own rerun is self-review, not the independent PASS required for release. Reuse equivalent prior checks, but independently review the repair and affected paths. Without an available independent reviewer, STOP release and report that gap; continue unaffected authorized work.

## Special attention and PR comments

Use `code-change-review`'s `references/pr-comments.md` for the shared comment format, authority, fresh-state checks, deduplication, publication and readback. Apply it on PASS, FIX and STOP; do not infer comment authority from merge or repair authority. Produce the protocol’s complete standalone comment, including its five review answers; mark unsupported answers unassessed. Compact chat summaries do not replace or shorten the required publication fields.

At Gate 1 STOP, retain preliminary Special attention and requirement findings, mark approach/correctness judgments unassessed where appropriate, and label full independent review incomplete. At Phase 3, preserve the independent review's five answers and constraint/defect/question conclusions in the shared comment format. Required but unconfirmed comment delivery blocks automated merge/release even if code readiness passed.

## Final verification and release handoff

**REQUIRED SUB-SKILL:** Use `superpowers:verification-before-completion` before any completion, merge, or release claim.

Refresh PR body, base SHA, head SHA, requirement and approval sources, main, review state, and checks. Prove the tested tree is the merge tree or has verifiable tree identity. Any material base SHA, head SHA, requirement, approval, main, or checks change invalidates affected evidence, including impact and constraint conclusions. Refreshing facts does not itself require rerunning equivalent tests or a full proposal review. Choose new checks from the actual change in behavior, inputs, configuration or environment; when necessary evidence remains sufficient, finish the authorized handoff without another clean-review round. Refresh the attention summary/comment when its content or anchored version changes.

Only the latest independent review PASS may enter `finishing-a-development-release`, and only for already authorized push, merge, and release actions. Pass the concrete task worktree/local and remote branch identities, PR head, existing cleanup authority and exclusions, anchored tree/local-state evidence and any completed merge/release readbacks to that Skill; it performs pending integration and release verification. Its Local State Gate and Cleanup Gate exclusively govern cleanup and recovery-package retention; do not maintain a second policy here. An earlier explicit request covering the cleanup objects remains sufficient while scope and risk are unchanged. Report its cleanup and recovery results or blockers without treating review PASS as cleanup evidence.

## State summary

Lead with Special attention, impact level, Scope/architecture and readiness. Keep PR/base/head, backend/capabilities, requirement/approval sources, review origin, tested tree, granted actions and phase evidence in the task record. In the user report, give the current candidate, material findings/decisions, actual verification boundaries, comment delivery (posted/reused URL, draft, failed or unverified) and next authorized action; link a complete report instead of repeating its inventories. Explain the origin of new findings using code-change-review’s rereview rules. A resumed task must read live state again; the summary is navigation, not current truth.

## Common failures

- Optimizing implementation before the requirement passes.
- Treating inherited review as independent review.
- Repairing P0 or decision-bearing changes silently.
- Reusing stale SHA, review, check, or test evidence.
- Switching GitHub backends without re-anchoring repository, PR, and head.
- Inferring PR comment, merge, release, production, or cleanup authority from repair authority.
- Hiding a new interface/table/field or architecture/function change behind green tests or a no-defect verdict.
- Treating High impact as a defect, or allowing a PR to approve its own scope/architecture exceptions.
