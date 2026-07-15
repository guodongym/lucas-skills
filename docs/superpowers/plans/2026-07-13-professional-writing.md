# professional-writing skill 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 `professional-writing` 的 human-review-first beta 验收与部署交接：保留 7 份 current-skill 文档的原始评测证据，记录人工可用性结论，停止合成迭代并转入真实任务验证。

**Architecture:** 继续使用已提交的单一薄入口 SKILL.md 与既有三个 references，不再修改 runtime、self-review、description、evals.json 或 fixtures。Batch 6 至 Batch 11 与 iteration-6 至 iteration-9 保留为历史证据；最终 viewer 复用 Batch 11 两份 eval-6 和 iteration-9 五份 smoke 文档。人工审阅结果为 4 份可直接使用、3 份小改可用、0 份不可用，用户已接受当前 beta。后续只在同类用户可见问题于至少 2 份真实文档中重复时重启小规模迭代。

**Tech Stack:** Markdown skill 文件、skill-creator evals/viewer、fresh subagents、Python 派生校验。

**Spec:** `docs/superpowers/specs/2026-07-13-professional-writing-skill-design.md`。最终 human-review-first 合同、用户接受与部署路径记录在 approved spec commit `a03bc9d7e9f775e02346cf5862d61dd343c72f01`。发现冲突时以该提交为准并停下来报告。

## Global Constraints

- 交付语言：skill 全文中文（description 触发词含英文短语）。
- SKILL.md 总行数 ≤ 150（含 frontmatter）；模板、骨架细节一律下沉 references/。
- Avoid 判词表 7 条、三道确认门、快速通道、教程例外（判词 1/2/5 与流程步骤 2/4/5）必须与 spec 5.0-5.3 一致，不得增删改义。
- evals 全程遵循 `skills/skill-creator/SKILL.md` 的评测链路与 `skills/skill-creator/references/schemas.md` 的字段定义；不使用 /skill-test。**字段名约定（三个文件各不相同，以 schemas.md 为准源）**：`evals/evals.json` 用 `expectations`；每个 eval 目录的 `eval_metadata.json` 用 `assertions`（内容复制自对应 expectations）；每个运行的 `grading.json` 的 expectations[] 严格使用 `text` / `passed` / `evidence` 三字段（viewer 依赖精确字段名）。
- **workspace 目录契约**：`iteration-N/eval-<id>-<name>/eval_metadata.json` 是 canonical metadata（eval 级，含 eval_id/name/prompt/assertions）；配置目录保留相同 metadata，运行产物位于 `eval-<id>-<name>/<configuration>/run-<N>/`。历史 iteration 的 with/without 双配置保持不变；Task 6C 的 iteration-7 只创建 `with_skill/run-1`，eval-6 两份输出从 Batch 9 以 source path + SHA-256 绑定给 viewer。
- workspace 位于 `skills/professional-writing-workspace/`（与 skill 目录同级），通过 .gitignore 排除，不入 git。
- Commit 粒度：Task 1-5 与 runtime 加固均已提交；本轮先单独提交 approved spec，再单独提交本 plan。Task 6C 只写 ignored workspace，不产生 tracked runtime/eval diff；viewer 审阅前不提交 description 或部署变更。
- Commit 规范：`<type>(professional-writing): 中文描述` + body 说明为什么与验证结果 + trailer `<AI-TRAILER>`。**`<AI-TRAILER>` 按实际执行 agent 填写**：Claude 执行 → `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`；Codex 执行 → `Co-authored-by: OpenAI Codex <noreply@openai.com>`；其他 agent 按仓库规范用可辨认的自身身份。
- 交付契约完整覆盖 spec 第 9 节语义（成稿干净无流程痕迹 + 质检摘要放对话内 + 中间产物不落盘 + 明确要求才另存），不绑定条数。
- 教训（spec 第 10 节）：任何 SKILL.md 后续改动必须同步检查 references/evals 旁支。
- 默认文风是基础可读性契约，不是个人文风模仿：无内部黑话和空泛套话，简洁但不机械缩短，准确、专业、清晰、易懂；专业不等于复杂，简洁不等于删除事实、条件或边界。
- 黑话按目标读者能否解释“谁、做什么、产生什么结果”判断，不维护死词表；有精确含义的标准技术术语保留，非通用缩写和内部术语按读者需要首次解释。
- 黑话只有在冻结的 `source bound` 明确支持时才能改成具体主体、动作与结果；否则保留带引号的源词并增加“未知”项，按主体、动作、对象、责任范围和强度逐项说明未定义内容；不损失决策语义时可删除纯空话，但不得按行业惯例增强主体职责、动作、对象、范围或强度。
- 阶段 B 必须保持证据关系、认识状态、判断极性与强度：缺证不等于反证，未知或待决不得写成冲突或证伪，已确认冲突不得弱化为待确认；语义去重按“主体 + 判断/动作 + 关键条件/范围边界”判断，不按字面匹配。
- 阶段 C 中，黑话动词变得更具体或更强，主体、对象、责任范围或强度变化，以及证据关系、认识状态、极性或强度变化，均为 mismatch。
- 流程升级只修改正式 `skills/professional-writing/SKILL.md` 与 `skills/professional-writing/references/self-review.md`；不新增 runtime 文件或 reference，不修改 `evidence-map.md`，不新增 Avoid 判词第 8 条，不用固定句长、字数或禁词表替代语义判断。
- runtime 交付保持“干净成稿 + 对话内质检摘要”；事实锁、style review 和 gate 记录只存在当前上下文或被忽略评测 workspace，不进入成稿，也不默认作为附件落盘。
- 活动计数固定为 `SMOKE_COUNTS = {1: 4, 2: 6, 3: 3, 4: 3, 5: 6}`：eval-1..5 current-skill smoke 共 `22/22`；Batch 9 eval-6 两个 fresh run 共 `14/14`；总计 7 份文档、`36/36`。
- `Task 6F` 的 viewer 与人工审阅已经完成：保留原始 `36/36`、smoke `0 mismatch`、eval-6 `6 mismatch` 和 raw style findings `0/2`，不生成 passed full status。用户已接受 beta；Task 7 继续后置，Task 8 仅在分支整合后执行安装与真实首战交接。

---

### Task 1: SKILL.md（薄入口本体）

**Files:**
- Create: `skills/professional-writing/SKILL.md`

**Interfaces:**
- Produces: 目录 `skills/professional-writing/`；SKILL.md 中引用的三个文件名 `references/narrative-patterns.md`、`references/evidence-map.md`、`references/self-review.md`（Task 2-4 必须使用这三个精确文件名）。

- [ ] **Step 1: 创建目录并写入 SKILL.md 全文**

以下为完整内容（可在措辞上润色，但结构、判词表、门与例外不得改义）：

````markdown
---
name: professional-writing
description: |
  专业文档写作与重写 skill，覆盖四类：总结与汇报（调研总结、复盘、进展汇报、变更总结）、技术解释与专业文章、方案与决策文档、教程与操作指南。当用户要求写总结、调研总结、写报告、复盘、方案说明、决策材料、汇报材料、技术文章、专业文章、教程、操作指南、"整理成文档"、"写成文档给人看"（write a summary/report/postmortem/design doc/tutorial/article），或 agent 完成一段工作后需要产出给人阅读的文档文件时使用；也用于诊断和重写已有的结构差的文档（"帮我改一下这份文档/报告"）。仅当产出物是给人阅读的正式文档时触发，聊天内三五句口头总结不触发。SKIP：公众号文章 → khazix-writer；评审已有技术方案 → technical-proposal-review；交接包 → handoff；深度研究报告 → hv-analysis；API 参考、代码注释、DOCX/PDF 排版（docx/pdf skill）。
---

# 专业文档写作

产出中心意图先行、按读者认知路径组织、有取舍、依据可靠的专业文档；或诊断并重写已有的结构差文档。

## 第一步：路由

| 情形 | 走法 |
| --- | --- |
| "直接出稿" / 给全素材要结果 / 你在自主完成任务后写文档 | 快速通道：不打断用户，三道门全部自检替代，一次成稿 + 质检摘要 |
| "先跟我讨论" / 素材或意图不明确 | 完整通道：走三道确认门 |
| "帮我改一下" / 给了已有文档 | 重写模式（见下） |

确认门不是盘问：先根据材料完成判断，把假设和建议摆出来让用户确认或纠偏；只有无法可靠推断的关键问题，才一次问一个。用户可随时要求跳过或加密度。

## 从零写（思考顺序 1→7；落笔顺序不同：先写最核心章节，标题、开头、摘要最后写）

### 1 想读者

读者是谁？最关心什么？可能质疑什么？答不出就问用户。自主场景优先从任务上下文推断；推断不出时默认读者 = 不在场、具备领域通识但不了解本次上下文的同岗位专业读者。长文、对外文章可启用六项读者卡（见 references/narrative-patterns.md）。

### 2 定目标与中心意图

- 目标：读者读完要能做什么决定或行动。
- 中心意图，按文档类型二分：
  - 论证型（总结/汇报、方案/决策、技术解释/文章）→ 核心命题：一句可被反驳的断言。"本文介绍 X 的调研结果"是主题不是命题；"X 方案可行，建议走 B 路线"才是命题。支撑结构一并写出："主张 X，依据 A、B、C。"
  - 任务型（教程/操作指南）→ 任务承诺：读完能完成什么、前提是什么，完成标志可验证，不硬造观点命题。

这句话写不清楚，就不要列大纲。

### 3 盘证据（条件式）

素材含外部信息、时效信息或跨来源判断时，按四格盘点：事实（有出处）/ 判断（标注依据）/ 推测（显式标注）/ 未知（缺口）；细则见 references/evidence-map.md。总结自己刚完成的工作可跳过盘点仪式，但不豁免底线：验证过的才写"已验证"，跑了一半的测试不能写成全过。

缺口会改变中心意图时：用户在场 → 列出缺口征求同意后再研究；自主场景 → 不得按原意图硬写，把命题/承诺收窄到已确认事实能支撑的范围，收窄理由写进质检摘要。

→ **门 1（写作契约）**：复述"读者 + 目标 + 中心意图 + 文档类型 + 篇幅"给用户确认。快速通道自检替代。

### 4 画叙事地图

列出读者接受中心意图前会依次追问的问题，章节按序回答（教程按任务路径："操作目标 → 完成标志"）；每章一行"读者的问题 → 本节结论"。取舍在这一步做：不服务中心意图的材料砍掉或移附录。骨架起点按文档类型选（references/narrative-patterns.md）；标题风格：决策材料偏断言式，教程偏任务式，解释文章偏读者问题式。

→ **门 2（叙事地图）**：完整通道给用户确认再动笔；快速通道自检替代。

### 5 写章节

先写最核心、最不确定的章节。每节首句即该节结论，节间过渡承接读者的下一个追问（教程步骤章节例外：首句是操作目标，正文是步骤 + 验证，不强制结论句）。细节只为论点服务。正文完成后，最后写标题、开头和摘要。

→ **门 3（代表章节，条件式）**：长文、对外文章、新文风且用户在场时，先写最关键一章确认风格与密度；短总结、常规汇报、快速通道跳过。

### 6 自检

过一遍 references/self-review.md 的合并清单（含下方判词表 + 四个测试）。

### 7 新读者测试（条件式）

重要交付（用户要求高质量、对外/对上材料）：预测 5-10 个读者问题 → 派一个只拿到成稿的新 subagent 作答并指出歧义、隐含前提、内部矛盾 → 按结果回第 5 步修订。无 subagent 环境：问题清单交用户在新会话手测。日常自主场景轻量版：以"读者只看得到成稿"的假设自过一遍读者问题。

## 重写模式

1. 诊断：对照判词表列出命中项 + 具体位置。
2. 分级处置：局部问题（个别章节顺序、空标题、结论后置）在原文上外科式修改，不另起重复内容；结构性问题（无中心意图、整体流水账）才按读者 + 中心意图重构叙事地图后重写。
3. 收尾：走从零写第 6-7 步。

## Avoid 判词表

| # | 判词 | 判定方法 |
| --- | --- | --- |
| 1 | 结论埋深或无中心意图 | 读完第一屏（前 ~10 行）仍不知道"所以呢"；论证型提炼不出一句可被反驳的断言；教程提炼不出可验证的任务承诺 |
| 2 | 执行时间线叙事 | 组织顺序是"我先做了 A 再做了 B"，而非读者关心度（教程例外：操作步骤本身就是读者要的顺序） |
| 3 | 罗列无取舍 | N 个发现/要点平铺，无主次、无权重、无"最重要的是" |
| 4 | 缺"为什么"层 | 只说做了什么，不说为何这么选、排除了什么备选 |
| 5 | 空标题 | 标题是"背景/分析/总结"式栏目名而非信息载体；检验：全部标题连读应构成完整故事线（决策/汇报类）或完整任务路径（教程类） |
| 6 | 读者错位 | 给决策者的文档塞实现细节，或给执行者的文档只有愿景 |
| 7 | 断言无依据 | 关键断言既无出处也无标注的推断依据，或把推测写成事实 |

## 交付

- 成稿只含给读者看的正文，不混入流程痕迹、自检记录、判词引用；写作契约、证据盘点、叙事地图留在对话中，不制造中间文件。
- 短内容直接对话内交付；较长或需持续维护的文档写入 Markdown 文件；改稿在原文上修改。
- 交稿时在对话中附质检摘要：中心意图一句话、判词自检结果、遗留的推测/未知项、是否做了新读者测试。
- 只有用户明确要求，才另外保存大纲、研究材料或审校报告。
````

- [ ] **Step 2: 结构断言**

Run（分步执行）：

```bash
wc -l skills/professional-writing/SKILL.md
```

```bash
grep -c '^| [1-7] |' skills/professional-writing/SKILL.md
```

```bash
grep -c '门 [123]（' skills/professional-writing/SKILL.md
```

```bash
grep -o 'references/[a-z-]*\.md' skills/professional-writing/SKILL.md | sort -u
```

Expected: 行数 ≤150；判词行数 `7`；门出现 `3` 次；引用文件名恰为 narrative-patterns.md / evidence-map.md / self-review.md 三个。

- [ ] **Step 3: 不单独 commit**

此时 SKILL.md 引用的三个 references 文件尚不存在，skill 不完整；统一在 Task 4 末尾提交。

---

### Task 2: references/narrative-patterns.md

**Files:**
- Create: `skills/professional-writing/references/narrative-patterns.md`

**Interfaces:**
- Consumes: Task 1 的文件名约定。
- Produces: 四类骨架的节名（Task 5 的 eval 断言引用"前置条件""验证"等节点概念）。

- [ ] **Step 1: 写入文件**

必须包含以下五部分，每部分成文（禁止只写标题）：

1. **金字塔原理操作化**（结论 → 论据 → 细节；每层回答上层引出的问题；先总后分）与 **SCQA 开头**（情境 Situation → 冲突 Complication → 问题 Question → 答案 Answer，用于建立上下文后立刻给出中心意图），各配一个 3-5 行的工程文档示例。
2. **六项读者卡选用模板**（仅长文/对外文章启用）：`目标读者 / 阅读场景 / 已有认知 / 核心关切 / 可能质疑 / 阅读时间`，附一个填写示例。
3. **五列叙事地图选用模板**（仅长文/对外文章启用）：`章节 | 读者的问题 | 本节结论 | 使用的证据 | 读完后的认知变化`，附一个 3 行示例。
4. **四类文档骨架**，每类给"读者默认问题清单（3-4 问）+ 推荐骨架 + 标题风格"：
   - 总结/汇报：结论 → 证据 → 影响 → 风险 → 下一步；读者默认问题：结果如何/凭什么/对我意味着什么/接下来做什么；标题断言式。复盘变体的读者默认问题：发生了什么影响多大 → 根因是什么 → 怎么防止再发生。
   - 方案/决策：问题 → 约束 → 选项 → 推荐 → 权衡 → 决策事项；读者默认问题：要解决什么/有哪些选择/推荐哪个为什么/要我拍板什么；标题断言式。
   - 技术解释/专业文章：问题 → 核心判断 → 推理与证据 → 反例/边界 → 启示；读者默认问题：这是什么问题/你的判断是什么/凭什么/什么时候不成立；标题读者问题式。
   - 教程/操作指南：任务承诺 → 前置条件 → 步骤（每步含验证）→ 故障处理；读者默认问题：我能做成什么/需要准备什么/每步怎么确认对了/出错了怎么办；标题任务式。
5. **启用规则一句话**：主流程默认不用模板（三问 + 每章一行即可），仅长文/对外文章升级启用第 2、3 部分。

- [ ] **Step 2: 结构断言**

Run（分步执行）：

```bash
grep -c '^## ' skills/professional-writing/references/narrative-patterns.md
```

```bash
grep -c '任务承诺\|前置条件' skills/professional-writing/references/narrative-patterns.md
```

