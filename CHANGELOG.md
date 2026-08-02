# 更新日志

本文件记录 lucas-skills 的重要版本变更。

`0.x` 阶段的版本规则：新增可见 Skill、Agent Manager 能力或工作流行为时递增 minor；patch 仅用于不新增产品行为的缺陷修复、测试、文档和内部维护。

## 编写规范

版本按时间倒序记录，并按“定位、分类变更、验证、关联文档”组织；同一版本中优先说明用户可见行为和兼容性边界。

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
