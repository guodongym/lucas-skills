# professional-writing skill 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `skills/professional-writing/`（SKILL.md + 3 个 references + evals 五用例），跑通 iteration-1 双跑对比与触发评测，部署软链。

**Architecture:** 薄入口 SKILL.md（模式路由 + 七步流程 + 三道门 + 判词表 + 交付契约），模板与骨架全部下沉 references/ 按需加载；evals 走 skill-creator 标准链路（分批双跑 → timing/grading → aggregate_benchmark → analyst pass → viewer → feedback.json），触发评测走其 Description Optimization 流程。

**Tech Stack:** Markdown skill 文件、skill-creator evals 流程（subagent 双跑）、Bash 结构断言。

**Spec:** `docs/superpowers/specs/2026-07-13-professional-writing-skill-design.md`（已评审通过，最新 commit 3c9ded7）。本计划中所有成文内容以 spec 为准源；发现冲突时以 spec 为准并停下来报告。

## Global Constraints

- 交付语言：skill 全文中文（description 触发词含英文短语）。
- SKILL.md 总行数 ≤ 150（含 frontmatter）；模板、骨架细节一律下沉 references/。
- Avoid 判词表 7 条、三道确认门、快速通道、教程例外（判词 1/2/5 与流程步骤 2/4/5）必须与 spec 5.0-5.3 一致，不得增删改义。
- evals 全程遵循 `skills/skill-creator/SKILL.md` 的评测链路与 `skills/skill-creator/references/schemas.md` 的字段定义；不使用 /skill-test。**字段名约定（三个文件各不相同，以 schemas.md 为准源）**：`evals/evals.json` 用 `expectations`；每个 eval 目录的 `eval_metadata.json` 用 `assertions`（内容复制自对应 expectations）；每个运行的 `grading.json` 的 expectations[] 严格使用 `text` / `passed` / `evidence` 三字段（viewer 依赖精确字段名）。
- **workspace 目录契约（同时满足 aggregate_benchmark.py 与 viewer）**：`iteration-1/eval-<id>-<name>/eval_metadata.json` 是 canonical metadata（eval 级，含 eval_id/name/prompt/assertions）；`with_skill/` 与 `without_skill/` 各保留一份相同 metadata 供 viewer 从 run 的父目录读取。运行产物在 `eval-<id>-<name>/<configuration>/run-1/`，其中 `outputs/`、`timing.json`、`grading.json` 都在 run 目录内。
- workspace 位于 `skills/professional-writing-workspace/`（与 skill 目录同级），通过 .gitignore 排除，不入 git。
- Commit 粒度：Task 1-4 完成后**统一提交一个完整可用的 skill**（中间不单独 commit，避免检出残缺状态）；Task 5 提交 evals；Task 6-7 仅在产生实际校准修改时提交。
- Commit 规范：`<type>(professional-writing): 中文描述` + body 说明为什么与验证结果 + trailer `<AI-TRAILER>`。**`<AI-TRAILER>` 按实际执行 agent 填写**：Claude 执行 → `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`；Codex 执行 → `Co-authored-by: OpenAI Codex <noreply@openai.com>`；其他 agent 按仓库规范用可辨认的自身身份。
- 交付契约完整覆盖 spec 第 9 节语义（成稿干净无流程痕迹 + 质检摘要放对话内 + 中间产物不落盘 + 明确要求才另存），不绑定条数。
- 教训（spec 第 10 节）：任何 SKILL.md 后续改动必须同步检查 references/evals 旁支。

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

### Task 5: evals 五用例与输入素材

**Files:**
- Create: `skills/professional-writing/evals/evals.json`
- Create: `skills/professional-writing/evals/files/eval1-流水账调研总结.md`
- Create: `skills/professional-writing/evals/files/eval2-调研笔记.md`
- Create: `skills/professional-writing/evals/files/eval4-技术决策笔记.md`
- Create: `skills/professional-writing/evals/files/eval5-操作过程记录.md`

