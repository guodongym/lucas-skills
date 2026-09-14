---
name: handoff
description: >
  Use when the user invokes $handoff (including $hanoff), or asks for a copyable
  交接包、交接提示词、接力上下文 for another agent/thread/session to review, implement,
  fix, or continue work. Do not select this skill for direct review/implementation,
  requests to edit the handoff skill itself, or a receiving agent executing a pasted package.
---

# Handoff

Generate a concise, repo-grounded prompt that another agent or thread can use to review, execute, fix, or continue the current work.

The deliverable is one copy-ready handoff package. The current assistant is the **sender**; the agent receiving the pasted package is the **receiver**. Review, implementation, fixes, and subagent execution described in the request belong to the receiver.

## Sender Boundary

- `$handoff 开始开发代码，以 subagent 模式` means **write a package telling the receiver to develop with subagents**. It does not tell the sender to start development or dispatch subagents.
- While preparing a handoff, gather the necessary read-only evidence, output the package, then stop. Do not execute its plan, perform its review, create a task, send a message to another session, or claim that work has been dispatched.
- A prior approval to implement is context to carry into the package. A current handoff request changes this turn's deliverable to the package; words such as “执行”, “开始开发”, and “review+fix” within that request describe the receiver's task.
- If the user also explicitly asks the sender to do preparation, such as “先补文档，再给交接包；实现不用你做”, finish only that authorized preparation and verification, refresh the snapshot, then hand off. Likewise, an explicit request to send the package or create a task is a separate action handled under the host's tool rules; this skill itself never initiates dispatch.
- If the user explicitly changes the request to “不要交接，你现在直接做”, leave this skill and use the workflow for that task. Editing this skill is also maintenance work, not a request to generate a package.

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

First establish that this is a handoff request. The following verbs select the **receiver's** task; they are not standalone triggers for this skill:

| User intent | Route |
| --- | --- |
| `$handoff review`, `审一下`, `review 这个 spec/plan/方案` | `review-spec-plan` |
| `$handoff 执行`, `$handoff 开始开发`, `按 plan 做`, `交给另一个 agent 实现` | `execute-from-plan` |
| `$handoff code review`, `review 这个实现/分支/diff` | `review-implementation` |
| `$handoff review+fix`, `审核并修`, `先 review 再修复` | `review-and-fix` |
| `$handoff continue`, `接力`, `总结上下文`, `让另一个会话继续` | `continue-from-context` |

Infer the route from the current request and conversation. For mixed requests such as “先审查规范和 Demo，再继续优化”, preserve that sequence with `review-and-fix`. Ask one plain-language question only when the missing answer changes the target or whether edits are authorized; do not ask the user to choose internal route names.

Include cleanup or branch deletion only when they belong to the delegated scope and have explicit authorization in the conversation; preserve the authorized objects and conditions.

## Grounding Steps

Before writing the handoff package, gather only the evidence needed for the route. Do not do a deep investigation unless the user asks for one; deep investigation belongs to the receiving agent.

1. Check the current repo, cwd, worktree path, branch, HEAD short SHA, and `git status --short` output when available.
2. If uncommitted changes are part of the target, record staged and unstaged summaries (`git diff --cached --stat`, `git diff --stat`) and relevant untracked paths separately. Neither HEAD nor a diff stat proves exact content identity; use a focused diff or file hash only when exact identity matters. Do not stage, stash, discard, or clean files to make a handoff easier.
3. For plan-execution handoffs, capture the last change of the plan and spec/design files with `git log -1 --oneline -- <path>`.
4. Identify referenced files, docs, specs, plans, commits, diffs, commands, and validation results.
5. Distinguish confirmed facts from memory-derived or user-stated claims.
6. If a file/path is referenced but missing or not readable, say that in the package.
7. If the user wants a package for another thread, include exact paths and checkout locations.
8. For implementation review, identify the intended base/ref or commit range, plus relevant local changes. “完整 diff” means all requested branch changes, not just the last commit or unstaged changes. If the base cannot be established, mark it for receiver verification rather than inventing it.

Never tell the receiving agent to trust this handoff blindly. The package should instruct them to re-check the live repo state. Avoid exhaustive search logs; write "not verified" or "path not found in current checkout" when that is enough.

## Receiving Agent Protocol

Include this section in every handoff package, adapted to the task:

```markdown
## 接手工作协议

1. 先读取并遵循目标仓库的本地指令，例如 AGENTS.md / CLAUDE.md / GEMINI.md。
2. 你是接收方：核对现场后执行本包任务，不要再次生成交接包。采用子代理驱动方式，主代理负责拆分任务、协调、集成与验收；执行方式见第 6 条。
3. 先核对 repo/cwd/worktree/branch 是否匹配交接目标或已有明确迁移授权。不一致时定位正确工作区，不得改写交接目标以匹配当前环境；仍无法确认时暂停该目标的执行并向发起方询问。
4. 目标身份一致后，对照包内 HEAD、工作区快照与未提交 diff 锚点（如有）。可解释且不改变目标、授权和验收的正常进展，更新快照后继续；无法查明或存在实质冲突时，只暂停受影响部分并确认。
5. 按本包声明的任务边界执行：review 保持只读；review+fix 在编辑任何文件前先报 findings，再做最小修复，再验证。
6. 执行方式：<按下面的任务类型填入具体要求，不得只写“使用匹配流程”>
```

Fill item 6 for every route:

