# professional-writing 触发边界实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留 `professional-writing` 独立撰写技术方案的能力，同时避免它仅因其他流程会生成 `spec`、`plan` 或 `design doc` 而抢占主流程。

**Architecture:** 只修改 Skill frontmatter 的 `description`，用“正式文档是否为当前主要交付物”和“是否已有其他设计/开发/治理流程主导”划分职责。新增独立触发评测清单和一个标准库 `unittest` 合同测试；不修改正文写作流程、references 或现有六个内容评测。

**Tech Stack:** Markdown Skill、YAML frontmatter、JSON 触发评测、Python 3.11 `unittest`、PyYAML、Skill Creator `quick_validate.py`、Git。

## Global Constraints

- 正向保留从零撰写技术方案、资料不足但正式文档是主要交付物、已有正式文档重写。
- 负向排除其他设计、开发或治理 Skill 已主导且文档只是其必需产物的场景；用户显式点名或指定组合顺序时除外。
- 评审已有技术方案继续路由到 `technical-proposal-review`。
- 不修改 `skills/professional-writing/SKILL.md` 正文、references、现有 `evals/evals.json` 和六个 fixture。
- 不新增依赖、脚本、运行时编排器或 UI 元数据。
- 只在隔离 worktree 的 `fix/professional-writing-trigger-boundary` 分支实施；不 push、不合并、不激活、不发布。

---

### Task 1: 固化触发合同并最小修改 description

**Files:**
- Create: `tests/test_professional_writing_skill.py`
- Create: `skills/professional-writing/evals/trigger-evals.json`
- Modify: `skills/professional-writing/SKILL.md:1-5`

**Interfaces:**
- Consumes: `SKILL.md` YAML frontmatter；现有 `evals/evals.json` 内容评测保持只读。
- Produces: `trigger-evals.json`，字段固定为 `id`、`query`、`should_trigger`、`route`、`reason`；`route` 取 `professional-writing`、`other-skill` 或 `mixed`。

- [ ] **Step 1: 写入失败合同测试**

创建 `tests/test_professional_writing_skill.py`：

