# 版本发布运维部署材料整理能力实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (Native, user-selected) to implement this plan task-by-task, preserving fresh-context blind behavior evaluation and a final whole-branch independent review. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 `finishing-a-development-release`（配合 `references/deployment-package.md` 按需加载），在切版本发版时基于代码真实变更与零散 PR 过程产物产出入库随 tag 固化的运维部署文档、参数化脚本与数据库增量 SQL，同时最小化衔接 `review-and-release-pr` 并对齐 `ezone` 一次创建标签和版本说明的平台能力。

**Architecture:** 保留 `finishing-a-development-release/SKILL.md` 为薄编排入口，仅在命中部署材料条件时按需加载同目录 `references/deployment-package.md`，保持常规快速路径零回归；`review-and-release-pr/SKILL.md` 保持现有顶层目录结构与路由边界，仅扩展 Phase 0 授权区分与正式发版 handoff 透传；通过 `unittest` 验证目录、元数据、引用链接与核心合同，并按 `writing-skills` 的 RED/GREEN 隔离上下文流程完成行为验收。

**Tech Stack:** Markdown、JSON、YAML（现有 `PyYAML`）、Python 3.11+ `unittest`、`skills/skill-creator/scripts/quick_validate.py`、`uv`、独立子代理离线行为评测。

**Spec:** [docs/superpowers/specs/2026-11-24-release-deployment-package-design.md](../specs/2026-11-24-release-deployment-package-design.md)（已提交基线 `5c28286`）

## Global Constraints

- 特性开发禁止直接在 `main` 执行；先单独提交本计划文件到 `main`（记为 `<实施基线>`），再以该提交通过 `superpowers:using-git-worktrees` 创建隔离任务分支与 worktree（`feature/release-deployment-package`），确保任务工作树自带计划文件。
- 不新增独立全局 Skill、不新增项目依赖、不修改 `tools/agent_manager/`；初始实施阶段不推送、不打 tag、不向用户真实 HOME 执行 `agent-manager --apply`。
- `skills/finishing-a-development-release/` 不得新增 `scripts/` 或 `assets/`（首版不预写跨栈自动采集脚本）；`SKILL.md` 保持轻量薄入口，重规则下沉到 `references/deployment-package.md` 按条件加载。
- `skills/review-and-release-pr/` 顶层目录严格保持 `{"SKILL.md", "agents", "evals"}`（受 `tests/test_review_and_release_pr_skill.py` 约束，禁止新增 `references/`），frontmatter 保留全部既有正负向触发短语。
- 禁止向本公开仓库的测试或评测夹具写入任何私有业务仓库的真实内网地址、凭据、账号、对象标识或敏感数据；所有行为评测用例均使用脱敏合成夹具。
- 所有 Skill 修改遵循 `superpowers:writing-skills` 的 RED → GREEN → REFACTOR 验证原则，且必须通过 `quick_validate.py`、仓库全量 `unittest` 与 `git diff --check`。
- 不复制 `neat-freak`、`git-history-rewrite`、`finishing-a-development-branch`、`verification-before-completion` 或 `ezone` 的内部操作步骤，仅声明触发条件、消费输出与边界。

## Review Focus

以下五类最容易在真实发版中造成运维事故或状态损坏的边界输入，每一项均已在所属任务中绑定了对应测试与离线行为用例：

1. **受管迁移仓库同时出现空库初始化 `dbinit.sql` 与框架外存量升级 DDL**：已明确判定仅供空库初始化的脚本必须正常归入新装章节且不得误触第 4 条硬阻断，而已判定用于存量升级且疑似绕过受管迁移链的 DDL 必须准确命中第 4 条阻断（归属 Task 1、Task 4）。
2. **“每版必出”仓规仓库遇到同时含迁移与配置变更的版本**：仓规兜底只决定“必须产出记录”，绝不能跳过实际变更盘点而只给简报；有运维动作时必须交付完整部署文档与脚本，仅确认无运维动作时才出简短记录（归属 Task 1、Task 2、Task 4）。
3. **起点在本地 `main` 且主工作区已有用户无关未提交改动，随后在生成或脚本静态校验阶段触发阻断**：起点在 `main` 且需写入发布材料时一律使用独立准备 worktree/分支，阻断后禁止撤除准备区（沿用 Cleanup Gate 保留重试现场与准备分支提交），并保证本地 `main` 提交指针与主工作区原有改动完全未变（归属 Task 2、Task 4）。
4. **受保护分支发布 PR 等待审批期间 `main` 并发前移，或可执行部署脚本落在项目自定义路径（如 `ops/upgrade.sh`）**：必须锁定平台返回的该发布 PR 实际合并 SHA（而非“远端最新 `main`”），合并树发生实质变化时重核部署材料、重审并重验；且可执行内容独立审查门禁按文件用途判定，不局限于兜底 `scripts/`/`sql/` 目录（归属 Task 2、Task 3、Task 4）。
5. **Ezone 平台能力可用但用户仅授权打 Git tag 未授权平台 Release，以及 Ezone 历史 tag 补建说明**：前者退回纯 Git annotated tag 并报 `Portable Release`（`Platform release: skipped (not authorized)`，不误报 `unavailable`）；后者在 `ez release edit` 未实测确认不改写 tag 对象前必须报 `Blocked`（归属 Task 2、Task 4）。

