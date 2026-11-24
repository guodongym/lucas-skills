---
name: finishing-a-development-release
description: Use when a completed task branch, worktree, or version cut must be released, especially for requests such as 发布收尾, 合并 main 后打 tag/push, 整理版本部署文档与部署脚本, 创建或补齐 GitHub/Gitee/Ezone Release, or preserving ignored local configuration before cleanup.
---

# Finishing a Development Release

## Core Contract

- 先锚定 repo/worktree/branch/HEAD/base/upstream/remote、部署材料触发与版本基线、以及逐项授权。
- 默认快速路径；只在可观察风险或部署材料信号出现时升级。
- 按动作独立核对已有授权：本地集成、push main、创建/合入独立发布准备 PR、提交版本部署材料、push annotated tag、创建平台 Release、删除 worktree、删除 branch 互不自动推导，但一次明确请求可覆盖多项（明确切版本发版涵盖新增并提交该版本部署材料）。目标、范围和风险未实质变化时沿用已有授权，不因阶段切换、子 Skill 菜单或最终汇报重复询问。
- force-push、移动已有 tag、覆盖 ignored/untracked 私有配置、覆盖或修改内容不同的已存在同版本部署目录、删除未合并 branch、删除原有零散 PR 过程产物各自需要明确、逐项且指向目标的授权；本 Skill 严禁直连测试或生产环境执行任何远程部署。缺少授权或命中硬阻断时停止对应动作。

## Load Reference on Condition

未命中下表条件时仅用本入口完成常规快速路径，不读取参考文件：

| Condition | Read |
| --- | --- |
| 用户明确要求部署材料；或目标仓库规则明确要求每版产出部署/升级记录（且用户未显式跳过）；或无显式指令时同时命中项目可部署信号（服务容器/编排/网关/部署目录、受管或自建数据库迁移与 SQL 目录、服务配置模板或部署流程声明；纯文档/Skill/纯库/本地 CLI 仓库不命中）与版本变更信号（影响部署运行的真实变更或区间内 PR 过程产物；仅命中弱信号且归属不明时写入前简短确认） | [Deployment package](references/deployment-package.md) |

- **显式跳过优先**：用户明确要求跳过部署材料时，依据 `AGENTS.md`（用户当前明确要求优先于项目约定）立即放行跳过，不作二次打断确认；若覆盖了目标仓库规则，必须在最终报告的 `Deployment package: skipped (user override of repo rule)` 与 `Residual risk` 中记录。
- **历史 tag 补建平台 Release 模式**不触发入库部署材料生成。

## Skill Composition

**REQUIRED SUB-SKILL:** Use `neat-freak` when the user names it or release-relevant documentation/governance escalation signals are present: versioned CHANGELOG or directly related release docs are missing, stale against the release tree, conflict with repository rules, or require a governed documentation update. 消费其文档变更与未解决漂移清单；不得复制完整审计、知识整理或规则同步流程。

**REQUIRED SUB-SKILL:** 有 WIP/fixup/重复/乱序提交或用户明确要求整理历史时，先使用 `git-history-rewrite` 作预检；消费 no-op/改写结论、backup ref、tree identity 与远端安全结果，不复制改写操作或 force-push 规则。

**REUSED CONTRACT:** Use `finishing-a-development-branch`; 消费已确认 base、既有集成选择、merged-tree identity 与所有权/cleanup 结论。按本合同复用选择和等价树证据，完成发布前延后 cleanup；仅在尚无集成选择时询问，不重新展示已回答的菜单。清理按下面的 Cleanup Gate 判断，保留对子 Skill 所发现唯一数据和所有权风险的检查。

**REQUIRED SUB-SKILL (conditional):** 当目标发布 remote 为 Ezone 仓库且运行时已安装并预检通过 `ezone` Skill/CLI 时，使用 `ezone` 执行平台代码标签说明写入与回读；不得在此复制其 CLI 参数或认证实现。

