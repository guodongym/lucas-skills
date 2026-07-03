# 自研 Skills 优化设计

日期：2026-07-03
状态：已与用户逐项讨论定案，待 review
范围：4 个自研 skill（git-history-rewrite、handoff、technical-proposal-review、business-architecture-diagram）。wps365 为外部来源，明确排除。

## 背景

对 5 个非上游同步 skill 做了深度分析（5 个并行分析 agent + 关键结论人工核实），主要发现：

- git-history-rewrite：主推工具 `git rebase -i` 在 Claude Code/Codex 中不可用（交互式标志被禁）；预检脚本在空仓库崩溃、detached HEAD 无告警；测试仅 1 例；重写后验证依赖模型自觉，无机械判定。
- handoff：交接包缺新鲜度锚点（无 HEAD SHA、脏文件快照），接收方无法区分"包过期"与"自己看错"；execute-from-plan 的停止条件 "broad behavior changes" 不可判定。
- technical-proposal-review：反馈闭环停滞 67 天（2026-04-27 后无新反馈），根因确认为"评审在用但懒得给反馈"（回流 UX 问题）；iteration-2 已规划未执行。
- business-architecture-diagram：无 evals；样式约定停留在 prose，无模板沉淀；文本溢出只能渲染 PNG 后人眼检查。经外部调研确认无可替代的开源同类（详见附录），保留自研并借鉴社区机制。

## 一、git-history-rewrite（方案 B + 安全增强）

### 1.1 SKILL.md Step 5：非交互工具箱替代 `rebase -i`

`git rebase -i` 降级为"仅限人工终端"备注。agent 环境主推：

1. `git commit --amend` — 仅改 tip（保持现状）。
2. `git reset --soft <base>` + 分段重建 — 最通用（重排/合并/拆分），代价是丢弃原 author date。
3. `git commit --fixup=<sha>` + `git rebase --autosquash <base>` — 把修补折进历史中间的 commit，不动其他 commit。Git ≥ 2.44 原生支持非交互 `--autosquash`；旧版本用 `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <base>` 等价替代。
4. todo 文件 + `GIT_SEQUENCE_EDITOR="cp <todo>"` 的脚本化 rebase — 完整重排/reword 控制。

### 1.2 Step 6：树一致性硬校验（新增安全机制）

纯历史重写不改变最终文件树，因此在验证步骤加机械判定：

```bash
git diff --quiet backup/<ref> HEAD   # 退出码 0 = 重写前后内容逐字节一致
```

规则：默认期望 diff 为空；非空时（如用户要求丢弃某 commit）必须逐条解释差异并获用户确认后才算验证通过。

### 1.3 备份清理策略（新增）

- 默认保留 backup ref，最终报告附清理命令 `git branch -D backup/<ref>`。
- 用户明确要求"清理备份"时，按命名模式定位该分支的备份并删除。
- Step 4 补一句 reflog 兜底说明（backup ref 丢失仍可用 `git reflog` 恢复）。

### 1.4 脚本守卫与测试

- `inspect_history.py`：空仓库（无 HEAD）时优雅输出提示而非崩溃；detached HEAD 加入 risks 列表。
- 测试从 1 例扩到 5 例：空仓库、detached HEAD、range 含 merge、落后 upstream、无 upstream。
- `evals/evals.json` 3 个用例补机器可验证断言（含 "force-with-lease"、不含 "git push --force"、含 backup ref 名等）。

验证路径：`pytest tests/` 全绿；在临时仓库手动跑一次完整重写流程确认树一致性校验生效。

## 二、handoff（方案 B）

### 2.1 Git 状态快照与过期判定

- `定位` 区块新增字段：`HEAD: <短 SHA>`、`工作区: clean / 脏文件列表`。
- execute-from-plan 路由额外加：`plan/spec 最后改动: <git log -1 --oneline -- 路径>`。
- 接收方协议第 3 条升级："对照包内快照重新确认现场；不一致 = 包已过期，先停下向发起方确认，不要猜。"

### 2.2 stop conditions 具象化

execute-from-plan 中 "broad behavior changes" 替换为可判定规则：

> plan 未写明的对外可见行为变化（新增/修改 API、schema、权限、默认行为）一律停；plan 范围内的内部实现选择（日志文案、局部结构）继续。

### 2.3 spec/design 定位启发式

execute-from-plan 补 3 步搜索顺序：① plan 文件头的链接/引用 → ② plan 同目录的 DESIGN/SPEC/ARCHITECTURE.md → ③ `docs/` 下搜索 → 均无则标"未提供，向发起方确认"。

明确不做（讨论中砍掉）：存档落盘约定（用户为一次性粘贴用法）、发起方验收清单（返回时原会话通常已关闭）、fixture 端到端 evals、多平台适配（实际只在 Claude Code 与 Codex 间交接）。

验证路径：改动后生成一份 execute-from-plan 交接包样例，检查快照字段齐全、总长仍在 300-700 字目标内。

## 三、technical-proposal-review（方案 A，iteration-2 后置）

### 3.1 反馈回流修复（根因：评审在用、反馈懒得给）

- 输出末尾固定加一行轻量校准提示（非 YAML 块）：
  > 校准：对以上 findings 有误报/漏判/措辞不满，直接回一句（如 "P1-02 误报"、"漏了迁移回滚"）即可，我会记录到 feedback/pending/。