**Interfaces:**
- Consumes: 判词表编号（断言引用）；skill-creator 的 evals.json schema（`skills/skill-creator/references/schemas.md`）。
- Produces: Task 6 直接消费本任务的五个用例。

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
      "expected_output": "document.md：首段含一句命题式断言（推荐哪个、为什么）；有显式取舍标记；推断有依据标注；无空标题。",
      "expectations": [
        "首段含一句明确的推荐性断言",
        "存在主次排序或'细节见附录'类显式取舍标记",
        "素材中标注'未证实'的传闻在文中被标注或被排除，未写成事实",
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
      "expected_output": "document.md：开头是可验证的任务承诺而非观点命题；含前置条件；素材能支持的步骤附验证方式，素材不足处标记'待确认'而非编造；步骤章节无强造的结论句。",
      "expectations": [
        "开头为任务承诺（完成什么、前提是什么）而非观点命题",
        "含前置条件内容",
        "素材能支持的步骤附验证方式；素材含糊处（如'改了下那个配置'）标记待确认，未编造具体命令或路径",
        "步骤章节无强造的结论句或'综上所述'式总结段"
      ]
    }
  ]
}
```

字段名提醒（Global Constraints 的约定）：本文件用 `expectations`；Task 6 每个 eval 目录的 canonical `eval_metadata.json` 用 `assertions`（内容复制自上面对应 expectations），并复制到两个 configuration 目录供 viewer 读取；`grading.json` 的 expectations[] 严格用 `text/passed/evidence`。

- [ ] **Step 2: 写入四个素材文件**

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

`eval5-操作过程记录.md` —— 第一人称流水账操作记录（"我先 ssh 到跳板机，然后改了配置，中间报了个错我重启解决了……"约 10 步，含 2 处口语化含糊表述如"改了下那个配置"，供改写时暴露前置条件与验证缺失）。

- [ ] **Step 3: 结构断言**

Run（分步执行）：

```bash
python3 -c "import json;d=json.load(open('skills/professional-writing/evals/evals.json'));assert len(d['evals'])==5;assert all(e.get('expectations') for e in d['evals']);print('OK',[e['name'] for e in d['evals']])"
```

```bash
ls skills/professional-writing/evals/files/ | wc -l
```

Expected: OK + 五个 name（每个 eval 均含非空 expectations）；素材文件 `4`。

- [ ] **Step 4: Commit**

```bash
git add skills/professional-writing/evals/
git commit -m "test(professional-writing): 添加 evals 五用例与输入素材

覆盖四类骨架×三种运行场景：重写总结/决策文档/资料不足/技术文章/教程。
素材按 spec 埋入判词病灶（eval-1 埋判词 1/2/5）；expectations 已随用例写入。
验证：evals.json 解析通过、5 用例均含非空 expectations、4 素材齐。

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

### Task 7: 触发评测（skill-creator Description Optimization 流程）

**Files:**
- Create: `skills/professional-writing-workspace/trigger-eval/queries.json`（工作区文件，不入 git）

**Interfaces:**
- Consumes: Task 1 的 description；执行前**通读** `skills/skill-creator/SKILL.md` 的 "Description Optimization" 节并照其执行（20 用例、重复 3 次、train/held-out、≤5 轮）。

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

### Task 8: 部署与收尾

**Files:**
- Create: `~/.claude/skills/professional-writing`（软链）、`~/.codex/skills/professional-writing`（软链）

- [ ] **Step 1: 幂等预检（写 `~/` 属仓库外写入，需相应权限批准）**

```bash
ls -la ~/.claude/skills/professional-writing ~/.codex/skills/professional-writing 2>&1
```

三种结果分别处理：不存在 → 下一步创建；已存在且指向 `~/.cc-switch/skills/professional-writing` → 跳过创建；已存在但指向别处 → **停下来报告**，不覆盖未知路径。

- [ ] **Step 2: 只创建缺失的软链（逐条执行，不串联）**

```bash
ln -s ~/.cc-switch/skills/professional-writing ~/.claude/skills/professional-writing
```

```bash
ln -s ~/.cc-switch/skills/professional-writing ~/.codex/skills/professional-writing
```

- [ ] **Step 3: 验证链路**

Run（分步执行）：

```bash
ls -la ~/.claude/skills/professional-writing ~/.codex/skills/professional-writing
```

```bash
ls ~/.cc-switch/skills/professional-writing/
```

Expected: 两条软链均指向 `~/.cc-switch/skills/professional-writing`；目标目录列出 SKILL.md、references、evals（证明 cc-switch 目录级软链已使新目录可见）。

- [ ] **Step 4: 【停——用户检查点】首战交接**

告知用户：skill 已部署，请拿一个真实场景实测（验收样本覆盖从零写/重写/资料不足三种）；反馈按 handoff/tpr 同款闭环沉淀（后续校准不在本计划内）。

---

## 后置任务（不在本计划内）

- 首战反馈校准（判词措辞/阈值/类型适配，spec 第 11 节预期内迭代）。
- `sync-links.sh` 是否值得补：维持 YAGNI 搁置，除非再次漏建软链。
