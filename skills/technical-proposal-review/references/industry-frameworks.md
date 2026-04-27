# Industry Frameworks

This reference distills industry review practices into general proposal review questions. Do not copy a cloud-specific checklist into the final response. Use these frameworks to fill gaps beyond the user's historical cases.

## Source Frameworks To Consider

- AWS Well-Architected: operational excellence, security, reliability, performance efficiency, cost optimization, sustainability.
- Azure Well-Architected: reliability, security, cost optimization, operational excellence, performance efficiency.
- Google Cloud Architecture Framework: reliability, operational excellence, security, privacy, compliance, cost optimization, performance optimization.
- SEI ATAM: identify quality attribute scenarios, tradeoffs, risks, sensitivity points, and non-risks.
- SRE practice: define service level indicators, service level objectives, error budgets, and operational response.

## Distilled Review Questions

### Reliability

- What fails, how is it detected, and how does the system recover?
- Are retries bounded and idempotent?
- Are dependencies isolated enough to avoid cascading failure?
- Is fail-open or fail-closed behavior intentional?

### Security

- Who is authenticated?
- Who is authorized?
- What trust boundary changes?
- What sensitive data, tokens, credentials, or headers are created, forwarded, stored, or logged?
- How are keys rotated or revoked?

### Performance And Capacity

- What is the expected baseline and peak?
- Which component saturates first?
- What queue, shard, connection, token, or concurrency limit enforces the promise?
- How is overload communicated to callers?

### Operational Excellence

- What will operators monitor?
- What alerts indicate user-visible degradation?
- What manual runbooks or dashboards are required?
- Can rollout, rollback, and troubleshooting be done safely?

### Cost

- What new always-on resources are introduced?
- Does the design grow linearly with tenants, services, routes, indexes, shards, or keys?
- Can capacity be shared without breaking tenant fairness?

### Maintainability And Evolvability

- Does the design use standard extension points before custom forks?
- Are ownership boundaries clear?
- What future migration does this make easier or harder?

### Quality Attribute Tradeoffs

Use ATAM-style thinking when the proposal optimizes one quality by weakening another.

Examples:

- Lower latency by removing a queue may weaken recovery and backpressure.
- Strong isolation may increase cost and operational overhead.
- Global credentials may simplify writes but weaken domain isolation.
- Custom source changes may reduce short-term changes but increase upgrade cost.

Final review comments should name the tradeoff, not just the preferred side.
