---
name: finishing-a-development-release
description: Use when a completed task branch or worktree must be released, especially for requests such as 发布收尾, 合并 main 后打 tag/push, 创建或补齐 GitHub/Gitee Release, or preserving ignored local configuration before cleanup.
---

# Finishing a Development Release

## Core Contract

- 先锚定 repo/worktree/branch/HEAD/base/upstream/remote 与授权。
- 默认快速路径；只在可观察风险出现时升级。
- 授权按动作分别确认：本地集成、push main、push annotated tag、创建平台 Release、删除 worktree、删除 branch 均不得从另一项授权推断。已有明确选择不得重复询问。

## Skill Composition

**REQUIRED SUB-SKILL:** Use `neat-freak` when the user names it or release-relevant documentation/governance escalation signals are present: versioned CHANGELOG or directly related release docs are missing, stale against the release tree, conflict with repository rules, or require a governed documentation update.

**REQUIRED SUB-SKILL:** Use `git-history-rewrite` when WIP/fixup/duplicate/out-of-order commits are present or the user explicitly requests history cleanup.

**REUSED CONTRACT:** Use `finishing-a-development-branch` for base confirmation, the chosen integration path, merged-tree verification, ownership-safe cleanup, and branch deletion; preserve an existing user choice, reuse equivalent-tree evidence, and defer cleanup until release gates pass.

**REQUIRED SUB-SKILL:** Use `verification-before-completion` before any successful merge, verification, release, or cleanup claim.

## Fast Path

1. 锚定现场并记录本地状态候选快照。
2. 同步版本化 CHANGELOG 和直接相关文档；出现文档升级信号时先执行 `neat-freak`。
3. 有历史整理信号时先执行 `git-history-rewrite`：可观察信号为 WIP、fixup、重复、乱序提交或用户明确要求；否则按已选路径集成 main，暂停 cleanup。
4. 在 main 对账本地状态并取得一次最终验证证据。仅当测试在当前 release run 内完成、测试命令成功、测试时的 Git tree object 与最终待发布的 Git tree object 相同，且测试输入所依赖的版本化配置未变时，才可复用该证据；任一条件不能证明则运行一次新的最终验证。不要为同一已证明等价树重复完整测试。
5. 在已授权范围内 push main 并回读；push annotated tag 并回读；按 provider 能力创建并回读 Release。
6. 通过 cleanup 门禁后清理。

## Provider Result

Provider capability 仅在已知、已认证且有本仓库或 provider 官方文档支持的 Release 创建与回读路径存在时为可用；不得猜测私有 provider 接口或索取、输出 token。

| Result | Observable predicate |
| --- | --- |
| `Full Release` | main、annotated tag、原生平台 Release 和各自回读全部完成。 |
| `Portable Release` | provider 无可用 Release 能力；main、annotated tag、版本化 CHANGELOG 和 Git 回读完成。 |
| `Partial Release` | main/tag 已发布，但预期可用的平台 Release 创建或回读失败。 |
| `Blocked` | main/tag 写入失败，或版本、notes、remote 无法确定。 |

`Partial Release` 保留 worktree 和本地状态，报告已经回读的 main/tag 与失败的 provider 操作；在不改变已发布 Git 产物的前提下，取得授权后重试或由用户选择补建/回滚，不把它称为 `Full Release`。`Blocked` 不进入 cleanup。

## Local State Gate

- 只报告路径、key 名、元数据、等价性和分类计数，不报告值。
- 同一 key 的不同值是 conflict；conflict 或 unclassified 大于 0 时保留 worktree，且不得用删除 worktree 代替丢弃 branch/commits 的授权。

## Cleanup Gate

仅在以下六项均为真时 cleanup：

1. 用户明确授权该 worktree 的 cleanup。
2. 已集成的最终树有一次最终验证，或有符合等价条件的复用验证证据。
3. main 已按授权 push 并回读。
4. annotated tag 已按授权 push 并回读。
5. provider 结果为 `Full Release` 或 `Portable Release`，不是 `Partial Release` 或 `Blocked`。
6. 本地状态已分类且 conflict、unclassified 均为 0，并且该 worktree 归当前流程安全清理。

## Final Report

Release / Version/tag / Main / Tag / Platform release / Verification / History / Local state / Cleanup / Residual risk