Expected: 至少 5 个二级标题；教程骨架关键词命中 ≥2。

- [ ] **Step 3: 不单独 commit**（统一在 Task 4 末尾提交）

---

### Task 3: references/evidence-map.md

**Files:**
- Create: `skills/professional-writing/references/evidence-map.md`

**Interfaces:**
- Consumes: Task 1 文件名约定；SKILL.md 第 3 步只写了梗概，本文件承载细则。

- [ ] **Step 1: 写入文件**

必须包含三部分，与 spec 5.1 步骤 3 逐条对应：

1. **四格盘点法**：事实（有出处）/ 判断（自己的推断，标注依据）/ 推测（待验证，显式标注）/ 未知（缺口）；各格一个工程示例（如：事实="eval-1 断言 3/3 通过（本次运行日志）"；推测="该 API 可能在 v2 废弃（未查证）"）。
2. **检索规则**（逐条照录 spec）：现有材料足够直接写，不为显得丰富而检索；关键事实可能过期且易核实 → 自动查官方或一手来源；缺失信息会改变中心意图 → 用户在场列缺口征求同意再研究，自主场景把命题/承诺收窄到已确认事实能支撑的范围并把收窄理由写进质检摘要；无法确认的信息明确标记为判断/推测/待确认，不得自行补全；证据清单是内部产物，不默认塞进成稿。
3. **不确定性的行文标注方式**：给 3 个正反例（"预计可降低 40% 延迟（基于 staging 压测，生产未验证）" vs 裸写"可降低 40% 延迟"）。

- [ ] **Step 2: 结构断言**

Run: `grep -c '事实\|判断\|推测\|未知' skills/professional-writing/references/evidence-map.md | awk '{print ($1>=8)?"OK":"FAIL"}'`
Expected: OK（四格概念反复出现，说明各格有展开）。

- [ ] **Step 3: 不单独 commit**（统一在 Task 4 末尾提交）

---

### Task 4: references/self-review.md

**Files:**
- Create: `skills/professional-writing/references/self-review.md`

**Interfaces:**
- Consumes: Task 1 判词表（本文件引用判词编号 1-7，不复制全表，标注"判词表见 SKILL.md"）。

- [ ] **Step 1: 写入文件**

单份合并清单（不是多套并行检查），按局部/全局分组，外加新读者测试步骤：

1. **全局组**：判词 1-7 逐条过（引用 SKILL.md 判词表编号）+ 四个可操作测试：
   - 中心意图测试：论证型能否提炼一句可被反驳的命题，任务型能否提炼可验证的任务承诺；
   - 标题连读测试：全部标题连读应构成完整故事线或任务路径；
   - 第一屏测试：只读第一屏，读者能否复述中心意图；
   - 删减测试：每节问"删掉这节读者会损失什么"，答不出就删。
2. **局部组**：每段落是否清楚、证据是否支撑该段结论、转场是否自然、术语是否前后一致。
3. **新读者测试执行步骤**：
   - 预测读者问题清单模板（5-10 问，含"这个决策的主要风险是什么"式示例 3 个）；
   - subagent 指令模板（成文照录，执行时可直接复制）：

     ```text
     你是这份文档的目标读者：[读者一句话画像]。你只有这份文档，没有其他上下文。
     通读后回答：1) 下列问题各用一两句回答：[问题清单]；
     2) 哪些地方有歧义或可作两种解读；3) 文档假设了你已知道哪些它没交代的背景；
     4) 有无内部矛盾。只基于文档作答，不要补充外部知识。
     ```

   - 无 subagent 退路：把上述指令与问题清单交给用户，在新会话手测；
   - 日常轻量版：作者自己以"只看得到成稿"假设过一遍问题清单。

- [ ] **Step 2: 结构断言**

Run（分步执行）：

```bash
grep -c '测试\|判词' skills/professional-writing/references/self-review.md | awk '{print ($1>=10)?"OK":"FAIL"}'
```

```bash
grep -c '你只有这份文档' skills/professional-writing/references/self-review.md
```

Expected: OK；subagent 模板存在（`1`）。

- [ ] **Step 3: Commit（skill 本体统一提交，Task 1-4 全部产物）**

```bash
git add skills/professional-writing/SKILL.md skills/professional-writing/references/
git commit -m "feat(professional-writing): 新增专业文档写作 skill

按 spec（3c9ded7）落地完整 skill 本体：
- SKILL.md 薄入口：模式路由+快速通道、七步从零写流程+三道确认门、
  重写模式分级处置、Avoid 判词表七条（含教程例外）、交付契约
- narrative-patterns：金字塔/SCQA、四类骨架+读者默认问题、读者卡与
  五列叙事地图选用模板
- evidence-map：四格盘点、混合资料策略、不确定性标注正反例
- self-review：单份合并自检清单、新读者测试模板与退路
验证：SKILL.md ≤150 行、判词 7 条、三道门齐、references 引用名一致、
三个 references 结构断言全过。

<AI-TRAILER>"
```

---

### Task 5: evals 六用例、输入素材与 grader fixture

**Files:**
- Create: `skills/professional-writing/evals/evals.json`
- Create: `skills/professional-writing/evals/files/eval1-流水账调研总结.md`
- Create: `skills/professional-writing/evals/files/eval2-调研笔记.md`
- Create: `skills/professional-writing/evals/files/eval4-技术决策笔记.md`
- Create: `skills/professional-writing/evals/files/eval5-操作过程记录.md`
- Create: `skills/professional-writing/evals/files/eval6-黑话密集专业材料.md`
- Create: `skills/professional-writing/evals/files/eval6-风格压力事实清单.json`

**Interfaces:**
- Consumes: 判词表编号（断言引用）；skill-creator 的 evals.json schema（`skills/skill-creator/references/schemas.md`）。
- Produces: Task 6A/6B 直接消费本任务的六个用例、29 条单配置断言与两个绑定 fixture。

- [ ] **Step 1: 写入 evals.json**

```json
{
  "skill_name": "professional-writing",
  "evals": [
    {
      "id": 1,
      "name": "rewrite-summary",
      "prompt": "这是我们组一位同学写的调研总结，读起来很累。帮我改一下，读者是我们的技术负责人。",
      "files": ["evals/files/eval1-流水账调研总结.md"],
      "expected_output": "先给出诊断（命中判词及位置，存 diagnosis.md），再给出重写稿（rewritten.md）；重写稿结论在首段，按读者关心度重组，不按时间线。",
      "expectations": [
        "diagnosis.md 指出至少 3 处结构问题并给出原文位置",
        "rewritten.md 首段包含明确的调研结论与推荐",
        "rewritten.md 的组织顺序不是执行时间线（无'周二/周三/然后'式推进）",
        "rewritten.md 无'背景/过程/分析/总结'式空标题"
      ]
    },
    {
      "id": 2,
      "name": "write-decision-doc",
      "prompt": "根据这份笔记写一份方案说明，给要拍板的决策者看，帮他决定要不要换方案 B。",
      "files": ["evals/files/eval2-调研笔记.md"],
      "expected_output": "document.md：首段含一句命题式断言（推荐哪个、为什么）；有显式取舍标记；关键推荐与推断有素材事实依据，或明确标注为推断/估算；新增治理控制区分素材既定约束与写作者推导建议，建议说明依据和待确认主体，不冒充素材既定约束，不做无依据的确定性陈述；未证实传闻不写成事实；无空标题。",
      "expectations": [
        "首段含一句明确的推荐性断言",
        "存在主次排序或'细节见附录'类显式取舍标记",
        "关键推荐与推断给出素材中的事实依据，或明确标注为推断/估算；不限定具体句式",
        "素材中标注'未证实'的传闻在文中被标注或被排除，未写成事实",
        "有明确推导依据的责任分工、控制线、审批规则或 SLA 可作为建议/待决事项，但须说明依据和待确认主体；不得将写作者推导的新增治理控制冒充素材既定约束，或无依据写成确定性陈述；不限定标注句式",
        "无'背景/分析/总结'式空标题"
      ]
    },
    {
      "id": 3,
      "name": "insufficient-material",
      "prompt": "帮我写一份关于我们数据库选型的调研总结文档。",
      "files": [],
      "expected_output": "response.md：不硬写。先问读者与目标，或列出事实缺口（未知格）征求确认；不编造选型数据。",
      "expectations": [
        "没有生成虚构数据的正式选型文档",
        "response.md 包含对读者/目标的追问，或列出需要补齐的事实缺口",
        "未编造任何具体的选型数据或结论"
      ]
    },
    {
      "id": 4,
      "name": "write-explainer-article",
      "prompt": "根据这份笔记写一篇技术文章，给公司内的后端工程师讲清楚我们为什么放弃了方案 X 换成 Y。",
      "files": ["evals/files/eval4-技术决策笔记.md"],
      "expected_output": "document.md：首段含核心判断；有反例/边界内容（什么情况下 X 仍更好）；推断有依据标注。",
      "expectations": [
        "首段包含核心判断（为什么换 Y）",
        "包含反例或边界内容（素材中'小数据量下 X 延迟反而低'被使用）",
        "关键断言有出处或推断依据标注"
      ]
    },
    {
      "id": 5,
      "name": "write-tutorial",
      "prompt": "把这份操作记录整理成一份新人也能照做的操作指南。",
      "files": ["evals/files/eval5-操作过程记录.md"],
      "expected_output": "document.md：开头是可验证的任务承诺而非观点命题；含前置条件；素材能支持的步骤附验证方式，素材不足处标记'待确认'而非编造；分别说明目标发布包如何成为待启动内容，以及运行进程如何核对实际加载的版本或构建标识；步骤章节无强造的结论句。",
      "expectations": [
        "开头为任务承诺（完成什么、前提是什么）而非观点命题",
        "含前置条件内容",
        "素材能支持的步骤附验证方式；素材含糊处（如'改了下那个配置'）标记待确认，未编造具体命令或路径",
        "T1 发布包采用动作：已上传且校验通过后，必须说明目标发布包如何通过部署、安装、替换或切换成为待启动内容；素材未提供必要动作时显式列为待确认步骤或阻塞项，不得省略或编造动作、命令、路径或参数",
        "T2 运行版本身份验证：服务启动后必须核对运行进程实际加载的版本或构建标识与目标一致；素材未提供核对方法时显式标为待确认，不得用'Application started'、健康检查'UP'或业务成功替代版本身份验证",
        "步骤章节无强造的结论句或'综上所述'式总结段"
      ]
    },
    {
      "id": 6,
      "name": "rewrite-style-pressure",
      "prompt": "请把这份说明重写成一份给公司内后端工程师阅读的专业说明。保留所有技术事实、数值、成立条件和范围边界，不要补充材料中没有的事实。输出 document.md。",
      "files": ["evals/files/eval6-黑话密集专业材料.md"],
      "expected_output": "document.md：在不损失事实、数值、条件和边界的前提下，改写黑话密集、缩写后置解释、重复命题和空泛表达；标准技术术语保留，非通用缩写首次出现时解释或删除；未定义黑话不得增强为具体职责。",
      "expectations": [
        "PSG 与 RRA 如保留，首次出现时须分别解释为支付状态网关与退款风险评估服务；也可删除缩写只写全称",
        "F1 完整保留：2026-07-08、staging、1,000 rps、p99 从 480 ms 降到 310 ms，并明确生产尚未验证",
        "F2 完整保留：只对网络超时重试、最多 3 次、间隔 200 ms，并明确 HTTP 4xx 不重试",
        "F3 完整保留：连续 5 分钟错误率超过 1.5%、由当班 SRE 发起回滚，并明确生产阈值配置仍待审批",
        "F4 完整保留：只覆盖支付状态查询、账户对账不在范围内，并保留每天 02:00 批处理",
        "重复命题 R1 只完整展开一次；后续如引用不得与 F4 的范围边界矛盾",
        "U1 未定义黑话：源文'监控侧做统一收口'未定义主体、动作、对象、责任范围和强度；只能删除该表述且不新增职责命题，或保留带引号原词并说明未定义项；不得增强为'负责'、'承担'、'统一管理'、'统一监控'、'触发回滚'等更具体或更强职责"
      ]
    }
  ]
}
```

字段名提醒（Global Constraints 的约定）：本文件用 `expectations`；Task 6 每个 eval 目录的 canonical `eval_metadata.json` 用 `assertions`（内容复制自上面对应 expectations），并复制到两个 configuration 目录供 viewer 读取；`grading.json` 的 expectations[] 严格用 `text/passed/evidence`。

- [ ] **Step 2: 写入五个输入素材与一个 grader fixture**

`eval1-流水账调研总结.md` —— 必须埋入判词 1（结论在最后）、2（时间线）、5（空标题），基调如下（可扩充到 300 字左右，保持病灶）：

```markdown
# 消息队列调研总结

## 背景
上周接到任务后，我先看了 Kafka 的文档，了解了它的分区机制。

## 过程
周二我搭了测试环境，先测了 Kafka，吞吐量数据见附件。周三测了 RabbitMQ，
遇到一个连接池问题，排查花了半天。周四测了 Pulsar，部署比较复杂。
周五我把三个的数据整理了一下，还看了几篇对比文章。

## 分析
Kafka 吞吐高但运维重；RabbitMQ 简单但吞吐一般；Pulsar 功能全但社区小；
另外我还注意到延迟、生态、云托管价格等十来个维度各有差异（逐条罗列）。

## 总结
综合来看各有优劣，我个人倾向在我们的场景下可以考虑 Kafka。
```

`eval2-调研笔记.md` —— 散乱 bullet（10-15 条无序要点：现状痛点 2-3 条、方案 A/B 各自数据 3-4 条、迁移成本 2 条、一条未验证的传闻如"听说 B 的新版本要改收费模式（未证实）"、一条与决策无关的杂讯）。

`eval4-技术决策笔记.md` —— 散乱 bullet（X 的三个问题及数据、Y 的两个优势、一次线上事故记录、一个 X 仍占优的场景如"小数据量下 X 延迟反而低 20%"、迁移中踩的坑一条）。

`eval5-操作过程记录.md` —— 第一人称流水账操作记录（"我先 ssh 到跳板机，然后改了配置，中间报了个错我重启解决了……"约 10 步，含 2 处口语化含糊表述如"改了下那个配置"，供改写时暴露前置条件与验证缺失）。素材必须明确提供发布包已上传且校验通过、日志出现 `Application started`、健康检查为 `UP` 和后续业务成功，但故意不提供发布包如何成为待启动内容的部署/安装/替换/切换动作，也不提供核对运行进程实际版本或构建标识的方法，用于分别触发 T1/T2。

`eval6-黑话密集专业材料.md` —— 保持既有 F1-F4、R1、PSG/RRA 与四项 style pressure；其中精确保留源文“监控侧做统一收口”，该短语不定义主体、动作、对象、责任范围或强度，作为 U1 的 source bound。

`eval6-风格压力事实清单.json` —— 在既有 `non_common_abbreviations`、`facts` 与 `repeated_proposition` 后增加以下精确 fixture 合同；grader 只能按这些已冻结值判断 U1，不得用行业惯例补义：

```json
"undefined_jargon": [
  {
    "id": "U1",
    "source_text": "监控侧做统一收口",
    "undefined_dimensions": ["主体", "动作", "对象", "责任范围", "强度"],
    "allowed_handling": [
      "删除该表述且不新增职责命题",
      "保留带引号原词并说明全部未定义项"
    ],
    "forbidden_enhancements": ["负责", "承担", "统一管理", "统一监控", "触发回滚"]
  }
]
```

- [ ] **Step 3: 结构断言**

Run（分步执行）：

```bash
python3 -c "import json;d=json.load(open('skills/professional-writing/evals/evals.json'));assert len(d['evals'])==6;assert [len(e['expectations']) for e in d['evals']]==[4,6,3,3,6,7];print('OK',[e['name'] for e in d['evals']])"
```

```bash
ls skills/professional-writing/evals/files/ | wc -l
```

Expected: OK + 六个 name，断言数精确为 `4/6/3/3/6/7`；素材与 grader fixture 文件共 `6`。

- [ ] **Step 4: Commit**

```bash
git add skills/professional-writing/evals/
git commit -m "test(professional-writing): 加固教程与黑话保真评测合同

将 eval-5 的发布包采用动作与运行版本身份验证拆为 T1/T2，
并为 eval-6 增加未定义黑话 U1 与 grader fixture，防止职责语义增强。
验证：evals.json 解析通过、6 用例断言数为 4/6/3/3/6/7、6 个 fixture 文件齐。

<AI-TRAILER>"
```

---

### Task 6: iteration-1 标准评测链路（skill-creator 全流程，含用户检查点）

**Files:**
- Create: `skills/professional-writing-workspace/iteration-1/`（.gitignore 排除，不入 git）
- Modify: `.gitignore`（追加 `skills/*-workspace/`）

