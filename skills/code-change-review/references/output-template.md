# Code Change Review Output Template

Use the user's language. Keep the verdict and actionable evidence ahead of process narration.

## Verdict

```text
Merge readiness: Ready | Ready with non-blocking follow-ups | Unable to determine | Not ready
Reason: <one or two evidence-based sentences>
```

When there are no confirmed findings, include this exact sentence:

> 结论：未发现有代码证据支持的缺陷。

Do not add low-value suggestions merely because `Confirmed findings` is empty.

## Scope

```text
Repository/cwd: <path>
Branch/HEAD: <branch or detached> / <immutable SHA>
Range: <base/head, staged, unstaged, or working snapshot>
Requirements used: <user request, spec/plan, tests, contract, or none>
Excluded: <unrelated WIP, ignored content, out-of-range files, unavailable remote state>
```

## Confirmed findings

List `P0`, then `P1`, then `P2`. Omit this section's entries when there are none.

```markdown
### P1-01 — <short defect title>

- Location: `<file>:<line>`
- Current behavior: <what the changed implementation does or omits>
- Reachable path: <precondition → trigger → code path → bad state/effect>
- Impact: <specific user, data, protocol, or system consequence>
- Controls/reversibility: <existing checks, isolation, rollback, degradation; why insufficient>
- Remediation: <smallest direct root-cause correction>
- Verification: Verified | Unverified | Not applicable — <evidence or limitation>
```

Stable IDs use `P0-01`, `P1-01`, or `P2-01`. Merge findings with one root cause. A confirmed finding cannot use `Q-01`.

### Severity

- `P0 — blocking`: proved, reachable severe security, data-corruption, irreversible side-effect, or broad-unavailability risk; existing controls and reversibility are insufficient. Do not use `P0` without evidence of severity and containment failure.
- `P1 — important`: proved or fully traced functional regression, contract break, or bad state with material impact that should be fixed before merge. A missing test alone is not `P1`.
- `P2 — follow-up`: a real in-scope issue with narrow, controlled, independently reversible impact, or a directly related quality/control gap. Style preference is not `P2`.

Every `P0/P1` must state the reachable path, actual impact, and why existing controls or reversibility do not contain it. Otherwise downgrade to `P2` or `Q`.

## Questions

Questions are not confirmed findings.

```markdown
### Q-01 — <question>

- Missing evidence: <requirement, range, environment, runtime, or consumer fact>
- Decision affected: <scope, reachability, severity, or merge readiness>
- Resolution: <specific readback, test, owner answer, or artifact>
- Blocking: blocking | non-blocking
```

- `blocking`: the answer could change scope, establish a `P0/P1`, or determine a necessary verification; merge readiness cannot be decided yet.
- `non-blocking`: the answer affects only a `P2`, future work, or an explicitly out-of-gate boundary.

## Merge readiness

| Condition | Verdict |
| --- | --- |
| At least one `P0/P1` | `Not ready` |
| No `P0/P1`, but scope is ambiguous, a blocking question remains, or necessary verification is incomplete | `Unable to determine` |
| No `P0/P1` or blocking question; necessary verification is complete; only `P2`, non-blocking questions, or out-of-gate gaps remain | `Ready with non-blocking follow-ups` |
| No confirmed findings or unresolved questions; necessary verification is complete | `Ready` |

The verdict covers only the declared range and evidence. It is not a claim that the entire repository, every deployment environment, or production behavior was verified.

## Verification

List only commands actually run in this review.

```text
- `<command>` — passed/failed/blocked; <count or decisive result>
- Direct code evidence — <what was proved without execution>
```

Never describe an unrun test as passing. Keep environment failure separate from product behavior.

## Coverage boundaries

List code, callers, consumers, environments, CI, external services, or runtime behavior that were excluded or could not be verified. State whether each boundary can affect the current verdict.
