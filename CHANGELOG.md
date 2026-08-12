# 更新日志

本文件记录 lucas-skills 的重要版本变更。

`0.x` 阶段的版本规则：新增可见 Skill、Agent Manager 能力或工作流行为时递增 minor；patch 仅用于不新增产品行为的缺陷修复、测试、文档和内部维护。

## 编写规范

版本按时间倒序记录，并按“定位、分类变更、验证、关联文档”组织；同一版本中优先说明用户可见行为和兼容性边界。

---

## [v0.5.1] - 2026-08-12

**定位**：修复 `professional-writing` 的触发边界，在保留独立技术方案写作与正式汇报召回的同时，避免它抢占已有设计、开发或治理流程的文档产物。

### 🐛 触发边界修复

* 路由改为判断正式文档是否为当前主要交付物；单独要求从零撰写技术方案、总结、复盘、进展汇报或重写已有正式文档时继续触发。
* 用户明确要求继续或按原设计、开发、治理流程生成其必需的 `spec`、`plan` 或 `design doc` 时，不加载 `professional-writing`；显式点名或指定组合顺序仍按用户要求执行。
* 正文写作流程、参考资料和已有内容评测保持不变。

### 🧪 验证

* 新增 20 条触发路由矩阵：10 条应触发、10 条不应触发，覆盖从零技术方案、正式汇报、已有流程产出设计文档、方案评审和显式组合等近邻场景。
* `professional-writing` 合同测试 2/2 通过；仓库测试 286/286 通过。
* `quick_validate.py`、两个评测 JSON 解析与 `git diff --check` 均通过。

### 📄 关联文档

* [professional-writing 触发边界设计](docs/superpowers/specs/2026-08-12-professional-writing-trigger-boundary-design.md)
* [professional-writing 触发边界实施计划](docs/superpowers/plans/2026-08-12-professional-writing-trigger-boundary.md)

---

## [v0.5.0] - 2026-08-11

**定位**：新增 Codex 专用的 `review-and-release-pr` 薄编排 Skill，把需求合理性、已有 review、独立代码审查、授权修复和发布收尾串成一条证据门禁流程；同时收紧 Agent 面向用户说明时的中文优先规则。

### ✨ 新 Skill

* `review-and-release-pr` 在实现审查前先用第一性原理判断 PR 需求；需求不合理、证据不足或需要新决策时进入 `STOP`。
* 运行状态保持为 `PASS / FIX / STOP`，复用现有方案评审、评论处理、代码审查、调试、TDD、完成验证和发布 Skills，不新增工作流引擎或持久状态。
* v0.1 只支持 Codex；普通代码审查、方案审查、评论处理、单点 Bug 修复和 release-only 请求继续路由到各自现有 Skill。

### 🛡️ 门禁、GitHub 与授权边界

* 已有 reviewer 结论与独立 `code-change-review` 保持分离；P0/P1 始终阻止合并，只有修法明确、范围受控且已有修复授权的问题才能在披露后进入 `FIX`，修完必须重新独立评审。
* Connector 无法读取目标私有仓库但身份健康时记录 `connector_scope_gap`，可锁定到已认证的 `gh`；不会自动登录、刷新凭据或修改 GitHub App 安装范围。
* PR 评论、代码修复、push、合并、tag/Release、生产操作和 cleanup 分别授权，不能从一个动作推断另一个动作。

### 🗣️ Agent 交互规则

* 面向用户的普通说明默认使用自然中文，技术标识符、命令、路径、日志和报错保持原文，并在首次影响理解时补充中文含义。
* 代码、命令、原文引用和英文仓库交付物继续保持原有语言，不为中文可读性破坏机器依赖的精确文本。

### 🧪 验证

* 无 Skill 的 RED 基线证明编排缺口；加载 Skill 后 FIX/STOP 微测 5/5、压力场景 4/4 通过。
* 两个真实 PR 只读演练 2/2 完成；私有 `x-scraper#26` 正确回退到 `gh`、确认 1 个 P1 并在无修复授权时停止，PR、代码和 Git refs 均未改变。
* `uv run python -m unittest discover -s tests -q`：284/284 通过；`review-and-release-pr` 聚焦测试 3/3 通过，最终独立代码评审为 `Ready`。
* `quick_validate.py`、`uv lock --check`、sdist/wheel 构建与 `git diff --check` 均通过；Agent Manager 预览只包含 `codex-shared` 目标且未 apply。

### 📄 关联文档

* [PR 评审发布编排设计](docs/superpowers/specs/2026-08-11-review-and-release-pr-design.md)
* [PR 评审发布编排实施计划](docs/superpowers/plans/2026-08-11-review-and-release-pr.md)

---

## [v0.4.0] - 2026-08-11

**定位**：新增面向真实代码差异的 `code-change-review` Skill，与技术方案评审分工，提供只读、证据优先的缺陷与合并就绪审查。

### ✨ 新 Skill

* 支持 working tree、staged/unstaged、提交范围、当前分支和 PR 等代码变更范围，并在审查前后核对 Git 状态。
* 默认使用第一性原理还原需求、约束和可达路径；只在高风险信号出现时进入对抗性审查。

### 🛡️ 证据与评审边界

* 将已证实缺陷、待确认问题和验证边界分开输出；P0/P1 必须通过影响、现有控制和可逆性的统一证据门禁。
* `technical-proposal-review` 继续负责技术方案/RFC；`code-change-review` 只审查已有代码变更，混合请求可按两个工作流分别处理。
* 对无证据缺陷的变更给出干净 no-op 结论，不为覆盖不足或外部环境不可用臆造产品问题。