**Interfaces:**
- Consumes: Task 1-5 全部产物；执行前**通读** `skills/skill-creator/SKILL.md` 的 "Running and evaluating test cases" 全节与 `skills/skill-creator/references/schemas.md`（字段名以 schemas.md 为准）。
- Produces: `iteration-1/benchmark.json`、`feedback.json`（Task 7 之前的迭代依据）。

- [ ] **Step 1: 追加 .gitignore 并建 workspace**

用文件编辑工具（Edit/apply_patch，不用 `echo >>`）在 `.gitignore` 追加一行：

```
skills/professional-writing-workspace/
```

然后分步执行（git 命令不串联）：

```bash
mkdir -p skills/professional-writing-workspace/iteration-1
```

```bash
git add .gitignore
```

```bash
git commit -m "chore(professional-writing): 忽略 evals workspace 目录

评测运行产物（runs/grading/benchmark）不入 git，仅保留 evals 定义。

<AI-TRAILER>"
```

- [ ] **Step 2: 分批双跑（每 eval 一批，一批 = 同 prompt 的 with_skill + without_skill 一对）**

**运行次数口径（写死）：MVP 每配置运行 1 次**（5 evals × 2 配置 = 10 次运行；iteration-1 的目的是发现 skill 缺陷，不是精确统计；如后续需要方差分析再按每配置 3 次重跑）。受宿主并发上限约束（评审环境总槽位 4：主 agent 占 1，最多 3 个并发 subagent），**不要一次 spawn 10 个**：按 eval 分 5 批，每批同时启动一对（with_skill + without_skill 同批保证运行条件一致），一批完成并保存 timing 后进下一批；在 benchmark notes 记录"受并发上限影响的分批运行；每配置 1 次"。

**目录契约（必须匹配 aggregate_benchmark.py 的扫描规则，见 Global Constraints）**：

```
skills/professional-writing-workspace/iteration-1/
├── eval-1-rewrite-summary/
│   ├── eval_metadata.json          # eval 级（含 eval_id: 1 与 assertions）
│   ├── with_skill/
│   │   ├── eval_metadata.json      # canonical metadata 的副本，供 viewer 读取
│   │   └── run-1/
│   │       ├── outputs/            # 该 eval 的输出契约文件
│   │       ├── timing.json
│   │       └── grading.json
│   └── without_skill/（同构，含 metadata 副本与 run-1）
├── eval-2-write-decision-doc/ …
└── eval-5-write-tutorial/
```

目录名必须以 `eval-<数字>-` 开头（脚本按 `eval-*` glob 并从名字取 id）；configuration 目录名严格为 `with_skill` / `without_skill`。

每个 eval 的**输出契约**（写进 subagent 指令，viewer 只能展示落盘文件）：

| eval | 必须落盘的输出 |
| --- | --- |
| eval-1 | `diagnosis.md`（诊断，评测产物，不混入交付稿）、`rewritten.md`（干净重写稿）、`qa-summary.md` |
| eval-2/4/5 | `document.md`（干净成稿）、`qa-summary.md` |
| eval-3 | `response.md`（追问或缺口清单；正确行为是不产出正式文档） |
| 全部 | `transcript.md`（执行过程摘要，供 grader 检查交互行为） |

with_skill 指令模板（替换 <>；baseline 同 prompt 去掉 Skill path，输出到 `without_skill/outputs/`）：

```text
Execute this task:
- Skill path: skills/professional-writing
- Task: <该 eval 的 prompt>
- Input files: <files 或 "none">
- Save outputs to: skills/professional-writing-workspace/iteration-1/eval-<id>-<name>/with_skill/run-1/outputs/
- Outputs to save: <上表该 eval 的文件清单>
```

**每个运行完成的通知到达时，立即**把 `total_tokens` 与 `duration_ms` 写入该运行的 `run-1/timing.json`（这是唯一捕获机会，不可批处理）：

```json
{"total_tokens": 84852, "duration_ms": 23332, "total_duration_seconds": 23.3}
```

- [ ] **Step 3: 写 canonical eval_metadata.json，并复制给两个 configuration**

canonical 文件放在 `eval-<id>-<name>/eval_metadata.json`，含 `eval_id`（整数，与 evals.json 的 id 一致）、`eval_name`、原始 `prompt` 与 `assertions`（= evals.json 中该 eval 的 `expectations` 逐条复制）。然后把相同文件复制到 `with_skill/eval_metadata.json` 和 `without_skill/eval_metadata.json`：aggregate 读取 eval 级文件，viewer 从各 run 的父目录读取 configuration 级副本。

- [ ] **Step 4: 逐运行生成 grading.json**

spawn grader subagent（读 `skills/skill-creator/agents/grader.md`）或 inline 评分。expectations[] 严格使用 `text` / `passed` / `evidence` 三字段。能程序判定的断言（如"无空标题"可 grep 标题行）写脚本跑，不靠目测。

- [ ] **Step 5: 聚合 benchmark 并做 analyst pass**

在 `skills/skill-creator/` 作为工作目录执行：

```bash
python -m scripts.aggregate_benchmark ../professional-writing-workspace/iteration-1 --skill-name professional-writing
```

产出 benchmark.json/md（pass_rate、时间、token 的 with/without 对比）。然后按 `skills/skill-creator/agents/analyzer.md` 的 "Analyzing Benchmark Results" 节做 analyst pass：找非区分断言（两配置都过）与时间/token 代价，把结果写入 `benchmark.json.notes`。**不做高方差分析**（每配置仅 1 次运行，stddev 无意义——这也是 MVP 口径的已知取舍，在 notes 里注明）。

聚合脚本固定写 `runs_per_configuration: 3`，因此 analyst pass 后从仓库根目录执行以下归一化：把 JSON 标记改为真实的 `1`，再用同一份 JSON 重新生成 Markdown，保证两个产物口径与 notes 一致。

```bash
python3 -c "import json,pathlib,sys;sys.path.insert(0,'skills/skill-creator');from scripts.aggregate_benchmark import generate_markdown;p=pathlib.Path('skills/professional-writing-workspace/iteration-1/benchmark.json');d=json.loads(p.read_text());d['metadata']['runs_per_configuration']=1;p.write_text(json.dumps(d,ensure_ascii=False,indent=2));p.with_suffix('.md').write_text(generate_markdown(d))"
```

- [ ] **Step 6: 生成评审页面（generate_review.py，不写自制 HTML）**

```bash
python skills/skill-creator/eval-viewer/generate_review.py \
  skills/professional-writing-workspace/iteration-1 \
  --skill-name "professional-writing" \
  --benchmark skills/professional-writing-workspace/iteration-1/benchmark.json \
  --static skills/professional-writing-workspace/iteration-1/review.html
```

（有显示环境可去掉 `--static` 起服务；headless 用 `--static` 产静态页。）

- [ ] **Step 7: 【停——用户检查点】用户在 viewer 审阅并提交 feedback.json**

告知用户：Outputs 标签逐用例看产出并留反馈（叙事质量的人工判断在此完成），Benchmark 标签看定量对比。提交后把 `feedback.json` 放回 workspace 目录。如用户想要更严格的对照，可在标准链路之外补一轮匿名 A/B 盲评（with/without 去标识对调），但它是补充，不替代 viewer 流程。

- [ ] **Step 8: 读 feedback.json 决定迭代**

空反馈 = 满意。有具体意见 → 按 skill-creator "Improving the skill" 节改 SKILL.md/references（改后检查旁支一致性），重跑全部用例到 `iteration-2/`（baseline 仍为 without_skill），viewer 加 `--previous-workspace` 再审。收敛后如 evals 定义有修订：

```bash
git add skills/professional-writing/evals/evals.json
git commit -m "test(professional-writing): 按 iteration 反馈校准 evals 定义

修订点与 iteration-N 通过率写入 body（数据来自 benchmark.json）。

<AI-TRAILER>"
```

---

### Task 6A: 历史严格闭环方案（已被 Task 6C 取代，不执行）

> 本节保留旧 5-run / new-old 全量闭环的设计记录，不再是活动任务；不得按本节命令修改 Batch 6、Batch 7、Batch 8 或 iteration-6。

**Files:**
- Modify: skills/professional-writing/SKILL.md
- Modify: skills/professional-writing/references/self-review.md
- Create in ignored workspace: skills/professional-writing-workspace/style-calibration/process-candidate/（完整候选快照；仅 SKILL.md 与 references/self-review.md 相对正式 skill 有差异）
- Create in ignored workspace: skills/professional-writing-workspace/style-calibration/process-batches/batch-1/
- Create in ignored workspace: skills/professional-writing-workspace/style-calibration/derive-content-status.py
- Create in ignored workspace: skills/professional-writing-workspace/iteration-4/
- Create in ignored workspace: skills/professional-writing-workspace/iteration-4/user-content-review.json
- Create in ignored workspace: skills/professional-writing-workspace/iteration-4/content-calibration-status.json

**Interfaces:**
- Consumes: approved spec commit 1a22ed30a49eeb6b4c1d1265cf5372a0b9d8874f；已提交的 eval-6 fixture 与 7 条 hard assertions；固定旧 skill 快照 skills/professional-writing-workspace/style-calibration/old-skill-77afd2d/；已记录并经主 agent 核验的 RED：old skill 5/5 文档存在四项 style control 问题，no-guidance 3/5。
- Produces: 只包含 SKILL.md 与 references/self-review.md 的候选 delta；固定批次 5 份 fresh candidate outputs；同 5 份输出的 fresh style reviews；正式两文件精确提升；iteration-4 的 eval-1..6 new/old 全量结果、viewer、用户内容结论和 content-calibration-status.json。
- Candidate snapshot: process-candidate/ 是可直接加载的完整 skill 快照；只允许 SKILL.md 与 references/self-review.md 相对正式 skill 有差异，其他 references、evals 和目录结构必须逐字一致。
- Command workdir: 除 aggregate 命令明确切到 skills/skill-creator/ 外，以下命令均从仓库根目录 /Users/zhaoguodong/Codes/ai-coding/lucas-skills/.worktrees/professional-writing 执行。

**Hard gates:**
- 候选固定批次必须恰好 5 份 fresh 输出，先达到 eval-6 hard assertions 35/35 且双向事实核对 0 mismatch。
- 事实门通过后，才对同 5 份原始输出做 5 次 fresh style review；主 agent 核验 finding 后，四项 criterion 的 accepted issue-document union 必须 <=1/5。
- A/B 只用于诊断，不是 hard gate，不进入 content-calibration-status.json。
- 正式两文件必须与通过门槛的候选逐字一致；iteration-4 的 eval-1..6 new/old 全量结构与事实断言及用户内容检查点用于记录原流程结果。当前 Task 7 仍必须等待 Task 6B 的新合同重跑，不得由 iteration-4 或 iteration-6 解锁。
- 任一文件、字段、样本或证据缺失即失败；不得补跑替换同批次失败样本，不得用 eval-2/4、总通过率、A/B 胜率或人工豁免替代任一硬门。

- [ ] **Step 1: 复用已记录 RED，不重跑基线**

不重跑基线、不挑样本，也不在此维护第二份校验命令。Step 3 的唯一派生器会直接读取 10 份既有主 agent validation，并要求计数精确为 old 5/5、no-guidance 3/5；任一 validation 缺失、validated_by_main 不为 true 或计数漂移时 hard phase 非零退出，不得伪造或重跑历史 RED。

- [ ] **Step 2: 建立完整候选快照，只用 apply_patch 修改两个文件**

创建可直接作为 skill path 加载的完整候选快照。首次执行先确认 process-candidate 不存在；中断后续跑时只允许复用本任务创建、且除目标两文件外仍与正式 skill 逐字一致的目录。批次 manifest 会固定候选 hash，因此失败后可在同一路径修订 wording，但必须使用新的 batch-N，不能覆盖旧批次证据：

~~~bash
python3 -c "import pathlib;p=pathlib.Path('skills/professional-writing-workspace/style-calibration/process-candidate');assert not p.exists(),f'refuse existing candidate: {p}';print('candidate path is empty')"
~~~

Expected: 输出 candidate path is empty，退出 0；目录已存在时非零退出，不执行复制。

~~~bash
cp -R skills/professional-writing skills/professional-writing-workspace/style-calibration/process-candidate
~~~

Expected: 退出 0，完整候选快照创建成功。

只对这两个候选文件使用 apply_patch。SKILL.md 的精确候选 wording 如下。

先把入口标题精确替换为：

~~~markdown
## 从零写（思考顺序 1→9；落笔顺序不同：先写最核心章节，标题、开头、摘要最后写）
~~~

旧标题“思考顺序 1→7”不得保留。

在标题后的目标说明中加入：

~~~markdown
成稿同时满足基础专业表达标准：无内部黑话和空泛套话，简洁但不机械缩短，准确、专业、清晰、易懂。不参与本项目但具备领域常识的目标读者，无需额外项目上下文即可理解。专业不等于复杂，简洁不等于删掉事实、条件或边界。
~~~

将现有“5 写章节”至“7 新读者测试”替换为：

~~~markdown
### 5 写内容初稿并形成事实锁（阶段 A）

先解决结构、论证和事实完整性，不把“更短”当目标。先写最核心、最不确定的章节；每节首句给出本节结论，教程步骤章节首句给出操作目标，正文包含步骤与验证。正文完成后再写标题、开头和摘要。

教程逐个关键状态转换按“前态 → 使转换发生的必要动作 → 后态 → 验证证据”成文，动作与验证不能互相替代。source bound 未提供必要动作时，必须把该转换单列为待确认步骤或阻塞项并说明缺失信息，不得省略、按惯例补造，或仅用后态和后续成功信号代替动作。

在初稿前优先根据原材料与已核实证据形成内部事实锁；已有初稿或先完成初稿时，必须在阶段 B 前补建。初稿只能用于覆盖检查，不能成为字段值的唯一来源。事实锁逐项记录：

- stable ID：本次交付内唯一，如 F-01、J-01。
- type：事实、判断、推测、未知之一。
- 精确命题：必须保持不变的完整语义。
- 限定信息：数值、成立条件、适用范围、否定或排他边界；没有时记“无”。
- 标准术语/标识符：必须精确保留的术语、缩写、对象名、接口名；没有时记“无”。
- source locator：原材料或已核实证据的精确位置，不指向改写后的初稿。
- 判断专用字段：判断依据与 status（已确认、建议、待决或待确认）。

source bound 中的黑话或含糊措辞无法确定具体主体、动作、对象、责任范围或强度时，事实锁的精确命题保留带引号的源文原词，不写入行业惯例推断；同时增加“未知”项，按五个维度逐项记录未定义内容和缺失信息。可确定部分与未知部分分开锁定。

同时冻结 source bound，即本轮允许使用的原材料与已核实证据集合。阶段 B/C 不得暗改事实锁或引入 bound 外事实；需要新证据时回到阶段 A，更新 source bound 和事实锁后重新冻结。事实锁只存在当前上下文，不默认落盘或进入成稿；即使跳过完整证据地图，也不能跳过最小事实锁。

### 6 独立风格校准（阶段 B）

内容初稿完成后单独做一次风格校准，不与起草混在同一轮。逐项检查并只改问题句段：

- 优先使用“主体 + 动作 + 结果”。
- 标准术语与非通用缩写首次出现时按读者需要解释，标题中的出现也算首次。完稿后按读者可见顺序逐个定位事实锁中的非通用缩写，释义滞后时将释义移到首次出现处或只保留全称。
- 一段只表达一个意思，一句只承担一个主要判断或动作。
- 保持证据关系、认识状态、判断极性与强度。缺少证据不等于存在反证：未验证、无数据、待审批或证据不足，只能表达为未知、待确认或证据边界；只有 source bound 明确给出冲突事实或相反证据时，才能判定存在冲突。反向也不得把已确认冲突弱化为单纯待确认。
- 按“主体 + 判断/动作 + 关键条件/范围边界”扫描语义重复，不只比对字面；每个完整命题只设一个权威展开位置。其他位置只有承担摘要、过渡或证据等不同读者功能时才保留，并压缩为引用或指向。删除仪式性开头和空泛结尾，但不机械压缩篇幅。
- 只有 source bound 明确支持时，才把原材料中的内部黑话改写为具体主体、动作与结果。否则保留带引号的源词，并对照事实锁按“主体、动作、对象、责任范围、强度”逐项说明未定义内容；不损失决策语义时可删除纯空话。不得依据行业惯例增强主体职责、动作、对象、范围或强度。

→ **门 3（代表章节，条件式）**：长文、对外文章、新文风且用户在场时，先完成最关键一章的阶段 A/B，确认叙事密度与表达后再展开全篇；短总结、常规汇报或快速通道跳过交互确认。

### 7 对照事实锁复核（阶段 C）

做双向核对：

