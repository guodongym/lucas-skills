# Review scope and retrieval

## Snapshot selection

Prefer a user-specified PR, immutable endpoints, commit or file range, then a specified staged, unstaged or working-tree snapshot, then the current branch against a uniquely resolved baseline. Complete safe discovery first. Ask one scope question if competing choices could change the verdict.

| Input | Compare and include | Exclude |
| --- | --- | --- |
| Working tree / all uncommitted work | HEAD to current snapshot, including staged, unstaged and non-ignored untracked changes. Label each source. | Ignored content |
| Current branch | Committed changes to HEAD from the explicit base, otherwise PR base, otherwise the merge-base with the remote default branch. | Uncommitted work |
| PR | Live base/head and complete diff. Use local objects only when SHAs match. | Local WIP and later commits |

An explicit file range intersects the selected snapshot. Read beyond it for caller/consumer context only. An out-of-range location is reportable only if an in-range change introduced the defect.

Classify non-ignored untracked files before reading them. Apply ignore, secret and local-configuration rules. Leave credentials, private configuration and files that cannot safely be classified out of inspection. Report material exclusions as coverage gaps.

## Remote evidence

Choose the platform before retrieval. GitHub uses its live API (such as the GitHub connector) or authenticated `gh`, including `gh pr diff` for the diff. Ezone uses the available `ezone` Skill and bundled CLI for metadata, immutable endpoints, complete diffs, comments and gates. CLI startup requires no additional Skill. Interpret Ezone thread sides and outdated state only from verified Ezone fields. Missing independent-review capability affects only phases that require it.

Keep a verified host, company (where applicable), repository, PR and identity for reads and authorized writes. Re-anchor these facts after switching backends. For a comment, follow the platform-specific publication and readback in [PR comments](pr-comments.md).

If required objects are absent, retrieve them with an isolated temporary clone/fetch of the authorized repository. Preserve the reviewed checkout, index, refs and unrelated WIP. Honor explicit no-write and no-network limits. If no permitted retrieval works, mark affected conclusions unverified and continue independent review. Request only access or mutations outside existing authority.