```python
import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "professional-writing"


def load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class ProfessionalWritingSkillTests(unittest.TestCase):
    def test_description_preserves_authoring_and_excludes_incidental_artifacts(self):
        frontmatter = load_frontmatter(SKILL_ROOT / "SKILL.md")
        self.assertEqual(set(frontmatter), {"name", "description"})
        self.assertEqual(frontmatter["name"], "professional-writing")
        description = frontmatter["description"]
        self.assertTrue(description.startswith("Use when "))
        self.assertLessEqual(len(description), 1024)
        for phrase in (
            "首要目标",
            "正式专业文档",
            "从零撰写技术方案",
            "主要交付物",
        ):
            self.assertIn(phrase, description)
        for phrase in (
            "不得仅因",
            "设计、开发或治理流程",
            "spec",
            "plan",
            "design doc",
            "technical-proposal-review",
        ):
            self.assertIn(phrase, description)

    def test_trigger_eval_matrix_covers_positive_negative_and_mixed_routes(self):
        manifest = json.loads(
            (SKILL_ROOT / "evals" / "trigger-evals.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["skill_name"], "professional-writing")
        evals = manifest["evals"]
        self.assertEqual(len(evals), 20)
        self.assertEqual(len({case["id"] for case in evals}), 20)
        self.assertEqual(sum(case["should_trigger"] for case in evals), 10)
        self.assertEqual(
            {case["route"] for case in evals},
            {"professional-writing", "other-skill", "mixed"},
        )
        required = {"id", "query", "should_trigger", "route", "reason"}
        for case in evals:
            self.assertEqual(set(case), required)
            self.assertTrue(case["query"].strip())
            self.assertTrue(case["reason"].strip())

        positive = " ".join(
            case["query"] for case in evals if case["should_trigger"]
        )
        negative = " ".join(
            case["query"] for case in evals if not case["should_trigger"]
        )
        for phrase in ("技术方案", "设计文档", "design doc"):
            self.assertIn(phrase, positive)
            self.assertIn(phrase, negative)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认 RED 原因正确**

Run:

```bash
uv run python -m unittest tests.test_professional_writing_skill -v
```

Expected: FAIL；当前 `description` 不以 `Use when ` 开头，并且 `trigger-evals.json` 尚不存在。不得修改测试来适配旧行为。

- [ ] **Step 3: 创建 20 条触发路由评测**

创建 `skills/professional-writing/evals/trigger-evals.json`。固定分布：

- 8 条 `professional-writing`：从零技术方案、给定材料成稿、资料不足但要求正式方案、决策材料、技术解释、操作指南、总结重写、已有技术方案表达重写；
- 2 条 `mixed`：用户明确要求“Superpowers 起草、professional-writing 验证”，以及明确要求先形成设计判断再由本 Skill 成稿；
- 10 条 `other-skill`：Superpowers 主导的软件功能设计、实施计划、已有技术方案评审、代码 review、公众号文章、深度研究、交接包、API 参考、DOCX 排版、聊天内三句总结。

正负两组都必须真实包含“技术方案”“设计文档”和 `design doc`，并至少包含以下近邻反例：

```json
{
  "id": "negative-active-superpowers-design-doc",
  "query": "继续刚才的 Superpowers 设计流程：方案已经确认，现在按该流程写入可评审的设计文档，实施等我复核后再开始。",
  "should_trigger": false,
  "route": "other-skill",
  "reason": "设计文档是已选设计流程的必需产物，不能仅因进入写文档阶段切换主 Skill。"
}
```

并至少包含以下独立写作正例：

```json
{
  "id": "positive-standalone-technical-proposal",
  "query": "请单独写一份从 MySQL 迁移到 PostgreSQL 的技术方案，给架构委员会评审；现有约束如下，缺的信息先列出来问我。",
  "should_trigger": true,
  "route": "professional-writing",
  "reason": "正式技术方案本身是主要交付物，且用户要求从零撰写。"
}
```

- [ ] **Step 4: 运行旧 description 的触发基线**

在仍未修改 `SKILL.md` 时运行：

```bash
WORKTREE_ROOT="$(pwd -P)"
EVAL_TMP_ROOT="${TMPDIR:-/tmp}"
EVAL_TMP_ROOT="${EVAL_TMP_ROOT%/}"
EVAL_TMP_DIR="$(mktemp -d "$EVAL_TMP_ROOT/professional-writing-trigger-eval.XXXXXX")"
(
  cd "$EVAL_TMP_DIR"
  CLAUDE_CONFIG_DIR="$EVAL_TMP_DIR/claude-config" \
  PYTHONPATH="$WORKTREE_ROOT/skills/skill-creator" \
    python3 -m scripts.run_eval \
      --eval-set "$WORKTREE_ROOT/skills/professional-writing/evals/trigger-evals.json" \
      --skill-path "$WORKTREE_ROOT/skills/professional-writing" \
      --runs-per-query 1 \
      --num-workers 10 \
      --timeout 45 \
      --verbose
)
case "$EVAL_TMP_DIR" in
  "$EVAL_TMP_ROOT"/professional-writing-trigger-eval.*)
    rm -rf -- "$EVAL_TMP_DIR"
    ;;
  *)
    echo "Refusing to remove unexpected temp path: $EVAL_TMP_DIR" >&2
    exit 1
    ;;
esac
```

Expected: 命令记录当前 description 的 20 条基线；重点确认 `negative-active-superpowers-design-doc` 是否误触发。`CLAUDE_CONFIG_DIR` 隔离全局同名 Skill，避免模型命中已激活副本而漏记候选命令。

- [ ] **Step 5: 最小修改 frontmatter description**

只替换 `SKILL.md` 的 `description`，正文从 `# 专业文档写作` 起保持字节不变：

```yaml
description: |
  Use when 用户的首要目标是产出、重写或完善一份给人阅读的正式专业文档，包括总结与汇报、技术解释与专业文章、方案与决策文档（含从零撰写技术方案）、教程与操作指南，以及已有正式文档的诊断与重写（write a summary/report/postmortem/design doc/tutorial/article）；即使材料不足，只要正式文档本身是主要交付物也应触发。不得仅因其他设计、开发或治理流程会生成 spec、plan 或 design doc 而触发；当这些流程已经主导当前任务，文档只是其必需产物时继续使用原流程。用户显式点名本 Skill 或指定组合顺序时按其要求执行。聊天内三五句口头总结不触发。SKIP：公众号文章 → khazix-writer；评审已有技术方案 → technical-proposal-review；交接包 → handoff；深度研究报告 → hv-analysis；API 参考、代码注释、DOCX/PDF 排版（docx/pdf skill）。
```

