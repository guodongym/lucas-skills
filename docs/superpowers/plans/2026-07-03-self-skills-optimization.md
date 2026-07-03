# 自研 Skills 优化实施计划

> **状态：已全部实施并通过整分支终审（2026-07-03，分支 feature/self-skills-optimization，4 个 skill commit）。**
> 执行期修正：eval-3 文案按计划意图加长至实际触发溢出并补断言；checker 移除死代码、补输入错误处理。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按已批准的设计文档 `docs/superpowers/specs/2026-07-03-self-skills-optimization-design.md` 完成 4 个自研 skill 的优化。

**Architecture:** 4 个 skill 的改动互相独立，按 spec 实施顺序执行：git-history-rewrite（脚本 TDD + SKILL.md）→ technical-proposal-review（文档 + 文件重命名）→ handoff（纯 SKILL.md 编辑）→ business-architecture-diagram（模板资产 + 脚本 + evals）。每个 skill 一个独立 commit。

**Tech Stack:** Markdown（SKILL.md）、Python 3.9+ 仅标准库（unittest、xml.etree、re）、Bash、SVG。

## Global Constraints

- 提交格式：`<type>(<skill-name>): 中文描述`，必须有 body（说明为什么改 + 验证结果），footer 加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- 每个 skill 的全部改动放一个 commit；spec/plan 文档修正跟随相关 skill 的 commit 或单独 docs commit。
- SKILL.md 正文语言沿用各文件现状（git-history-rewrite/handoff 为英文正文 + 中文触发词与模板；business-architecture-diagram 为英文正文）。
- Python 脚本不引入任何第三方依赖；测试用 unittest，直接以 `python3 <test-file>` 运行。
- 不做 spec "明确不做" 列表中的任何事项（risk-patterns 拆分、handoff 存档约定、UML 图类型等）。
- 仓库根目录：`/Users/zhaoguodong/Codes/ai-coding/lucas-skills`，以下路径均相对于它。

---

### Task 1: git-history-rewrite — inspect_history.py 守卫（空仓库 + detached HEAD）

**Files:**
- Modify: `skills/git-history-rewrite/scripts/inspect_history.py`（`inspect()` 函数，约 111-148 行）
- Test: `skills/git-history-rewrite/tests/test_inspect_history.py`

**Interfaces:**
- Produces: 空仓库时脚本以退出码 1 输出 `repository has no commits yet; nothing to rewrite`；detached HEAD 时 JSON 报告 `risks` 数组含 `"detached HEAD"` 开头的条目。Task 2 的测试依赖同一测试文件结构。

- [x] **Step 1: 写失败测试（追加到 test_inspect_history.py 的 InspectHistoryTest 类内）**

```python
    def test_empty_repo_reports_no_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            run(["git", "init", "-q", "--initial-branch=main", str(work)], cwd=tmp)
            proc = subprocess.run(
                ["python3", str(INSPECTOR)],
                cwd=work,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("no commits yet", proc.stderr)

    def test_detached_head_is_flagged_as_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            run(["git", "init", "-q", "--initial-branch=main", str(work)], cwd=tmp)
            run(["git", "config", "user.email", "test@example.com"], cwd=work)
            run(["git", "config", "user.name", "Test User"], cwd=work)
            (work / "a.txt").write_text("one\n")
            run(["git", "add", "a.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "one"], cwd=work)
            (work / "a.txt").write_text("two\n")
            run(["git", "commit", "-q", "-am", "two"], cwd=work)
            run(["git", "checkout", "-q", "--detach", "HEAD"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json", "--base", "HEAD~1"],
                cwd=work,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertEqual(report["branch"], "(detached HEAD)")
            self.assertTrue(
                any(risk.startswith("detached HEAD") for risk in report["risks"]),
                report["risks"],
            )
```

- [x] **Step 2: 运行测试确认失败**

Run: `python3 skills/git-history-rewrite/tests/test_inspect_history.py -v`
Expected: `test_empty_repo_reports_no_commits` FAIL（当前 stderr 是 `git rev-parse --short HEAD failed: fatal: ...`，不含 "no commits yet"）；`test_detached_head_is_flagged_as_risk` FAIL（risks 中无 detached HEAD 条目）；原有测试 PASS。

- [x] **Step 3: 实现守卫**

在 `inspect()` 中 work-tree 检查之后（`raise SystemExit("not inside a Git work tree")` 之后、`branch = ...` 之前）插入：

```python
    if not git("rev-parse", "--verify", "--quiet", "HEAD").ok:
        raise SystemExit("repository has no commits yet; nothing to rewrite")
```

在 risks 构建块（`risks: list[str] = []` 之后、`if dirty:` 之前）插入：

```python
    if branch == "(detached HEAD)":
        risks.append("detached HEAD; determine the intended branch and base explicitly before rewriting")
```

- [x] **Step 4: 运行测试确认通过**

Run: `python3 skills/git-history-rewrite/tests/test_inspect_history.py -v`
Expected: 3 个测试全部 PASS。

（本 task 不单独 commit，与 Task 2、3 合并为一个 commit。）

---

### Task 2: git-history-rewrite — 补 3 个场景测试（merge in range / behind upstream / no upstream）

这三个场景的检测逻辑已存在于 `inspect_history.py`（134-147 行），只是没有测试覆盖。本 task 只加测试，预期直接通过；若不通过则说明发现了真 bug，按 systematic-debugging 处理。