**REQUIRED SUB-SKILL:** Use `verification-before-completion` before any successful merge, verification, release, or cleanup claim. 消费 fresh 命令、结果与对应 tree identity；不得另建完成标准或以旧日志替代证据。

## Release Paths

### 路径 A：常规快速路径（未命中部署材料，保持原顺序零回归）
1. 锚定现场并记录本地状态候选快照：浅层盘点 ignored 与 untracked 的配置、secret、runtime 候选及拟清理的旧备份和临时文件；不递归扫描 cache，只记录路径、key 名、元数据、等价性和分类计数，禁止输出敏感值。
2. 同步版本化 CHANGELOG 和直接相关文档；出现文档升级信号时先执行 `neat-freak`。
3. 有历史整理信号（WIP、fixup、重复、乱序或用户明确要求）时先执行 `git-history-rewrite` 预检，曾推送但远端未刷新时先停止；否则按已选路径集成 `main`，暂停 cleanup。
4. 在 `main` 对账本地状态并在 cleanup 前再次浅层盘点，取得一次最终验证证据。仅当测试在当前 release run 内完成、命令成功、测试 Git tree object 与最终待发布 Git tree object 相同且依赖的版本化配置未变时才可复用，否则重跑一次最终验证。
5. 按下方发布与回读规则完成远端写入与回读。
6. 通过 Cleanup Gate 后完成已授权清理。

### 路径 B：本地可合入 `main` 且命中部署材料
1. 锚定现场、本地 `main` 提交 SHA 与主工作区状态（保留用户原有无关未提交改动，禁止 stash/覆盖/清理），并记录本地状态初始快照。
2. 任务分支先同步最新 `main` 与按需 `git-history-rewrite`；**起点就在本地 `main` 且需要写入发布材料时，一律在独立临时 worktree / 准备分支上开展准备，严禁直接向主工作区写文件**。先完成 [Deployment package](references/deployment-package.md) 规定的全部只读预检与 SQL 阻断检查。
3. 全部只读预检通过后，在隔离准备分支/worktree 中同步 CHANGELOG、相关文档（按需 `neat-freak`）并生成/复用部署材料，完成全部脚本本地静态校验；任一环节阻断则停在本地报 `Blocked`，**保留隔离准备区与重试现场（沿用 Cleanup Gate，不做例外删除）**，确保本地 `main` 指针与主工作区保持原貌。
4. 全部校验通过并提交收口提交后，将本地 `main` 集成到该最终树（暂缓 cleanup），在最终树完成本地状态对账与覆盖该精确 Git tree object 的一次最终验证，再执行远端发布、回读与 Cleanup Gate。

### 路径 C：受保护分支 / `review-and-release-pr` 链路
1. 绝不向已审查 `PASS` 的功能 PR 追加跨版本 CHANGELOG 或部署材料；先按授权合入功能 PR 并保存平台返回的**实际合并 SHA**。
2. 基于该基线切出独立发布准备分支/PR（如 `release/<version>`），在其上完成只读预检、CHANGELOG、部署材料整理、本地静态校验与提交（按动作核对发布 PR 创建与合并授权）。
3. **按文件用途判定可执行内容审查门禁**：凡发布 PR 新增或修改任意路径下的可执行部署内容（脚本、SQL 或容器/编排/网关等基础设施执行配置，不限于兜底目录，同样覆盖项目自有目录如 `ops/`、`deploy/`），禁止同一上下文自审后自动合并，须经独立复审 `PASS` 且满足保护分支 CI/审批门禁，或由人工审批合入；待审时停在 `Blocked`（标注 `release PR awaiting review/merge` 及 PR URL），保留现场不打 tag、不进 cleanup。
4. 发布 PR 合入后，**保存平台返回的该发布 PR 实际合并 SHA**（绝不默认取远端最新 `main`），核对其合并树与已审查/验证树等价后以该精确 SHA 执行打 tag 与平台 Release。若等待期间 `main` 并入其他改动导致合并树实质变化，须重新核对受影响部署材料、重审并重验；若合入后 `main` 又因无关提交前移，仍锁定已验证的该实际合并 SHA（或停止请用户确认是否纳入新提交）。

