# Code Change Review Output Template

Use the user's language. Keep the verdict and actionable evidence ahead of process narration.

## Attention and verdict

```text
Special attention: <concrete API/contract, table/field, architecture and existing-function changes; separate unverified impact>
Impact level: Low | Medium | High | Undetermined — <evidence-based reason; known floor if undetermined>
Scope/architecture: Conforms | Violates | Needs decision — <approved baseline and reason>
Merge readiness: Ready | Ready with non-blocking follow-ups | Unable to determine | Not ready
Reason: <one or two evidence-based sentences>
```

Special attention names concrete before/after behavior and evidence, even for approved, compatible or defect-free changes. With no trigger, say so briefly; with incomplete screening, name unchecked surfaces. This block can serve as a comment draft, never proof of publication.

### Impact level

| Level | Evidence-based meaning |
| --- | --- |
| `Low` | Local effect, no changed external contract, persistent semantics or shared behavior; independently reversible. |
| `Medium` | Bounded contract/data/function change with established compatibility and independent recovery. |
| `High` | Breaking compatibility, core data semantics or architecture ownership changes, broad shared/security paths, coordinated deployment, or hard-to-reverse effects. |
| `Undetermined` | Missing material evidence could change the level. State the known impact/floor and the missing consumer, scope or recovery facts. |

Choose the highest supported level, not an average, file count or score. Proven High remains High despite gaps or an approved breaking cutover; approval and recovery affect readiness separately. High calls for deeper attention, not automatic rejection.

A new write path alone does not prove ownership transfer or broad impact. If missing before/after responsibility or consumer facts decide the level, use Undetermined with known exposure.

### Scope and architecture

- `Conforms`: the capability scope and architectural choices fit approved requirements and applicable boundaries; no material unresolved scope/architecture decision remains. This is not a correctness verdict: an in-scope implementation can still have P0/P1 defects. A bounded user requirement and observed code can suffice; a formal architecture document is not mandatory.
- `Violates`: an added/removed capability, architectural choice or changed governance control conflicts with a specific approved scope, exclusion or mandatory boundary. Record a constraint issue below; an independently approved exception can establish Conforms.
- `Needs decision`: a material scope, necessity or boundary fact/decision is missing. Record a blocking `Q`; absence of approval evidence is not proof that approval was refused.

If both a proven violation and unknowns exist, retain Violates and list the questions. These statuses assess compliance, not whether architecture changed. No-defect wording never means Conforms or Ready by itself.

When there are no confirmed findings, include this exact sentence:

> 结论：未发现有代码证据支持的缺陷。

Do not add low-value suggestions merely because `Confirmed findings` is empty.

## Review answers

After the verdict, answer these five questions once for each material change group, in a compact table or short prose. Use the user's language and explicitly retain any extra priorities they requested.

| Question | Required answer |
| --- | --- |
| Need | Approved goal and its value, separately from observed prior failure; mark prior failure unverified when baseline evidence is absent. |
| Approach | Responsibility/data boundary, existing alternatives and why the chosen approach fits. |
| Scope | Concrete objects added/modified/removed; justified scope and any bundled or premature work. |
| Result | Original scenario → expected outcome → implementation evidence; what is resolved and what remains unverified. |
| Impact | Affected consumers/functions, contracts/state, compatibility, deployment and recovery. |

Keep requirement necessity, approach suitability and implementation correctness independent within these answers. Reuse evidence links and C/P/Q IDs; do not add a second change inventory repeating the same facts. Group checked-unchanged screening surfaces in one sentence and name unverified ones separately. Routine changes can use one short paragraph; empty ranges need no table. Preliminary reviews mark unassessed answers explicitly.

For rereviews, add a compact disposition of prior findings (resolved, retained, revised) and say whether coverage is the full final candidate or a delta. Identify self-review versus an actually separate independent review.

## Constraint issues

Use `C-01`, `C-02` for proven scope or architecture violations, separate from defect severity and Questions. Each contains:

- Baseline: exact approved requirement, exclusion or boundary and its source/version, including owner adoption if it began as a reviewer suggestion.
- Location and conflict: in-scope changed file/line and how its behavior conflicts.
- Impact: affected ownership, functionality or concrete new maintenance responsibility.
- Resolution: smallest removal/alignment or the specific owner decision needed; existing approval is evaluated, not requested again.
- Verification: direct evidence, actual checks and limitations.

A C blocks merge without needing a runtime defect. Pure preference is not C; missing evidence is Q. A correctness failure within approved scope (wrong arithmetic, broken consumer, lost atomicity or faulty identity propagation) is P, not an additional C merely because acceptance fails. Use C when restoring approved behavior still leaves an out-of-scope capability, unauthorized architecture choice or weakened governance control. One root cause gets one issue; reference its impact from other sections without adding a second C/P ID. Unrelated historic debt stays excluded.

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

Locations identify the smallest causal changed lines in target-file coordinates. Verify the cited line text with a numbered target-file readback. For diff-only evidence, reconstruct numbered new-side lines: start at the `+` hunk number, assign the current number to each context/added line, then increment; deleted lines and hunk headers neither receive nor advance that number. Cite the causal line from that reconstruction, not the hunk start or fixture-document line.

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
- Decision affected: <specific conclusion and merge/deployment/business acceptance gate>
- Resolution: <smallest decisive readback, test, owner answer, or artifact>
- Blocking: blocking | non-blocking
```

- `blocking`: identify the approved merge requirement or concrete reachable risk that depends on the answer; explain how the answer changes scope, a `P0/P1`, or necessary merge verification. Unknown environments alone do not qualify.
- `non-blocking`: the answer affects only a `P2`, future work, or an explicitly later/out-of-gate boundary. Retain later acceptance as a follow-up without claiming it passed.

## Merge readiness

| Condition | Verdict |
| --- | --- |
| At least one `P0/P1` or proven constraint issue (`Violates`) | `Not ready` |
| No blocking defect/violation, but `Needs decision`, scope is ambiguous, a blocking question remains, or necessary verification is incomplete | `Unable to determine` |
| `Conforms`, no `P0/P1` or blocking question; necessary verification is complete; only `P2`, non-blocking questions, or out-of-gate gaps remain | `Ready with non-blocking follow-ups` |
| `Conforms`, no confirmed findings or unresolved questions; necessary verification is complete | `Ready` |

The verdict covers only the declared range and evidence. It is not a claim that the entire repository, every deployment environment, or production behavior was verified.

## Verification

List only commands actually run in this review.

```text
- `<command>` — passed/failed/blocked; <count or decisive result>
- Direct code evidence — <what was proved without execution>
```

Never describe an unrun test as passing. Keep environment failure separate from product behavior.

## Coverage boundaries

List excluded or unverified code, consumers, environments and runtime behavior. For each material gap, identify the affected conclusion, its acceptance gate and the smallest missing evidence. Separate original-task/business acceptance from code-path proof and merge readiness.