**Files:**
- Test: `skills/git-history-rewrite/tests/test_inspect_history.py`

**Interfaces:**
- Consumes: Task 1 的测试文件结构（`run()` helper、`INSPECTOR` 常量）。

- [x] **Step 1: 追加 3 个测试（同一类内）**

```python
    def _init_repo(self, root: Path) -> Path:
        work = root / "work"
        run(["git", "init", "-q", "--initial-branch=main", str(work)], cwd=root)
        run(["git", "config", "user.email", "test@example.com"], cwd=work)
        run(["git", "config", "user.name", "Test User"], cwd=work)
        (work / "app.txt").write_text("base\n")
        run(["git", "add", "app.txt"], cwd=work)
        run(["git", "commit", "-q", "-m", "base"], cwd=work)
        return work

    def test_merge_commits_in_range_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self._init_repo(Path(tmp))
            run(["git", "checkout", "-q", "-b", "feature"], cwd=work)
            (work / "feat.txt").write_text("feature\n")
            run(["git", "add", "feat.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "feat: add feature"], cwd=work)
            run(["git", "checkout", "-q", "main"], cwd=work)
            (work / "main.txt").write_text("main\n")
            run(["git", "add", "main.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "chore: advance main"], cwd=work)
            run(["git", "checkout", "-q", "feature"], cwd=work)
            run(["git", "merge", "-q", "--no-edit", "main"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json", "--base", "main"],
                cwd=work, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertTrue(report["merge_commits"], report)
            self.assertTrue(any("merge commits" in r for r in report["risks"]), report["risks"])

    def test_behind_upstream_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = self._init_repo(root)
            remote = root / "origin.git"
            run(["git", "init", "-q", "--bare", str(remote)], cwd=root)
            run(["git", "remote", "add", "origin", str(remote)], cwd=work)
            (work / "app.txt").write_text("base\nmore\n")
            run(["git", "commit", "-q", "-am", "feat: more"], cwd=work)
            run(["git", "push", "-q", "-u", "origin", "main"], cwd=work)
            run(["git", "reset", "-q", "--hard", "HEAD~1"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json"],
                cwd=work, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertEqual(report["ahead_behind"], {"behind": 1, "ahead": 0})
            self.assertTrue(any("behind its upstream" in r for r in report["risks"]), report["risks"])

    def test_no_upstream_flagged_and_base_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = self._init_repo(root)
            remote = root / "origin.git"
            run(["git", "init", "-q", "--bare", str(remote)], cwd=root)
            run(["git", "remote", "add", "origin", str(remote)], cwd=work)
            run(["git", "push", "-q", "-u", "origin", "main"], cwd=work)
            run(["git", "checkout", "-q", "-b", "feature"], cwd=work)
            (work / "feat.txt").write_text("feature\n")
            run(["git", "add", "feat.txt"], cwd=work)
            run(["git", "commit", "-q", "-m", "feat: add feature"], cwd=work)
            proc = subprocess.run(
                ["python3", str(INSPECTOR), "--json"],
                cwd=work, check=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            report = json.loads(proc.stdout)
            self.assertIsNone(report["upstream"])
            self.assertEqual(report["base_source"], "merge-base with origin/main")
            self.assertTrue(any("no upstream" in r for r in report["risks"]), report["risks"])
```

注意：`test_behind_upstream_flagged` 在 main 分支上操作且有 upstream，`detect_base` 走 74-77 行的 merge-base 分支，行为已定义，无需关心 base。

- [x] **Step 2: 运行全部测试**

Run: `python3 skills/git-history-rewrite/tests/test_inspect_history.py -v`
Expected: 6 个测试全部 PASS。若有 FAIL，先判断是测试搭建问题还是脚本真 bug，脚本 bug 需修复后再过。

---

### Task 3: git-history-rewrite — SKILL.md 工具箱/树校验/清理策略 + eval 断言 + 提交

**Files:**
- Modify: `skills/git-history-rewrite/SKILL.md`（Step 4/5/6/7 与 Output Format）
- Modify: `skills/git-history-rewrite/evals/evals.json`

**Interfaces:**
- Consumes: Task 1/2 已改的脚本与测试（同一 commit 提交）。

- [x] **Step 1: 替换 SKILL.md Step 5（125-135 行整节）**

原文（从 `### 5. Rewrite with the least surprising tool` 到 `preserve that rule in every rewritten commit.`）替换为：

```markdown
### 5. Rewrite with the least surprising tool

Interactive editors are unavailable in agent environments such as Claude Code and Codex, so
plain `git rebase -i` is a human-terminal-only option. Prefer the non-interactive forms below,
picking the simplest one that preserves intent:

- `git commit --amend` for a single tip fixup.
- `git reset --soft <base>` followed by scoped commits for reordering, squashing, or splitting.
  This is the most general tool. It discards original author dates; say so in the plan when
  that matters.
- `git commit --fixup=<sha>` then `git rebase --autosquash <base>` to fold a fix into an earlier
  commit without touching the rest. Git >= 2.44 runs `--autosquash` non-interactively; on older
  Git use `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <base>` as the equivalent.
- A generated todo file with `GIT_SEQUENCE_EDITOR="cp <todo-file>" git rebase -i <base>` when
  full reorder/reword control is needed without an interactive editor.
- Plain `git rebase -i <base>` only when a human will run it in their own terminal.

Keep chronological order. A later commit may depend on an earlier one; avoid moving commits ahead of their prerequisites just to group by file type.

Commit messages must follow the repository's own convention. If the repo requires bodies or trailers, preserve that rule in every rewritten commit.
```

