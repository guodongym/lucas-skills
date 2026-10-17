---
name: finishing-a-development-release
description: Use when a completed task branch or worktree must be released, especially for requests such as 发布收尾, 合并 main 后打 tag/push, 创建或补齐 GitHub/Gitee Release, or preserving ignored local configuration before cleanup.
---

# Finishing a Development Release

## Core Contract

- 先锚定 repo/worktree/branch/HEAD/base/upstream/remote 与授权。
- 默认快速路径；只在可观察风险出现时升级。
- 按动作核对已有授权：本地集成、push main、push annotated tag、创建平台 Release、删除 worktree、删除 branch 不互相授予权限，但一次明确请求可以覆盖多项。目标、范围和风险未实质变化时沿用已有授权，不因阶段切换、子 Skill 菜单或最终汇报重复询问。
- force-push、移动已有 tag、覆盖 ignored/untracked 私有配置、删除未合并 branch 各自需要明确、逐项且指向目标的授权；普通 push/tag/cleanup/branch-deletion 授权不涵盖它们。缺少该授权时停止对应动作。

## Skill Composition

**REQUIRED SUB-SKILL:** Use `neat-freak` when the user names it or release-relevant documentation/governance escalation signals are present: versioned CHANGELOG or directly related release docs are missing, stale against the release tree, conflict with repository rules, or require a governed documentation update. 消费其文档变更与未解决漂移清单；不得复制完整审计、知识整理或规则同步流程。

**REQUIRED SUB-SKILL:** 有 WIP/fixup/重复/乱序提交或用户明确要求整理历史时，先使用 `git-history-rewrite` 作预检；消费 no-op/改写结论、backup ref、tree identity 与远端安全结果，不复制改写操作或 force-push 规则。

**REUSED CONTRACT:** Use `finishing-a-development-branch`; 消费已确认 base、既有集成选择、merged-tree identity 与所有权/cleanup 结论。按本合同复用选择和等价树证据，完成发布前延后 cleanup；仅在尚无集成选择时询问，不重新展示已回答的菜单。清理按下面的 Cleanup Gate 判断，保留对子 Skill 所发现唯一数据和所有权风险的检查。

**REQUIRED SUB-SKILL:** Use `verification-before-completion` before any successful merge, verification, release, or cleanup claim. 消费 fresh 命令、结果与对应 tree identity；不得另建完成标准或以旧日志替代证据。

## Fast Path

1. 锚定现场并记录本地状态候选快照：在当前 release 范围浅层盘点 ignored 与 untracked 的配置、secret、runtime 候选，以及拟清理的仓库内旧备份和临时文件；不递归扫描 cache。只记录路径、key 名、元数据、等价性和分类计数；允许工具在本地比较、复制与校验，禁止输出敏感值。
2. 同步版本化 CHANGELOG 和直接相关文档；出现文档升级信号时先执行 `neat-freak`。
3. 有历史整理信号时先执行 `git-history-rewrite` 预检：可观察信号为 WIP、fixup、重复、乱序提交或用户明确要求；仅提交数或形式性 squash 不足以改写，曾推送但远端未刷新时在改写前停止。否则按已选路径集成 main，暂停 cleanup。
4. 在 main 对账本地状态并在 cleanup 前再次浅层盘点 ignored 与 untracked 候选，取得一次最终验证证据。仅当测试在当前 release run 内完成、测试命令成功、测试时的 Git tree object 与最终待发布的 Git tree object 相同，且测试输入所依赖的版本化配置未变时，才可复用该证据；任一条件不能证明则运行一次新的最终验证。不要为同一已证明等价树重复完整测试。
5. 在已授权范围内，只有仓库/provider 已建立支持时，才可用 atomic push 同时发布 main 与 annotated tag，并用一次 Git 回读验证两个 ref；否则 push main 并回读，再 push annotated tag 并回读。按 provider 能力创建 Release 后始终单独回读。若为既有历史 annotated tag 补建缺失的平台 Release，回读并保持该精确 tag 及其 peeled target；创建该平台 Release 时，其 target 必须为该精确回读的历史 annotated tag（及其已验证 peeled target），绝不为当前 main；不得移动、重建或改指向该 tag；notes 只取该版本专属 CHANGELOG 章节，tag/peeled target/章节任一不可验证时停止，不得臆造 notes。
6. 发布成功且通过下面的 Cleanup Gate 后，完成已授权的任务 worktree、本地与远端分支及备份清理。

## Provider Result

