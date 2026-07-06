---
name: handoff
description: >
  Use when the user explicitly invokes $handoff, or asks for agent handoff, 交接, 接力,
  another agent/thread/session to review or continue work, review prompt, execution prompt,
  context summary for another agent, spec/plan review delegation, implementation review,
  review+fix delegation, or transferring current repo/thread state for continued progress.
---

# Handoff

Generate a concise, repo-grounded prompt that another agent or thread can use to review, execute, fix, or continue the current work.

This skill is for delegation. Do not perform the delegated review or implementation unless the user separately asks for that. Produce a copy-ready handoff package that is short enough to preserve the receiving agent's focus while still giving the repo location, worktree, goal, constraints, and verification expectations.

## Core Principle

A good handoff is not a transcript. It is a compact launch brief that tells the receiving agent:

- what task they are taking over
- why the work exists, in one or two sentences, so they can resolve small ambiguities in the direction of intent instead of stopping or guessing
- where the work lives, including repo, cwd, worktree, and branch
- what workflow constraints they should follow
- what output the user expects back
- where they must stop and ask before changing scope

Keep the default package brief: aim for one screen, usually 300-700 words; the fixed 接手工作协议 block and the git snapshot fields do not count toward this budget. Add detail only when it prevents a likely mistake. Prefer pointers to exact files, commits, commands, and worktrees over long prose or copied logs.

## Human Quick Start

Use these short prompts when you want to trigger this skill directly:

- `$handoff review <spec/plan path>`: ask another agent to review the spec or plan only, without implementation.
- `$handoff 执行 <plan path>`: ask another agent to implement from an accepted plan, including the corresponding spec/design path.
- `$handoff code review <branch/diff/worktree>`: ask another agent to review the full current diff.
- `$handoff review+fix <scope>`: ask another agent to report findings first, then apply minimal fixes and verify.
- `$handoff 接力`: summarize the current worktree state so another thread can continue.

## Route the Request

Prefer the user's explicit short intent when present:

| User intent | Route |
| --- | --- |
| `$handoff review`, `审一下`, `review 这个 spec/plan/方案` | `review-spec-plan` |
| `$handoff 执行`, `按 plan 做`, `交给另一个 agent 实现` | `execute-from-plan` |
| `$handoff code review`, `review 这个实现/分支/diff` | `review-implementation` |
| `$handoff review+fix`, `审核并修`, `先 review 再修复` | `review-and-fix` |
| `$handoff continue`, `接力`, `总结上下文`, `让另一个会话继续` | `continue-from-context` |

If the request is ambiguous, ask one short question:

> 你是要 `review-spec-plan`、`execute-from-plan`、`review-implementation`、`review-and-fix`，还是 `continue-from-context`？

Do not add low-frequency cleanup or branch deletion workflows unless the user explicitly requests them in this turn.

## Grounding Steps

Before writing the handoff package, gather only the evidence needed for the route. Do not do a deep investigation unless the user asks for one; deep investigation belongs to the receiving agent.

1. Check the current repo, cwd, worktree path, branch, HEAD short SHA, and `git status --short` output when available.
2. For plan-execution handoffs, capture the last change of the plan and spec/design files with `git log -1 --oneline -- <path>`.
3. Identify referenced files, docs, specs, plans, commits, diffs, commands, and validation results.
4. Distinguish confirmed facts from memory-derived or user-stated claims.
5. If a file/path is referenced but missing or not readable, say that in the package.
6. If the user wants a package for another thread, include exact paths and checkout locations.

Never tell the receiving agent to trust this handoff blindly. The package should instruct them to re-check the live repo state. Avoid exhaustive search logs; write "not verified" or "path not found in current checkout" when that is enough.

## Receiving Agent Protocol

Include this section in every handoff package, adapted to the task:

```markdown
## 接手工作协议

1. 先读取并遵循目标仓库的本地指令，例如 AGENTS.md / CLAUDE.md / GEMINI.md。
2. 如果当前环境有 Superpowers 或同类 workflow skill，先调用匹配流程；否则按同等工程流程手动执行。
3. 不要只相信本交接摘要；先重新确认 repo/cwd/worktree/branch/diff，并对照包内 HEAD 与工作区快照。发现不一致时视为交接包已过期：停下向发起方确认，不要基于过期快照继续。
4. 按本包声明的任务边界执行：review 保持只读；review+fix 在编辑任何文件前先报 findings，再做最小修复，再验证。
```

Use "must" style only for safety and scope boundaries. Avoid over-constraining the receiving agent's implementation choices. Do not add generic process advice that the target repository's AGENTS.md already covers.

## Output Shape

Output one copy-ready Markdown package. Start with the route name and target. Use this compact default shape:

```markdown
# Handoff: <route>

## 交接目标
- 为什么: <一两句 — 解决什么问题/由什么触发。plan/spec 已有背景章节时，只写一句本质并指向该文档，不复述>

## 定位
- repo:
- cwd:
- worktree:
- branch:
- HEAD: <短 SHA>
- 工作区: <clean / git status --short 摘要>
- target:

## 当前状态
- 已确认:
- 未确认:

## 接手工作协议

## 重点

## 验收 / 返回

## 停止条件
```

Use the longer shape only when the handoff would otherwise be ambiguous:

```markdown
## 必读材料

## 停止条件

## 可选附录：已验证证据
```

Keep it compact. Prefer exact file paths, worktrees, branches, commands, and commit SHAs over narrative. Do not paste long command outputs. Do not include every command you ran unless the user asked for an audit trail.

## Route Templates

### review-spec-plan

Use for reviewing a spec, plan, RFC, proposal, roadmap item, or technical design before implementation.

