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

Always require `github:github` or readable local `gh`, `code-change-review`, `superpowers:verification-before-completion`, and `finishing-a-development-release`.

Conditionally require:

- `technical-proposal-review` when the PR cites a formal PRD, RFC, spec, or technical proposal.
- `github:gh-address-comments` and `superpowers:receiving-code-review` when existing review comments, threads, or requested changes exist.
- `superpowers:systematic-debugging` and `superpowers:test-driven-development` before `FIX`.

Missing capability -> STOP. List the missing capability and affected phase. Do not install, authenticate, copy, skip, or approximate a missing Skill. Capability presence never grants authority.

## States

| State | Meaning | Next action |
| --- | --- | --- |
| `PASS` | The current gate has sufficient fresh evidence. | Continue. |
| `FIX` | A confirmed bounded defect has a direct repair and existing repair authority. | Disclose, use debugging and TDD, then rerun independent review. |
| `STOP` | Requirement, evidence, capability, risk, or repair needs a decision. | Draft or publish an authorized PR comment and stop. |

P0/P1 always block merge. blocking Q -> STOP. P2 is non-blocking by default.

## Phase 0: Anchor facts, capabilities, and authority

Record repository, PR number, PR URL, base branch, base SHA, head SHA, main, Draft/mergeable/check/review state, requirement sources, local worktree/branch/HEAD/WIP exclusions, selected GitHub backend, and runtime capabilities.

Record authority independently for repair, PR comment, push, merge, tag/Release, production, and cleanup. Never infer one action from another.

Probe the connector first. A private-repository 404 or NOT_FOUND with working identity is a connector_scope_gap, not proof of logout. Probe `gh auth status` and the target repository read-only. Lock one main GitHub backend for canonical PR facts and writes. Another backend may supply thread-aware read-only data only after repository, PR number, and head SHA match.

Both GitHub backends unavailable -> STOP. Preserve the original errors and do not log in, refresh credentials, or change GitHub App installation scope.

## Gate 1: Review the requirement from first principles

Use approved user requirements, linked Issue/PRD/RFC/spec, repository contracts, real callers, and observable baseline behavior in that order. PR titles, commits, and code names are clues only.

Answer whether the problem exists, the goal fits project contracts, acceptance is verifiable, the PR solves the declared problem, added complexity follows from the requirement, and what evidence would overturn the conclusion.

PASS only when goal, evidence, constraints, and acceptance are executable. Missing evidence that could change scope is a blocking Q and STOP. An unreasonable, contradictory, already-satisfied, unverifiable, mis-scoped, or unjustifiably risky requirement is STOP. Do not inspect repair details to rationalize a failed requirement.

With PR comment authority, publish the gate result through the locked backend and read it back. Without authority, produce the same content as a draft. Do not continue until an updated requirement passes a fresh Phase 0 and Gate 1.

## Phase 2: Verify existing review independently

When existing review comments, threads, or requested changes exist, **REQUIRED SUB-SKILL:** use `github:gh-address-comments` for thread-aware state and `superpowers:receiving-code-review` to verify each actionable claim.

Classify unresolved, resolved, outdated, informational, and duplicate threads. For each claim, verify evidence, reachability, impact, controls, root cause, and whether the proposed repair actually closes it. Keep these results separate from independent findings.

When no existing review comments, threads, or requested changes exist, record `no existing review` and the coverage boundary, then proceed directly to Phase 3.

A newly exposed requirement problem returns to Gate 1. A reviewer suggestion requiring a product or technical decision is STOP.

## Phase 3: Run an independent code review

**REQUIRED SUB-SKILL:** Use `code-change-review` against the immutable current base/head. Do not seed it with inherited finding counts or treat resolved threads as proof.

Map the result:

- PASS: no P0/P1 or blocking Q, necessary verification exists, and only P2/non-blocking Q/declared coverage boundaries remain.
- FIX: the defect is confirmed, direct repair is inside the approved requirement and PR, repair authority exists, and it changes no API, Schema, dependency, product semantics, cross-module ownership, or irreversible behavior.
- STOP: any P0, blocking Q, missing evidence, decision-bearing repair, multiple long-term behaviors, or scope expansion.

Before FIX, disclose finding ID, impact, root cause, repair scope, and verification. Use `superpowers:systematic-debugging` and `superpowers:test-driven-development`. Re-anchor the new head and rerun code-change-review; never jump from a repair directly to release.

## Final verification and release handoff

**REQUIRED SUB-SKILL:** Use `superpowers:verification-before-completion` before any completion, merge, or release claim.

Refresh PR body, base SHA, head SHA, requirement, main, review state, and checks. Prove the tested tree is the merge tree or has verifiable tree identity. Any material base SHA, head SHA, requirement, main, or checks change invalidates affected evidence.

Only the latest independent review PASS may enter `finishing-a-development-release`, and only for already authorized push, merge, and release actions. cleanup always requires separate authority.

## State summary

Report PR/base/head, backend and capabilities, phase, state, requirement sources, inherited review result, independent findings/questions, verification tree, granted actions, stop reason, and next action. A resumed task must read live state again; the summary is navigation, not current truth.

## Common failures

- Optimizing implementation before the requirement passes.
- Treating inherited review as independent review.
- Repairing P0 or decision-bearing changes silently.
- Reusing stale SHA, review, check, or test evidence.
- Switching GitHub backends without re-anchoring repository, PR, and head.
- Inferring PR comment, merge, release, production, or cleanup authority from repair authority.