- SKILL.md 新增会话内自然反馈捕获规则：用户对 findings 的任何表态（"这条不成立"、"这个提得好"、"以后别把外链当 P1"）视为反馈信号，skill 主动整理成 feedback-loop YAML 并写入 `feedback/pending/`。安全性由既有 pending → accepted 人工确认门槛保证。

### 3.2 卫生

- `references/output-preferences.md`：3 条"外链处理"重复规则合并为 1 条（Avoid 列表 11 → 9 条）。
- `materials/private/historical-reviews/` 下 2 个含 U+2049（`⁚`）的文件名改为正常字符，同步更新 `index.local.md`（纯本地文件，git 无感知）。

### 3.3 明确不做

- risk-patterns 按 scope 拆分：与 skill 自身 "Review Scope Rule"（域标签只加检查、永不缩小范围）冲突，且 333 行加载成本可接受；文件超过约 600 行时再评估"全局常驻 + 域模式追加"拆法。
- 案例时效性标注：8 个案例均在 3 个月内，无过期压力。

后置项：iteration-2（按 `materials/private/eval-workspace/iteration-1/analysis.md` 的 5 个 action item 改 eval 并重跑 benchmark），等本轮 4 个 skill 改动全部落地后统一执行，一次验证所有改动。

验证路径：改 SKILL.md 后跑一次真实方案评审，确认输出末尾出现校准提示行、口头反馈能落到 pending/。

## 四、business-architecture-diagram（方案 B+C + 社区借鉴）

外部调研结论：保留自研，不替换（无同类开源 skill 覆盖"中文汇报语境 + 业务语言归一化 + 管理层受众"；社区最强同类 fireworks-tech-graph 与本 skill 技术选型一致，验证了手写 SVG 路线）。

### 4.1 模板沉淀

新增 `assets/svg-base.svg`：1600×900 画布，标题栏/三层架构区/底部价值条骨架，集中 `<style>` 预定义类（`.title` `.layer-label` `.card` `.card-title` `.caption` `.arrow` `.value-bar`），汇报风色板（具体色值），中文字体栈（`PingFang SC → Microsoft YaHei → sans-serif`）。SKILL.md Step 3 改为"从模板起步，删改而非从零写"。模板即输出示例，不在 SKILL.md 内嵌大段代码。

### 4.2 脚本增强

- `render_svg_preview.sh` 加降级链：现有 macOS 应用路径 → PATH 上的 `google-chrome`/`chromium` → `rsvg-convert`，兼容云端 Linux 环境。
- 新增 `scripts/check_text_overflow.py`（仅标准库的小型脚本）：字符宽度启发式（CJK ≈ 1.0em、拉丁 ≈ 0.55em）估算 text/tspan 宽度，对比所在卡片 rect 宽度，输出疑似溢出列表；同时校验悬空 `url(#id)` 引用（marker 等）。定位为预检，PNG 预览仍是最终判定。

### 4.3 社区借鉴的硬规则（写入 SKILL.md）

来源：fireworks-tech-graph、diagram-design、Cocoon-AI（详见附录）。

- PNG 回读自检清单：箭头走框间走廊不穿框；标签重叠先偏移 6-8px 再考虑底衬；同层箭头留 gutter；跨层重复箭头合并为一条下沉轨；带 filter 元素距 viewBox 边缘 ≥30px。
- 坐标/间距/宽度取 4 的倍数；强调色每图仅 1-2 个焦点元素。
- 先画连线后画框（线在框后）；组件垂直间距 ≥40px；图例放边界框外。

明确不做：增加 UML/时序图等技术图类型（稀释汇报定位，且为 fireworks-tech-graph 已占领域）。

### 4.4 evals

新增 `evals/evals.json`：3 个用例（中文汇报风 3 层图 / 技术分解图 / 迭代修改换行），断言机器可验证：`xmllint` 通过、viewBox 1600×900、存在集中 `<style>` 且使用预定义类、真实 text 节点、含中文字体栈。

验证路径：用 3 个 eval 用例各跑一次生成，断言脚本全过；`check_text_overflow.py` 对一个故意溢出的样例能报出。

## 实施顺序与工作量

| 顺序 | 内容 | 预估 |
|---|---|---|
| 1 | git-history-rewrite（缺陷修复优先，已上线） | 1-2 小时 |
| 2 | technical-proposal-review（改动最小） | 0.5 小时 |
| 3 | handoff | 0.5-1 小时 |
| 4 | business-architecture-diagram（新文件最多） | 2-3 小时 |
| 5 | technical-proposal-review iteration-2（后置，统一验证） | 半天 |

每个 skill 独立提交（`feat(<skill-name>): ...`），互不依赖，可分批 review。

## 附录：business-architecture-diagram 外部调研摘要

- 相邻项目：fireworks-tech-graph（手写 SVG，技术图定位，6k+ stars）、diagram-design（英文技术写作场景）、Cocoon-AI architecture-diagram-generator（暗色工程风 HTML）、Daves-Claude-Code-Skills（ELK.js 自动布局）。anthropics/skills 官方无 diagram 类 skill。
- DSL 路线（Mermaid/D2/PlantUML/Excalidraw/draw.io）均为自动布局或非演示美学，无法满足"演示级 + 像素级可控"，验证了手写 SVG 选型。
- 社区做到演示级的项目全部采用手写 SVG 路线。
