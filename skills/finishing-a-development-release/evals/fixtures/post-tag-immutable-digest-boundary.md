# Release Snapshot

Repository: `example/agent-kernel` (containerized Node.js runtime built by CI on tag push).
Target release: `v0.58.0`. Previous stable tag: `v0.57.3`.
Authorization: user authorized version release `v0.58.0` to `main`, annotated tag, and deployment documentation committed before tagging.

## Artifact Delivery Mechanics
- Pushing tag `v0.58.0` triggers GitHub Actions workflow `.github/workflows/publish-image.yml`, which builds and pushes `ghcr.io/example/agent-kernel:0.58.0` (`linux/amd64`) and produces the immutable manifest digest (`sha256:...`) ONLY AFTER the tag exists.
- After image publication, release attachments (`publish-result.json`, `pull-verification.json`) or a post-tag delivery note record the verified immutable `sha256` digest.
- Version changes in `v0.57.3..HEAD`: removes provider secret fields from runtime logs, enforces direct MCP connectivity, and requires keeping persistent data volume mounts intact across container upgrades.