---

## 文件结构与职责划分

- Create: `skills/finishing-a-development-release/references/deployment-package.md` — 按需加载的部署材料整理细则（基线/首次全量树盘点、代码 diff 反向核对、目录与幂等复用、`DEPLOY.md` 七章契约与标签前后制品边界、参数化脚本底线与本地校验、SQL 四类用途前置分类 + 受管迁移识别含自有迁移链 + 合法框架外手工 SQL + 五条硬阻断）。
- Create: `skills/finishing-a-development-release/evals/evals.json` — 离线行为与触发路由评估清单。
- Create: `skills/finishing-a-development-release/evals/fixtures/*.md` — 覆盖真实边界与 5 项 Review Focus 的脱敏自包含场景夹具。
- Modify: `skills/finishing-a-development-release/SKILL.md` — 薄编排入口更新（条件路由表、显式/仓规/双信号触发优先级、路径 A/B/C、Ezone 一次写入与双回读、统一 `Portable Release` 谓词、Cleanup Gate #3/#4/#5 适配、Final Report `Deployment package` 字段）。
- Modify: `skills/finishing-a-development-release/agents/openai.yaml` — 同步 `short_description`（保持 25–64 字符）与 `default_prompt`（保留 `$finishing-a-development-release`）。
- Create: `tests/test_finishing_development_release_skill.py` — 布局、元数据、渐进加载链接、关键契约及 eval 清单完整性单元测试。
- Modify: `skills/review-and-release-pr/SKILL.md` — Phase 0 独立授权补充与正式发版 handoff 最小透传（保护分支先合功能 PR 锁实际合并 SHA，不向已审功能 PR 追加跨版本产物）。
- Modify: `skills/review-and-release-pr/evals/evals.json` — 新增 3 个正式发版 vs 单 PR 合并及保护分支自定义路径脚本交接离线用例。
- Modify: `tests/test_review_and_release_pr_skill.py` — 补充对新增 handoff 用例与既有布局/路由不变量的回归校验。

---

### Task 1：编写部署材料整理规范（`references/deployment-package.md`）、脱敏场景夹具与首批契约测试

