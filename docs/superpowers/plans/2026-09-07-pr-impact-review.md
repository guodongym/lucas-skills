# PR 影响审查增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在已有代码审查与 PR 编排中识别架构冲击、范围越界和无必要能力，并输出证据化定级。

**Architecture:** `code-change-review` 的规则和模板是判断的唯一来源；`review-and-release-pr` 消费结果并保持原有状态与授权边界。复用现有 JSON 评测清单及 unittest，不添加运行器。

**Tech Stack:** Markdown、JSON、Python unittest、现有 PyYAML、独立评测 agent。

**Spec:** `docs/superpowers/specs/2026-09-07-pr-impact-review-design.md`

## Global Constraints

- 不增加独立 skill、评分系统、依赖、自动标签或审批平台。
- 不修改 Agent Manager；初始实施阶段不推送、不发布、不激活到用户工具目录。后续本地合并、清理与生效采用用户明确追加的授权，见收尾记录。
- 已有审查只读、外部写入授权和 P0/P1/P2 缺陷证据规则保持有效。
- 英文 skill 与评测沿用英文，设计和执行记录使用中文。

## Task 1：代码审查的影响与约束结论

**Files:** 修改 `skills/code-change-review/SKILL.md`、`references/review-rubric.md`、`references/output-template.md`、`evals/evals.json`、`tests/test_code_change_review_skill.py`；在现有 `evals/fixtures/` 增加本设计的 12 个原始案例。

**Interfaces:** 消费固定变更快照与已认可需求；输出 Impact level、Scope/architecture、独立约束问题和现有 Merge readiness。

- [x] 写入 12 个自包含案例与预期断言。每个只提供该案例材料，不泄露 counterpart、预期答案或其他案例。
- [x] 新增案例要求单元测试检查 ID 唯一、fixture 存在、安全反例对应真实问题；先运行并观察缺失案例失败。
- [x] 对核心范围扩张案例以旧版 skill 做 5 次独立运行；保存原始输出并逐条人工判读，记录规则遗漏或证据判断失败。
- [x] 实施设计定义的八维筛查、变更前可信基线、能力必要性、影响等级和范围结论；模板新增所需字段与合并条件。
- [x] 以新版 skill 对同案例做 5 次独立运行，再执行其他新增与旧行为案例；按清单断言逐条评估，不把文本匹配当行为通过。
- [x] 验证：`uv run --frozen python -m unittest discover -s tests -p 'test_code_change_review_skill.py' -v`。

## Task 2：PR 编排消费结果并完成验证

**Files:** 修改 `skills/review-and-release-pr/SKILL.md`、`tests/test_review_and_release_pr_skill.py`；新增 `skills/review-and-release-pr/evals/evals.json` 保存 7 个离线状态与评论情境；执行结果追加到本计划，不创建独立报告体系。

**Interfaces:** 消费 Task 1 四种独立判断；沿用 `PASS / FIX / STOP` 与发布前验证。

- [x] 用旧版 PR skill 对纯越界、批准后的高影响、关键依据缺失三种审查结果及三种评论情境做隔离状态判断，记录基线差异；另补局部缺陷修复情境验证修订。
- [x] 在 Gate 1 引用同一必要性与约束判断；Phase 3 按 `Conforms / Violates / Needs decision` 映射状态；输出摘要增加影响和范围结论。新增接口、表字段、架构或功能变化必有特别提醒；有评论授权就发布并回读，检查重复和内容变化，无授权给草稿，失败要披露。
- [x] 用新版复跑七种状态和评论场景，验证越界无 Bug 仍 STOP、高影响符合约束可 PASS、缺证 STOP；不实际读写远端。
- [x] 独立 reviewer 对照已确认设计检查最终差异；修正有依据的问题，定向重跑受影响检查。
- [x] 验证：`uv run --frozen python -m unittest discover -s tests -q`；对两个 skill 运行系统 skill-creator 的 `scripts/quick_validate.py`；`git diff --check`。
- [x] 记录实际次数、失败原因、修复和覆盖边界；按仓库规范提交本次变更，保留分支供用户审阅。

## 设计与计划复核

已对照当前两个 skill、输出模板和既有 24 个评测条目自检。八维筛查、四种结论、无缺陷的越界阻塞和正常反例均有对应任务。用户已确认聊天设计并授权实施，计划只展开该范围，无新产品或架构决策。


## 执行结果（2026-09-07）

实现与行为验证完成时保留 `feature/pr-impact-review` 供后续集成；该阶段未推送、合并、发布或同步到用户工具目录。后续状态见收尾记录。

