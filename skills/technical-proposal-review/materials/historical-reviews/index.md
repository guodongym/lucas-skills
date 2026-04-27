# Historical Review Materials Index

This public index describes historical proposal and review material used to calibrate the skill. Exact source filenames and full source files live under `../private/historical-reviews/` and are intentionally ignored by git. Keep reusable, shareable knowledge in `references/`, `feedback/accepted/`, and this index; keep raw proposal text and local path mappings private.

## Sources

| Case | Private Source Key | Domain Tags | Notes |
|---|---|---|---|
| CASE-001 | `CASE-001` | `auth`, `security`, `maintainability` | SSO and login-state authority review |
| CASE-002 | `CASE-002` | `auth`, `gateway`, `observability`, `migration` | Internal gateway authentication and user attribution |
| CASE-003 | `CASE-003` | `gateway`, `auth`, `migration`, `security`, `maintainability` | API key plugin merge and open source fork risk |
| CASE-004 | `CASE-004` | `audit`, `observability`, `maintainability` | Operation audit coverage, reuse boundary, and MVP-first rollout |
| CASE-005 | `CASE-005` | `logging-observability`, `operations`, `capacity` | Service log collection, index lifecycle, and rollout |
| CASE-006 | `CASE-006` | `multi-tenant-capacity`, `reliability`, `operations`, `cost` | Tenant fairness, capacity promises, queue consistency, and HPA design |
| CASE-007 | `CASE-007` | `audit`, `sdk`, `cross-service`, `maintainability` | Operation audit v2 snapshot with author responses, architecture/current-state ambiguity, SDK/API contract gaps, and phase-boundary feedback |

## Loading Guidance

- Load `references/case-bank.md` first.
- Open full source files only when proposal similarity, calibration, or feedback processing requires details.
- If `../private/historical-reviews/index.local.md` exists, use it to map a case key to an exact local source path.
- If a referenced private file is unavailable, continue with tracked references and accepted feedback. The skill remains usable, but cannot perform source-level traceability for that case.
- Existing human `评审意见` can be used as reviewer context, calibration data, or comparison baseline. Do not treat prior review comments as proposal-body evidence for a new finding.
- For blind replay evals, use externally prepared masked inputs from the evaluation workspace rather than the private source files directly.

## Privacy Rules

- Do not commit files under `../private/historical-reviews/`, including local path maps.
- Do not paste raw proposal text, tenant names, internal domains, credentials, or customer-sensitive details into tracked references or feedback.
- When turning a source detail into a reusable rule, summarize the pattern and remove unnecessary identifiers.