**Files:**
- Create: `skills/finishing-a-development-release/references/deployment-package.md`
- Create: `skills/finishing-a-development-release/evals/evals.json`
- Create: `skills/finishing-a-development-release/evals/fixtures/`（14 个自包含脱敏夹具，清单见 Step 1）
- Create: `tests/test_finishing_development_release_skill.py`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-11-24-release-deployment-package-design.md` §5.1、§5.3、§6.2。
- Produces:
  - 供 Task 2 `SKILL.md` 条件路由引用的相对路径 `references/deployment-package.md`（稳定章节锚点覆盖触发与基线、原料采集与反向核对、目录落地与幂等复用、`DEPLOY.md` 七章契约、脚本底线与本地校验、SQL 四类分类与五条阻断）；
  - 供 Task 2 与 Task 4 复用的 `skills/finishing-a-development-release/evals/evals.json` 清单格式（`skill_name`, `evals[]` 含 `id`, `kind`, `category`, `prompt`, `expected_output`, `files`, `assertions`）及 `tests/test_finishing_development_release_skill.py` 测试模块。

- [ ] **Step 1: 建立脱敏行为与触发评测清单及夹具**

创建 `skills/finishing-a-development-release/evals/evals.json` 与 `skills/finishing-a-development-release/evals/fixtures/`，每个夹具只包含该场景自身素材（不泄露预期答案、对照项或私有项目敏感标识），固定包含以下 14 个场景（ID 唯一）：

1. `bootstrap-and-incremental-sql`（首选验收案例，映射空库初始化 + 4 个独立增量 SQL + 已有归档规范目录；验证 `dbinit.sql` 仅归入空库新装、4 个增量按序引用原路径不重复拷贝）
2. `managed-bootstrap-ok`（成对对照 A：受管迁移仓库含已确认仅供空库初始化的 `dbinit.sql` → 正常分类，**不**误触第 4 条硬阻断）
3. `managed-bypass-ddl-blocked`（成对对照 B：同一受管迁移仓库含已判定用于存量升级的框架外裸 DDL → 准确命中第 4 条硬阻断）
4. `managed-custom-chain-and-skipped-prod`（项目自建 Python 顺序迁移链 + 历史连续发版但生产停在更早版本 → 不重写迁移文件，文档写清适用应用/DB 起始版本、现场核对命令与跨版补齐原则，支持显式指定起点）
5. `managed-legitimate-dba-sql-hybrid`（受管迁移仓库含框架无法承载的合法 DBA 前置建扩展/赋权 SQL → 保留原迁移不变，合法手工 SQL 共存并标注 `pre-migration` / `post-migration` 顺序）
6. `sql-unclassified-purpose-blocked`（区间内存在无法从入口或内容判定用途的 `.sql` → 命中第 5 条硬阻断）
7. `repo-rule-with-ops-changes`（成对对照 A：“每版必出”仓规仓库且本版含迁移与配置变更 → 交付完整部署文档与脚本，不得降级为简短记录）
8. `repo-rule-no-ops-changes`（成对对照 B：同一“每版必出”仓规仓库且确认无运维/迁移变更 → 触发并产出简短版本升级说明）
9. `initial-release-full-tree`（无历史 tag 的首次发版 → 盘点目标提交完整文件树而非 `initial_commit..HEAD` diff，产出首次全量部署文档）
10. `post-tag-immutable-digest-boundary`（打 tag 后由 CI 生成不可变容器镜像 `sha256` 摘要 → 标签内 `DEPLOY.md` 写明拉取核验方式与发布后最终摘要权威来源，不臆造摘要）
11. `same-version-dir-reuse-vs-conflict`（同版本部署目录续跑：内容一致直接 `reused` 复用；存在实质差异时暂停请求覆盖确认）
12. `local-main-blocked-preserves-workspace`（起点在本地 `main`、主工作区存在用户无关未提交改动、脚本静态校验或 SQL 阻断 → 使用独立准备 worktree，阻断时保留准备区不撤除，主工作区与本地 `main` 指针原样保留）
13. `protected-release-pr-merge-sha-and-custom-exec`（受保护分支独立发布 PR 含项目自定义路径 `ops/upgrade.sh` 且等待审批期间/合入后 `main` 并发前移 → 按用途触发独立审查门禁，合入后锁定平台返回的实际合并 SHA，合并树变化须重核重审重验）
14. `ezone-atomic-and-portable-auth-split`（包含三项子核验：Ezone 全量发版走 `ez release create --commit <sha> --no-notify` + 双回读不先 `git push tag`；平台有能力但用户仅授权 Git tag 时报 `Portable Release` + `skipped (not authorized)`；Ezone 历史 tag 补写说明报 `Blocked`）

另在 `evals.json` 中补 2 个轻量内联触发/覆盖用例（`files: []`，不建额外夹具文件）：`fast-path-tool-repo-skip`（纯工具/Skill 仓库无部署信号跳过部署材料且不读重参考）与 `explicit-skip-overrides-repo-rule`（用户明确要求跳过部署材料时按 `AGENTS.md` 直接放行并在 `Deployment package` 与 `Residual risk` 记录覆盖）。前 14 个行为用例各自对应 `evals/fixtures/<id>.md`，总计 16 个用例、14 个夹具文件。

- [ ] **Step 2: 编写 Task 1 对应的失败单元测试**

创建 `tests/test_finishing_development_release_skill.py`，编写先失败的测试方法：
- `test_layout_allows_only_expected_entries`：断言顶层仅含 `{"SKILL.md", "agents", "references", "evals"}`，禁止出现 `{"scripts", "assets", "README.md"}`；
- `test_deployment_package_reference_covers_core_contracts`：断言 `references/deployment-package.md` 存在且覆盖：首次发版完整文件树、四类 SQL 前置分类（空库初始化/存量升级/回滚/测试）、受管迁移含自有迁移链、五条 SQL 硬阻断（含第 4 条限定“已判定用于存量升级”与第 5 条用途不明）、`DEPLOY.md` 七大要点（含应用/DB 起始版本与现场核对、跨版原则、标签前后制品摘要边界）、同版本目录内容一致复用、单套参数化脚本与 `bash -n` 静态校验、不自动删除原 PR 过程产物、严禁明文密钥与远程执行；
- `test_eval_manifest_is_complete_and_fixtures_exist`：断言 `evals/evals.json` 含 16 个唯一 ID 用例、所有必填键齐全、全部 `files` 路径落在 `skills/finishing-a-development-release/` 内且真实存在，且成对对照用例（`managed-bootstrap-ok` / `managed-bypass-ddl-blocked`、`repo-rule-with-ops-changes` / `repo-rule-no-ops-changes`）完整存在。

- [ ] **Step 3: 运行单元测试与 RED 基线压力测试，确认预期失败**

1. 运行单元测试确认 RED：
   Run: `uv run --frozen python -m unittest tests/test_finishing_development_release_skill.py -v`
   Expected: FAIL（缺失 `references/deployment-package.md`）
2. 在尚未写入新规则前，做真正盲测的 RED 基线演练：旧版基线统一取设计提交 `5c28286` 中的 `skills/finishing-a-development-release/SKILL.md`，用独立只读子代理分别执行 3 个代表性用例（`bootstrap-and-incremental-sql`、`managed-custom-chain-and-skipped-prod`、`post-tag-immutable-digest-boundary`）；执行者只接收旧版 Skill、用户请求和**中性编号命名的原料**（不泄露 `evals.json`、`expected_output`、`assertions` 或含答案暗示的用例名），由评分侧另行对照断言记录旧版实际缺口，写入本计划末尾执行记录。

- [ ] **Step 4: 编写 `skills/finishing-a-development-release/references/deployment-package.md`**

严格按设计 §5.1.2 与 §5.3（5.3.1–5.3.5）编写，做到清晰、无歧义、面向跨项目通用运维交付，并注意：
- 明确写清“每版必出”仓规触发后仍须完整盘点实际变更（有运维动作交付完整文档与脚本，确认无运维动作才出简短记录）；
- 明确写清第 4 条 SQL 硬阻断严格限定为**已判定用于存量升级**、位于受管迁移链之外且疑似绕过该机制的 DDL，明确豁免已确认仅供空库初始化的脚本，用途不明走第 5 条；
- 要求对每条存量增量 SQL 标明适用执行前提与重复执行风险（例如仅在目标列缺失时执行、重复执行会报错时的前置核对方法），且允许彼此独立的 SQL 标明无先后耦合关系；
- 保持精炼可执行，不复制 `ezone`、`neat-freak` 等其他 Skill 的内部命令。

- [ ] **Step 5: 运行 Task 1 单元测试验证通过并提交**

Run: `uv run --frozen python -m unittest tests/test_finishing_development_release_skill.py -v && git diff --check`
Expected: `Ran 3 tests ... OK`，`git diff --check` 退出 0。

```bash
git add skills/finishing-a-development-release/references/deployment-package.md \
  skills/finishing-a-development-release/evals/ \
  tests/test_finishing_development_release_skill.py