1. 锁内每个 stable ID 的精确命题、限定信息、术语/标识符，以及判断的依据与 status 都完整保留。
2. 风格稿没有新增事实锁或 source bound 之外的事实与判断。
3. 按成稿阅读顺序复核每个非通用缩写的首次出现，并将每个保留黑话逐项对照事实锁中的未知维度；释义滞后或任一未知维度遗漏都算 mismatch。

逐项核对黑话替换的“源文原词 → 风格稿表达”映射。把抽象词换成更具体或更强的动词，或者改变主体、对象、责任范围或强度，均算 mismatch。

同时核对判断依据中的证据关系、认识状态、极性与强度。把缺证、未知或待决写成存在冲突或已被证伪，或者把已确认冲突弱化为待确认，均算 mismatch。

遗漏、弱化、扩大、缩小、改变或锁外新增都算 mismatch，最终只接受 0 mismatch。同一问题句段只允许一次局部修复：先恢复事实锁中的原事实，只改该句段，再执行双向核对；仍有 mismatch 时，撤销该句段全部 style 改动，恢复 pre-style、事实正确的原文，并停止继续改写该句段。恢复后仍存在的风格问题写入对话内质检摘要，不盲目重写整篇。

重要交付（用户显式要求高质量，或对外/对上材料）优先创建不继承当前对话或任务历史的 fresh subagent，只提供目标读者、内容初稿、冻结事实锁、source bound 与阶段 B/C 标准，由其完成风格校准和事实复核；主 agent 只接收 0 mismatch 的稿件。无 subagent 环境或日常文档，由同一 agent 明确分开阶段 A、B、C 执行。快速通道只跳过交互确认，不跳过事实锁或阶段 C。

### 8 合并自检

执行 references/self-review.md 的单份清单；不另起第二套 style checklist 或事实 checklist。

### 9 新读者测试（条件式）

重要交付预测 5-10 个读者问题，再创建不继承当前对话或任务历史的新上下文，只传读者画像、问题清单和成稿，让 fresh reader 指出歧义、隐含前提与内部矛盾。若修订引入新证据，或改变事实、判断、条件、范围，回阶段 A 更新并重新冻结事实锁，再执行 B/C；纯表达修改不改锁，但必须再执行阶段 C。无 subagent 环境时把问题清单交用户在新会话手测；日常交付由作者以“读者只看得到成稿”为前提轻量自测。
~~~

将“重写模式”替换为：

~~~markdown
## 重写模式

1. 诊断：对照判词表列出命中项与具体位置。
2. 分级处置：局部问题在原文上外科式修改；结构性问题才按读者与中心意图重构叙事地图。
3. 收尾：把已有文档或结构重写稿视为内容初稿，从原材料和已核实证据形成并冻结事实锁，依次执行阶段 B、阶段 C、合并自检和条件式新读者测试。局部表达修改也必须通过阶段 C。
~~~

在“交付”中明确加入：

~~~markdown
- 事实锁、source bound、风格检查和事实复核是内部过程产物，不默认落盘、不进入成稿；最终仍只交付干净成稿，并在对话内给出质检摘要。
~~~

references/self-review.md 保留现有判词、四个测试和新读者测试，在“局部检查”与“全局检查”之间加入以下精确内容：

~~~markdown
## 阶段 B：独立风格校准

- [ ] 是否优先写成“主体 + 动作 + 结果”，而非用口号、营销语、比喻或抽象名词替代定义和证据。
- [ ] 是否按成稿阅读顺序逐个定位事实锁中的非通用缩写，并确认其首次出现处已按需解释或只保留全称；标题中的出现是否同样检查。
- [ ] 是否一段一意、一句一个主要判断或动作；必要的因果、条件和范围边界是否完整保留；是否把未验证、无数据、待审批或证据不足仅写为未知、待确认或证据边界，并仅在 source bound 明确给出冲突事实或相反证据时判定冲突；是否避免反向弱化已确认冲突。
- [ ] 是否按“主体 + 判断/动作 + 关键条件/范围边界”扫描语义重复；仪式性开头和空泛结尾是否删除；是否避免把“更短”本身当成功标准。
- [ ] 材料内黑话是否仅在 source bound 明确支持时改成具体主体、动作与结果；证据不足时，是否保留带引号的源词，并对照事实锁按“主体、动作、对象、责任范围、强度”逐项说明未定义内容，或在不损失决策语义时删除纯空话；是否避免依据行业惯例增强职责判断。

## 阶段 C：对照事实锁复核

- [ ] 事实锁是否绑定原材料和已核实证据，包含 stable ID、type、精确命题、限定信息、标准术语/标识符、source locator，以及判断的依据与 status，并在阶段 B 前与 source bound 一起冻结；黑话含义不明时，是否保留带引号的源词，并以“未知”项按“主体、动作、对象、责任范围、强度”逐项记录未定义内容和缺失信息；可确定项与未知项是否分开冻结，任一应检查维度未记录时是否停止进入阶段 B。
- [ ] 正向核对是否逐 stable ID 保留完整命题、数值、条件、范围、否定/排他边界、术语/标识符、判断依据与 status。
- [ ] 反向核对是否确认风格稿没有新增锁外或 source bound 外的事实与判断。
- [ ] 是否按成稿阅读顺序复核每个非通用缩写的首次出现，并逐项对照事实锁中每个保留黑话的未知维度；释义滞后或任一维度遗漏是否都记为 mismatch。
- [ ] 是否逐项核对“源文黑话 → 风格稿表达”映射；更具体或更强的动词，以及主体、对象、责任范围或强度的变化，是否均记为 mismatch；判断依据中的证据关系、认识状态、极性或强度发生变化时，是否同样记为 mismatch。
- [ ] mismatch 是否为 0；同一问题句段一次局部修复后仍 mismatch 时，是否恢复 pre-style、事实正确的原文并停止继续改写该句段。

## 教程连续性与身份验证

- [ ] 是否逐个核对“前态 → 必要动作 → 后态”，动作与验证是否分别存在；source bound 缺必要动作时，是否列为待确认步骤或阻塞项而未编造。
- [ ] 最终验证是否确认运行进程实际加载的版本或构建标识；是否避免用对象存在、`Application started`、健康检查 `UP` 或后续业务成功替代采用、加载或生效证据。
~~~

最后验证候选与正式 skill 的文件集合相同、差异只有两个目标文件，且正式 skill 尚未变化：

~~~bash
python3 - <<'PY'
import pathlib
base = pathlib.Path("skills/professional-writing")
candidate = pathlib.Path("skills/professional-writing-workspace/style-calibration/process-candidate")
base_files = {p.relative_to(base) for p in base.rglob("*") if p.is_file()}
candidate_files = {p.relative_to(candidate) for p in candidate.rglob("*") if p.is_file()}
assert base_files == candidate_files
changed = sorted(str(p) for p in base_files if (base / p).read_bytes() != (candidate / p).read_bytes())
assert changed == ["SKILL.md", "references/self-review.md"], changed
print("candidate delta: SKILL.md, references/self-review.md")
PY
~~~

Expected: 输出 candidate delta: SKILL.md, references/self-review.md，退出 0。

~~~bash
git status --short
~~~

Expected: 不显示被忽略候选，也不显示正式 skill 变更。候选不得新增 runtime 脚本、reference、Avoid 第 8 条、固定句长/字数规则或禁词表。

- [ ] **Step 3: 预注册固定批次并生成恰好 5 份 fresh candidate outputs**

先用 apply_patch 创建唯一的 ignored 派生器 skills/professional-writing-workspace/style-calibration/derive-content-status.py。它只校验并派生内容门；不实现 A/B、不带 self-test。hard/style/promotion/full 四个 phase 复用同一套逐级校验，完整代码为 192 行：

~~~python
#!/usr/bin/env python3
import argparse, hashlib, json, pathlib, re, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[3]
STYLE, FORMAL = ROOT / "skills/professional-writing-workspace/style-calibration", ROOT / "skills/professional-writing"
CANDIDATE, TARGETS = STYLE / "process-candidate", ["SKILL.md", "references/self-review.md"]
COUNTS = {1: 4, 2: 6, 3: 3, 4: 3, 5: 6, 6: 7}
CRITERIA = {"unexplained_abbreviation", "empty_management_phrase", "repeated_proposition", "overloaded_sentence"}
LEVEL = {"hard": 1, "style": 2, "promotion": 3, "full": 4}
def need(ok, message):
    if not ok: raise ValueError(message)
def load(path):
    need(path.is_file(), f"missing: {path}"); return json.loads(path.read_text())
def digest(path):
    need(path.is_file(), f"missing: {path}"); return hashlib.sha256(path.read_bytes()).hexdigest()
def rel(path): return path.resolve().relative_to(ROOT).as_posix()
def command(argv):
    run = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True)
    need(run.returncode == 0, f"{' '.join(argv)}: {run.stdout}{run.stderr}"); return run.stdout
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"); tmp.replace(path)
def red():
    counts = {}
    for variant, wanted in (("old_skill", 5), ("no_guidance", 3)):
        rows = [load(STYLE / "micro-test" / variant / f"run-{n}" / "control-validation.json") for n in range(1, 6)]
        need(all(r["variant"] == variant and r["run_number"] == n and r["validated_by_main"] is True
                 and r["validated_style_problem_present"] == bool(r["evidence"]) and str(r["validation_notes"]).strip()
                 for n, r in enumerate(rows, 1)), f"RED {variant}")
        count = sum(r["validated_style_problem_present"] for r in rows); need(count == wanted, f"RED count {variant}: {count}")
        counts[variant] = count
    return counts
def manifest(batch, expected):
    data = load(batch / "manifest.json"); hashes = {name: digest(CANDIDATE / name) for name in TARGETS}
    need(data["schema_version"] == 1 and data["batch_id"] == batch.name, "manifest identity")
    need(data["candidate_files"] == TARGETS and data["candidate_sha256"] == hashes, "candidate hash drift")
    files = {p.relative_to(FORMAL) for p in FORMAL.rglob("*") if p.is_file()}
    copy = {p.relative_to(CANDIDATE) for p in CANDIDATE.rglob("*") if p.is_file()}
    need(files == copy and all(str(p) in TARGETS or (FORMAL / p).read_bytes() == (CANDIDATE / p).read_bytes()
         for p in files), "candidate snapshot drift")
    need(data["run_ids"] == [f"run-{n}" for n in range(1, 6)] and data["hard_assertions"] == expected
         and data["sealed_before_runs"] is True, "manifest runs/assertions")
    need(data["fixture"] == "skills/professional-writing/evals/files/eval6-黑话密集专业材料.md"
         and data["fixture_sha256"] == digest(ROOT / data["fixture"])
         and data["grader_reference"] == "skills/professional-writing/evals/files/eval6-风格压力事实清单.json"
         and data["grader_reference_sha256"] == digest(ROOT / data["grader_reference"])
         and data["frozen_style_criteria_version"] == "2026-07-14-v1", "sealed fixture/reference/style criteria"); return data
def fact_lock(lock, run_id, fixture):
    need(lock["schema_version"] == 1 and lock["run_id"] == run_id and lock["frozen_before_style"] is True, f"lock {run_id}")
    bound = [{"locator": rel(fixture), "sha256": digest(fixture)}]; need(lock["source_bound"] == bound and lock["items"], f"bound {run_id}")
    ids = [item["stable_id"] for item in lock["items"]]
    need(all(isinstance(x, str) and x.strip() for x in ids) and len(ids) == len(set(ids)), f"IDs {run_id}")
    qkeys, allowed = {"numbers", "conditions", "scope", "negative_boundaries"}, {row["locator"] for row in bound}
    for item in lock["items"]:
        need(set(item) == {"stable_id", "type", "exact_proposition", "qualifiers", "terms_and_identifiers",
             "source_locator", "judgment_basis", "status"}, f"item fields {run_id}")
        need(item["type"] in {"事实", "判断", "推测", "未知"} and str(item["exact_proposition"]).strip(), f"item {run_id}")
        need(set(item["qualifiers"]) == qkeys, f"qualifiers {run_id}")
        for values in item["qualifiers"].values():
            need(isinstance(values, list) and values and all(isinstance(v, str) and v.strip() for v in values)
                 and (values == ["无"] or "无" not in values), f"qualifier values {run_id}")
        terms = item["terms_and_identifiers"]
        need(isinstance(terms, list) and terms and all(isinstance(v, str) and v.strip() for v in terms)
             and (terms == ["无"] or "无" not in terms), f"terms {run_id}")
        locator = str(item["source_locator"])
        need(any(locator == src or locator.startswith(src + ":") for src in allowed), f"locator {run_id}")
        if item["type"] == "判断":
            need(str(item["judgment_basis"]).strip() and str(item["status"]).strip(), f"judgment {run_id}")
        else: need(item["judgment_basis"] is None and item["status"] is None, f"non-judgment {run_id}")
def candidate(batch, expected, with_style):
    sealed, issues = manifest(batch, expected), 0; fixture = ROOT / sealed["fixture"]
    need(sorted(p.name for p in batch.glob("run-*") if p.is_dir()) == sealed["run_ids"], "unexpected run set")
    for run_id in sealed["run_ids"]:
        run = batch / run_id; document, pre, lock_path = run / "outputs/document.md", run / "pre-style.md", run / "fact-lock.json"
        for path in (document, pre, lock_path, run / "outputs/qa-summary.md", run / "outputs/transcript.md"):
            need(path.is_file() and path.stat().st_size, f"artifact {path}")
        grade = load(run / "grading.json")["expectations"]
        need([x["text"] for x in grade] == expected and len(grade) == len(expected)
             and all(set(x) == {"text", "passed", "evidence"} and x["passed"] is True and str(x["evidence"]).strip()
                     for x in grade), f"grading {run_id}")
        fact_lock(load(lock_path), run_id, fixture); check = load(run / "fact-check.json")
        fact_check_fields = {"run_id", "source_bound", "grader_reference", "fact_lock_sha256",
            "pre_style_sha256", "document_sha256", "lock_to_draft_mismatches",
            "draft_to_lock_mismatches", "mismatch_count"}
        need(set(check) == fact_check_fields, f"fact-check fields {run_id}")
        need(check["run_id"] == run_id and check["grader_reference"] == sealed["grader_reference"]
             and check["source_bound"] == [rel(fixture)]
             and check["fact_lock_sha256"] == digest(lock_path) and check["pre_style_sha256"] == digest(pre)
             and check["document_sha256"] == digest(document), f"fact hashes {run_id}")
        mismatch_fields = ("lock_to_draft_mismatches", "draft_to_lock_mismatches")
        need(all(isinstance(check[name], list) for name in mismatch_fields), f"mismatch types {run_id}")
        mismatches = sum(len(check[name]) for name in mismatch_fields)
        need(check["mismatch_count"] == mismatches == 0, f"mismatch {run_id}")
        if not with_style: continue
        review, validation = load(run / "style-review.json"), load(run / "style-validation.json"); findings = review["findings"]
        need(set(review) == {"run_id", "output_sha256", "criteria_version", "findings"}
             and set(validation) == {"run_id", "output_sha256", "validated_by_main", "accepted_findings", "validation_notes"}
             and review["run_id"] == run_id and review["output_sha256"] == digest(document)
             and review["criteria_version"] == "2026-07-14-v1"
             and all(set(x) == {"criterion", "exact_quote", "location", "reader_impact"} and x["criterion"] in CRITERIA
                     and all(str(v).strip() for v in x.values()) and x["exact_quote"] in document.read_text()
                     for x in findings), f"review {run_id}")
        need(validation["run_id"] == run_id and validation["output_sha256"] == digest(document)
             and validation["validated_by_main"] is True and all(x in findings for x in validation["accepted_findings"])
             and str(validation["validation_notes"]).strip(), f"validation {run_id}")
        issues += bool(validation["accepted_findings"])
    need(not with_style or issues <= 1, f"style issues: {issues}"); return sealed, issues
def formal(sealed):
    hashes = {name: digest(FORMAL / name) for name in TARGETS}
    need(sealed["candidate_sha256"] == hashes == {name: digest(CANDIDATE / name) for name in TARGETS}, "promotion hash")
    files = {p.relative_to(FORMAL) for p in FORMAL.rglob("*") if p.is_file()}
    copy = {p.relative_to(CANDIDATE) for p in CANDIDATE.rglob("*") if p.is_file()}
    need(files == copy and all((FORMAL / p).read_bytes() == (CANDIDATE / p).read_bytes() for p in files), "snapshot")
    text = (FORMAL / "SKILL.md").read_text()
    heading = "## 从零写（思考顺序 1→9；落笔顺序不同：先写最核心章节，标题、开头、摘要最后写）"
    need(text.count(heading) == 1 and "思考顺序 1→7" not in text, "title")
    refs = set(re.findall(r"references/[a-z-]+\.md", text))
    need(len(text.splitlines()) <= 150 and len(re.findall(r"^\| [1-7] \|", text, re.M)) == 7
         and refs == {"references/evidence-map.md", "references/narrative-patterns.md", "references/self-review.md"}, "structure")
    need("Skill is valid!" in command(["uv", "run", "--with", "pyyaml",
         "skills/skill-creator/scripts/quick_validate.py", "skills/professional-writing"]), "quick_validate")
    command(["git", "diff", "--check"]); tracked = sorted(command(["git", "diff", "--name-only", "HEAD", "--"]).splitlines())
    wanted = ["skills/professional-writing/SKILL.md", "skills/professional-writing/references/self-review.md"]
    need(tracked in ([], wanted), f"tracked scope: {tracked}")
    return {"candidate_matches_formal": True, "quick_validate_passed": True, "diff_check_passed": True,
            "tracked_scope": tracked, "skill_sha256": hashes["SKILL.md"],
            "self_review_sha256": hashes["references/self-review.md"]}