## Provider & Tag Execution

- **GitHub / Gitee / Portable**：在已授权范围内，仅当仓库/provider 已建立支持时可用 atomic push 同时发布 `main` 与 annotated tag 并回读两个 ref；否则先 push `main`（或锁定保护分支发布 PR 实际合并 SHA）并回读，再 push annotated tag 并用 `git ls-remote` 回读。按 provider 能力创建原生 Release 后始终单独回读。为既有历史 annotated tag 补建缺失平台 Release 时，回读并保持该精确 tag 及其 peeled target（绝不为当前 `main`，不得移动或重建 tag），notes 只取专属 CHANGELOG 章节，任一项不可验证即停止。
- **Ezone**：
  - 正常全量发版（已授权 tag + 平台 Release 且 `ezone` 预检可用）：完成 `main` 推送/合入并回读精确 `main_sha` 后，**跳过**本地 `git push <tag>`，直接通过 `ezone` 一次创建代码标签与版本说明（传入精确 `main_sha`、短摘要与 notes，默认 `--no-notify`，仅用户明确授权通知并指定对象时使用 `--at`），随后做 `ezone` 回读 + `git ls-remote` 双回读验证 tag 锚定该精确 `main_sha`。创建失败且远端无该 tag 报 `Blocked`；远端已建 tag 但说明或回读校验失败报 `Partial Release`。
  - 仅授权 Git tag 未授权平台 Release，或预检 `ezone` 不可用：退回纯 Git annotated tag + `git ls-remote` 回读，按 `Portable Release` 收口（预检可用且已授权但实际执行/回读失败不得降级为 `Portable Release`）。
  - Ezone 历史 tag 补建说明：在 `ez release edit` 未于隔离测试标签实测确认不改写已有 annotated tag 对象与 peeled target 前，一律报 `Blocked`。

## Provider Result

Provider capability 仅在已知、已认证且有本仓库或 provider 官方文档支持的 Release 创建与回读路径存在时为可用；不得猜测私有 provider 接口或索取、输出 token。

| Result | Observable predicate |
| --- | --- |
| `Full Release` | 目标 `main`（含发布 PR 实际合并 SHA）、远端 tag、原生平台 Release 和各自回读全部完成。 |
| `Portable Release` | `main`、annotated tag、版本化 CHANGELOG 和 Git 回读全部完成，且平台 Release 属于以下两种合法不执行原因之一：平台无可用 Release 能力（`unavailable`），或本次仅授权 Git 发布、未授权创建平台 Release（`skipped (not authorized)`）。 |
| `Partial Release` | 预检确认平台 Release 可用且已授权，`main`/远端 tag 已发布，但原生平台 Release 创建或回读失败。 |
| `Blocked` | `main`/tag 写入失败，版本/基线/notes/remote 无法确定，部署材料或 SQL 命中硬阻断，发布 PR 待审（`release PR awaiting review/merge`），或 Ezone 历史 tag 补建未验证阻断。 |

`Partial Release` 和 `Blocked` 均不进入 cleanup，保留 worktree、隔离准备区、本地状态和有效备份。报告失败或阻断原因及重试来源，不把它们称为发布成功。

## Local State Gate