- [x] **Step 2: Step 4 追加 reflog 兜底说明**

在 `Tell the user the backup ref name in the final report.`（123 行）后追加一行：

```markdown
If the backup ref is ever lost, `git reflog` still records the pre-rewrite HEAD as a last resort.
```

- [x] **Step 3: Step 6 加树一致性硬校验**

在 Step 6 现有验证命令块（`git diff --check <base>..HEAD` 之后、"Also run the most relevant project tests" 段之前）插入：

````markdown
Then run the tree-identity check against the backup ref created in step 4:

```bash
git diff --quiet backup/<ref> HEAD && echo "tree identical" || echo "TREE DIFFERS"
```

A pure history rewrite (squash, reorder, reword) must leave the final tree byte-identical, so
expect `tree identical`. If the tree differs, show `git diff --stat backup/<ref> HEAD`, explain
every difference, and get the user's confirmation before treating the rewrite as verified. An
unexplained difference means restore from the backup ref instead of proceeding.
````

- [x] **Step 4: Step 7 后追加备份清理小节**

在 Step 7 末尾（`fetch and re-evaluate.` 之后、`## Output Format` 之前）插入：

```markdown
### 8. Backup cleanup

Keep the backup ref by default; it is the recovery path if a problem surfaces after push. Include
the cleanup command in the final report instead of deleting anything. When the user explicitly
asks to clean up, list the matches first with
`git branch --list 'backup/<branch>-before-history-rewrite-*'`, then delete with `git branch -D`.
```

同时在 Output Format 模板中 `- Residual risk:` 之前加一行：

```markdown
- Backup cleanup: `git branch -D <backup-ref>` (run once you are confident)
```

- [x] **Step 5: evals.json 补断言**

为 3 个用例各加 `assertions` 字段（对象内 `files` 之前）：

```json
      "assertions": [
        "output includes a backup ref named backup/",
        "proposed target history has 3-4 commits (feature/tests/docs), not a single squash",
        "tree-identity check against the backup ref is run or planned",
        "output never suggests git push --force (force-with-lease only)"
      ],
```

（eval 1 用上面这组；eval 2 用：）

```json
      "assertions": [
        "identifies pushed history as a risk gate and asks for explicit confirmation",
        "rewrite base is the integration branch, not origin/<feature>",
        "creates or proposes a backup ref before rewriting",
        "push uses --force-with-lease and never plain --force"
      ],
```

（eval 3 用：）

```json
      "assertions": [
        "stops before rewriting",
        "names dirty working tree as a blocker",
        "names ambiguous base as a blocker",
        "asks for the minimum clarification instead of guessing"
      ],
```

- [x] **Step 6: 全量验证**

Run: `python3 skills/git-history-rewrite/tests/test_inspect_history.py -v && python3 -c "import json; json.load(open('skills/git-history-rewrite/evals/evals.json')); print('evals.json OK')"`
Expected: 6 测试 PASS + `evals.json OK`。

- [x] **Step 7: 手动端到端验证树校验流程**

在 `/tmp` 建临时仓库、造 3 个 commit、按新 Step 4-6 手工执行一次 soft-reset 重写 + backup ref + `git diff --quiet` 校验，确认命令按文档跑通。

- [x] **Step 8: Commit**

```bash
git add skills/git-history-rewrite
git commit -m "feat(git-history-rewrite): 非交互工具箱与树一致性校验

- rebase -i 降级为人工终端选项，agent 环境改用 soft-reset/autosquash/GIT_SEQUENCE_EDITOR
- 新增树一致性硬校验（git diff --quiet backup HEAD）与备份清理策略、reflog 兜底
- inspect_history.py 补空仓库/detached HEAD 守卫，测试 1->6，evals 补机器可验证断言

验证：python3 tests/test_inspect_history.py 6/6 PASS；临时仓库端到端跑通重写+校验流程。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: technical-proposal-review — 反馈回流修复 + 卫生 + spec 修正

**Files:**
- Modify: `skills/technical-proposal-review/SKILL.md`（Feedback 节，69-71 行）
- Modify: `skills/technical-proposal-review/references/output-template.md`（末尾追加）
- Rename: `skills/technical-proposal-review/materials/private/historical-reviews/` 下 2 个含 U+2049 的文件（git 未追踪，纯本地操作）
- Modify: `skills/technical-proposal-review/materials/private/historical-reviews/index.local.md`（10、13 行，git 未追踪）
- Modify: `docs/superpowers/specs/2026-07-03-self-skills-optimization-design.md`（§3.2 修正）

**Interfaces:** 无跨 task 依赖。

- [x] **Step 1: output-template.md 末尾追加校准节**

在 `## 人工复审重点` 节之后追加：

```markdown
## 校准

在报告最末固定输出这一行（不输出 YAML 反馈块）：

> 校准：对以上 findings 有误报/漏判/措辞不满，直接回一句（如 "P1-02 误报"、"漏了迁移回滚"）即可，我会记录到 feedback/pending/。
```

- [x] **Step 2: SKILL.md Feedback 节替换**

原文（71 行整段 `Do not include the feedback YAML block ...` 到段尾）替换为：

