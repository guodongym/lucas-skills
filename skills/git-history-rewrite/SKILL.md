---
name: git-history-rewrite
description: >
  Git commit-history rewrite workflow for cleaning up a task branch before push, PR, or release.
  Use this skill whenever the user asks to整理提交历史, 合并本次任务提交, squash/fixup/amend/rebase commits,
  clean up WIP commits, make each commit independently reviewable, keep an appropriate commit granularity,
  preserve a normal chronological story, or prepare a branch for force-with-lease push. Also use it for
  Chinese prompts such as "把本次任务的提交历史酌情合并一下", "粒度适中", "每个提交独立闭环",
  "提交之间保持正常演进的时间线顺序", and "push 前重整提交".
---

# Git History Rewrite

Rewrite a task branch's commit history into a small, reviewable, chronological sequence before push or PR.

This skill is about engineering judgment, not automatic squashing. The target history should tell the story of the work: each commit should compile as a coherent step when practical, have a clear purpose, and avoid leaving fixup/WIP churn for reviewers.

## Safety Boundaries

Treat history rewriting as high-risk until proven local and safe.

Stop and ask before rewriting when any of these are true:

- The working tree is dirty or has staged changes unrelated to the rewrite.
- The base commit is unclear.
- The branch has already been pushed and the user did not explicitly approve rewriting remote history.
- The branch is shared, protected, or appears to have collaborator commits.
- The candidate range contains merge commits.
- The local branch is behind its upstream.
- The user asks to delete commits whose purpose is unclear.

Use `--force-with-lease`, never plain `--force`, when pushing rewritten remote history.

## Quick Inspection

If available, run the bundled read-only inspector first:

```bash
python3 <skill-dir>/scripts/inspect_history.py
```

Use `--base <rev>` when the intended base is known:

```bash
python3 <skill-dir>/scripts/inspect_history.py --base origin/main
```

Replace `<skill-dir>` with the directory that contains this `SKILL.md`.
The inspector only reads Git state. It must not be used as permission to rewrite; it is a factual preflight report.

## Workflow

### 1. Establish the rewrite range

Gather facts before proposing any change:

```bash
git status --short --branch
git branch -vv
git log --oneline --decorate --graph --max-count=30
git log --reverse --stat <base>..HEAD
git log --merges --oneline <base>..HEAD
git diff --stat <base>..HEAD
```

Choose `<base>` conservatively:

- Prefer the target integration branch or PR base, such as `origin/main`, `origin/master`, `upstream/main`, `upstream/master`, or the branch named by the user.
- If the branch has an open PR, use the PR base branch when it can be checked with the available GitHub tooling.
- Do not use a same-named tracking branch such as `origin/<feature>` as the rewrite base. It is evidence that the branch was pushed; use it for remote-risk checks instead.
- Use the branch's upstream as the rewrite base only when it is clearly the integration branch, not the same feature branch.
- If multiple bases are plausible, ask before rewriting.

For pushed or PR branches, refresh remote state before trusting ahead/behind data. If network access or GitHub access is unavailable, mark the remote state as unverified and stop before rewriting.

### 2. Classify commits

Read the commit subjects and patches in order. Group them by purpose:

- Feature slice: introduces one coherent behavior or user-visible capability.
- Test slice: adds or updates tests that belong with a behavior change.
- Fixup/WIP: repairs an earlier commit, typo, formatting, missed import, or follow-up adjustment.
- Docs/release/chore: should remain separate only when it is a real review boundary.

Prefer folding fixup/WIP commits into the commit they repair. Do not merge unrelated behavior just because the commits are small.

### 3. Propose the target history

Before rewriting, show a compact plan:

```markdown
Base: <base sha/branch>

Current commits:
1. <sha> <subject>
2. ...

Target commits:
1. <type(scope): subject>
   - includes: <old shas>
   - closes over: <files/behavior>
   - verify: <command or reason not applicable>
2. ...

Risk gates:
- pushed: yes/no
- remote state refreshed: yes/no
- dirty worktree: yes/no
- merge commits in range: yes/no
- needs force-with-lease: yes/no
```

