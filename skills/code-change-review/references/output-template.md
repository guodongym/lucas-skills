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

Special attention comes first whenever a trigger is present, even when compatible, approved, Medium/Low or Ready with zero defects. Name the actual interface, table/field and before/after behavior; give evidence locations. This block is reusable as a PR comment draft, not a claim of publication. If screening found no trigger, say so briefly; if incomplete, name the unchecked surfaces instead of claiming none.

### Impact level

| Level | Evidence-based meaning |
| --- | --- |
| `Low` | Local effect, no changed external contract, persistent semantics or shared behavior; independently reversible. |
| `Medium` | Bounded contract/data/function change with established compatibility and independent recovery. |
| `High` | Breaking compatibility, core data semantics or architecture ownership changes, broad shared/security paths, coordinated deployment, or hard-to-reverse effects. |
| `Undetermined` | Missing material evidence could change the level. State the known impact/floor and the missing consumer, scope or recovery facts. |

Choose the highest supported level, not an average, file count or numeric score. If High is already proved, retain High and list remaining gaps; a gap must never lower known impact. High is an attention/depth signal, not an automatic blocker. Necessary verification and unresolved decisions determine readiness separately.

A newly observed write path alone does not prove ownership transfer, core data semantics or broad impact. Establish its before/after responsibility and actual consumers; if those facts decide the level but are unavailable, use Undetermined with the known write exposure.

### Scope and architecture

- `Conforms`: the capability scope and architectural choices fit approved requirements and applicable boundaries; no material unresolved scope/architecture decision remains. This is not a correctness verdict: an in-scope implementation can still have P0/P1 defects. A bounded user requirement and observed code can suffice; a formal architecture document is not mandatory.
- `Violates`: an added/removed capability, architectural choice or changed governance control conflicts with a specific approved scope, exclusion or mandatory boundary. Record a constraint issue below; an independently approved exception can establish Conforms.
- `Needs decision`: a material scope, necessity or boundary fact/decision is missing. Record a blocking `Q`; absence of approval evidence is not proof that approval was refused.

If both a proven violation and unknowns exist, retain Violates and list the questions. These statuses assess compliance, not whether architecture changed. No-defect wording never means Conforms or Ready by itself.

When there are no confirmed findings, include this exact sentence:

> 结论：未发现有代码证据支持的缺陷。

Do not add low-value suggestions merely because `Confirmed findings` is empty.

## Change inventory

For material changes, use compact rows:

| Object / add-modify-remove | Approved need | Affected callers/functions/architecture | Compatibility / recovery | Evidence / gap |
| --- | --- | --- | --- | --- |

Cover the rubric's eight screening surfaces. Group checked-unchanged surfaces in one sentence; identify unverified ones separately. Empty ranges need no table. Counts may summarize objects but cannot replace their names, impact or evidence.

## Requirement, approach and correctness

For each material change, give three explicit judgments with evidence, either as a compact table or short prose:

| Change | Requirement necessity: problem and outcome | Approach suitability: boundaries and alternatives | Implementation correctness: behavior and defects |
| --- | --- | --- | --- |

Use supported, unsupported or unresolved conclusions in plain language; these are explanations, not a second severity system. Link to the existing C/P/Q entries rather than duplicating findings. Routine changes can use one sentence covering the three judgments. When only preliminary review was requested or completed, mark unassessed judgments explicitly.

## Constraint issues

Use `C-01`, `C-02` for proven scope or architecture violations, separate from defect severity and Questions. Each contains:

- Baseline: exact approved requirement, exclusion or boundary and its source/version.
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

List code, callers, consumers, environments, CI, external services, or runtime behavior that were excluded or could not be verified. State whether each boundary can affect the current verdict.