git commit -F - <<'EOF'
feat(release): 新增版本部署材料整理参考规范与行为评测夹具

依据已定稿设计新增按需加载的 references/deployment-package.md，系统定义增量 diff 与首次全量树盘点、SQL 四类用途前置分类与自有迁移链识别、合法框架外 DBA 手工 SQL 混用、五条 SQL 硬阻断、DEPLOY.md 七章契约（含实际起点核对与标签前后制品边界）、同版本目录幂等复用及参数化脚本静态校验底线，并配套 16 个脱敏行为/触发评测场景与契约测试。

验证：
- 已先在旧版 SKILL.md 上完成 3 个核心场景 RED 基线演练并记录缺口。
- uv run --frozen python -m unittest tests/test_finishing_development_release_skill.py -v：3/3 通过。
- git diff --check 通过。
EOF
```
（提交时按 `AGENTS.md` 追加实际执行模型的 `Co-authored-by` trailer。）

---

### Task 2：升级 `finishing-a-development-release/SKILL.md` 编排合同、`openai.yaml` 与完整结构校验测试

**Files:**
- Modify: `skills/finishing-a-development-release/SKILL.md:1-73`
- Modify: `skills/finishing-a-development-release/agents/openai.yaml:1-4`
- Modify: `tests/test_finishing_development_release_skill.py`

**Interfaces:**
- Consumes: Task 1 产出的 `references/deployment-package.md` 相对路径与触发语义。
- Produces:
  - 升级后的 `skills/finishing-a-development-release/SKILL.md`（供 Task 3 `review-and-release-pr` 在 release handoff 对接：接收合并后实际 `main` SHA、版本/显式起点基线线索、PR 过程产物线索、显式部署材料开关及独立发布 PR 授权）；
  - 统一后的四级 `Provider Result`（`Full Release`、`Portable Release` 含 `unavailable` / `skipped (not authorized)`、`Partial Release`、`Blocked`）、更新后的六项 `Cleanup Gate` 与含 `Deployment package` 字段的 `Final Report`。

- [ ] **Step 1: 在 `tests/test_finishing_development_release_skill.py` 补充失败的入口编排与元数据测试**

新增以下测试方法：
- `test_metadata_and_openai_yaml_are_valid`：断言 `SKILL.md` frontmatter 仅含 `name`、`description`，`name == "finishing-a-development-release"`，`description` 覆盖发布收尾与版本部署材料触发词且不含流程摘要；`agents/openai.yaml` 仅含 `interface` 三字段、`short_description` 长度在 25–64 之间、`default_prompt` 含 `$finishing-a-development-release`；
- `test_entry_routes_deployment_reference_conditionally`：断言 `SKILL.md` 含条件路由表链接 `references/deployment-package.md`，全部相对引用路径真实存在且不越出 Skill 目录，并声明未命中条件时仅用入口完成快速路径；
- `test_entry_encodes_orchestration_paths_ezone_and_gates`：断言 `SKILL.md` 保留 `REQUIRED SUB-SKILL`（`neat-freak`、`git-history-rewrite`、`verification-before-completion`，新增条件式 `ezone`）与 `REUSED CONTRACT`（`finishing-a-development-branch`），并显式覆盖：
  - 显式开关优先级（含显式跳过覆盖仓规记录）与“每版必出”仓规触发；
  - 路径 A 常规快速路径顺序不变；
  - 路径 B 起点在本地 `main` 且需写材料时一律使用独立准备 worktree/分支、阻断时保留准备区沿用 Cleanup Gate；
  - 路径 C 保护分支独立发布 PR、锁定平台返回的实际合并 SHA、按文件用途判定可执行内容独立审查门禁与 `release PR awaiting review/merge` 等待态；
  - Ezone 一次创建 tag+Release 双回读、`--no-notify` 默认及历史 tag 补写阻断；
  - `Portable Release` 明确覆盖“平台无可用 Release 能力”与“未授权平台 Release”两种合法原因；
  - `Final Report` 包含 `Deployment package` 字段（`skipped` / `reused` / `generated` / `blocked`）。

- [ ] **Step 2: 运行测试与 RED 基线演练确认预期失败**

1. 运行单元测试确认 RED：
   Run: `uv run --frozen python -m unittest tests/test_finishing_development_release_skill.py -v`
   Expected: FAIL（新增 3 个测试方法失败）
2. 在修改 `SKILL.md` 前，按统一盲测口径（旧版基线取 `5c28286`，执行者只拿旧版 Skill、用户请求与中性编号原料，评分侧另看断言），用独立只读子代理跑 3 个编排级核心用例（`local-main-blocked-preserves-workspace`、`protected-release-pr-merge-sha-and-custom-exec`、`ezone-atomic-and-portable-auth-split`）的 RED 基线，记录旧版缺失行为。

- [ ] **Step 3: 更新 `skills/finishing-a-development-release/SKILL.md` 与 `agents/openai.yaml`**

按设计 §5.1.1、§5.2、§5.4、§5.6 精炼改写 `SKILL.md`，保持薄入口风格（控制在 ~110–145 行，不把 `references/deployment-package.md` 细则复制到主正文，不复制 `ezone` CLI 细节）：
- Frontmatter `description` 简洁补充版本部署文档/脚本整理触发语（保持英文/中文混合触发风格，不摘要流程）；
- `Core Contract` 增补独立发布 PR 创建/合并、部署材料提交及高风险覆盖/删旧产物/远程部署禁令的授权边界；
- 新增紧凑的 `Load reference on condition` 路由表指向 `[Deployment package](references/deployment-package.md)`；
- `Skill Composition` 增加条件式 `ezone`（仅当目标 remote 为 Ezone 且运行期预检可用）；
- `Fast Path` 明确区分路径 A（常规快速路径原顺序不变）、路径 B（本地合入 + 部署材料：一律先只读预检并在独立准备分支/worktree 生成与校验后再集成 `main`）、路径 C（保护分支：独立发布 PR、按文件用途判定可执行内容独立审查、锁定平台返回实际合并 SHA）；
- `Provider Result` 统一四级状态定义（含 `Portable Release` 两种原因及 Ezone 写入/双回读/历史 tag 补写阻断规则）；
- `Cleanup Gate` 适配第 3、4、5 条并明确阻断/待审时保留准备区；
- `Final Report` 增加 `Deployment package`。
- 同步微调 `agents/openai.yaml` 的 `short_description`（控制在 25–64 字符内，如确认原 27 字符或更新后满足范围）。

- [ ] **Step 4: 验证 Task 2 测试与 `quick_validate.py` 通过并提交**

Run:
```bash
uv run --frozen python -m unittest tests/test_finishing_development_release_skill.py -v
uv run --frozen python skills/skill-creator/scripts/quick_validate.py skills/finishing-a-development-release
git diff --check
```
Expected: `tests/test_finishing_development_release_skill.py` 全部通过（6/6），`quick_validate.py` 输出 `Skill is valid!`，`git diff --check` 退出 0。

```bash
git add skills/finishing-a-development-release/SKILL.md \
  skills/finishing-a-development-release/agents/openai.yaml \
  tests/test_finishing_development_release_skill.py