Emphasize:

- review only; do not implement
- inspect both the document and the repo structure it references
- find missing requirements, false assumptions, untestable acceptance criteria, unclear scope, and implementation-risk gaps
- separate blockers from suggestions
- preserve the user's review authority
- keep the handoff short; include the plan path and worktree, not a full document paraphrase

Add this route-specific return format:

```markdown
## 返回格式
- Findings: 按 P0/P1/P2/Q 排序，每条包含证据和影响
- Suggested edits: 只描述建议修改，不直接改文件，除非用户明确要求
- Open questions: 需要用户或作者决策的问题
- Review verdict: ready / needs changes / blocked
```

### execute-from-plan

Use when the receiving agent should implement from an accepted spec or plan.

Emphasize:

- read the plan, then verify it still matches current repo state
- include both the implementation plan path and its corresponding spec/design document path in the handoff
- to infer the spec/design path, check in order: (1) links or "see also" references in the plan file header, (2) DESIGN/SPEC/ARCHITECTURE documents in the plan's own directory, (3) a docs/ search by feature name; if all three miss, mark it as "spec/design: 未提供，接手后向发起方确认" instead of omitting it
- implement only the requested scope
- keep changes surgical
- run route-specific validation
- stop on any externally visible behavior change the plan does not spell out: new dependencies, schema changes, API additions or signature changes, permission or auth boundary changes, and default-behavior changes. Implementation choices inside the plan's stated scope (log wording, local code structure) do not require a stop
- keep the handoff short; if the plan or spec/design path is missing, make "locate the plan/spec pair" the first task rather than expanding into speculative steps

For this route, extend the default `定位` fields (repo/cwd/worktree/branch/HEAD/工作区) with:

```markdown
- plan:
- plan 最后改动: <git log -1 --oneline -- <plan path>>
- spec/design:
- spec/design 最后改动: <同上；未提供则省略>
```

Add this route-specific return format:

```markdown
## 返回格式
- Changes: 改了什么和为什么
- Files changed: 关键文件
- Verification: 命令和结果
- Deviations from plan: 如有，说明原因
- Remaining risks / next step
```

### review-implementation

Use for code, feature branches, worktrees, diffs, or commits that should be reviewed before merge or handoff.

Emphasize:

- read the full current diff, not only the last fix commit or summary
- include the phrase "完整 diff" in implementation-review handoffs
- verify user-visible behavior and end-to-end reachability, not just internal plumbing
- include docs/spec/plan drift when those artifacts describe implementation
- findings first, ordered by severity, with file/line evidence when available
- keep review read-only
- keep the handoff short; name the diff range/worktree and review focus instead of listing every candidate file unless the user asked for a checklist

Add this route-specific return format:

```markdown
## 返回格式
- Findings first: severity, file/line, evidence, impact, remediation
- Verification performed: commands or checks run
- Test gaps / residual risk
- Verdict: merge-ready / needs changes / blocked
```

### review-and-fix

Use when the receiving agent should review and then apply minimal fixes.

Emphasize:

- first do the review pass and identify concrete findings
- before editing any file, report the initial findings that justify the fix
- fix only confirmed issues inside the requested scope
- do not refactor unrelated code
- rerun focused validation after fixes
- include the phrase "修复后聚焦验证" in review+fix handoffs
- summarize both findings and applied fixes
- keep the handoff short; make sequencing and scope boundaries more prominent than implementation speculation

Add this route-specific return format:

```markdown
## 返回格式
- Initial findings
- Fixes applied
- Files changed
- Verification
- Remaining risks
- Anything intentionally not changed
```

### continue-from-context

Use when the current work is midstream and another agent/thread needs enough state to continue.

Emphasize:

- summarize the real current state, not a polished success narrative
- separate completed, in-progress, not-started, and blockers; use the label "已知问题 / blockers" so the receiving agent sees blockers as a distinct status bucket
- include only command outcomes that affect the next step
- do not include eval harness paths, output directories, or task-runner bookkeeping unless that is the actual work being handed off
- include important decisions, assumptions, and uncertainty
- recommend the next concrete step, but tell the receiving agent to verify before acting
- include repo, cwd, worktree, and branch even when other context is sparse
- keep this route especially short; context handoff should reduce switching cost, not recreate the transcript

Add this route-specific structure:

```markdown
## 当前目标
- 为什么: <一两句 — 这项工作解决什么问题/由什么触发>

## 定位
- repo:
- cwd:
- worktree:
- branch:
- HEAD: <短 SHA>
- 工作区: <clean / 脏文件列表>

## 当前状态
- 已完成:
- 进行中:
- 未完成:
- 已知问题 / blockers:

## 关键上下文
- 相关文件:
- 相关文档:
- 相关线程 / 记忆线索:

## 已确认 / 待验证
- 已确认:
- 仍需验证:

## 继续推进建议

## 停止条件
```

Only add an "已执行操作" or "Commands run" section if the user asks for an audit trail or if one command result is essential to avoid repeated work. If the user provides too little task context, say what is missing and ask the receiving agent to re-anchor on the live repo; do not fill the gap with eval metadata or internal run details.

## Common Mistakes

- Writing a vague summary without exact files, cwd, branch, or verification commands.
- Telling the receiving agent to trust prior conclusions instead of re-checking the repo.
- Mixing read-only review with implementation work.
- Sending a spec/plan review package that quietly asks the reviewer to implement.
- Letting a handoff become a long transcript. Compress to decisions, evidence, and next actions.
- Forgetting to include local workflow instructions such as AGENTS.md and optional Superpowers usage.
- Omitting the worktree path. Branch names alone are not enough when multiple checkouts exist.
