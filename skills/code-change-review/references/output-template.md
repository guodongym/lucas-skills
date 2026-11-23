# Code Change Review Output Template

Use the [entry’s report contract and verdicts](../SKILL.md#report-and-verdict). For a bounded review with a finding, lead with attention and verdict, then give actionable disposition and verification/coverage. Integrate the five answers and scope once. For an expanded report, use sections for attention and verdict, review answers, scope, evidence entries, and verification/coverage. Skip empty sections. Preliminary reviews explicitly mark answers they could not assess.

## Scope and verification

Give repository/cwd, branch or detached HEAD and SHA, immutable endpoints or local snapshot, requirements used and exclusions. Disclose material sampling, unavailable consumers/environments and the smallest missing evidence for the affected acceptance gate. For commands actually run, give the command, passed/failed/blocked and the decisive result or count. Give direct code evidence separately. Environment failure alone establishes no product defect.

## Evidence entries

Report one issue per cause. Use stable IDs and list P0 before P1 before P2.

- **C-01** — approved baseline and source/version (with owner adoption for inherited suggestions), changed location and conflict, affected ownership/function/maintenance, smallest alignment or specific decision and actual evidence/verification limits. Evaluate approval already supplied.
- **P0-01 / P1-01 / P2-01** — changed causal location, current behavior, reachable path, user/data/protocol/system impact, controls and reversibility, smallest root-cause remedy, verification status and evidence. Keep unrelated historical debt out of the review.
- **Q-01** — missing evidence, affected conclusion and gate (merge, deployment or business acceptance), smallest resolution, and blocking/non-blocking status. Apply the entry’s blocking criterion.

### Location

Cite the smallest causal changed line(s) in target-file coordinates. Verify text with a numbered target-file readback. For diff-only evidence, start at the `+` hunk number and number each context/added line before incrementing. Deleted lines and hunk headers neither receive nor advance the new-side number. Use the resulting target-file line numbers for the causal code.