git commit -F - <<'EOF'
feat(release): 扩展发布编排支持按需部署材料、保护分支发布 PR 与 Ezone 对齐

在 finishing-a-development-release/SKILL.md 中引入按条件加载 references/deployment-package.md 的渐进路由，保持无部署信号时的常规快速路径不变；补齐本地 main 独立工作树准备、受保护分支独立发布 PR 锁定实际合并 SHA 与按文件用途判定可执行内容独立审查门禁、Ezone 一次创建标签与版本说明双回读规则，并统一 Portable Release 对“平台不可用”与“未授权平台 Release”的状态界定。

验证：
- 已先在旧版 SKILL.md 上完成本地防脏、保护分支发布 PR 与 Ezone 场景 RED 基线演练。
- uv run --frozen python -m unittest tests/test_finishing_development_release_skill.py -v：6/6 通过。
- uv run --frozen python skills/skill-creator/scripts/quick_validate.py skills/finishing-a-development-release：通过。
- git diff --check 通过。
EOF
```
（提交时追加实际执行模型的 `Co-authored-by` trailer。）

---

### Task 3：对齐 `review-and-release-pr` 正式发版交接与回归测试

**Files:**
- Modify: `skills/review-and-release-pr/SKILL.md:40-46,96-107`
- Modify: `skills/review-and-release-pr/evals/evals.json`
- Modify: `tests/test_review_and_release_pr_skill.py`

**Interfaces:**
- Consumes: Task 2 `finishing-a-development-release/SKILL.md` 的保护分支发布 handoff 入口契约（接收实际合并 SHA、版本/显式起点基线、PR 过程产物线索、显式部署材料开关与独立发布 PR 授权）。
- Produces: 更新后的 `skills/review-and-release-pr/SKILL.md` 及 3 个新增离线 handoff 评测用例（总计 13 个用例）。

- [ ] **Step 1: 补充 `review-and-release-pr` 的失败单元测试并跑 RED 基线**

1. 在 `tests/test_review_and_release_pr_skill.py` 新增测试方法 `test_release_handoff_preserves_single_pr_vs_version_release_boundary`：
   - 断言 `SKILL.md` Phase 0 独立记录 `merge`、`tag/Release`、`deployment package`、`release-prep PR` 授权；
   - 断言 `Final verification and release handoff` 明确单 PR 合并与正式切版本发版的区分、保护分支先合功能 PR 并传递平台返回的实际合并 SHA、不向已审功能 PR 追加跨版本部署材料，以及透传版本/基线/过程产物线索与显式部署材料开关给 `finishing-a-development-release`；
   - 断言 `evals/evals.json` 包含 3 个新 ID：`single-pr-merge-no-deploy-package`、`version-release-handoff-separate-pr`、`release-pr-custom-exec-requires-independent-review`；
   - 确认既有 `test_minimal_layout` 与 `test_metadata_routes_only_end_to_end_pr_requests` 未放宽。
2. 运行单元测试确认 RED：
   Run: `uv run --frozen python -m unittest tests/test_review_and_release_pr_skill.py -v`
   Expected: FAIL（新增断言与 3 个用例尚未落地）
3. 按统一盲测口径（旧版基线取 `5c28286`，执行者只拿旧版 `review-and-release-pr/SKILL.md`、用户请求与中性编号原料，评分侧另看断言），用独立只读子代理跑 `version-release-handoff-separate-pr` 与 `release-pr-custom-exec-requires-independent-review` 的 RED 基线并记录缺口。

- [ ] **Step 2: 实施 `review-and-release-pr/SKILL.md` 最小修改与 3 个新评测用例**

按设计 §5.5 精准更新 `skills/review-and-release-pr/SKILL.md`（不修改 frontmatter，不新增 `references/` 目录，不复制部署或 SQL 整理规则）：
- `Phase 0`（第 44 行附近）：扩展独立记录的授权动作，区分单 PR 合并、正式切版本发版（tag/Release）、部署材料准备及创建/合入独立发布准备 PR；
- `Final verification and release handoff`（第 102 行附近）：明确单 PR 合入不触发跨版本部署材料；进入正式切版本发版 handoff 给 `finishing-a-development-release` 时，受保护分支先按授权合入已 `PASS` 功能 PR 并传递平台返回的实际合并 SHA，不把跨版本 `CHANGELOG` 或部署材料塞回原功能 PR，同时透传已知版本/显式起点基线、PR 过程产物线索及显式部署材料开关；若独立发布 PR 含任意路径新增/修改的可执行部署内容，仍遵守本 Skill 的独立审查门禁。
- 在 `skills/review-and-release-pr/evals/evals.json` 追加上述 3 个离线状态交接用例（遵循原有离线评估风格，无真实远端写入）。

- [ ] **Step 3: 验证 Task 3 测试与 `quick_validate.py` 通过并提交**

Run:
```bash
uv run --frozen python -m unittest tests/test_review_and_release_pr_skill.py -v
uv run --frozen python skills/skill-creator/scripts/quick_validate.py skills/review-and-release-pr
git diff --check
```
Expected: `tests/test_review_and_release_pr_skill.py` 全部通过（5/5），`quick_validate.py` 输出 `Skill is valid!`，`git diff --check` 退出 0。

```bash
git add skills/review-and-release-pr/SKILL.md \
  skills/review-and-release-pr/evals/evals.json \
  tests/test_review_and_release_pr_skill.py