```markdown
Do not include the feedback YAML block in the review output. End every review with the single
calibration line defined in `references/output-template.md`.

Treat any in-session user verdict on findings as a feedback signal — for example "这条不成立",
"这个提得好", "以后别把外链当 P1", or short corrections like "P1-02 误报". When such a signal
appears, draft a feedback entry following `references/feedback-loop.md` and write it to
`feedback/pending/<YYYY-MM-DD>-<short-name>.yaml`, then tell the user it awaits their
confirmation. Only human-approved feedback moves to `feedback/accepted/` and gets folded into
`references/risk-patterns.md`, `references/case-bank.md`, and `references/output-preferences.md`.
```

- [x] **Step 3: 重命名特殊字符文件并更新 index.local.md**

```bash
cd skills/technical-proposal-review/materials/private/historical-reviews
mv "基础平台操作审计-技术方案[04-24 12⁚26]-v1快照.md" "基础平台操作审计-技术方案[04-24-1226]-v1快照.md"
mv "基础平台操作审计-技术方案[04-27 18⁚58]-v2快照.md" "基础平台操作审计-技术方案[04-27-1858]-v2快照.md"
```

然后把 `index.local.md` 第 10、13 行中的旧文件名同步替换为新文件名。
验证：`ls | grep -c "⁚"` 输出 0；`grep -c "⁚" index.local.md` 输出 0。

- [x] **Step 4: 修正 spec §3.2（实施前核实发现的偏差）**

spec 中 `- \`references/output-preferences.md\`：3 条"外链处理"重复规则合并为 1 条（Avoid 列表 11 → 9 条）。` 一行替换为：

```markdown
- ~~合并 output-preferences 重复外链规则~~ 实施前核实：Avoid 列表仅 1 条外链规则（e6b2e37 已完成合并，分析时引用了旧版），无需改动。
```

- [x] **Step 5: 验证与提交**

手动验证路径（spec 要求）：改动后对任一历史方案跑一次评审，确认输出末尾出现校准行；口头说一句 "P2-01 太泛"，确认 skill 提议写入 `feedback/pending/`。此验证在改动落地后的首次真实使用中执行，本次提交前验证文档一致性即可：

Run: `grep -n "校准" skills/technical-proposal-review/references/output-template.md && grep -n "calibration line" skills/technical-proposal-review/SKILL.md`
Expected: 两个命令均命中（模板为中文"校准"，SKILL.md 正文为英文 "calibration line"）。

```bash
git add skills/technical-proposal-review/SKILL.md skills/technical-proposal-review/references/output-template.md docs/superpowers/specs/2026-07-03-self-skills-optimization-design.md
git commit -m "feat(technical-proposal-review): 修复反馈回流 UX

- 评审输出末尾固定一行轻量校准提示，替代已移除的 YAML 反馈块
- 会话内自然语言反馈自动整理为 YAML 写入 feedback/pending/，accepted 仍需人工确认
- 修正 spec：output-preferences 重复规则合并项经核实已在 e6b2e37 完成
- 本地私有材料 2 个含 U+2049 文件名已重命名（git 不追踪）

验证：模板与 SKILL.md 校准行 grep 命中；私有目录特殊字符清零。反馈捕获行为待首次真实评审验证。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: handoff — 快照字段 + 过期判定 + stop 规则 + spec 启发式

**Files:**
- Modify: `skills/handoff/SKILL.md`（6 处编辑：60 行、72-79 行、87-110 行、156-169 行、161 行、250-277 行）

**Interfaces:** 无跨 task 依赖。

- [x] **Step 1: Grounding Steps 第 1 条扩展（60 行）**

原文：

```
1. Check the current repo, cwd, worktree path, branch, and working-tree status when available.
```

替换为：

```
1. Check the current repo, cwd, worktree path, branch, HEAD short SHA, and `git status --short` output when available.
```

- [x] **Step 2: Output Shape 默认模板的 定位/当前状态 区块（87-110 行）**

`## 定位` 区块在 `- branch:` 之后追加两行：

```markdown
- HEAD: <短 SHA>
- 工作区: <clean / git status --short 摘要>
```

- [x] **Step 3: 接手工作协议第 3 条升级（77 行）**

原文：
`3. 不要只相信本交接摘要；先重新确认 repo/cwd/worktree/branch/diff。`
替换为：
`3. 不要只相信本交接摘要；先重新确认 repo/cwd/worktree/branch/diff，并对照包内 HEAD 与工作区快照。发现不一致时视为交接包已过期：停下向发起方确认，不要基于过期快照继续。`

- [x] **Step 4: execute-from-plan 定位块与 spec 启发式（156-169 行）**

定位块替换为：

```markdown
- plan:
- plan 最后改动: <git log -1 --oneline -- <plan path>>
- spec/design:
- spec/design 最后改动: <同上；未提供则省略>
```

Emphasize 列表中原行：
`- if the corresponding spec/design path is not provided or cannot be inferred confidently, mark it as "spec/design: 未提供，接手后先定位" instead of omitting it`
替换为：
`- to infer the spec/design path, check in order: (1) links or "see also" references in the plan file header, (2) DESIGN/SPEC/ARCHITECTURE documents in the plan's own directory, (3) a docs/ search by feature name; if all three miss, mark it as "spec/design: 未提供，接手后向发起方确认" instead of omitting it`

- [x] **Step 5: stop conditions 具象化（161 行）**

