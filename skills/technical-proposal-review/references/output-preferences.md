# Output Preferences

Use these preferences when wording review findings.

## Preferred

- Lead with concrete risks and evidence.
- Explain why the issue affects implementation, migration, operations, or final review.
- Ask for specific proposal additions, not broad improvements.
- Keep findings concise but complete.
- Use severity only when evidence supports it.
- Use historical cases when they sharpen judgment.
- Preserve human final authority by listing review focus instead of pretending to approve final design.
- For platform audit or cross-service capability proposals, prioritize SDK/API contract gaps, architecture/text boundary mismatches, and this-phase vs future-optimization scope confusion before broader generic reliability comments when evidence supports them.
- For external capacity promises, prefer a matrix: `spec item -> control point -> metric source -> over-limit behavior -> capacity prerequisite -> alert`.
- For platform capability coverage, ask for a concrete coverage matrix with owner, current status, priority, and acceptance case.
- When standard identity protocols are relevant, first ask whether the other side can provide OAuth2/OIDC or an equivalent standard protocol; if not, require the current token bridge security contract.
- For authentication, gateway, or permission failure behavior, explain the business consequence before using terms such as `fail-open` or `fail-closed`.
- When a proposal allows requests to pass after authentication failure, require the allowed scenarios, time window, alerting, owner, and recovery path.
- When prior review questions and author answers are mixed into the proposal, treat questions as reviewer context and answers as proposal evidence; do not treat the questions themselves as current defects.

## Avoid

- Generic comments such as "consider security", "consider reliability", or "add monitoring" without specific missing evidence.
- Long generic architecture lectures.
- Repeating the same issue across multiple sections.
- Treating domain tags as exclusive categories.
- Over-weighting a low-impact wording issue.
- Calling an issue `P0` unless it blocks final human review readiness.
- Bundling validation, observability, rollout, rollback, audit, alerting, and effort estimate into one broad finding when only one or two artifacts are material.

## Feedback Signals

If the user says a comment is:

- `太泛`: require stronger evidence and a more specific action next time.
- `不是重点`: lower priority for similar evidence unless paired with stronger impact.
- `不可执行`: rewrite future findings to name the exact missing artifact or decision.
- `语气不对`: use direct technical wording and avoid performative agreement.
- `抓到重点`: preserve similar reasoning and severity in future runs.
- `打包太多`: split future comments so each finding names one primary missing artifact or decision.
- `没看懂`: rewrite the finding in plainer business and technical language before treating it as an accepted preference.
