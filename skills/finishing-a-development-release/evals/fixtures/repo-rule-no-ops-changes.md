# Release Snapshot

Repository: `example/order-gateway` (deployable Go HTTP gateway).
Target release: `v2.1.1`. Previous stable tag: `v2.1.0`.
Authorization: user requested version release `v2.1.1` (no explicit deployment-package override).

## Repository Rules (`AGENTS.md`)
- "Every released version MUST include a release deployment record under `deploy/releases/<version>/`."

## Version Diff (`v2.1.0..HEAD`)
1. `internal/pricing/rounding.go` (modified): fixes an off-by-one cent rounding bug in discount calculation.
2. `internal/pricing/rounding_test.go` (modified): adds unit test covering the rounding edge case.
3. No changes to migrations, SQL, `.env.example`, config templates, dependencies, Docker/Compose, ports, cron jobs, queues, or startup flags.