原文：
`- stop if the plan requires new dependencies, schema changes, core API signature changes, or broad behavior changes not approved by the user`
替换为：
`- stop on any externally visible behavior change the plan does not spell out: new dependencies, schema changes, API additions or signature changes, permission or auth boundary changes, and default-behavior changes. Implementation choices inside the plan's stated scope (log wording, local code structure) do not require a stop`

- [x] **Step 6: continue-from-context 的 定位 区块同步加快照字段（253-257 行）**

`- branch:` 之后追加：

```markdown
- HEAD: <短 SHA>
- 工作区: <clean / 脏文件列表>
```

- [x] **Step 7: 验证：生成样例包**

用改后的 SKILL.md 生成一份 execute-from-plan 样例交接包（以本仓库当前状态为素材），人工检查：快照字段齐全、包总长仍在 300-700 字、协议第 3 条含过期判定。

- [x] **Step 8: Commit**

```bash
git add skills/handoff/SKILL.md
git commit -m "feat(handoff): 交接包增加 git 状态快照与过期判定

- 定位区块新增 HEAD 短 SHA 与工作区脏文件快照，execute-from-plan 加 plan/spec 最后改动 commit
- 接收方协议升级：快照不一致 = 包过期，停下确认而非继续
- stop conditions 从'broad behavior changes'改为可判定规则（对外可见行为变化一律停）
- spec/design 路径补三步定位启发式

验证：按新模板生成 execute-from-plan 样例包，字段齐全且长度保持 300-700 字。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: business-architecture-diagram — SVG 基础模板

**Files:**
- Create: `skills/business-architecture-diagram/assets/svg-base.svg`

**Interfaces:**
- Produces: 预定义类 `.title` `.subtitle` `.layer-label` `.layer-band` `.card` `.card-title` `.caption` `.arrow` `.accent` `.value-bar` `.value-text`；Task 7-9 的脚本、SKILL.md、evals 均引用该文件路径与类名。

- [x] **Step 1: 创建模板文件（完整内容）**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" font-family="PingFang SC, Microsoft YaHei, sans-serif">
  <style>
    .title       { font-size: 40px; font-weight: 600; fill: #16324F; }
    .subtitle    { font-size: 20px; fill: #6B7A90; text-anchor: end; }
    .layer-label { font-size: 24px; font-weight: 600; fill: #16324F; }
    .layer-band  { fill: #EEF3F9; stroke: #D5DEEA; stroke-width: 1; }
    .card        { fill: #FFFFFF; stroke: #C9D6E4; stroke-width: 1; }
    .card-title  { font-size: 22px; font-weight: 600; fill: #1F3B57; text-anchor: middle; }
    .caption     { font-size: 16px; fill: #5B6B7F; text-anchor: middle; }
    .arrow       { stroke: #8CA3BC; stroke-width: 2; fill: none; marker-end: url(#arrowhead); }
    .accent      { fill: #E8833A; } /* 每图最多 1-2 个焦点元素使用 */
    .value-bar   { fill: #16437E; }
    .value-text  { font-size: 22px; font-weight: 600; fill: #FFFFFF; text-anchor: middle; }
  </style>
  <defs>
    <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8 z" fill="#8CA3BC"/>
    </marker>
  </defs>

  <rect width="1600" height="900" fill="#F7F9FC"/>

  <text x="64" y="88" class="title">业务架构总览（示例标题）</text>
  <text x="1536" y="88" class="subtitle">Business Architecture Overview</text>

  <!-- z-order：层带 -> 连线 -> 卡片，卡片压住连线端点，层带不遮连线 -->
  <!-- 1) 层带与层标签 -->
  <rect x="64" y="136" width="1472" height="180" rx="12" class="layer-band"/>
  <text x="88" y="176" class="layer-label">管理层</text>
  <rect x="64" y="340" width="1472" height="180" rx="12" class="layer-band"/>
  <text x="88" y="380" class="layer-label">执行层</text>
  <rect x="64" y="544" width="1472" height="180" rx="12" class="layer-band"/>
  <text x="88" y="584" class="layer-label">基础设施层</text>

  <!-- 2) 层间连线：走卡片间走廊，不穿卡片 -->
  <path d="M 308 288 L 308 392" class="arrow"/>
  <path d="M 308 492 L 308 596" class="arrow"/>

  <!-- 3) 卡片与文字 -->
  <rect x="88" y="192" width="440" height="96" rx="12" class="card"/>
  <text x="308" y="232" class="card-title">示例节点 A</text>
  <text x="308" y="264" class="caption">一句话职责说明</text>

  <rect x="88" y="396" width="440" height="96" rx="12" class="card"/>
  <text x="308" y="436" class="card-title">示例节点 B</text>
  <text x="308" y="468" class="caption">
    <tspan x="308" dy="0">长说明使用 tspan 换行，</tspan>
    <tspan x="308" dy="20">每行 5-12 个中文字符</tspan>
  </text>

  <rect x="88" y="600" width="440" height="96" rx="12" class="card"/>
  <text x="308" y="640" class="card-title">示例节点 C</text>
  <text x="308" y="672" class="caption">一句话职责说明</text>

  <!-- 底部价值条 -->
  <rect x="64" y="772" width="1472" height="64" rx="12" class="value-bar"/>
  <text x="800" y="812" class="value-text">一句话价值主张：更快交付 · 更低成本 · 可持续演进</text>
</svg>
```

