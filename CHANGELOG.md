# 更新日志

本文件记录 lucas-skills 的重要版本变更。

`0.x` 阶段的版本规则：新增可见 Skill、Agent Manager 能力或工作流行为时递增 minor；patch 仅用于不新增产品行为的缺陷修复、测试、文档和内部维护。

## 编写规范

版本按时间倒序记录，并按“定位、分类变更、验证、关联文档”组织；同一版本中优先说明用户可见行为和兼容性边界。

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