### 🧪 验证

* 行为评测 12/12 通过；4 组缺陷/安全对照在去除答案泄漏后重新隔离复测 8/8 通过。
* 路由评测 12/12 通过；只读状态检查 4/4 前后指纹一致；真实提交范围前向测试 1/1 通过。
* `uv run python -m unittest discover -s tests`：280/280 通过。
* `quick_validate.py`、eval JSON、`uv lock --check`、sdist/wheel 构建与 `git diff --check` 均通过。

### 📄 关联文档

* [代码变更评审设计](docs/superpowers/specs/2026-08-10-code-change-review-design.md)
* [代码变更评审实施计划](docs/superpowers/plans/2026-08-10-code-change-review.md)

---

## [v0.3.0] - 2026-08-08

**定位**：将第一性原理与对抗性审查作为 `technical-proposal-review` 的通用推理规则，在保留关键风险识别能力的同时减少机械量化和过度定级。

### ✨ 工作流增强

* 增加第一性原理、对抗性审查和证据控制三条横切规则，覆盖目标与约束还原、可达失败链以及证据充分性判断。
* 增加 P0/P1 出口门：只有现有控制和可逆性无法约束已证实影响时，才能保留高严重级别。

### 🛡️ 评审边界

* 定量决策继续要求指标、基线和阈值；定性决策不再被强制补造数字门槛。
* 评测样本改为自包含输入，并收紧反馈写盘授权、脱敏和跨领域风险模式边界。

### 🧪 验证

* A/B 微测 40 次：定量与关键风险命中保持 5/5；定性强制量化由 5/5 降至 0/5；平均输出减少 15.4%，findings 减少 18.8%。
* 完整 Skill 回归：低风险场景 5/5 通过且 0/5 出现 P0/P1；3 个关键风险场景 3/3 命中。
* `uv run python -m unittest discover -s tests -v`：275/275 通过。
* `quick_validate.py`、eval JSON、accepted YAML 与 `git diff --check` 均通过。

### 📄 关联文档

* [推理增强设计](docs/superpowers/specs/2026-08-08-technical-proposal-review-reasoning-design.md)
* [推理增强实施计划](docs/superpowers/plans/2026-08-08-technical-proposal-review-reasoning.md)

---

## [v0.2.0] - 2026-08-05

**定位**：引入通用中文“活人感”写作 Skill，并将其作为独立上游持续跟踪。

### ✨ 新功能

* 新增 `human-writing` Skill 1.0.0，覆盖现实长文、虚构故事、论坛长帖、口播和演讲稿等通用中文创作与改稿场景。
* 随 Skill 同步 5 份按需加载的写作参考，以及只报告、不自动改稿的 `check_prose.py` 检查器。

### 🛠️ 上游管理

* 新增 `KKKKhazix/human-writing` 独立上游映射，固定首次同步提交 `22d20b67`，后续由每周同步流程检测更新。
* `human-writing` 保持通用写作定位；已有 `khazix-writer` 继续承担卡兹克个人公众号文风生成，两者不合并。

### 🧪 验证

* Skill 结构校验通过，上游文件 10/10 字节一致，重复同步无差异。
* `check_prose.py` 正反例分别以退出码 0/1 返回，反例检出 4 类硬性问题。
* `uv run python -m unittest discover -s tests -v`：275/275 通过。
* `uv lock --check` 与 `uv build` 通过。

### 📄 关联文档

* 无新增关联文档。

---

## [v0.1.1] - 2026-08-02

**定位**：将 WorkBuddy Desktop 纳入 Agent Manager 的 Skill 纳管范围，并保持其自定义指令与 `AGENTS.md` 管理边界分离。

### ✨ 新功能

* 新增 WorkBuddy Desktop Skill 适配器；每个已启用 Skill 以直接符号链接写入 `~/.workbuddy/skills/<skill>`。
* CLI、HTTP API、Web 控制台和库存扫描均支持查看与控制 WorkBuddy Skill 状态。

### 🛠️ 管理边界

* WorkBuddy 的自定义指令保留为应用内手动配置，不写入或接管 `AGENTS.md`。
* 激活仅针对已发现的 WorkBuddy Desktop，且不支持插件或整目录链接。

### 🧪 验证

* `uv run python -m unittest discover -s tests -v`：275/275 通过。
* `uv lock --check` 与 `uv build` 通过。
* 实机激活检查：16/16 个 WorkBuddy Skill 为直接仓库链接，`issues=0`。

### 📄 关联文档

* [WorkBuddy Skill 纳管设计](docs/superpowers/specs/2026-08-02-workbuddy-skill-management-design.md)
* [WorkBuddy Skill 纳管实施计划](docs/superpowers/plans/2026-08-02-workbuddy-skill-management.md)

---

## [v0.1.0] - 2026-08-02

**定位**：提供面向完成态开发分支的轻量发布收尾工作流。

### ✨ 新功能

* 新增 `finishing-a-development-release`，覆盖 worktree 集成、带注释标签、发布平台 Release 与安全清理编排。
* 明确 `neat-freak`、`git-history-rewrite`、`finishing-a-development-branch` 和 `verification-before-completion` 的复用契约。

### 🛠️ 发布工作流

* 发布收尾请求默认从 `neat-freak` 转入专用编排 Skill；文档或治理升级场景除外。
* 清理 worktree 前先分类迁移被忽略和未跟踪的本地配置，并进行等价性检查。

### 📄 关联文档

* 无新增关联文档。
