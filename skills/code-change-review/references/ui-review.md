# User-visible UI review

For copy-only or style-token changes on an existing page, check the changed text or style and confirm the surrounding control and behavior are unchanged. A walkthrough is required for these only if the repository says so.

Trace changed backend inputs into their renderers and check the visible result even on existing pages.

For added or restructured pages, flows, forms, dialogs, actions, layouts, interaction states or shared UI, read repository UI rules, the shared-component guide and the closest existing feature that does the same job. Trace the main task from entry through decision, action, result and return. Check each changed page.

| Surface | Check along the task path |
| --- | --- |
| States | Loading keeps the structure and does not show empty copy. Empty, error with recovery, success, disabled and permission-denied states are distinct. |
| Raw values | Resolve IDs to names. Keep raw enums, ISO/UTC timestamps, internal error objects and source markup out of display. Verify the producer/renderer format matches. |
| Actions | Distinguish primary, secondary and destructive actions, with mandated grouping and alignment. Confirm destructive actions. Verify every actionable control works. |
| Forms and dialogs | Check labels, widths, control type (date/time/select versus free text), field count and cancel/submit placement. |
| Layout | Look for overlap, overflow and unintended stretching at target viewports. |
| Reuse | Compare the closest feature and the changed page by component name. Record mandated components reused, replaced or missing. Hand-built equivalents or parallel layout classes that bypass mandatory components require a traceable approved reason. |

## Runtime walkthrough

For new or restructured UI or when repository rules require a walkthrough, run a safe isolated preview if available. Follow [Validation safety](validation-safety.md). Render the changed pages, walk the main task and its states at the repository's target viewports, and collect screenshots or measured boxes. Static evidence cannot establish overlap, width, alignment or state timing.

Record `UI coverage` with pages, rules/reuse and walkthrough status, viewports and states. Distinguish author-supplied evidence from checks performed here. If no safe preview exists, mark the walkthrough unverified with the reason and affected gate. When mandatory pre-merge walkthrough evidence is missing from both author and reviewer, use C for a proved rule breach or blocking Q for an unresolved prerequisite. Merge readiness cannot be Ready or Ready with non-blocking follow-ups.