- [x] **Step 2: 验证模板**

Run: `xmllint --noout skills/business-architecture-diagram/assets/svg-base.svg && bash skills/business-architecture-diagram/scripts/render_svg_preview.sh skills/business-architecture-diagram/assets/svg-base.svg`
Expected: xmllint 无输出（通过）；脚本输出 PNG 路径。打开 PNG 人工确认：无裁剪、无文字溢出、箭头不穿卡片。

（与 Task 7-9 合并 commit。）

---

### Task 7: business-architecture-diagram — 预览脚本降级链

**Files:**
- Modify: `skills/business-architecture-diagram/scripts/render_svg_preview.sh`（28-31 行错误分支之前）

**Interfaces:**
- Consumes: 现有 `chrome_bin` 探测循环（17-26 行）。

- [x] **Step 1: 在 macOS 应用探测循环之后、报错分支之前插入**

```bash
if [[ -z "$chrome_bin" ]]; then
  for candidate in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge; do
    if command -v "$candidate" >/dev/null 2>&1; then
      chrome_bin="$(command -v "$candidate")"
      break
    fi
  done
fi

if [[ -z "$chrome_bin" ]] && command -v rsvg-convert >/dev/null 2>&1; then
  rsvg-convert -w 1600 -h 900 "$input_svg" -o "$output_png"
  echo "$output_png"
  exit 0
fi
```

并把 29 行报错文案改为：
`echo "No renderer found. Install Google Chrome/Chromium/Edge or librsvg (rsvg-convert)." >&2`

- [x] **Step 2: 验证**

Run: `bash skills/business-architecture-diagram/scripts/render_svg_preview.sh skills/business-architecture-diagram/assets/svg-base.svg /tmp/svg-base-preview.png && bash -n skills/business-architecture-diagram/scripts/render_svg_preview.sh`
Expected: 输出 PNG 路径（macOS 走 Chrome 分支，行为不变）；`bash -n` 语法检查通过。降级链分支在 Linux 环境的行为靠代码审查确认（本机无法真实触发）。

---

### Task 8: business-architecture-diagram — check_text_overflow.py（TDD）

**Files:**
- Create: `skills/business-architecture-diagram/scripts/check_text_overflow.py`
- Test: `skills/business-architecture-diagram/tests/test_check_text_overflow.py`

**Interfaces:**
- Produces: CLI `python3 check_text_overflow.py <file.svg>`；无问题退出 0 无输出（或 `OK`），发现疑似溢出/悬空引用时逐行打印并退出 1。Task 9 的 SKILL.md 引用此命令。

- [x] **Step 1: 写失败测试**

