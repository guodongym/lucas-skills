---
name: finishing-a-development-release
description: Use when a completed task branch or worktree must be released, especially for requests such as 发布收尾, 合并 main 后打 tag/push, 创建或补齐 GitHub/Gitee Release, or preserving ignored local configuration before cleanup.
---

# Finishing a Development Release

## Core Contract

- 先锚定 repo/worktree/branch/HEAD/base/upstream/remote 与授权。
- 默认快速路径；只在可观察风险出现时升级。
- 授权按动作分别确认：本地集成、push main、push annotated tag、创建平台 Release、删除 worktree、删除 branch 均不得从另一项授权推断。已有明确选择不得重复询问。
- force-push、移动已有 tag、覆盖 ignored/untracked 私有配置、删除未合并 branch 各自需要明确、逐项且指向目标的授权；普通 push/tag/cleanup/branch-deletion 授权不涵盖它们。缺少该授权时停止对应动作。

## Skill Composition

**REQUIRED SUB-SKILL:** Use `neat-freak` when the user names it or release-relevant documentation/governance escalation signals are present: versioned CHANGELOG or directly related release docs are missing, stale against the release tree, conflict with repository rules, or require a governed documentation update. 消费其文档变更与未解决漂移清单；不得复制完整审计、知识整理或规则同步流程。

**REQUIRED SUB-SKILL:** 有 WIP/fixup/重复/乱序提交或用户明确要求整理历史时，先使用 `git-history-rewrite` 作预检；消费 no-op/改写结论、backup ref、tree identity 与远端安全结果，不复制改写操作或 force-push 规则。

**REUSED CONTRACT:** Use `finishing-a-development-branch`; 消费已确认 base、既有集成选择、merged-tree identity 与所有权/cleanup 结论。编排器只保留既有选择、复用等价树证据、延后但不取消 cleanup；不得重写其集成选项、授权或删除规则。

**REQUIRED SUB-SKILL:** Use `verification-before-completion` before any successful merge, verification, release, or cleanup claim. 消费 fresh 命令、结果与对应 tree identity；不得另建完成标准或以旧日志替代证据。

## Fast Path

1. 锚定现场并记录本地状态候选快照：在当前 release 范围浅层盘点 ignored 与 untracked 的配置、secret、runtime 候选；不递归扫描 cache。只记录路径、key 名、元数据、等价性和分类计数，不读取或输出值。
2. 同步版本化 CHANGELOG 和直接相关文档；出现文档升级信号时先执行 `neat-freak`。
3. 有历史整理信号时先执行 `git-history-rewrite` 预检：可观察信号为 WIP、fixup、重复、乱序提交或用户明确要求；仅提交数或形式性 squash 不足以改写，曾推送但远端未刷新时在改写前停止。否则按已选路径集成 main，暂停 cleanup。
4. 在 main 对账本地状态并在 cleanup 前再次浅层盘点 ignored 与 untracked 候选，取得一次最终验证证据。仅当测试在当前 release run 内完成、测试命令成功、测试时的 Git tree object 与最终待发布的 Git tree object 相同，且测试输入所依赖的版本化配置未变时，才可复用该证据；任一条件不能证明则运行一次新的最终验证。不要为同一已证明等价树重复完整测试。
5. 在已授权范围内，只有仓库/provider 已建立支持时，才可用 atomic push 同时发布 main 与 annotated tag，并用一次 Git 回读验证两个 ref；否则 push main 并回读，再 push annotated tag 并回读。按 provider 能力创建 Release 后始终单独回读。若为既有历史 annotated tag 补建缺失的平台 Release，回读并保持该精确 tag 及其 peeled target；创建该平台 Release 时，其 target 必须为该精确回读的历史 annotated tag（及其已验证 peeled target），绝不为当前 main；不得移动、重建或改指向该 tag；notes 只取该版本专属 CHANGELOG 章节，tag/peeled target/章节任一不可验证时停止，不得臆造 notes。
6. 通过 cleanup 门禁后清理。

## Provider Result

Provider capability 仅在已知、已认证且有本仓库或 provider 官方文档支持的 Release 创建与回读路径存在时为可用；不得猜测私有 provider 接口或索取、输出 token。

| Result | Observable predicate |
| --- | --- |
| `Full Release` | main、annotated tag、原生平台 Release 和各自回读全部完成。 |
| `Portable Release` | provider 无可用 Release 能力；main、annotated tag、版本化 CHANGELOG 和 Git 回读完成。 |
| `Partial Release` | main/tag 已发布，但预期可用的平台 Release 创建或回读失败。 |
| `Blocked` | main/tag 写入失败，或版本、notes、remote 无法确定。 |

`Partial Release` 默认保留 worktree 和本地状态；仅可在 Cleanup Gate 六项全真时例外清理。报告失败的 provider 操作及重试来源，不把它称为 `Full Release`。`Blocked` 不进入 cleanup。

## Local State Gate

- 初始快照与 cleanup 前快照都必须浅层盘点 ignored 和 untracked 的配置、secret、runtime 候选；不递归扫描 cache。
- 只报告路径、key 名、元数据、等价性和分类计数，不读取或报告值。
- 同一 key 的不同值是 conflict；conflict 或 unclassified 大于 0 时保留 worktree，且不得用删除 worktree 代替丢弃 branch/commits 的授权。

## Cleanup Gate

仅在以下六项均为真时 cleanup：

1. 用户明确授权该 worktree 的 cleanup。
2. 已集成的最终树有一次最终验证，或有符合等价条件的复用验证证据。
3. main 已按授权 push 并回读。
4. annotated tag 已按授权 push 并回读。
5. provider 结果为 `Full Release`/`Portable Release`；或为 `Partial Release` 且 notes 已版本化固化、main/tag 已回读并可由明确 ref 恢复、本地状态已迁移/对账、已创建 backup ref。任何 Git 写入或回读失败仍为 `Blocked`。
6. 初始与 cleanup 前的 ignored/untracked 候选均已分类，conflict、unclassified 均为 0；所有 useful 候选已迁移到 main 工作区对应本地状态，并在不读取或输出 secret 值的前提下验证来源/目标等价；该 worktree 归当前流程安全清理。

## Final Report

Release / Version/tag / Main / Tag / Platform release / Verification / History / Local state / Cleanup / Residual risk