git commit -F - <<'EOF'
feat(review-and-release-pr): 衔接正式发版部署材料透传与独立发布 PR 边界

在 Phase 0 独立区分单 PR 合并、正式发版、部署材料及独立发布 PR 授权，并在 release handoff 中明确受保护分支先合入已通过审查的功能 PR 并锁定实际合并 SHA 交由 finishing-a-development-release 处理，避免篡改已通过审查的功能 PR head 或在 PR 编排器中复制部署规则。

验证：
- 已先在旧版 review-and-release-pr/SKILL.md 上完成新增交接场景 RED 基线演练。
- uv run --frozen python -m unittest tests/test_review_and_release_pr_skill.py -v：5/5 通过。
- uv run --frozen python skills/skill-creator/scripts/quick_validate.py skills/review-and-release-pr：通过。
- git diff --check 通过。
EOF
```
（提交时追加实际执行模型的 `Co-authored-by` trailer。）

---

### Task 4：新鲜上下文 GREEN 行为验收、实仓边界只读回放与全量回归收口

**Files:**
- Modify（仅当 GREEN/REFACTOR 暴露措辞漏洞时）: `skills/finishing-a-development-release/SKILL.md`、`skills/finishing-a-development-release/references/deployment-package.md`、`skills/review-and-release-pr/SKILL.md`
- Modify: `docs/superpowers/plans/2026-11-24-release-deployment-package.md`（追加实际执行与验证记录）

**Interfaces:**
- Consumes: Task 1–3 产出的两个 Skill、参考规范、16 + 3 个新增离线评测用例与自动化测试。
- Produces: 完整的 RED/GREEN 逐条断言核验结果、脱敏/只读回放检验记录与全量回归证据。

- [ ] **Step 1: 新鲜上下文真正盲测全部 19 个新增用例 + 一次性 Git 仓库实操演练（GREEN 验证）**

1. **真正盲测 19 个用例**：新版统一取当前任务工作树中的 Skill 内容；盲测执行子代理**仅接收**对应新版 Skill、用户请求和**中性编号命名的原料**（不提供 `evals.json`、`expected_output`、`assertions` 或含 `blocked`/`ok` 等答案暗示的用例名/文件名），成对对照用例拆分在不同独立上下文中执行；评分侧另行对照 `evals.json` 全部 `assertions` 逐条判分：
   - `skills/finishing-a-development-release/evals/evals.json` 全部 16 个用例（特别逐条核验 5 项 Review Focus）；
   - `skills/review-and-release-pr/evals/evals.json` 新增的 3 个交接用例。
2. **一次性临时 Git 仓库实操演练（验证本地 `main` 防脏承诺）**：在临时目录新建一次性 Git 仓库（含基线版本 tag、主工作区用户原有未提交文件改动），按新版 `finishing-a-development-release` 路径 B 在独立准备 worktree 生成部署材料并故意制造配套脚本静态校验失败（`bash -n` 失败），实测对比演练前后：
   - 本地 `main` HEAD SHA 完全不变；
   - 主工作区用户原有未提交文件内容逐字节不变，无新增/残留半成品文件；
   - 独立准备 worktree 及其分支上的本地准备现场与提交原样保留（未被阻断流程擅自撤除）。

- [ ] **Step 2: 实仓边界只读回放验证（1 个空库初始化 + 4 个存量增量 SQL 共存场景）**

在不向任何目标业务仓库写入文件或远端的前提下，由独立盲测上下文加载新版 `finishing-a-development-release` + `references/deployment-package.md`，对本地只读可访问的“1 个空库初始化文件 + 4 个新增独立 SQL”真实多文件版本差异（或当本地无目标仓库时使用等价多文件仿真 git 仓库；具体回放对象留在本地，不写入公开仓库文档）做一次只读部署材料草稿回放，按**执行条件与依赖关系**逐项评分：
- 列全全部 4 个存量增量 SQL 的准确原路径（沿用项目归档规范，不重复拷贝）；
- 标明各自适用执行条件与重复执行风险（例如某条 `ALTER` 仅在目标列缺失时执行、重复执行会报错，并给出前置检查方法）；
- 给出有依据的先后依赖关系，同时允许彼此独立的步骤采用不同合法顺序；
- 将空库初始化脚本明确排除出存量升级清单，仅列于空库新装说明；
- 输出无任何真实密钥值；公开仓库的执行记录只保留脱敏结论，不写入私有仓库名称、版本号组合、凭据、内网地址或内部对象标识。

- [ ] **Step 3: REFACTOR 收敛漏洞（若 Step 1 或 Step 2 暴露任何规则歧义）**

如发现任一断言未通过或合理化绕过，先定位对应规则缺口，做最小精准修正，再由新鲜盲测上下文重跑受影响用例直到全部断言通过，并单独提交修正 commit。

- [ ] **Step 4: 执行最终全量验证、隔离 HOME 预览与整分支独立复核**

1. 在最终待交付树上运行完整验证命令（`verification-before-completion`）：
```bash
uv run --frozen python -m unittest discover -s tests -p 'test_*.py' -q
uv run --frozen python skills/skill-creator/scripts/quick_validate.py skills/finishing-a-development-release
uv run --frozen python skills/skill-creator/scripts/quick_validate.py skills/review-and-release-pr
tmp_home=$(mktemp -d)
HOME="$tmp_home" uv run --frozen agent-manager skills set finishing-a-development-release --tool codex --on --json
rm -rf "$tmp_home"
git diff --check <实施基线>...HEAD
```
Expected:
- 全量 `unittest` 全部通过（无跳过/失败，在原 370 项基础上包含本轮新增测试）；
- 两个 Skill 均通过 `quick_validate.py`；
- 临时 HOME 隔离预览退出码 0，核对输出中 `source` 指向当前任务工作树且预期启用动作正确（不带 `--apply`，不触碰真实 HOME）；
- `git diff --check <实施基线>...HEAD` 覆盖整条分支全部提交且退出 0。
2. **最终整分支独立复核**：由新鲜只读独立复审子代理审阅从 `<实施基线>` 到最终 `HEAD` 的完整差异、本计划 `Review Focus` 及执行记录，明确检验两个 Skill 的端到端配合，并在交付结论中单列 Ezone 的离线验证边界（尚未执行真实平台写入与 `ez release edit` 实测）。如有 Critical/Important 发现，按 `executing-plans` 执行唯一一轮 TDD 修复并重跑全量验证。

- [ ] **Step 5: 记录执行结果并提交收口文档**

将实测盲测 RED/GREEN 逐轮结果、一次性 Git 仓库防脏演练证据、脱敏只读回放评分、最终全量验证数字、整分支独立复核结论及剩余限制（单列 Ezone 离线验证边界）追加到本计划文末并提交；保留 `feature/release-deployment-package` 分支等待用户决定后续合并与生效方式。