def regression(iteration, definitions):
    actual = {"with_skill": {}, "without_skill": {}}
    expected_dirs = {f"eval-{i}-{definitions[i]['name']}" for i in COUNTS}; need({p.name for p in iteration.glob("eval-*") if p.is_dir()} == expected_dirs, "eval directory set")
    for eval_id, wanted in COUNTS.items():
        dirs = list(iteration.glob(f"eval-{eval_id}-*")); need(len(dirs) == 1, f"eval {eval_id}"); definition = definitions[eval_id]
        need({p.name for p in dirs[0].iterdir() if p.is_dir()} == {"with_skill", "without_skill"}, f"config set {eval_id}")
        expected_meta = {"eval_id": eval_id, "eval_name": definition["name"], "prompt": definition["prompt"],
                         "assertions": definition["expectations"]}
        need(load(dirs[0] / "eval_metadata.json") == expected_meta, f"root metadata {eval_id}")
        for config in actual:
            root = dirs[0] / config; meta = load(root / "eval_metadata.json")
            need(sorted(p.name for p in root.glob("run-*") if p.is_dir()) == ["run-1"], f"run set {eval_id}/{config}")
            need(meta == expected_meta, f"metadata {eval_id}/{config}")
            out = root / "run-1/outputs"; names = {1: ("diagnosis.md", "rewritten.md", "qa-summary.md", "transcript.md"), 3: ("response.md", "transcript.md")}.get(eval_id, ("document.md", "qa-summary.md", "transcript.md"))
            need(all((out / name).is_file() and (out / name).stat().st_size for name in names) and bool(load(root / "run-1/timing.json")), f"run artifacts {eval_id}/{config}")
            rows = load(root / "run-1/grading.json")["expectations"]
            need(len(rows) == wanted and [x["text"] for x in rows] == definition["expectations"]
                 and all(set(x) == {"text", "passed", "evidence"} and x["passed"] is True
                         and str(x["evidence"]).strip() for x in rows), f"grading {eval_id}/{config}")
            actual[config][str(eval_id)] = len(rows)
    benchmark = load(iteration / "benchmark.json")
    note = f"{iteration.name} without_skill is old skill snapshot 77afd2d, not a no-skill baseline"
    need(benchmark["metadata"]["runs_per_configuration"] == 1 and note in benchmark["notes"]
         and (iteration / "benchmark.md").is_file(), "benchmark")
    viewer = iteration / "review.html"; viewer_hash = digest(viewer); review = load(iteration / "user-content-review.json")
    need(set(review) == {"schema_version", "viewer", "viewer_sha256", "accepted", "notes"}
         and review["schema_version"] == 1 and review["viewer"] == rel(viewer)
         and review["viewer_sha256"] == viewer_hash and review["accepted"] is True
         and str(review["notes"]).strip(), "user review")
    return {"metadata_files_found": 12, "grading_files_found": 12, "eval_count": 6,
            "assertions_per_configuration": sum(COUNTS.values()),
            "assertions_across_configurations": 2 * sum(COUNTS.values()), "actual_expectation_counts": actual,
            "viewer": rel(viewer), "viewer_sha256": viewer_hash,
            "user_content_review": rel(iteration / "user-content-review.json")}
def derive(phase, batch, iteration):
    definitions = {x["id"]: x for x in load(ROOT / "skills/professional-writing/evals/evals.json")["evals"]}
    counts = red(); sealed, issues = candidate(batch, definitions[6]["expectations"], LEVEL[phase] >= 2)
    if LEVEL[phase] < 3: return None
    checked_formal = formal(sealed)
    if phase != "full": return None
    result = regression(iteration, definitions)
    result.update({"new_skill_evals": list(COUNTS), "old_skill_evals": list(COUNTS),
        "new_all_structural_factual_assertions_passed": True, "old_all_structural_factual_assertions_passed": True,
        "eval_2_focus_passed": True, "eval_4_focus_passed": True, "user_content_checkpoint": "passed"})
    hard_total = len(sealed["run_ids"]) * len(sealed["hard_assertions"])
    return {"schema_version": 2, "spec_commit": "1a22ed30a49eeb6b4c1d1265cf5372a0b9d8874f",
        "iteration": iteration.name, "red": {"old_style_issue_documents": counts["old_skill"], "old_total": 5,
        "no_guidance_style_issue_documents": counts["no_guidance"], "no_guidance_total": 5, "reused": True},
        "candidate": {"batch_id": sealed["batch_id"], "files": TARGETS, "candidate_sha256": sealed["candidate_sha256"],
        "outputs": 5, "hard_assertions_passed": hard_total, "hard_assertions_total": hard_total, "fact_mismatch_count": 0,
        "style_reviewed_outputs": 5, "main_validations": 5, "accepted_issue_documents": issues,
        "style_issue_document_limit": 1, "passed": True}, "formal": checked_formal, "regression": result,
        "content_calibration_status": "passed"}
def main():
    p = argparse.ArgumentParser(); p.add_argument("--phase", choices=LEVEL, required=True); p.add_argument("--batch", required=True)
    p.add_argument("--iteration"); p.add_argument("--output"); a = p.parse_args()
    batch = (ROOT / a.batch).resolve(); iteration = (ROOT / a.iteration).resolve() if a.iteration else None
    try:
        need(a.phase != "full" or (iteration and a.output), "full requires iteration/output"); value = derive(a.phase, batch, iteration)
        if a.phase == "full": write((ROOT / a.output).resolve(), value)
        print(f"{a.phase} passed"); return 0
    except Exception as error:
        if a.output: write((ROOT / a.output).resolve(), {"schema_version": 2,
            "content_calibration_status": "failed", "error": f"{type(error).__name__}: {error}"})
        print(f"{a.phase} failed: {error}"); return 1
if __name__ == "__main__": raise SystemExit(main())
~~~

写入后先验证语法：

~~~bash
python3 -m py_compile skills/professional-writing-workspace/style-calibration/derive-content-status.py
~~~

Expected: 无输出，退出 0。

选择下一个不存在的 batch-N。初始流程示例使用 process-batches/batch-1；review remediation 必须按 Task 6B 选择下一空编号。batch-7 已失败并封存，当前下一空编号为 batch-8。以下生成命令就是 manifest 的唯一 schema：固定 candidate 两文件及其 SHA-256、run-1..5、eval-6 fixture 与 grader reference 的路径和字节 SHA-256、hard assertions、style criteria version，并在任何 run 前写入 sealed_before_runs=true。

先 fail-closed 创建 batch-1 和 manifest；三个命令必须分开执行，任一失败立即停止：

~~~bash
python3 -c "import pathlib;p=pathlib.Path('skills/professional-writing-workspace/style-calibration/process-batches/batch-1');assert not p.exists(),f'refuse existing batch: {p}';print('batch path is empty')"
~~~

Expected: 输出 batch path is empty，退出 0。

~~~bash
mkdir -p skills/professional-writing-workspace/style-calibration/process-batches/batch-1
~~~

Expected: 退出 0。