Provider capability 仅在已知、已认证且有本仓库或 provider 官方文档支持的 Release 创建与回读路径存在时为可用；不得猜测私有 provider 接口或索取、输出 token。

| Result | Observable predicate |
| --- | --- |
| `Full Release` | main、annotated tag、原生平台 Release 和各自回读全部完成。 |
| `Portable Release` | provider 无可用 Release 能力；main、annotated tag、版本化 CHANGELOG 和 Git 回读完成。 |
| `Partial Release` | main/tag 已发布，但预期可用的平台 Release 创建或回读失败。 |
| `Blocked` | main/tag 写入失败，或版本、notes、remote 无法确定。 |

`Partial Release` 和 `Blocked` 均不进入 cleanup，保留 worktree、本地状态和有效备份。报告失败操作及重试来源，不把它们称为发布成功。

## Local State Gate

- 初始快照与 cleanup 前快照均按 Fast Path 第 1 项盘点，按实际用途与依赖区分当前有效状态、必要恢复内容和确认无恢复价值的内容；不能仅凭文件名、时间或“只有一份”决定去留。
- 当前有效的私有配置、业务数据、原始附件、身份及执行状态须保留在待删 worktree 之外的主工作区或原业务位置；位于待删 worktree 内的须先迁出，验证内容、权限及必要身份/状态等价，不覆盖有效配置。仅用于恢复或必要回退的内容纳入下面的恢复包。
- 确认无恢复价值的旧测试库、合成样本、截图、追踪、调试日志、构建副本、缓存和过期备份归入可删除项，不再全部打包保存。
- 同一 key 的不同值是 conflict；conflict 或 unclassified 大于 0 时暂停对应对象的删除，继续查明；不自动丢弃未保存改动或 branch/commits，不将当前业务数据当作缓存。

## Cleanup Gate

仅在以下六项均为真时 cleanup：

1. 用户已授权拟清理的本次任务 worktree、本地与远端分支，以及涉及的仓库内备份和临时文件；此前覆盖这些对象的授权继续有效。对象扩大或风险变化时暂停对应删除并询问，不跨仓库清理。
2. 已集成的最终树有一次最终验证，或有符合等价条件的复用验证证据。
3. main 已按授权 push 并回读。
4. annotated tag 已按授权 push 并回读。
5. provider 结果为 `Full Release`/`Portable Release`。任何 Git 写入或回读失败仍为 `Blocked`。
6. 待删除对象已完成本地状态分类与对账，conflict、unclassified 均为 0；必要内容已按下面规则保全并验证。删除前复核待删数据与已验证快照等价，worktree 无未保存改动、业务进程或其他任务占用，且归当前流程安全清理；状态变化则暂停对应删除，重新对账验证。

- 通过门禁后删除本次任务已合并、不再使用的 worktree 和本地、远端分支；保留 main、tag、未合并或仍在使用的工作。压缩合并（squash）须核对 PR 已合并、待删分支 head 与该 PR head 一致及实际合入内容，不能仅凭祖先关系或 PR 状态删除。分支删除须以已验证 head 为条件，引用变化则暂停对应删除。
- 每个仓库最终只保留一份必要恢复包，使用主工作区中待删 worktree 之外的稳定位置，限制访问权限。只收纳必要代码历史、有效私有配置、业务数据及恢复所需的身份和执行状态；必要回退点也放入同一包，附来源、版本、校验清单与恢复说明。旧包仅提取仍必要且未覆盖的内容，禁止备份套备份。
- 新包先校验，再在独立临时目录实际恢复，验证必要 Git 历史、数据库一致性、身份和执行状态、权限及符号链接；数据库采用一致性备份，SQLite 正确处理 WAL，只读冻结输入恢复后仍须只读。仅文件哈希相同不能证明可恢复。
- 同一仓库从读取旧包、生成与恢复验证至替换和冗余删除须互斥。轮换期间允许新旧包暂时并存；恢复验证全部通过后再原子替换旧包，删除已覆盖旧包、确认无用资料、冗余目录和临时文件。验证失败则保留原有效包及尚未安全保全的源数据，不删除当前业务数据、配置或未保存改动。
- 清理后回读 worktree、本地与远端分支、tag、剩余恢复包及主工作区状态，确认保留对象和当前业务状态未被改变。

## Final Report

Release / Version/tag / Main / Tag / Platform release / Verification / History / Local state / Cleanup（删除与保留对象、恢复包位置及实际恢复结果、清理前后占用）/ Residual risk