- 基线 `dad2e6b62ba0327778cb669c245e0d9cf396fc1b`，工作区初始干净。系统 Python 缺少项目既有 PyYAML；使用 `uv run --frozen` 按锁文件建立工作区环境后，基线 266/266 通过，无新增依赖。
- 先增加评测清单完整性检查，观察到预期失败 `24 != 36`。这只验证清单完整性，不冒充行为验证。
- 旧版核心范围扩张案例 5 次独立运行均阻止合并，但都缺少独立影响等级并将范围冲突归为 P1；首版增强 5 次独立运行均给出 High / Violates / C-01 / Not ready，未编造运行缺陷。
- 首轮扩展行为评测暴露：4 个普通正确性案例同时生成 C/P，可能误阻断局部 FIX；1 个缺少职责与消费者事实的写入案例过早定 High。已收紧 C/P 边界与未知影响规则，补充对应断言。
- 独立复核发现并修正 3 项评测问题：提前停止阶段描述矛盾、原始材料夹带结论提示、迁移数据性质不足。原始运行保留，清理后的输入重新执行，不以旧结果代替最终验证。
- 最终代码行为案例 24/24、逐项断言 100/100 通过；覆盖原有 12 个及新增 12 个。4 个既有缺陷案例仅追加防重复 C 断言，保留原缺陷路径、位置与严重性要求。
- 最终 PR 状态与评论案例 7/7、逐项断言 20/20 通过：越界、批准高影响、关键缺证、兼容字段提醒、重复复用、提前停止与评论失败、局部 P1 修复。
- 仓库回归 `uv run --frozen python -m unittest discover -s tests -q`：267/267；两个 skill 的系统 `quick_validate.py` 均通过；`git diff --check` 通过。项目未配置独立 lint/typecheck 命令。
- 修订后独立静态复核：原 3 个问题已解决，无遗留阻塞项；没有以静态复核替代上述行为运行。

原始报告、输入版本、逐断言核查和最终 skill 文件 SHA-256 保留在本机忽略目录：`/Users/zhaoguodong/Codes/ai-coding/lucas-skills/.worktrees/pr-impact-review-evidence-20260907`。`final-grades.json` 记录人工逐项核对依据，`tested-files.json` 记录最终被测文件身份与验证边界。

边界：最终 24 个不同代码案例分三个隔离 agent 批次执行，成对反例分在不同 agent，未把每个不同案例都分配到全新上下文；五次对照重复各用独立上下文。保留的 12 个触发案例做结构校验，未重跑实时自动路由。评论验证为离线模拟，未执行真实 PR 写入、发布、生产验证或技能激活。

## 收尾记录（2026-09-07）

用户明确要求自行复核，通过后合并、清理并让 skill 生效。主线程复核最终差异与评测证据：影响为 Medium，范围与架构 Conforms，Merge readiness 为 Ready；未发现有代码证据支持的缺陷。变化涉及审查报告、合并判断和评论流程，没有新增生产接口、数据库或依赖。

- 本轮重跑仓库测试 267/267（30.801 秒），两个 quick_validate 和范围 diff 检查通过；32 个 skill 文件与最终行为评测的 SHA-256 一致。未重复离线行为运行或真实 PR 写入。
- main 从 `dad2e6b` 快进到实现提交 `ca9ceedbc29b2c0aa517b927c601c3733878e0f1`；合并树 `dee77cba59ff8bae8867e6fbd0f97c63b11ff26b` 与本轮测试树相同。合并前远端 main 仍为 `dad2e6b`。两个任务提交顺序清楚，无需重写历史。
- 已安装目录直接链接到主仓库，合并即更新内容，无需重新安装。逐文件验证 code-change-review 的 Codex、Claude、Copilot 三个目标，以及 review-and-release-pr 的 Codex 目标均与被测版本一致；后者保持仅 Codex 启用。Agent Manager 状态为 0 冲突、0 问题。
- 删除本次 `feature/pr-impact-review` 分支及对应 worktree；清理前只存在本次生成的虚拟环境和 Python 缓存，没有未提交文件或私有配置。其他三个工作区与独立评测证据目录保留。
- 本地收尾时未推送、打 tag 或创建平台 Release。新版文件已生效；当时尚未验证实时自动路由、真实 PR 评论发布与回读。后续实测与发布授权见下节。

## 真实 PR 验证与版本发布（2026-09-07）

用户随后授权在两个真实 PR 上验证评论流程，并明确禁止合并。公开记录只保留匿名场景和验证结果；包含 PR 身份与评论回执的原始证据保留在上述本机忽略目录的 `live-pr-validation/` 下。

| 场景 | 审查结果 | 评论验证 | 操作边界 |
| --- | --- | --- | --- |
| A：交付范围需要决策 | 需求阶段 `STOP`，影响待确定；没有声称完成代码审查 | 发布成功；正文、作者、目标与链接回读一致；重复投递复用 1 条，新增 0 条 | 未合并、未修改代码 |
| B：范围符合、存在非阻塞缺陷 | `Medium / Conforms / PASS`，披露 2 个 P2；142 个既有聚焦测试通过，2 个新增复现检查失败并支持缺陷结论，本地回环冒烟通过 | 发布成功；正文、作者、目标与链接回读一致；重复投递复用 1 条，新增 0 条 | 未合并、未修复代码、未执行生产操作 |

两次实测补齐真实 `STOP / PASS` 评论发布、回读和重复复用证据。实时自动路由、真实 `FIX`、版本或结论变化后的重新发布、评论失败恢复仍未实测；这些路径的已有离线覆盖不等于线上验证。

用户据此同意结束功能迭代，并追加授权发布版本、打 tag。按仓库新增可见工作流行为递增 minor 的规则，版本为 `v0.7.0`；发布说明见 `CHANGELOG.md` 对应章节。本次发布准备只更新日志与本记录，不再修改 Skill 行为。