```python
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_text_overflow.py"

OK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
  <style>.card { fill: #fff; } .card-title { font-size: 20px; text-anchor: middle; }</style>
  <rect x="40" y="40" width="320" height="96" class="card"/>
  <text x="200" y="90" class="card-title">短标题</text>
</svg>
"""

OVERFLOW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
  <style>.card { fill: #fff; } .card-title { font-size: 20px; text-anchor: middle; }</style>
  <rect x="40" y="40" width="120" height="96" class="card"/>
  <text x="100" y="90" class="card-title">这是一个明显超出卡片宽度的超长标题文本</text>
</svg>
"""

BROKEN_REF_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">
  <style>.arrow { stroke: #888; }</style>
  <path d="M0,0 L100,100" class="arrow" marker-end="url(#missing-marker)"/>
</svg>
"""


def run_script(svg_text: str):
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
        f.write(svg_text)
        path = f.name
    return subprocess.run(
        ["python3", str(SCRIPT), path],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


class CheckTextOverflowTest(unittest.TestCase):
    def test_ok_svg_passes(self):
        proc = run_script(OK_SVG)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_overflow_is_reported(self):
        proc = run_script(OVERFLOW_SVG)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("OVERFLOW", proc.stdout)

    def test_missing_marker_ref_is_reported(self):
        proc = run_script(BROKEN_REF_SVG)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing-marker", proc.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: 运行确认失败**

Run: `python3 skills/business-architecture-diagram/tests/test_check_text_overflow.py -v`
Expected: 3 个测试全部 ERROR（脚本文件不存在）。

- [x] **Step 3: 实现脚本**

```python
#!/usr/bin/env python3
"""Heuristic pre-checks for hand-authored diagram SVGs.

Checks:
1. Text overflow: estimated text width (CJK ~= 1.0 em, Latin ~= 0.55 em) vs enclosing rect width.
2. Dangling url(#id) references (markers, gradients) with no matching element id.

Heuristic only: PNG preview remains the final visual judge.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"
CJK_EM = 1.0
LATIN_EM = 0.55
PADDING = 16.0
DEFAULT_FONT_SIZE = 16.0


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_class_styles(root: ET.Element) -> dict[str, dict[str, str]]:
    styles: dict[str, dict[str, str]] = {}
    for style_el in root.iter(f"{SVG_NS}style"):
        css = style_el.text or ""
        for match in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", css):
            cls, body = match.group(1), match.group(2)
            props = styles.setdefault(cls, {})
            for prop in body.split(";"):
                if ":" in prop:
                    key, value = prop.split(":", 1)
                    props[key.strip()] = value.strip()
    return styles


def font_size_of(el: ET.Element, styles: dict[str, dict[str, str]]) -> float:
    raw = el.get("font-size")
    if not raw:
        for cls in (el.get("class") or "").split():
            raw = styles.get(cls, {}).get("font-size")
            if raw:
                break
    if not raw:
        return DEFAULT_FONT_SIZE
    match = re.match(r"([\d.]+)", raw)
    return float(match.group(1)) if match else DEFAULT_FONT_SIZE


def anchor_of(el: ET.Element, styles: dict[str, dict[str, str]]) -> str:
    raw = el.get("text-anchor")
    if not raw:
        for cls in (el.get("class") or "").split():
            raw = styles.get(cls, {}).get("text-anchor")
            if raw:
                break
    return raw or "start"


def est_width(text: str, font_size: float) -> float:
    return sum(CJK_EM if ord(ch) > 0x2E80 else LATIN_EM for ch in text) * font_size


def text_lines(el: ET.Element) -> list[str]:
    tspans = list(el.iter(f"{SVG_NS}tspan"))
    if tspans:
        return [(t.text or "").strip() for t in tspans if (t.text or "").strip()]
    return [(el.text or "").strip()] if (el.text or "").strip() else []


def check(path: str) -> list[str]:
    tree = ET.parse(path)
    root = tree.getroot()
    styles = parse_class_styles(root)
    problems: list[str] = []

    rects = []
    for rect in root.iter(f"{SVG_NS}rect"):
        try:
            rects.append(
                (
                    float(rect.get("x", "0")),
                    float(rect.get("y", "0")),
                    float(rect.get("width", "0")),
                    float(rect.get("height", "0")),
                )
            )
        except ValueError:
            continue

    for text_el in root.iter(f"{SVG_NS}text"):
        try:
            tx = float(text_el.get("x", "0"))
            ty = float(text_el.get("y", "0"))
        except ValueError:
            continue
        size = font_size_of(text_el, styles)
        anchor = anchor_of(text_el, styles)
        enclosing = [
            (x, y, w, h)
            for (x, y, w, h) in rects
            if x <= tx <= x + w and y <= ty <= y + h
        ]
        if not enclosing:
            continue
        # 最小的包含矩形视为所属卡片
        x, y, w, h = min(enclosing, key=lambda r: r[2] * r[3])
        for line in text_lines(text_el):
            width = est_width(line, size)
            if anchor == "middle":
                fits = width / 2 <= min(tx - x, x + w - tx) - PADDING / 2
            elif anchor == "end":
                fits = width <= tx - x - PADDING
            else:
                fits = width <= x + w - tx - PADDING
            if not fits:
                problems.append(
                    f"OVERFLOW: '{line[:24]}' est {width:.0f}px exceeds card w={w:.0f} at ({tx:.0f},{ty:.0f})"
                )

    ids = {el.get("id") for el in root.iter() if el.get("id")}
    svg_text = ET.tostring(root, encoding="unicode")
    for ref in set(re.findall(r"url\(#([\w-]+)\)", svg_text)):
        if ref not in ids:
            problems.append(f"DANGLING REF: url(#{ref}) has no matching element id")

    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_text_overflow.py <file.svg>", file=sys.stderr)
        return 2
    problems = check(sys.argv[1])
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: 运行测试确认通过**

Run: `python3 skills/business-architecture-diagram/tests/test_check_text_overflow.py -v`
Expected: 3 个测试 PASS。

- [x] **Step 5: 对模板自检**

Run: `python3 skills/business-architecture-diagram/scripts/check_text_overflow.py skills/business-architecture-diagram/assets/svg-base.svg`
Expected: `OK`（退出 0）。若报 OVERFLOW，调整模板文本或估宽参数（模板是标定基准）。

---

### Task 9: business-architecture-diagram — SKILL.md 硬规则/自检清单/模板引用 + evals + 提交

**Files:**
- Modify: `skills/business-architecture-diagram/SKILL.md`（Step 3、Step 5、Resources 节）
- Create: `skills/business-architecture-diagram/evals/evals.json`

**Interfaces:**
- Consumes: Task 6 模板路径与类名、Task 8 脚本 CLI。

- [x] **Step 1: SKILL.md Step 3 开头改为模板起步**

在 `### 3. Build the SVG directly` 标题后、`Use a presentation-oriented canvas by default:` 之前插入：

```markdown
Start from `assets/svg-base.svg` and edit it down, instead of writing SVG from scratch. The
template fixes the canvas (1600x900), the class set (`.title`, `.subtitle`, `.layer-label`,
`.layer-band`, `.card`, `.card-title`, `.caption`, `.arrow`, `.accent`, `.value-bar`,
`.value-text`), a
restrained executive palette, and the CJK font fallback chain
(`PingFang SC -> Microsoft YaHei -> sans-serif`). Reuse its classes; avoid inventing per-element
inline styles.
```

并在 `Keep the SVG editable:` 列表后追加硬规则小节：

```markdown
Hard layout rules (they prevent the "AI-generated look" and most iteration churn):

- Snap every coordinate, spacing, and size to multiples of 4.
- One accent color per diagram, on at most 1-2 focal elements.
- Source order: layer bands, then connector lines, then cards — cards sit on top of line endpoints, and bands never cover lines.
- Keep vertical spacing between cards >= 40px; route cross-layer arrows through the corridors
  between cards, never through a card.
- Merge repeated same-direction cross-layer arrows into one trunk line.
- Keep elements with filters or shadows >= 30px away from the viewBox edge to avoid clipping.
```

- [x] **Step 2: SKILL.md Step 5 加脚本预检与 PNG 回读自检**

在 `xmllint --noout diagram.svg` 代码块后追加：

````markdown
Then run the bundled heuristic pre-check (text overflow and dangling `url(#id)` references):

```bash
python3 scripts/check_text_overflow.py diagram.svg
```

Fix reported overflows by adding `tspan` line breaks first, then card height. The check is a
heuristic; the PNG preview remains the final judge.
````

在 `Review the preview for:` 列表末尾追加两项：

```markdown
- labels colliding with lines: offset the label 6-8px first; add a background chip only if that fails
- repeated parallel arrows that should merge into one trunk
```

- [x] **Step 3: Resources 节补两条**

```markdown
- `scripts/check_text_overflow.py`: heuristic text-overflow and dangling-reference pre-check
- `assets/svg-base.svg`: canonical starting template (canvas, classes, palette, CJK font stack)
```

- [x] **Step 4: 创建 evals/evals.json**

```json
{
  "skill_name": "business-architecture-diagram",
  "evals": [
    {
      "id": 1,
      "prompt": "帮我画一张给老板汇报用的业务架构图：我们要把内部的任务平台和新引入的 AI 助手融合。管理层看到的是任务下发和结果审批，执行层是任务编排、AI 助手执行、人工审批与接管，底层是模型服务、消息队列和权限体系。要 PPT 风格，中文。",
      "expected_output": "A 1600x900 executive-style SVG with 3 layers, business language (no raw tech jargon in layer 1), centralized <style> reusing the template classes, and a bottom value bar.",
      "assertions": [
        "xmllint --noout passes on the produced SVG",
        "viewBox is 0 0 1600 900",
        "a <style> block defines/reuses .card and .card-title classes",
        "all labels are real <text> nodes, no path-outlined text",
        "font-family includes PingFang SC with Microsoft YaHei fallback",
        "scripts/check_text_overflow.py exits 0 on the produced SVG"
      ],
      "files": []
    },
    {
      "id": 2,
      "prompt": "画一张技术分解视角的架构图：网关层（认证、限流）、服务层（订单、库存、支付）、数据层（MySQL、Redis、Kafka）。允许出现技术组件名，给架构评审用。",
      "expected_output": "Technical-working style diagram that still uses the template classes and layout rules; component names like Kafka/MySQL allowed.",
      "assertions": [
        "xmllint --noout passes on the produced SVG",
        "uses .layer-band and .card classes from a centralized <style>",
        "coordinates are multiples of 4",
        "scripts/check_text_overflow.py exits 0 on the produced SVG"
      ],
      "files": []
    },
    {
      "id": 3,
      "prompt": "以 assets/svg-base.svg 为底，把执行层示例节点 B 的说明文字换成'基于消息触发的自动化任务编排与人工审批接管机制说明'，文字会超宽，请正确处理换行后交付。",
      "expected_output": "The long caption is wrapped with tspan line breaks (5-12 CJK chars per line) instead of overflowing the card; card height increased only if wrapping alone is insufficient.",
      "assertions": [
        "scripts/check_text_overflow.py exits 0 on the produced SVG",
        "the long caption is split across multiple tspan elements",
        "xmllint --noout passes on the produced SVG"
      ],
      "files": []
    }
  ]
}
```

- [x] **Step 5: 全量验证**

Run:
```bash
xmllint --noout skills/business-architecture-diagram/assets/svg-base.svg \
  && python3 skills/business-architecture-diagram/scripts/check_text_overflow.py skills/business-architecture-diagram/assets/svg-base.svg \
  && python3 skills/business-architecture-diagram/tests/test_check_text_overflow.py \
  && python3 -c "import json; json.load(open('skills/business-architecture-diagram/evals/evals.json')); print('evals.json OK')"
```
Expected: 全部通过；末行 `evals.json OK`。

- [x] **Step 6: 端到端验证（eval 3 场景手跑一次）**

复制模板、把节点 B 说明换成超长文本、按 SKILL.md 流程修复换行、跑 check 脚本过零、渲染 PNG 人工确认。

- [x] **Step 7: Commit**

```bash
git add skills/business-architecture-diagram
git commit -m "feat(business-architecture-diagram): 沉淀模板与溢出预检，补 evals

- 新增 assets/svg-base.svg 基准模板（类体系/汇报风色板/中文字体栈），Step 3 改为模板起步
- 新增 check_text_overflow.py 启发式预检（估宽溢出 + 悬空引用），附 3 个单测
- 预览脚本加 PATH 浏览器与 rsvg-convert 降级链，兼容云端 Linux
- SKILL.md 写入社区硬规则（4 倍数坐标/单强调色/连线先画/走廊布线）与 PNG 回读自检清单
- 新增 evals（3 用例，断言全部机器可验证）；外部调研结论为保留自研（见 spec 附录）

验证：xmllint + check 脚本对模板过零；单测 3/3 PASS；eval-3 场景端到端手跑通过。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 后置任务（不在本计划内）

- technical-proposal-review iteration-2：按 `materials/private/eval-workspace/iteration-1/analysis.md` 的 5 个 action item 改 eval 并重跑 benchmark。等本计划全部落地后单独执行。
- 仓库级 `sync-links.sh`（新 skill 软链部署脚本）：用户已手工修复 git-history-rewrite 的软链，脚本待有下一个新 skill 时再考虑（YAGNI）。