Ask for confirmation if any safety boundary is present. If the branch is clearly local-only, clean, and the user already asked to rewrite, proceed after presenting the plan.

### 4. Protect the current state

Before changing history, create a local backup ref:

```bash
git branch backup/<branch>-before-history-rewrite-YYYYMMDD-HHMMSS HEAD
```

Tell the user the backup ref name in the final report.

If the backup ref is ever lost, `git reflog` still records the pre-rewrite HEAD as a last resort.

### 5. Rewrite with the least surprising tool

Interactive editors are unavailable in agent environments such as Claude Code and Codex, so
plain `git rebase -i` is a human-terminal-only option. Prefer the non-interactive forms below,
picking the simplest one that preserves intent:

- `git commit --amend` for a single tip fixup.
- `git reset --soft <base>` followed by scoped commits for reordering, squashing, or splitting.
  This is the most general tool. It discards original author dates; say so in the plan when
  that matters.
- `git commit --fixup=<sha>` then `git rebase --autosquash <base>` to fold a fix into an earlier
  commit without touching the rest. Git >= 2.44 runs `--autosquash` non-interactively; on older
  Git use `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <base>` as the equivalent.
- A generated todo file with `GIT_SEQUENCE_EDITOR="cp <todo-file>" git rebase -i <base>` when
  full reorder/reword control is needed without an interactive editor.
- Plain `git rebase -i <base>` only when a human will run it in their own terminal.

Keep chronological order. A later commit may depend on an earlier one; avoid moving commits ahead of their prerequisites just to group by file type.

Commit messages must follow the repository's own convention. If the repo requires bodies or trailers, preserve that rule in every rewritten commit.

### 6. Verify the rewritten history

Run fresh checks before claiming success:

```bash
git log --reverse --oneline <base>..HEAD
git diff --stat <base>..HEAD
git diff --check <base>..HEAD
```

Then run the tree-identity check against the backup ref created in step 4:

```bash
git diff --quiet backup/<ref> HEAD && echo "tree identical" || echo "TREE DIFFERS"
```

A pure history rewrite (squash, reorder, reword) must leave the final tree byte-identical, so
expect `tree identical`. If the tree differs, show `git diff --stat backup/<ref> HEAD`, explain
every difference, and get the user's confirmation before treating the rewrite as verified. An
unexplained difference means restore from the backup ref instead of proceeding.

Also run the most relevant project tests, lint, typecheck, or build commands. If a full suite is too expensive or unavailable, run the closest targeted checks and say what was not run.

Compare the final diff against the pre-rewrite intent. The rewritten history should change commits, not product behavior.

### 7. Push only when appropriate

For local-only branches, push normally if the user requested push.

For previously pushed branches, require explicit approval unless the user's current request already includes remote handling. Push with:

```bash
git push --force-with-lease
```

If `--force-with-lease` rejects, stop. Do not retry with `--force`; fetch and re-evaluate.

### 8. Backup cleanup

Keep the backup ref by default; it is the recovery path if a problem surfaces after push. Include
the cleanup command in the final report instead of deleting anything. When the user explicitly
asks to clean up, list the matches first with
`git branch --list 'backup/<branch>-before-history-rewrite-*'`, then delete with `git branch -D`.

## Output Format

End with:

```markdown
History rewritten.
- Base: <base>
- Backup ref: <backup/ref or "not needed">
- Final commits:
  1. <sha> <subject> - <closed-loop purpose>
  2. ...
- Verification:
  - <command>: <result>
- Push:
  - <not pushed / pushed / needs user approval>
- Backup cleanup: `git branch -D <backup-ref>` (run once you are confident)
- Residual risk:
  - <none known or concise caveat>
```

If you stopped at a risk gate, replace "History rewritten" with "Stopped before rewriting" and list the exact gate.