- [ ] **Step 6: 运行 GREEN 与基础校验**

Run:

```bash
uv run python -m unittest tests.test_professional_writing_skill -v
uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/professional-writing
python3 -m json.tool skills/professional-writing/evals/trigger-evals.json >/dev/null
git diff --check
```

Expected: 合同测试 2/2 通过；`quick_validate.py` 输出 `Skill is valid!`；JSON 解析和 diff 检查退出码为 0。

- [ ] **Step 7: 做实际路由对照**

用 Step 4 的同一命令运行新 `description`；为避免复制错误，命令仅复用原文，不更换评测清单、并发数或超时。先执行一次全矩阵；只有失败项存在时，才把失败项复制到临时 JSON 中补跑两次确认波动，不预先执行 120 次全量调用。临时 JSON 不提交。

验收重点：

- 新版本 10 条正例全部触发，尤其是独立从零技术方案；
- 新版本 10 条负例不触发，尤其是已有 Superpowers 流程写设计文档；
- 若本机 CLI 没有 Superpowers，只判断 `professional-writing` 是否错误接管，不把替代 Skill 缺失误报为 description 缺陷；
- 当前 Codex 激活链接指向 main checkout，worktree 内的新描述不会自动进入全新 Codex 进程；因此 worktree 阶段不得宣称已完成 Codex live routing，合并后需在新任务中复验。

- [ ] **Step 8: 提交最小实现**

```bash
git add \
  skills/professional-writing/SKILL.md \
  skills/professional-writing/evals/trigger-evals.json \
  tests/test_professional_writing_skill.py
git commit \
  -m "fix(professional-writing): 收紧技术方案触发边界" \
  -m "按正式文档是否为当前主要交付物划分技术写作职责，保留从零技术方案写作，同时避免抢占已由其他设计、开发或治理 Skill 主导的文档产物。" \
  -m "验证：
- uv run python -m unittest tests.test_professional_writing_skill -v
- quick_validate.py skills/professional-writing
- trigger routing eval
- git diff --check" \
  -m "Co-authored-by: OpenAI Codex <noreply@openai.com>"
```

### Task 2: 全量回归与分支交付

**Files:**
- Verify only: repository working tree and committed diff

**Interfaces:**
- Consumes: Task 1 的单个实现提交。
- Produces: 可供独立 review 的干净分支；不合并、不 push、不激活。

- [ ] **Step 1: 运行完整回归**

```bash
uv run python -m unittest discover -s tests -v
uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/professional-writing
python3 -m json.tool skills/professional-writing/evals/evals.json >/dev/null
python3 -m json.tool skills/professional-writing/evals/trigger-evals.json >/dev/null
git diff HEAD^ --check
```

Expected: 全部 unittest 通过且 failure/error 为 0；两个 JSON 均可解析；Skill 校验和 diff 检查退出码为 0。

- [ ] **Step 2: 核对范围和历史**

```bash
git status --short --branch
git diff HEAD^ --stat
git diff HEAD^ -- skills/professional-writing/SKILL.md
git log -2 --format=fuller
```

Expected: 工作区干净；实现提交只包含 3 个计划文件；`SKILL.md` 只有 frontmatter `description` 变化；正文、references 和原六个内容评测保持不变。

- [ ] **Step 3: 进入分支收尾**

使用 `superpowers:finishing-a-development-branch` 提供保留分支或本地集成选项。未经用户选择，不合并 main、不 push、不激活、不发布。

### Task 3: 恢复正向召回并强化 active workflow 排除

**Files:**
- Modify: `tests/test_professional_writing_skill.py`
- Modify: `skills/professional-writing/evals/trigger-evals.json`
- Modify: `skills/professional-writing/SKILL.md:1-5`

**Interfaces:**
- Consumes: Task 1 的 `{ "skill_name", "evals" }` 触发清单和 frontmatter description。
- Produces: 23 条触发路由合同，其中 `professional-writing=11`、`mixed=2`、`other-skill=10`；正文、references 和既有内容评测保持不变。

- [ ] **Step 1: 写入失败合同测试**

在现有两个测试中增加以下合同：