~~~bash
python3 - <<'PY'
import hashlib, json, pathlib
root = pathlib.Path("skills/professional-writing-workspace/style-calibration")
candidate = root / "process-candidate"
batch = root / "process-batches/batch-1"
evals = json.loads(pathlib.Path("skills/professional-writing/evals/evals.json").read_text())["evals"]
fixture = pathlib.Path("skills/professional-writing/evals/files/eval6-黑话密集专业材料.md")
grader_reference = pathlib.Path("skills/professional-writing/evals/files/eval6-风格压力事实清单.json")
manifest = {
    "schema_version": 1,
    "batch_id": "batch-1",
    "candidate_files": ["SKILL.md", "references/self-review.md"],
    "candidate_sha256": {
        name: hashlib.sha256((candidate / name).read_bytes()).hexdigest()
        for name in ("SKILL.md", "references/self-review.md")
    },
    "run_ids": [f"run-{n}" for n in range(1, 6)],
    "fixture": str(fixture),
    "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
    "grader_reference": str(grader_reference),
    "grader_reference_sha256": hashlib.sha256(grader_reference.read_bytes()).hexdigest(),
    "hard_assertions": next(x["expectations"] for x in evals if x["id"] == 6),
    "frozen_style_criteria_version": "2026-07-14-v1",
    "sealed_before_runs": True,
}
(batch / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print("sealed batch-1 manifest for run-1..run-5")
PY
~~~

Expected: 输出 sealed batch-1 manifest for run-1..run-5；manifest 在任何 run 启动前存在。

manifest 写完后不得改 candidate 或 manifest。五个 run 使用相互独立的 fresh context，同批预注册并按可用并发启动，均直接加载完整候选 skill；不得因先完成的结果替换后续 run。每个 run 分三段执行：fresh content author 只读取 eval-6 prompt、原材料与候选 skill，写事实锁和 pre-style 初稿；另一个不继承其历史的 fresh style subagent 只读取目标读者、pre-style 初稿、冻结事实锁、source bound 与候选阶段 B/C 指令，完成风格校准和事实复核；最后由 fresh hard grader 读取原材料、grader 专用事实清单和本 run artifacts，写 grading.json 与 fact-check.json。author 和 style subagent 都不得读取 grader 专用事实清单、旧 attempt、RED、其他 run、review 或 A/B 信息。每个 run 的 ignored artifact contract：

~~~text
process-batches/batch-1/run-N/
├── fact-lock.json
├── pre-style.md
├── outputs/
│   ├── document.md
│   ├── qa-summary.md
│   └── transcript.md
├── grading.json
└── fact-check.json
~~~

输出给读者的只有干净 document.md；qa-summary.md 只记录对话内质检摘要的评测副本，事实锁和 style report 不进入 document.md。fact-lock.json 与 pre-style.md 是证明流程执行的评测内部证据，不改变 runtime 默认不落盘合同。fact-lock.json schema：

~~~json
{
  "schema_version": 1,
  "run_id": "run-1",
  "source_bound": [
    {
      "locator": "skills/professional-writing/evals/files/eval6-黑话密集专业材料.md",
      "sha256": "b89bb1fc30768e8983bc25628c931f9aba1ce4b5116a92ff3efdac183a417f2e"
    }
  ],
  "frozen_before_style": true,
  "items": [
    {
      "stable_id": "F-01",
      "type": "事实",
      "exact_proposition": "2026-07-08 在 staging 以 1,000 rps 压测 PSG 时，p99 从 480 ms 降到 310 ms；生产尚未验证。",
      "qualifiers": {
        "numbers": ["2026-07-08", "1,000 rps", "480 ms", "310 ms"],
        "conditions": ["staging 环境压测"],
        "scope": ["PSG 承接的支付状态查询"],
        "negative_boundaries": ["生产环境尚未验证"]
      },
      "terms_and_identifiers": ["PSG", "p99", "staging"],
      "source_locator": "skills/professional-writing/evals/files/eval6-黑话密集专业材料.md:7",
      "judgment_basis": null,
      "status": null
    }
  ]
}
~~~

type 只能是事实/判断/推测/未知；同一锁内 stable_id 必须唯一。qualifiers 的 numbers/conditions/scope/negative_boundaries 四项都必须是非空字符串数组：有实际值就逐项记录，没有则精确写成 `["无"]`，不能留空或把“无”与实际值混用；terms_and_identifiers 同样至少记录实际值或 `["无"]`。判断项的 judgment_basis 与 status 必须为非空字符串，非判断项两字段必须为 null。source_locator 必须等于某个 source_bound locator 或在其后追加精确行号/章节定位，不能指向 pre-style.md 或 document.md。

grading.json 沿用 `skills/skill-creator/references/schemas.md` 的 canonical schema；其中 expectations 数组长度必须等于 manifest 中 hard_assertions 的长度（当前为 7），每项字段精确为 text/passed/evidence，text 与 eval-6 expectations 同序逐字相同，passed 为布尔值，evidence 是 document.md 中可定位的非空证据。summary、claims、timing 等 canonical 顶层字段可按 grader 实际结果保留，不作为本 micro gate 的额外通过条件。fact-check.json 字段合同：

| field | contract |
| --- | --- |
| run_id | 与目录名一致，如 run-1 |
| source_bound | 精确为只含 eval6-黑话密集专业材料.md 路径的数组 |
| grader_reference | 精确等于 manifest 的 `grader_reference`；其字节由 manifest 的 `grader_reference_sha256` 密封 |
| fact_lock_sha256 | grader 读取 fact-lock.json 原始字节后计算的 64 位 SHA-256 |
| pre_style_sha256 | grader 读取 pre-style.md 原始字节后计算的 64 位 SHA-256 |
| document_sha256 | grader 读取 outputs/document.md 原始字节后计算的 64 位 SHA-256 |
| lock_to_draft_mismatches | 锁内事实在成稿中的遗漏、弱化、扩大、缩小或改变；黑话动词变得更具体/更强，主体、对象、责任范围/强度变化，以及证据关系、认识状态、极性或强度变化均计入；通过时为空数组 |
| draft_to_lock_mismatches | 成稿新增的锁外事实或判断；未定义黑话被增强成具体职责命题也计入；通过时为空数组 |
| mismatch_count | 两个 mismatch 数组长度之和；通过时为 0 |

上表精确为 9 个既有字段。派生器必须先校验 `set(check)` 与这 9 个字段完全相等，再校验两个 mismatch 值均为 list，最后才能计算长度；不得接受多余顶层字段，也不得为黑话或判断语义分类增加新字段。分类结果只进入现有两个 mismatch 数组及其计数。

先验收 35/35、0 mismatch，以及 candidate、fixture、grader reference 的 sealed hash；统一调用派生器，不复制第二套 schema：

~~~bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase hard \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-1
~~~

Expected: 输出 hard passed，退出 0。

任一 run 缺失、任一 assertion 失败、任一 mismatch 非零，立即拒绝整个 batch-1；不得在 batch-1 内补跑或替换。修订候选 wording 后使用下一个空 batch-N，重新生成恰好 5 份 fresh 输出。

- [ ] **Step 4: 对同 5 份输出做 fresh style review，并由主 agent 核验 finding**

只有 Step 3 通过后才开始；不得重新生成 document.md。为 run-1..5 各创建一个相互独立的 fresh reviewer，只给原材料、eval prompt、该 run 的 document.md 和下列冻结定义，不给 candidate/baseline 身份、其他输出、历史 finding 或 A/B 结果：

| criterion | frozen definition |
| --- | --- |
| unexplained_abbreviation | 非通用缩写或项目内简称在读者可见的首次出现处没有解释，标题也算首次出现；精确标准术语或标识符不因形式简短而自动算问题 |
| empty_management_phrase | 表述无法说明具体主体、动作和结果，也没有可核验依据；已有明确主体、动作、结果或依据时，不因措辞抽象自动判定 |
| repeated_proposition | 同一完整命题在多个位置重复，且后一次没有不同读者功能；摘要与详情存在概览和证据展开等不同功能时不计 |
| overloaded_sentence | 一句话承载多个可独立成立的主要判断或动作，导致读者必须拆句才能确定关系；准确表达所需的因果、条件或范围边界与主判断同句时不计 |

reviewer 输出 run-N/style-review.json，顶层字段精确为 run_id/output_sha256/criteria_version/findings；run_id 对应该目录，output_sha256 是同目录 outputs/document.md 的 SHA-256，criteria_version 固定为 2026-07-14-v1。findings 为数组；每条字段精确为 criterion/exact_quote/location/reader_impact，四个值都非空，criterion 只能取上表四项。无 finding 时 findings 为空数组。

主 agent 逐条核对 exact_quote 是否逐字存在、location 是否准确、criterion 是否命中冻结定义、reader_impact 是否具体；只把通过核验的 finding 原样写入 run-N/style-validation.json。该文件顶层字段精确为 run_id/output_sha256/validated_by_main/accepted_findings/validation_notes；run_id 与 hash 必须和 review 相同，validated_by_main 固定为 true，accepted_findings 必须是 review findings 的子集，validation_notes 非空。

计数按 issue-document union：同一文档命中多个 criterion 仍只计 1，不按 finding 总数计。复用 Step 3 的派生器验证五份 review 绑定同五份输出，且 accepted issue-document union <=1/5：

~~~bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase style \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-1
~~~

Expected: 输出 style passed，退出 0。

任一 review/validation 缺失、hash 不符、finding 字段不是 criterion/exact_quote/location/reader_impact、主 agent 未签字或 union >1/5，候选失败并保持正式 skill 不变。A/B 可在此后匿名运行以定位差异，但不设置胜率阈值、不替代失败样本、不写入内容状态。

- [ ] **Step 5: 把通过门槛的候选原样提升到正式两文件并验证**

用 apply_patch 将候选 wording 精确应用到：

- skills/professional-writing/SKILL.md
- skills/professional-writing/references/self-review.md

不修改 description、narrative-patterns.md、evidence-map.md、evals 或其他文件。复用同一派生器验证 manifest/candidate/formal hash、完整快照、精确 1→9 标题、quick_validate、git diff --check 与 tracked scope：

~~~bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase promotion \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-1
~~~

Expected: 输出 promotion passed，退出 0；任一检查失败时非零退出。

任一检查失败时不进入 iteration-4；用 apply_patch 恢复正式两文件的 pre-promotion 内容，再修订候选并以新固定批次重新跑 Step 3-5。

- [ ] **Step 6: 在下一空 iteration-4 运行 eval-1..6 new/old 全量回归并生成 viewer**

先证明 iteration-4 尚不存在，再创建目录；已存在但不为空时停止，不覆盖旧证据：

~~~bash
python3 -c "import pathlib;p=pathlib.Path('skills/professional-writing-workspace/iteration-4');assert not p.exists(),f'refuse existing iteration: {p}';print('iteration-4 path is empty')"
~~~

Expected: 输出 iteration-4 path is empty，退出 0；目录已存在时非零退出，不执行创建。

~~~bash
mkdir -p skills/professional-writing-workspace/iteration-4
~~~

Expected: 退出 0。

六个 eval 目录精确为：

- skills/professional-writing-workspace/iteration-4/eval-1-rewrite-summary/
- skills/professional-writing-workspace/iteration-4/eval-2-write-decision-doc/
- skills/professional-writing-workspace/iteration-4/eval-3-insufficient-material/
- skills/professional-writing-workspace/iteration-4/eval-4-write-explainer-article/
- skills/professional-writing-workspace/iteration-4/eval-5-write-tutorial/
- skills/professional-writing-workspace/iteration-4/eval-6-rewrite-style-pressure/

每个目录下 with_skill/run-1 使用刚提升的正式 skill，without_skill/run-1 使用 old-skill-77afd2d。每个 run 都是 fresh context；同一 eval 的 new/old 同批启动。eval metadata 的 assertions 逐字复制 evals.json 对应 expectations，expectation 数固定为 `4/6/3/3/6/7`：单配置 29 条，两配置共 58 条。

运行产物保持读者输出干净：

~~~text
iteration-4/eval-N-name/
├── eval_metadata.json
├── with_skill/
│   ├── eval_metadata.json
│   └── run-1/
│       ├── outputs/diagnosis.md + rewritten.md（仅 eval-1）
│       ├── outputs/response.md（仅 eval-3）
│       ├── outputs/document.md（eval-2/4/5/6）
│       ├── outputs/qa-summary.md（eval-1/2/4/5/6）
│       ├── outputs/transcript.md
│       ├── timing.json
│       └── grading.json
└── without_skill/（同结构）
~~~

全量硬门：

- new 与 old 的 eval-1..6 结构/事实 assertions 都逐项通过；任何单项失败都不能用总通过率掩盖。
- eval-2 重点检查证据完整性、未证实信息与治理控制边界；eval-4 重点检查技术精度、反例/边界和关键断言依据。
- eval-2/4 是重点复核，不替代 eval-1、eval-3、eval-5、eval-6；六个用例都必须通过。
- eval-6 的事实、数值、条件、范围边界继续 0 mismatch。
- A/B 若运行，只作为 comparison 诊断附件；tie、loss 或 win 均不改变 gate。

逐 run 完成 grading 后聚合：

~~~bash
python3 -c "import subprocess;subprocess.run(['python','-m','scripts.aggregate_benchmark','../professional-writing-workspace/iteration-4','--skill-name','professional-writing'],cwd='skills/skill-creator',check=True)"
~~~

Expected: 退出 0，iteration-4/benchmark.json 与 benchmark.md 生成。

aggregate 固定写 runs_per_configuration=3，必须复用 Task 6 的归一化方式改为真实的 1，追加固定 old-skill baseline note，并从同一 JSON 重生 Markdown：

~~~bash
python3 - <<'PY'
import json, pathlib, sys
sys.path.insert(0, "skills/skill-creator")
from scripts.aggregate_benchmark import generate_markdown
p = pathlib.Path("skills/professional-writing-workspace/iteration-4/benchmark.json")
d = json.loads(p.read_text())
note = "iteration-4 without_skill is old skill snapshot 77afd2d, not a no-skill baseline"
d["metadata"]["runs_per_configuration"] = 1
if note not in d.setdefault("notes", []):
    d["notes"].append(note)
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
p.with_suffix(".md").write_text(generate_markdown(d))
print("normalized iteration-4 benchmark: runs=1, baseline=old 77afd2d")
PY
~~~

Expected: 输出 normalized iteration-4 benchmark: runs=1, baseline=old 77afd2d；benchmark.json 的 runs_per_configuration=1，notes 含固定 old-skill 说明，benchmark.md 由该 JSON 重生。

生成 viewer：

~~~bash
python skills/skill-creator/eval-viewer/generate_review.py \
  skills/professional-writing-workspace/iteration-4 \
  --skill-name professional-writing \
  --benchmark skills/professional-writing-workspace/iteration-4/benchmark.json \
  --previous-workspace skills/professional-writing-workspace/iteration-3 \
  --static skills/professional-writing-workspace/iteration-4/review.html
~~~

Expected: review.html 存在并包含 eval-1..6 的 new/old 成稿与 grading。若任一 artifact、assertion 或必要 metadata 缺失，将 content-calibration-status.json 写为 failed，停止，不运行 Task 7。

- [ ] **Step 7: 【停——用户内容检查点】创建唯一 status 派生器，确认后派生 passed**

请用户查看 skills/professional-writing-workspace/iteration-4/review.html，重点判断成稿是否简洁、专业、清楚、易懂，是否为缩短而删除事实、条件或边界，以及 eval-2 的证据完整性、eval-4 的技术精度。A/B 诊断附件可辅助定位，但不要求胜出，也不进入派生器或通过条件。

用户未明确接受时，不创建 accepted review，content_calibration_status 必须保持 failed，Task 7 继续 blocked。用户明确接受后，创建独立的 user-content-review.json；viewer hash 必须在写入时计算，不手填：

~~~bash
python3 - <<'PY'
import hashlib, json, pathlib
viewer = pathlib.Path("skills/professional-writing-workspace/iteration-4/review.html")
review = {
    "schema_version": 1,
    "viewer": str(viewer),
    "viewer_sha256": hashlib.sha256(viewer.read_bytes()).hexdigest(),
    "accepted": True,
    "notes": "用户已审阅 iteration-4 viewer，并明确接受当前内容结果。",
}
path = viewer.parent / "user-content-review.json"
path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
print("recorded accepted user content review")
PY
~~~

Expected: 输出 recorded accepted user content review；user-content-review.json 与当前 viewer hash 绑定。用户没有明确接受时不得运行。

复用 Step 3 已创建并通过 py_compile 的 derive-content-status.py；这里不复制第二套 schema 或校验逻辑。

再从原始 artifacts 派生 status：

~~~bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase full \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-1 \
  --iteration skills/professional-writing-workspace/iteration-4 \
  --output skills/professional-writing-workspace/iteration-4/content-calibration-status.json
~~~

Expected: 输出 full passed，退出 0。status 由 10 份 RED validation、manifest 与当前 candidate hashes、固定 5 份 grading/fact-check/fact-lock、同 5 份 style review/main validation、12 份 iteration metadata/grading、normalized benchmark、viewer、user-content-review、quick_validate、git diff --check 和 tracked scope 直接派生；字段统一使用 hard_assertions_total。任一原始 artifact、hash、schema、命令或用户接受证据缺失时，覆盖写入 schema v2 failed status 并非零退出。

状态通过后只提交正式两文件：

~~~bash
git add skills/professional-writing/SKILL.md skills/professional-writing/references/self-review.md
git commit -m "fix(professional-writing): 隔离文风校准与事实复核

将内容初稿、事实锁、独立风格校准和双向事实复核拆成明确阶段，
避免为改善表达而丢失数值、条件、范围边界或判断状态。

验证：eval-6 固定批次 5 份通过 35/35 hard assertions 且 0 mismatch；
四项 style control 的 accepted issue-document union <=1/5；
iteration-4 eval-1..6 new/old 结构与事实断言全过，用户内容检查点通过；
quick_validate 与 git diff --check 通过。

Co-authored-by: OpenAI Codex <noreply@openai.com>"
~~~

Expected: commit 只包含 skills/professional-writing/SKILL.md 与 skills/professional-writing/references/self-review.md；ignored workspace 不入 commit。

---

### Task 6B: Batch 8 旧流程（已被 Task 6C 取代，不执行）

> Batch 8 manifest 已按本节旧 5-run 合同密封，但流程未完成。保持 Batch 8 所有现存字节不变，不补 run、不改 manifest、不执行本节派生或放行命令。

**Files:**
- Read committed eval contract: `skills/professional-writing/evals/evals.json`
- Read committed fixtures: `skills/professional-writing/evals/files/eval5-操作过程记录.md`、`skills/professional-writing/evals/files/eval6-黑话密集专业材料.md`、`skills/professional-writing/evals/files/eval6-风格压力事实清单.json`
- Modify in ignored workspace: `skills/professional-writing-workspace/style-calibration/process-candidate/evals/`（只同步本任务已提交的 eval 合同字节）
- Modify in ignored workspace: `skills/professional-writing-workspace/style-calibration/derive-content-status.py`（精确同步 Task 6A 中的新 COUNTS、密封与派生逻辑）
- Modify tracked runtime: `skills/professional-writing/SKILL.md`、`skills/professional-writing/references/self-review.md`（只包含 Batch 7 失败导出的缩写首现与黑话未知五维加固）
- Create in ignored workspace: `skills/professional-writing-workspace/style-calibration/process-batches/batch-8/`
- Create in ignored workspace: `skills/professional-writing-workspace/iteration-7/`

**Interfaces:**
- Consumes: approved spec commit `1a22ed30a49eeb6b4c1d1265cf5372a0b9d8874f`；Task 5 已提交的 eval-5 六条、eval-6 七条与 U1 fixture；Batch 7 失败证据；本任务中已复审并提交的当前正式 runtime；固定 old-skill-77afd2d；既有 RED 5/5 与 3/5。
- Preserves: sealed `process-batches/batch-6/`、失败的 `process-batches/batch-7/` 与 `iteration-6/` 的所有字节。batch-7 只作为 5/7、1 mismatch 的失败证据；不得补跑、替换、修改或用作通过证据。iteration-6 的用户接受不得复制给新 iteration。
- Produces: batch-8 五份 fresh author/style/grader 证据、iteration-7 十二份 fresh new/old 回归、按新 viewer 重新取得的用户接受，以及新 schema v2 passed status。

**Hard gates:**
- batch-8：5 个 fresh run × 7 条 = `35/35`，`0 mismatch`，且 accepted style issue documents `<=1/5`。
- iteration-7：6 个 eval × 2 个配置 = 12 个 fresh run；每配置 `29/29`，两配置共 `58/58`；metadata/grading 文件各 12 份。
- runtime 文件范围仍只是 `SKILL.md` 与 `self-review.md`；必须在创建 batch-8 前与本 plan/spec 同步提交。Task 5 的 eval 合同/fixture 不再变更；batch-8 运行阶段不得再产生 tracked diff，workspace 继续忽略。

- [ ] **Step 1: fail-closed 封存 Batch 7 失败证据并确认下一空编号**

以下命令只读；必须证明 batch-7 已因 run-2 的 5/7 与 1 mismatch 失败，batch-8 尚不存在；iteration 最大编号仍为 6，因此下一空编号仍是 7。任一断言失败时停止，绝不覆盖已有目录：

```bash
python3 - <<'PY'
import json, pathlib, re
batch_root = pathlib.Path("skills/professional-writing-workspace/style-calibration/process-batches")
iteration_root = pathlib.Path("skills/professional-writing-workspace")
batches = sorted(int(re.fullmatch(r"batch-(\d+)", p.name).group(1)) for p in batch_root.glob("batch-*") if re.fullmatch(r"batch-(\d+)", p.name))
iterations = sorted(int(re.fullmatch(r"iteration-(\d+)", p.name).group(1)) for p in iteration_root.glob("iteration-*") if re.fullmatch(r"iteration-(\d+)", p.name))
assert batches and batches[-1] == 7 and (batch_root / "batch-7").is_dir(), batches
assert not (batch_root / "batch-8").exists(), batches
assert iterations and iterations[-1] == 6 and not (iteration_root / "iteration-7").exists(), iterations
assert (batch_root / "batch-6/manifest.json").is_file()
grade = json.loads((batch_root / "batch-7/run-2/grading.json").read_text())
fact = json.loads((batch_root / "batch-7/run-2/fact-check.json").read_text())
assert grade["summary"] == {"passed": 5, "failed": 2, "total": 7, "pass_rate": 5 / 7}
assert fact["mismatch_count"] == 1
assert (iteration_root / "iteration-6/content-calibration-status.json").is_file()
print("sealed failed batch=batch-7; next empty batch=batch-8; next empty iteration=iteration-7")
PY
```

Expected: 只输出 `sealed failed batch=batch-7; next empty batch=batch-8; next empty iteration=iteration-7`。从此不对 batch-6/batch-7/iteration-6 执行任何写命令。

- [ ] **Step 2: 提交已复审 runtime 修订，再同步候选快照与唯一派生器**

先单独提交已复审 spec，将新的 approved spec commit 写入本 plan 和状态派生合同后单独提交 plan；再提交 `SKILL.md` 与 `references/self-review.md`，这个 runtime 提交必须同时包含黑话未知五维事实锁、缩写首现顺序复核及阶段 C mismatch 门。三步提交完成后，把当前正式 skill 全部文件逐字同步到 ignored `process-candidate/`；Task 5 的 eval 合同与 fixture 保持已提交字节，不再修改。从候选快照完成后起，不得再修改候选或正式 runtime；如需再改，废弃 batch-8 并使用下一空 batch。

随后用 apply_patch 把 ignored `derive-content-status.py` 精确同步为 Task 6A 嵌入版本，并运行：

```bash
python3 -m py_compile skills/professional-writing-workspace/style-calibration/derive-content-status.py
```

```bash
python3 - <<'PY'
import pathlib
formal = pathlib.Path("skills/professional-writing")
candidate = pathlib.Path("skills/professional-writing-workspace/style-calibration/process-candidate")
formal_files = {p.relative_to(formal) for p in formal.rglob("*") if p.is_file()}
candidate_files = {p.relative_to(candidate) for p in candidate.rglob("*") if p.is_file()}
assert formal_files == candidate_files
changed = [str(p) for p in formal_files if (formal / p).read_bytes() != (candidate / p).read_bytes()]
assert changed == [], changed
print("review-remediation candidate matches formal skill byte-for-byte")
PY
```

Expected: py_compile 无输出；快照检查输出 `review-remediation candidate matches formal skill byte-for-byte`。这一步只更新 ignored workspace，不制造新的 runtime delta。

- [ ] **Step 3: 密封 batch-8 并生成 5 份 fresh author/style/grader run**

按 Task 6A manifest schema 创建 `batch-8/manifest.json`，在任何 run 前同时密封：candidate 两目标文件 SHA-256、`fixture_sha256`、`grader_reference`、`grader_reference_sha256`、7 条 hard assertions、run-1..5 和四项 style criteria version。manifest 写入后不得修改。

五个 run 沿用 Task 6A 的隔离与 artifact 合同：fresh author 只看 eval prompt、源材料与候选 skill；fresh style subagent 只看目标读者、pre-style、冻结事实锁、冻结 `source bound` 与阶段 B/C 标准；fresh grader 读取源材料、manifest 绑定的 grader reference 与本 run artifacts。author/style 不得读取 grader reference、旧结果或其他 run。

每个 `fact-check.json` 保持既有字段集合，并把以下语义计入两个 mismatch 数组：黑话动词更具体/更强；主体、对象、责任范围/强度变化；证据关系、认识状态、极性或强度变化；未定义 U1 被增强为具体职责。不得为这些分类新增 fact-check 顶层字段。

```bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase hard \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-8
```

Expected: `hard passed`；5 份 grading 各 7 条，总计 `35/35`，0 mismatch，fixture/reference/candidate hash 全部匹配 manifest。任一失败废弃整个 batch-8；不得补跑或替换 run。

- [ ] **Step 4: 复用同 5 份 document 做 fresh style review**

严格复用 Task 6A 的四项 criterion、review schema、主 agent validation 和 issue-document union 计数，不重新生成 document：

```bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase style \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-8
```

Expected: `style passed`，accepted issue documents `<=1/5`。A/B 仍仅诊断。

- [ ] **Step 5: 在 iteration-7 fresh 重跑 eval-1..6 的 new/old 两组**

创建 iteration-7 后，按 Task 6A 的目录与 output contract 运行 12 个 fresh context；with_skill 使用当前正式 skill，without_skill 使用 old-skill-77afd2d。metadata assertions 必须逐字来自已提交 evals.json，计数精确为 `4/6/3/3/6/7`。逐项 grading 全过后，聚合 benchmark，把 runs_per_configuration 归一为 1，并加入精确 note：

```text
iteration-7 without_skill is old skill snapshot 77afd2d, not a no-skill baseline
```

生成新 viewer，previous workspace 只用于对照显示：

```bash
python skills/skill-creator/eval-viewer/generate_review.py \
  skills/professional-writing-workspace/iteration-7 \
  --skill-name professional-writing \
  --benchmark skills/professional-writing-workspace/iteration-7/benchmark.json \
  --previous-workspace skills/professional-writing-workspace/iteration-6 \
  --static skills/professional-writing-workspace/iteration-7/review.html
```

Expected: eval 数 6，metadata/grading 各 12，单配置 `29/29`，new/old 合计 `58/58`；review.html 展示本轮 12 份 fresh 结果。

- [ ] **Step 6: 【停——用户内容检查点】只接受 iteration-7 新 viewer**

用户必须重新审阅 iteration-7/review.html，并明确接受本轮内容。新 `user-content-review.json` 的 viewer 路径与 SHA-256 必须绑定 iteration-7 当前文件；不得复制 iteration-6 的 review、notes 或 hash。未明确接受时，iteration-7 status 保持 failed 或不存在，Task 7 继续 blocked。

接受后派生新状态：

```bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase full \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-8 \
  --iteration skills/professional-writing-workspace/iteration-7 \
  --output skills/professional-writing-workspace/iteration-7/content-calibration-status.json
```

Expected: `full passed`；status 的 spec_commit 为批准 SHA，candidate hard total 为 35，regression 记录 29/58、6 个 eval、12 份 metadata/grading 与 iteration-7 新用户接受证据。只有此状态可解锁 Task 7。

---

### Task 6C: 工程实用版内容评测（已失败，历史只读）

> 2026-07-15 实际结果为 7 份文档 `33/36`：Batch 9 eval-6 `13/14`，iteration-7 smoke `20/22`；五份文档合计 10 mismatch，eval-6 accepted style issue documents `1/2`。Batch 9 与 iteration-7 自此封存，不补跑、不替换、不修改，也不生成 viewer。当前活动路径改为 Task 6D。

**Files:**
- Read only: `skills/professional-writing/SKILL.md`、`skills/professional-writing/references/self-review.md`、`skills/professional-writing/evals/evals.json` 与既有 fixtures。
- Modify in ignored workspace: `skills/professional-writing-workspace/style-calibration/derive-content-status.py`。
- Create in ignored workspace: `skills/professional-writing-workspace/style-calibration/process-batches/batch-9/`。
- Create in ignored workspace: `skills/professional-writing-workspace/iteration-7/`。

**Interfaces:**
- Consumes: approved spec commit `06e3906017154fb094878a478a13e380c7c42bd3`；当前正式 skill；eval-1..6 的已提交 prompts/assertions/fixtures；冻结四项 style criteria。
- Preserves: Batch 6、Batch 7、Batch 8、iteration-6 的所有字节，以及 tracked runtime、self-review、evals.json、fixtures。Batch 8 manifest SHA-256 必须保持 `d544a3953b3c14b4f97c96fd9391a9725decff0deb83c0b5eefd8f4d76fb55f1`。
- Produces: Batch 9 两份 eval-6 成稿和独立 grader 证据；iteration-7 五份 smoke 成稿和 grading；只含这 7 份文档的静态 viewer。

**Hard gates:**
- Batch 9：2 个 fresh run × 7 条 = `14/14`；每份 `0 mismatch`；accepted style issue documents = `0/2`。
- iteration-7 smoke：eval-1..5 各 1 个 current-skill run，断言数 `4/6/3/3/6`，合计 `22/22`。
- 总计：7 份文档、`36/36`；所有事实检查 `0 mismatch`。任一门失败立即停止，不补跑、不替换样本、不修改 runtime/evals/fixtures。

- [ ] **Step 1: 只读复核封存现场与空编号**

确认 branch/HEAD/clean 状态；重新计算 Batch 8 三个现存文件哈希；确认 Batch 9 与 iteration-7 不存在。任何值与交接快照或本计划不一致时停止。此后不对 Batch 6、Batch 7、Batch 8、iteration-6 执行写操作。

- [ ] **Step 2: 同步唯一派生器并做 fail-closed 自检**

用 `apply_patch` 更新 ignored `derive-content-status.py`，只支持本合同的 `hard`、`style`、`smoke`、`viewer` 四个 phase：

- 绑定 spec commit `06e3906017154fb094878a478a13e380c7c42bd3`，不得继续接受旧 spec SHA；
- `hard` 只接受 Batch 9 的 `run-1/run-2`、现有 7 条 assertions、`14/14` 与两份 `0 mismatch`；
- `style` 要求两份 validation 均由主 agent 核验，accepted issue documents 精确为 `0`；
- `smoke` 只接受 eval-1..5 的 current-skill `run-1`，断言合计 `22/22`，拒绝 old-skill/no-guidance 配置；
- `viewer` 复核 7 个展示项，其中两个 eval-6 项必须绑定 Batch 9 两份 document 的绝对来源路径与 SHA-256；不得读取或生成用户接受文件，也不得输出 passed full status。

运行 `python3 -m py_compile`；在 Batch 9 尚不存在时运行 `--phase hard` 必须 fail closed。不得复制 Task 6A/6B 的旧计数、RED、promotion、full 或 trigger 解锁逻辑。

- [ ] **Step 3: 创建并密封 Batch 9 manifest**

manifest 使用 schema version 1 和 `run_ids = ["run-1", "run-2"]`，并在任何 author run 前写入以下当前字节哈希：

- `SKILL.md`: `c0b320e354a9f3e908b251b608d5210399feb806390be1d16c641e0a46727706`
- `references/self-review.md`: `3e4150d989ce99bb0f1db6fc015525a48de233b888f965aac9cb4d6577db1e44`
- eval-6 fixture: `b89bb1fc30768e8983bc25628c931f9aba1ce4b5116a92ff3efdac183a417f2e`
- grader reference: `05e13655224bcffb0da9436e174e88ecfde1a9ea934d18cc53e865ac5d55eeac`

`hard_assertions` 精确复制 evals.json 的 eval-6 七条 expectations；`frozen_style_criteria_version` 保持 `2026-07-14-v1`；`sealed_before_runs` 为 true。manifest 写入后立即计算 SHA-256，此后不得修改。

- [ ] **Step 4: 同批派发两位 fresh author**

最多同时使用三位子代理：

- Author A：只读当前正式 skill、eval-6 prompt/fixture，生成 Batch 9 run-1；完成后继续生成 eval-1、eval-2、eval-3 smoke。
- Author B：只读当前正式 skill、eval-6 prompt/fixture，生成 Batch 9 run-2；完成后继续生成 eval-4、eval-5 smoke。
- Blind grader：不参与写作；两位 author 完成后统一检查两份 eval-6 与五份 smoke。

两位 author 不得读取 grader reference、其他 author 输出、Batch 7/8 成稿或 iteration-6 输出。eval-6 每份保留 `fact-lock.json`、`pre-style.md`、成稿、qa summary 与 transcript；smoke 输出按既有 eval output contract 落在 iteration-7。作者只生成内容与过程证据，不自行评分。

- [ ] **Step 5: 独立 grader 验收全部 36 条断言**

Blind grader 读取冻结 grader reference、对应输入与七份输出，为每个 run 生成精确 schema 的 `grading.json`；对 eval-6 另生成 `fact-check.json`、`style-review.json`。主 agent 逐条核验 style finding 的引用、位置、判据与读者影响后生成 `style-validation.json`，且必须不接受任何 finding。

依次运行派生器 `hard`、`style`、`smoke`。预期分别为 `14/14 + 0 mismatch`、`0/2`、`22/22`；任一失败按停止条件退出，不进入 viewer。

- [ ] **Step 6: 生成 7 文档 iteration-7 viewer 并停止**

iteration-7 viewer 数据只包含 eval-1..5 各一份 current-skill 输出，以及 Batch 9 run-1/run-2 两份 eval-6 输出。eval-6 通过 source path + SHA-256 绑定复用，不生成第三份成稿；viewer 不显示 old-skill/no-guidance/iteration-6 对照。

使用 `skills/skill-creator/eval-viewer/generate_review.py --static` 生成 `skills/professional-writing-workspace/iteration-7/review.html`。运行派生器 `viewer` 和 `quick_validate.py`，再执行 `git diff --check`、tracked scope 检查与 Batch 8 哈希复核。viewer 通过后立即停止并把绝对路径交给用户；用户明确接受前不生成 `content-calibration-status.json` 的 passed full 状态。

---

### Task 6D: 结构化拒绝门与 Batch 10（已失败，历史只读）

> 实际结果为 `35/36`、6 mismatch：Batch 10 eval-6 为 `14/14`，但 run-1 有 3 mismatch；iteration-8 smoke 为 `21/22`，eval-4 有 3 mismatch。两份 raw style review 均无 finding，但事实硬门未通过，因此未生成 style-validation 或 viewer。Batch 10 与 iteration-8 自此封存，当前活动路径改为 Task 6E。

**Files:**
- Modify tracked runtime: `skills/professional-writing/SKILL.md`、`skills/professional-writing/references/self-review.md`。
- Modify in ignored workspace: `skills/professional-writing-workspace/style-calibration/derive-content-status.py`。
- Create in ignored workspace: `skills/professional-writing-workspace/style-calibration/process-batches/batch-10/`。
- Create in ignored workspace: `skills/professional-writing-workspace/iteration-8/`。

**Interfaces:**
- Consumes: approved spec commit `ff731925d99dcd44dec1bba151aec61bbfe1b707`；Batch 9 的已封存 RED；当前正式 skill；eval-1..6 已提交 prompts/assertions/fixtures；冻结四项 style criteria。
- Preserves: Batch 6 至 Batch 9、iteration-6/7 的所有字节，以及 description、evals.json、fixtures、grader reference。Batch 9 manifest SHA-256 保持 `03c579ccb8c040a45ad543e6901f02feb5e3277283852e8dacbdff698f413de4`。
- Produces: 四槽结构化拒绝门 runtime；Batch 10 两份 eval-6 成稿和独立 grader 证据；iteration-8 五份 smoke 成稿和 grading；只含这 7 份文档的静态 viewer。

**Hard gates:**
- Batch 10：2 个 fresh run × 7 条 = `14/14`；每份 `0 mismatch`；accepted style issue documents = `0/2`。
- iteration-8 smoke：eval-1..5 各 1 个 current-skill run，断言数 `4/6/3/3/6`，合计 `22/22`；每份 `0 mismatch`。
- 总计：7 份文档、`36/36`；所有事实检查 `0 mismatch`。任一门失败立即停止，不补跑、不替换样本、不在同一批次修改 runtime/evals/fixtures。

- [ ] **Step 1: 只读复核封存现场与 RED 映射**

确认 branch、HEAD、clean tracked 状态；复核 Batch 9 manifest SHA-256 与 `33/36`、10 mismatch、style issue documents `1/2`；确认 Batch 10 与 iteration-8 不存在。把失败映射为四个结构槽：重写判词 1..7 全扫描、成稿反向主张追溯、缩写首次可见位置、教程状态转换表。任何历史字节或计数不符时停止。

- [ ] **Step 2: 先提交 spec 与 plan**

spec 已作为 `ff731925d99dcd44dec1bba151aec61bbfe1b707` 单独提交。plan 绑定该完整 SHA 后单独提交；两个提交都必须有说明原因与验证结果的 body，以及 `Co-authored-by: OpenAI Codex <noreply@openai.com>` trailer。runtime 修改不得混入这两个提交。

- [ ] **Step 3: 以 Batch 9 为 RED 实现最小 runtime 修订**

只用 `apply_patch` 修改两个运行时文件：

- 重写模式起草诊断前，内部逐项记录判词 1..7 的命中位置或未命中；交付只输出命中项。
- 阶段 C 设置正向事实、反向主张、可见顺序缩写、类型专项四个必填槽位。反向主张槽逐句追溯新增或改写的主体、动作、对象、因果、职责、范围和强度关系；无 source locator 且未标判断/推测即 mismatch。
- 教程起草前逐个关键转换填写“前态 → 必要动作 → 后态 → 验证证据”；未知动作必须在正文成为待确认步骤或阻塞项。
- 质检摘要不得用笼统声明替代槽位；任一适用槽位未完成或失败时，不得声明 `0 mismatch`。

不修改 description、evals.json、fixtures、grader reference，不新增 runtime 文件。运行 `quick_validate.py`、`git diff --check`，复核 diff 只含这两个文件，然后单独提交 runtime。

- [ ] **Step 4: 同步候选与唯一派生器**

取得 runtime 提交后，逐字同步正式 skill 到 ignored `process-candidate/`，重新计算 candidate、eval-6 fixture 与 grader reference 哈希。用 `apply_patch` 更新唯一 `derive-content-status.py`：绑定 spec commit `ff731925d99dcd44dec1bba151aec61bbfe1b707`，只接受 Batch 10 的 `run-1/run-2` 与 iteration-8 的 eval-1..5 current-skill run；保留 `hard/style/smoke/viewer` 四个 phase 和原 14/14、0/2、22/22、36/36 门。运行 `python3 -m py_compile`，并在 Batch 10 尚不存在时确认 `--phase hard` fail closed。

- [ ] **Step 5: 创建并密封 Batch 10 manifest**

manifest 使用既有 schema version 1，`run_ids = ["run-1", "run-2"]`，硬断言逐字复制 evals.json 的 eval-6 七条 expectations；写入当前 candidate、fixture、grader reference 哈希和 `frozen_style_criteria_version = "2026-07-14-v1"`，设置 `sealed_before_runs = true`。manifest 写入后立即记录 SHA-256，此后不得修改。

- [ ] **Step 6: 派发两个 fresh author 与一个 blind grader**

最多使用三位子代理：Author A 生成 Batch 10 run-1，随后生成 eval-1..3 smoke；Author B 生成 Batch 10 run-2，随后生成 eval-4..5 smoke；Blind grader 不参与写作，在七份文档完成后统一检查硬断言、双向 fact-check 与 eval-6 四项 style review。两位 author 不得读取 grader reference、其他 author 输出、Batch 7..9 成稿或 iteration-6/7 输出；grader 不得修改作者成稿。

- [ ] **Step 7: 验收并生成 iteration-8 viewer**

主 agent 核验 grader 的每条 assertion、mismatch 和 style finding，依次运行派生器 `hard`、`style`、`smoke`；预期为 `14/14 + 0 mismatch`、`0/2`、`22/22 + 0 mismatch`。全部通过后，viewer 只包含 eval-1..5 各一份 current-skill 输出，以及通过来源路径和 SHA-256 绑定复用的 Batch 10 run-1/run-2；不得生成第三份 eval-6 或 old-skill 对照。运行 viewer phase、`quick_validate.py`、`git diff --check`、tracked scope 检查和 Batch 6..9/iteration-6/7 不变性检查。生成 `iteration-8/review.html` 后立即停止，等待用户审阅；不生成 passed full status，不执行 trigger optimization。

---

### Task 6E: 原子命题与支持方式（历史失败，已封存）

**Files:**
- Modify tracked runtime: `skills/professional-writing/SKILL.md`、`skills/professional-writing/references/self-review.md`。
- Modify in ignored workspace: `skills/professional-writing-workspace/style-calibration/derive-content-status.py`、`process-candidate/`。
- Create in ignored workspace: `skills/professional-writing-workspace/style-calibration/process-batches/batch-11/`、`skills/professional-writing-workspace/iteration-9/`。

**Interfaces:**
- Consumes: approved spec commit `76fe3e50878c14fb13ffeb40595b49732d01d8ae`；Batch 10 的封存 RED；当前正式 skill；eval-1..6 已提交 prompts/assertions/fixtures；冻结四项 style criteria。
- Preserves: Batch 6 至 Batch 10、iteration-6/7/8 的所有字节，以及 description、evals.json、fixtures、grader reference。Batch 10 manifest SHA-256 保持 `6a060056aa400bbf881ac28a3066361b6b508e4c5c8b4198e5b847476b0edcf2`。
- Produces: 原子事实锁与主张支持方式 runtime；Batch 11 两份 eval-6；iteration-9 五份 smoke；全绿后只含这 7 份文档的静态 viewer。

**Hard gates:**
- Batch 11：`14/14`、每份 `0 mismatch`、accepted style issue documents `0/2`。
- iteration-9 smoke：`22/22`、每份 `0 mismatch`。
- 总计：7 份文档、`36/36`、所有事实检查 `0 mismatch`。任一失败立即封存，不补跑、不替换、不在同一批次修稿。

- [ ] **Step 1: 只读复核现场与根因**

确认 branch、HEAD、clean tracked 状态；复核 Batch 10 manifest SHA、`35/36` 与 6 mismatch；确认 Batch 11、iteration-9 不存在。根因必须保持为两个独立问题：F-02 把定义和动作合并为一个 stable ID；eval-4 的 locator 只提供相关记录，没有支持“越过/满足目标”的关系和强度。

- [ ] **Step 2: 先提交 spec 与 plan**

spec 已作为 `76fe3e50878c14fb13ffeb40595b49732d01d8ae` 单独提交。plan 绑定该完整 SHA 后单独提交；runtime 不得混入。提交 body 记录原因与验证，trailer 使用 `Co-authored-by: OpenAI Codex <noreply@openai.com>`。

- [ ] **Step 3: 以 Batch 10 为 RED 实现最小 runtime 修订**

只用 `apply_patch` 修改两个 runtime 文件：

- stable ID 每项只包含一个原子命题；定义、动作、职责、因果、目标、阈值分别锁定。含糊黑话关系不得混入相邻 direct 事实。
- 事实锁与反向主张槽记录 `direct / inference / unknown`。direct 要求 source locator 完整支持主体、关系、条件和强度；相关事实列表不自动支持合成判断。
- inference 必须在成稿显式标为判断/推测，并保留依据与 status；unknown 不得写成结论。
- 四槽未完成、support mode 与来源不符或只给 locator 未做蕴含核对时，不得声明 `0 mismatch`。

不修改 description、evals.json、fixtures、grader reference，不新增 runtime 文件。运行 `quick_validate.py`、`git diff --check`，确认 tracked diff 仅两个 runtime 文件后单独提交。

- [ ] **Step 4: 同步候选与派生合同**

用 `apply_patch` 将两个正式 runtime 文件逐字同步到 ignored `process-candidate/`。更新唯一 `derive-content-status.py`，绑定 spec commit `76fe3e50878c14fb13ffeb40595b49732d01d8ae`，只接受 Batch 11 与 iteration-9；同时验证 formal 与 candidate 两文件哈希一致。运行 `python3 -m py_compile`，并在 Batch 11 尚不存在时确认 hard phase fail closed。

- [ ] **Step 5: 密封 Batch 11 manifest**

manifest 保持 schema version 1、`run_ids = ["run-1", "run-2"]`、现有 eval-6 七条 hard assertions 和 `2026-07-14-v1` style criteria。写入当前 candidate、fixture、grader reference 哈希，设置 `sealed_before_runs = true`；记录 manifest SHA 后不得修改。

- [ ] **Step 6: 两位 fresh author 与一个 blind grader**

最多三位子代理。Author A 负责 Batch 11 run-1 与 eval-1..3；Author B 负责 run-2 与 eval-4..5；Blind grader 在全部作者封笔后统一评分。authors 不得读取 grader reference、Batch 7..10 成稿、iteration-6/7/8 或对方输出；grader 不修改成稿。所有 fact-check 同时检查正文、qa-summary 与 transcript 的复核声明。

- [ ] **Step 7: 全绿后生成 iteration-9 viewer**

主 agent 核验 assertions、mismatch 与 style findings，依次运行 `hard/style/smoke`。只有 `14/14 + 0 mismatch`、`0/2`、`22/22 + 0 mismatch` 全部成立，才生成只含七份 current-skill 文档的 iteration-9 viewer；两个 eval-6 文档按 source path + SHA-256 复用。运行 viewer phase、`quick_validate.py`、`git diff --check` 和 Batch 6..10/iteration-6..8 不变性检查。生成 viewer 后立即停止，不生成 passed full status，不执行 trigger optimization。

---

### Task 6F: human-review-first beta 验收（已完成）

**Files:**
- Modify tracked docs only: `docs/superpowers/specs/2026-07-13-professional-writing-skill-design.md`、本 plan。
- Create in ignored workspace: `skills/professional-writing-workspace/iteration-9/eval-6-rewrite-style-pressure/`、`known-issues.json`、`viewer-bindings.json`、`review.html`。

**Interfaces:**
- Consumes: approved spec commit `7dd253699d6005b761763a8957839fbf534ad1cd`；Batch 11 原始作者成稿与 blind grading；iteration-9 现有五份 smoke 成稿；标准 `skills/skill-creator/eval-viewer/generate_review.py`。
- Preserves: 当前正式 runtime、candidate、Batch 6 至 Batch 11、iteration-6/7/8、evals.json、fixtures、grader reference 和原始 16 份评分 JSON 的所有字节。
- Produces: 只含七个 current-skill run 的 iteration-9 静态 viewer；run-2 的已知问题说明；七份主文档的 source path + SHA-256 绑定。

**Acceptance contract:**
- 不创建 Batch 12，不补跑、不替换、不修订现有七份成稿。
- viewer 展示 eval-1 至 eval-5 各一个 run，以及 Batch 11 eval-6 run-1/run-2；不得生成 old-skill 或第三份 eval-6。
- run-2 明确标注两项正文遗漏；四项评测产物问题单独记录，不把它们表述为四个额外正文错误。
- 保留 `36/36`、smoke `0 mismatch`、eval-6 `6 mismatch` 和 raw style findings `0/2` 的原始结果，不生成 style-validation 或 passed full status。
- viewer 生成后立即停止，等待用户按“可直接使用 / 小改可用 / 不可用”审阅；old-skill 重跑和 trigger optimization 继续后置。

- [x] **Step 1: 记录 Batch 11 的证据分层**

用 `apply_patch` 创建 `iteration-9/known-issues.json`。正文问题只列 run-2 遗漏“PSG 承接状态查询”和“生产环境效果还没有数据”；评测基础设施问题列两个 `source_bound` 结构、一个非原子事实槽和一组 locator 行号偏移。绑定 Batch 11 两份 `fact-check.json` 的 SHA-256。

- [x] **Step 2: 为 viewer 复用两个 eval-6 run**

用 `apply_patch` 创建 eval-6 的 root/config metadata、run-1/run-2 `outputs/document.md` 和 `grading.json`。两个 `document.md` 必须与 Batch 11 原文逐字一致；run-2 另加 `outputs/known-issues.md`，只用于透明提示，不修改成稿。eval-1 至 eval-5 保持原字节。

- [x] **Step 3: 生成标准静态 viewer**

运行：

```bash
python3 skills/skill-creator/eval-viewer/generate_review.py \
  skills/professional-writing-workspace/iteration-9 \
  --skill-name professional-writing \
  --static skills/professional-writing-workspace/iteration-9/review.html
```

Expected: viewer 发现 7 个 run，eval 顺序为 `1,2,3,4,5,6,6`；不传 previous workspace，不生成 baseline 对比。

- [x] **Step 4: 写入并验证 viewer bindings**

用 `apply_patch` 创建 `viewer-bindings.json`，逐项记录 `eval_id / run_id / source_document / viewer_document / sha256`，并绑定 `review.html` SHA-256。运行独立 Python 检查：七份主文档 source/viewer 哈希一致；run-2 已知问题可见；16 份原始评分 JSON 不变；`content-calibration-status.json`、style-validation 和 Batch 12 均不存在。

- [x] **Step 5: 最终验证并停在人工检查点**

运行 `quick_validate.py`、`git diff --check`、tracked scope 检查，以及 runtime/candidate、evals、eval-6 fixture、grader reference、Batch 10/11 manifest 哈希复核。把 `review.html` 绝对路径交给用户后立即停止；不得执行 Task 7。

- [x] **Step 6: 记录人工审阅与用户接受**

主 agent 逐份审阅 7 份成稿：eval-1、eval-3、eval-4、eval-6 run-1 共 4 份可直接使用；eval-2、eval-5、eval-6 run-2 共 3 份小改可用；不可用为 0 份。用户接受当前 beta，并同意停止完整合成迭代。后续先运行 3～5 个真实任务；只有同类用户可见问题在至少 2 份真实文档中重复时，才启动一次以删减过程措辞与重复免责声明为主的小规模迭代。重要或对外文档继续人工事实复核。

---

### Task 7: 触发评测（后置，不执行）

> 本轮不创建 20 条 trigger queries，不执行每条 3 次的 description optimization，也不修改 description。是否恢复由用户审阅 iteration-9 viewer 后另行决定；以下旧预案仅作历史参考。

**Files:**
- Create: skills/professional-writing-workspace/trigger-eval/queries.json（工作区文件，不入 git）

**Interfaces:**
- Consumes: Task 1 的 description；Task 6B 由 batch-8 与 iteration-7 派生的 skills/professional-writing-workspace/iteration-7/content-calibration-status.json；执行前**通读** skills/skill-creator/SKILL.md 的 Description Optimization 节并照其执行（20 用例、重复 3 次、train/held-out、<=5 轮）。
- Does not consume: A/B winner、win count、comparison summary 或 blind gate。

**执行门：** Task 6B 的 iteration-7 status 不存在、不是 schema_version 2、不是 passed、正式两文件 hash 漂移，或 batch-8 事实门、绝对 style control、eval-1..6 全量 fresh 回归、iteration-7 用户内容检查点任一未通过时，Task 7 保持 blocked；不得用 batch-6/batch-7/iteration-6 的旧或失败状态解锁，不得创建或修改 trigger-eval 产物，不得优化 description。

- [ ] **Step 0: 重派生并最小消费新内容状态，非 passed 立即退出**

从仓库根目录运行：

~~~bash
python3 skills/professional-writing-workspace/style-calibration/derive-content-status.py \
  --phase full \
  --batch skills/professional-writing-workspace/style-calibration/process-batches/batch-8 \
  --iteration skills/professional-writing-workspace/iteration-7 \
  --output skills/professional-writing-workspace/iteration-7/content-calibration-status.json
~~~

Expected: 输出 full passed，退出 0。派生器重新校验全部原始证据；失败立即停止，不执行下一条命令。

~~~bash
python3 -c 'import json,pathlib;d=json.loads(pathlib.Path("skills/professional-writing-workspace/iteration-7/content-calibration-status.json").read_text());assert d["schema_version"]==2 and d["spec_commit"]=="1a22ed30a49eeb6b4c1d1265cf5372a0b9d8874f" and d["content_calibration_status"]=="passed" and d["candidate"]["hard_assertions_total"]==35 and d["regression"]["assertions_across_configurations"]==58;print("passed")'
~~~

Expected: 输出 passed，退出 0。文件缺失、JSON/schema/字段错误、hash 漂移或任一内容门失败时，命令非零并立即停止，保持现有 trigger-eval/queries.json 与 description 不变。

- [ ] **Step 1: 生成 20 个真实、具体的近邻用例**

10 个 should-trigger + 10 个 should-not-trigger，存 `queries.json`（格式 `[{"query": "...", "should_trigger": true}, ...]`）。种子用例（可在同分布内扩充凑满 20）：

should-trigger：性能调优结果整理成文档给同事、技术文章讲迁移决策、部署过程写成操作指南、agent 完成迁移后写报告文件、改一份读不下去的复盘报告、调研结果写给决策者、把变更总结写成文档发群里、写季度进展汇报、把事故处理过程写成复盘文档、把架构讨论结论整理成方案说明。

should-not-trigger（括号为正确归属）："这次会话做了什么简单说说"（聊天简答）、公众号文章（khazix-writer）、评审技术方案（technical-proposal-review）、整理交接包（handoff）、深度研究 Pulsar（hv-analysis）、给函数补 docstring（编码）、修 README 一处错别字（编码）、生成 PDF 报告排版（pdf）、"总结一下这篇论文的要点"（阅读理解简答）、写会议纪要发言逐条记录（非叙事文档）。

- [ ] **Step 2: 【停——用户检查点】用户审查用例清单**

skill-creator 要求用例先经用户审查——正负例是否真实、边界是否是你日常会遇到的。按用户意见修订后再跑。

- [ ] **Step 3: Claude 环境跑标准 trigger eval（含部署门槛）**

按 skill-creator "Description Optimization" 节使用其 `scripts.run_loop` 流程：每用例重复 3 次、60% train / 40% held-out、最多优化 5 轮、只改 description 不动正文。

**部署门槛（写死）**：20 条用例按 40% held-out 后为 8 条，要求 held-out **8/8 通过**，且四个关键邻居（khazix-writer、technical-proposal-review、handoff、hv-analysis）的负例**零误触**。`run_loop` 返回的"最佳版本"不自动等于达标——按此门槛判定。未达标处理：5 轮用尽仍不达标 → 保留最佳 description，但在交付说明中把隐式触发降级为"不承诺"（使用方式回退为显式调用为主），并把数据交用户决定是否接受或继续调。

- [ ] **Step 4: Codex 环境做真实触发抽测（仅记录，不作部署门槛）**

抽 5 个代表用例（3 正 2 负），在 Codex 宿主用 fresh agent **直接执行原始请求**——不告知这是测试、不给分类题——观察其是否真实读取/调用 `professional-writing`。样本仅 5 例、宿主触发机制不同，结果**只记录供首战参考**，不阻塞部署；分宿主记录，不把一个宿主的触发率当成另一个宿主的结论。

- [ ] **Step 5: 收敛后提交 description 改动（如有）**

description 改动后检查 references/evals 是否受影响（旁支教训）：

```bash
git add skills/professional-writing/SKILL.md
git commit -m "fix(professional-writing): 按触发评测校准 description

held-out 通过率与修正点写入 body；Codex 宿主抽测结果单独记录。

<AI-TRAILER>"
```

---

### Task 8: 部署与真实首战交接（部署已完成，首战待执行）

> 用户已经接受 iteration-9 的 beta 人工审阅结果。2026-07-16 feature 分支已 fast-forward 合入 main，两条宿主软链均直接指向主仓库；真实首战仍按下方检查点执行。

**Files:**
- Create: `~/.claude/skills/professional-writing`（软链）、`~/.codex/skills/professional-writing`（软链），目标均为主仓库 `/Users/zhaoguodong/Codes/ai-coding/lucas-skills/skills/professional-writing`

- [x] **Step 1: 幂等预检（写 `~/` 属仓库外写入，需相应权限批准）**

```bash
ls -la ~/.claude/skills/professional-writing ~/.codex/skills/professional-writing 2>&1
```

三种结果分别处理：不存在 → 下一步创建；已存在且指向主仓库 `skills/professional-writing` → 跳过创建；已存在但指向别处 → **停下来报告**，不覆盖未知路径。创建前确认主仓库目标已包含合入后的 `SKILL.md` 与 references。

- [x] **Step 2: 只创建缺失的软链（逐条执行，不串联）**

```bash
ln -s /Users/zhaoguodong/Codes/ai-coding/lucas-skills/skills/professional-writing ~/.claude/skills/professional-writing
```

```bash
ln -s /Users/zhaoguodong/Codes/ai-coding/lucas-skills/skills/professional-writing ~/.codex/skills/professional-writing
```

- [x] **Step 3: 验证链路**

Run（分步执行）：

```bash
ls -la ~/.claude/skills/professional-writing ~/.codex/skills/professional-writing
```

```bash
ls /Users/zhaoguodong/Codes/ai-coding/lucas-skills/skills/professional-writing/
```

Expected: 两条软链均指向主仓库 `skills/professional-writing`；目标目录列出 SKILL.md、references、evals。

- [ ] **Step 4: 【停——用户检查点】首战交接**

告知用户：skill 已部署，请拿一个真实场景实测（验收样本覆盖从零写/重写/资料不足三种）；反馈按 handoff/tpr 同款闭环沉淀（后续校准不在本计划内）。

---

## 后置任务（不在本计划内）

- old-skill / no-guidance 重跑与 A/B 对照。
- 20 条用例 × 每条 3 次的 trigger/description optimization。
- 首战反馈校准（判词措辞/阈值/类型适配，spec 第 11 节预期内迭代）。
- `sync-links.sh` 是否值得补：维持 YAGNI 搁置，除非再次漏建软链。