- 初始快照与 cleanup 前快照均按浅层盘点执行，按实际用途与依赖区分当前有效状态、必要恢复内容和确认无恢复价值的内容；不能仅凭文件名、时间或“只有一份”决定去留。
- 当前有效的私有配置、业务数据、原始附件、身份及执行状态须保留在待删 worktree 之外的主工作区或原业务位置；位于待删 worktree 内的须先迁出，验证内容、权限及必要身份/状态等价，不覆盖有效配置。仅用于恢复或必要回退的内容纳入下面的恢复包。
- 确认无恢复价值的旧测试库、合成样本、截图、追踪、调试日志、构建副本、缓存和过期备份归入可删除项，不再全部打包保存。
- 同一 key 的不同值是 conflict；conflict 或 unclassified 大于 0 时暂停对应对象的删除，继续查明；不自动丢弃未保存改动或 branch/commits，不将当前业务数据当作缓存。

## Cleanup Gate

仅在以下六项均为真时 cleanup：

1. 用户已授权拟清理的本次任务/准备 worktree、本地与远端分支及涉及的仓库内备份和临时文件；此前覆盖这些对象的授权继续有效。对象扩大或风险变化时暂停对应删除并询问，不跨仓库清理。
2. 已集成的最终树有一次最终验证，或有符合等价条件的复用验证证据。
3. `main` 已按授权 push 并回读，或受保护分支已锁定发布 PR 实际合并 SHA 并核对合并树与最终验证树一致。
4. tag 已按授权发布并回读：GitHub/Gitee/Portable 为 annotated tag 推送与 `git ls-remote` 回读；Ezone 一次创建为 `ezone` 与 `git ls-remote` 双回读确认锚定精确 `main_sha`。
5. provider 结果为 `Full Release`/`Portable Release`（无论原因是 `unavailable` 还是 `skipped (not authorized)`）。任何 Git 写入或回读失败仍为 `Blocked`。
6. 待删除对象已完成本地状态分类与对账，conflict、unclassified 均为 0；必要内容已按下面规则保全并验证。删除前复核待删数据与已验证快照等价，worktree 无未保存改动、业务进程或其他任务占用，且归当前流程安全清理；状态变化则暂停对应删除，重新对账验证。

- 通过门禁后删除本次任务/准备阶段已合并、不再使用的 worktree 和本地、远端分支；保留 `main`、tag、未合并或仍在使用的工作。压缩合并（squash）须核对 PR 已合并、待删分支 head 与该 PR head 一致及实际合入内容，不能仅凭祖先关系或 PR 状态删除。分支删除须以已验证 head 为条件，引用变化则暂停对应删除。
- 每个仓库最终只保留一份必要恢复包，使用主工作区中待删 worktree 之外的稳定位置，限制访问权限。只收纳必要代码历史、有效私有配置、业务数据及恢复所需的身份和执行状态；必要回退点也放入同一包，附来源、版本、校验清单与恢复说明。旧包仅提取仍必要且未覆盖的内容，禁止备份套备份。
- 新包先校验，再在独立临时目录实际恢复，验证必要 Git 历史、数据库一致性、身份和执行状态、权限及符号链接；数据库采用一致性备份，SQLite 正确处理 WAL，只读冻结输入恢复后仍须只读。仅文件哈希相同不能证明可恢复。
- 同一仓库从读取旧包、生成与恢复验证至替换和冗余删除须互斥。轮换期间允许新旧包暂时并存；恢复验证全部通过后再原子替换旧包，删除已覆盖旧包、确认无用资料、冗余目录和临时文件。验证失败则保留原有效包及尚未安全保全的源数据，不删除当前业务数据、配置或未保存改动。
- 清理后回读 worktree、本地与远端分支、tag、剩余恢复包及主工作区状态，确认保留对象和当前业务状态未被改变。

## Final Report

Release / Version/tag / Main / Tag / Platform release（含 `unavailable` 或 `skipped (not authorized)` 原因）/ Deployment package（`skipped` / `reused` / `generated` / `blocked`，附基线、路径、脚本校验与原 PR 过程产物建议）/ Verification / History / Local state / Cleanup（删除与保留对象、恢复包位置及实际恢复结果、清理前后占用）/ Residual risk