```python
for phrase in (
    "写总结",
    "调研总结",
    "进展汇报",
    "变更总结",
    "写报告",
    "整理成文档",
    "写成文档给人看",
    "agent 完成一段工作后",
    "不得用本 Skill 取代",
    "继续",
    "按原流程",
):
    self.assertIn(phrase, description)

self.assertEqual(len(evals), 23)
self.assertEqual(sum(case["should_trigger"] for case in evals), 13)
self.assertEqual(
    sum(case["route"] == "professional-writing" for case in evals), 11
)
for case_id in (
    "positive-agent-autonomous-postmortem",
    "positive-progress-report",
    "positive-change-summary",
):
    self.assertEqual(routes_by_id[case_id], (True, "professional-writing"))
```

- [ ] **Step 2: 运行测试确认 RED**

Run:

```bash
uv run python -m unittest tests.test_professional_writing_skill -v
```

Expected: FAIL；当前 description 缺少恢复的触发入口，清单仍为 20 条且缺少三个新 id。

- [ ] **Step 3: 增加三个正向触发样本**

向 `trigger-evals.json` 增加：

```json
{
  "id": "positive-agent-autonomous-postmortem",
  "query": "这次数据库迁移实施和验证已经完成。请把已确认的结果、风险和未决项主动整理成一份给技术负责人阅读的正式复盘文档，不要只在聊天里口头总结。",
  "should_trigger": true,
  "route": "professional-writing",
  "reason": "agent 完成工作后需要主动产出给人阅读的正式文档文件。"
}
```

```json
{
  "id": "positive-progress-report",
  "query": "根据本周已经验证的研发工作结果，写一份给项目干系人的正式进展汇报文档。",
  "should_trigger": true,
  "route": "professional-writing",
  "reason": "正式进展汇报本身是主要交付物。"
}
```

```json
{
  "id": "positive-change-summary",
  "query": "把刚完成的数据库切换范围、验证结果和未决项整理成给运维与研发共同阅读的正式变更总结。",
  "should_trigger": true,
  "route": "professional-writing",
  "reason": "正式变更总结本身是主要交付物。"
}
```

- [ ] **Step 4: 最小修改 description**

只替换 YAML `description`，正文保持字节不变：

```yaml
description: |
  Use when 用户要求产出、重写或完善给人阅读的正式专业文档，或 agent 完成一段工作后需要主动产出此类文档文件。触发场景包括写总结、调研总结、复盘、进展汇报、变更总结、写报告、方案说明、决策材料、汇报材料、技术解释、技术/专业文章、从零撰写技术方案、教程、操作指南、“整理成文档”“写成文档给人看”，以及已有正式文档的诊断与重写（write a summary/report/postmortem/design doc/tutorial/article）；材料不足不影响触发，前提是正式文档本身是当前主要交付物。若其他设计、开发或治理流程已主导内容判断，不得用本 Skill 取代其方案生成职责；用户明确要求继续或按原流程产出其必需的 spec、plan、design doc 时，不使用本 Skill，除非用户显式点名本 Skill、指定组合顺序，或该正式文档是内容判断完成后的独立交付物。聊天内三五句口头总结不触发。SKIP：公众号文章 → khazix-writer；评审已有技术方案 → technical-proposal-review；交接包 → handoff；深度研究报告 → hv-analysis；API 参考、代码注释、DOCX/PDF 排版（docx/pdf skill）。
```

- [ ] **Step 5: 运行 GREEN 与验证**

Run:

```bash
uv run python -m unittest tests.test_professional_writing_skill -v
uv run python /Users/zhaoguodong/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/professional-writing
python3 -m json.tool skills/professional-writing/evals/trigger-evals.json >/dev/null
git diff --check
```

Expected: 合同测试 2/2 通过，Skill 与 JSON 校验通过。

- [ ] **Step 6: fresh-agent 前向验证**

分别用不继承当前上下文的 fresh agent 验证自主正式复盘、进展汇报、变更总结和 active Superpowers 设计文档。前三条必须选择 `professional-writing`；最后一条不得选择 `professional-writing`。若 agent 仍加载全局 `main` 副本而非 worktree 候选，明确记录环境限制，不把结果算作候选失败。

- [ ] **Step 7: 提交最小修复**

只提交上述三个实现文件；提交正文记录 RED、GREEN、fresh-agent 结果及未验证边界。不 push、不发布。