- **Implementation / fixes / implementation continuation:** require `superpowers:subagent-driven-development`. Use a fresh implementation subagent per bounded task, a different reviewer for spec compliance and code quality, and a final review of the complete change. Preserve dependency order; subagent-driven does not mean parallel writes to shared files. A plan's generic `executing-plans` boilerplate does not override this receiving workflow.
- **Read-only review / review continuation:** require subagents for bounded review questions and the matching review skill. The main agent verifies evidence and consolidates findings; all agents stay read-only. Do not invoke an implementation workflow or authorize fixes for a review-only task.
- **Capability boundary:** if the named skill is unavailable but real subagent tools exist, preserve the same task delegation and independent review using those tools. If real subagent capability is unavailable, complete read-only grounding and report the missing capability; pause only dependent work until the user chooses an alternative. Do not silently replace subagents with single-agent execution or claim self-review is independent review.
- Preserve the user's model choice; inherit the current model unless the user explicitly selects another model or authorizes cost optimization. Preserve task-specific approval and stop conditions across all subagents.

These are instructions to put **inside the package**, not actions for the sender. Compress them to the requirements relevant to the route. If the user explicitly requests a different receiving workflow, follow that request and state it in the package.

## Output Shape

Output one complete Markdown package inside a single fenced code block so the user can copy it in one action. Use four backticks for the outer fence if the package contains triple-backtick command blocks. At most one short introductory sentence goes outside; every instruction the receiver needs stays inside. Start with the route name and target. Use this compact default shape:

```markdown
# Handoff: <route>

## 交接目标
- 角色: 你是接收方；核对现场后执行以下任务，不要再次生成交接包。
- 做什么: <一句话任务陈述>
- 为什么: <一两句 — 这项工作存在的动机或触发，不是复述上面的任务；不要另立"背景/触发"字段。plan/spec 已有背景章节时，只写一句本质并指向该文档>

## 定位
- repo:
- cwd:
- worktree:
- branch:
- HEAD: <短 SHA>
- 工作区: <clean / git status --short 摘要>
- target:
- target 最后改动: <git log -1 --oneline -- <path>；可选，交接对象为已提交内容时使用>

## 当前状态
- 已确认:
- 未确认:
- 授权边界: <接收方已获准做什么；哪些动作未获准；不因本包重新审批已有批准或扩大授权>

## 接手工作协议

## 重点

## 验收 / 返回

## 停止条件
```

Each route template below defines a `返回格式` block; it is the concrete form of `验收 / 返回` — include one of the two, not both.

Use the longer shape only when the handoff would otherwise be ambiguous:

```markdown
## 必读材料

## 停止条件

## 可选验证命令（最多 5 条单行命令，供接收方重新锚定现场）

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
- require the receiving subagent workflow above, including when the user only says “执行 plan” without repeating “subagent”
- include the accepted plan path and any corresponding spec/design document that actually exists
- to locate a referenced spec/design, check the plan header, its directory, then a focused docs/ search. If an independent plan already states the goal, constraints and acceptance, mark "spec/design: 无独立文档，按已批准 plan 执行"; missing a separate file is not a blocker. If a required decision is only in an unavailable reference, identify that gap and pause the dependent work
- implement only the requested scope
- keep changes surgical
- run route-specific validation
- carry forward existing approval from the conversation and linked decisions. Ask before new, unapproved dependencies, schema/API contracts, permission boundaries or default-behavior decisions; omission from the plan alone does not revoke independently recorded approval. Implementation choices inside the accepted scope do not require a stop
- keep the handoff short; locate missing requirement evidence only when it is needed to decide the next action, without inventing a plan/spec pair

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
- include an existing task progress ledger or unfinished subagent result only when needed to resume at the first incomplete task; record which implementation/review/validation remains. Do not include unrelated eval harness paths, output directories, or task-runner bookkeeping
- include important decisions, assumptions, and uncertainty
- recommend the next concrete step, but tell the receiving agent to verify before acting
- include repo, cwd, worktree, and branch even when other context is sparse
- keep this route especially short; context handoff should reduce switching cost, not recreate the transcript

Add this route-specific structure:

```markdown
## 当前目标
- 角色: 你是接收方；核对现场后继续以下任务，不要再次生成交接包。
- 为什么: <一两句 — 动机或触发，不是复述上面的目标>

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

## 接手工作协议

## 验收 / 返回

## 停止条件
```

Only add an "已执行操作" or "Commands run" section if the user asks for an audit trail or if one command result is essential to avoid repeated work. If the user provides too little task context, say what is missing and ask the receiving agent to re-anchor on the live repo; do not fill the gap with eval metadata or internal run details.

## Common Mistakes

- Treating `$handoff 开始开发` or an earlier implementation approval as sender execution authority.
- Creating or messaging a task when the user only asked for a copyable package.
- Leaving the receiving workflow optional, substituting `executing-plans`, or omitting the protocol from a continuation package.
- Producing unfenced prose or putting essential instructions outside the copyable block.
- Writing a vague summary without exact files, cwd, branch, or verification commands.
- Telling the receiving agent to trust prior conclusions instead of re-checking the repo.
- Mixing read-only review with implementation work.
- Sending a spec/plan review package that quietly asks the reviewer to implement.
- Letting a handoff become a long transcript. Compress to decisions, evidence, and next actions.
- Forgetting local instructions, the required receiving subagent workflow, or the user's existing authorization.
- Omitting the worktree path. Branch names alone are not enough when multiple checkouts exist.
