# Agent Manager 页面清晰度修订实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 Skills、个人约束和库存列表的视觉结构，为库存增加默认“受管 + 异常”范围及组合筛选。

**Architecture:** 保持现有无框架单页和服务端 schema 不变。库存筛选、排序、摘要和中文映射实现为可导出的纯 JavaScript 函数，DOM 层只负责控件状态与渲染；CSS 使用共享面板、状态和按钮类统一三个页面。

**Tech Stack:** Python 3.11+、`unittest`、浏览器原生 JavaScript、HTML、CSS、Node.js 行为探针、`uv`。

## Global Constraints

- 不修改 CLI、HTTP 路由、JSON schema 或 Skill/Instructions 写入语义。
- 不引入前端框架、构建工具和第三方依赖。
- 库存默认范围为 `source_type === "managed" || flags.length > 0`。
- 刷新库存后保留筛选；所有筛选只作用于已加载数据。
- 真实 HOME apply、旧状态归档和远端 push 不在本计划授权范围内。
- 新提交的 subject、body 和验证说明全部使用中文，type/scope 保持 Conventional Commit 格式。

## File Map

- `tools/agent_manager/web/index.html`：库存摘要、范围、筛选、来源说明和个人约束列标题。
- `tools/agent_manager/web/app.js`：库存映射、摘要、筛选、排序和列表渲染。
- `tools/agent_manager/web/app.css`：共享面板、表格、状态、按钮和响应式布局。
- `tests/test_agent_manager_web.py`：真实 JS 行为与 HTML/CSS 契约测试。

---

### Task 1: 锁定库存分类、筛选和排序语义

**Files:**
- Modify: `tests/test_agent_manager_web.py`
- Modify: `tools/agent_manager/web/app.js`

**Interfaces:**
- Produces: `inventorySourcePresentation(sourceType)` → `{label, description}`
- Produces: `inventoryFlagPresentation(flag)` → `{label, raw}`
- Produces: `inventorySummary(records, visibleRecords)` → `{managed, flagged, total, visible}`
- Produces: `filterInventoryRecords(records, filters)`
- Produces: `sortInventoryRecords(records)`

- [ ] **Step 1: 写来源与异常中文映射失败测试**

使用 `_run_exports` 断言 `managed/plugin/built-in/local-copy/external-link/broken/unknown` 分别显示为“仓库受管/插件提供/工具内置/本地独立/外部链接/无效条目/其他来源”；`duplicate-name/broken-link/invalid-skill:/unknown` 分别显示为“名称重复/链接已失效/Skill 无效/未知标记”。

- [ ] **Step 2: 运行测试确认因函数不存在而失败**

Run: `uv run python -m unittest tests.test_agent_manager_web.AgentManagerWebTests.test_inventory_presentations_use_chinese_labels -v`

Expected: FAIL，包含 `inventorySourcePresentation is not a function`。

- [ ] **Step 3: 实现并导出中文映射函数**

未知枚举必须保留原始值供详情抽屉显示；`invalid-skill:` 使用前缀匹配。

- [ ] **Step 4: 写默认范围、组合筛选、摘要和排序失败测试**

测试数据包含受管正常、受管异常、插件异常、插件正常、本地独立。筛选参数固定为 `{scope, query, tool, source, status}`；scope 支持 `managed-or-flagged/all/managed/flagged`，status 支持 `all/clean/flagged`。搜索字段固定为 name、slug、path、raw_target、resolved_target。排序为异常 → 受管 → 其他，再按名称、工具、路径。

- [ ] **Step 5: 运行测试确认缺少筛选函数**

Run: `uv run python -m unittest tests.test_agent_manager_web.AgentManagerWebTests.test_filter_inventory_records_combines_all_filters tests.test_agent_manager_web.AgentManagerWebTests.test_inventory_summary_and_sorting -v`

Expected: FAIL，指向缺少 `filterInventoryRecords` 或 `inventorySummary`。

- [ ] **Step 6: 实现最小纯函数并导出**

flagged 定义为 `flags.length > 0 || source_type === "broken"`；排序复制数组，不原地修改 payload。

- [ ] **Step 7: 运行完整 Web 测试并提交**

Run: `uv run python -m unittest tests.test_agent_manager_web -q`

Commit: `feat(agent-manager): 增加库存分类与组合筛选`

---

### Task 2: 重构库存页面信息层级

**Files:**
- Modify: `tests/test_agent_manager_web.py`
- Modify: `tools/agent_manager/web/index.html`
- Modify: `tools/agent_manager/web/app.js`
- Modify: `tools/agent_manager/web/app.css`

**Interfaces:**
- Consumes: Task 1 的五个纯函数
- Produces: `state.inventoryRecords`、`state.inventoryScope` 和无参数 `renderInventory()`

- [ ] **Step 1: 写库存控件与可访问性失败测试**

HTML 必须包含 `inventory-summary`、`inventory-result-count`、`inventory-query`、`inventory-tool-filter`、`inventory-source-filter`、`inventory-status-filter`、`inventory-clear-filters`、`inventory-source-legend`。范围按钮使用 `data-inventory-scope`，值为 `managed-or-flagged/all/managed/flagged`，默认按钮 `aria-pressed="true"`。

- [ ] **Step 2: 运行测试确认控件缺失**

Run: `uv run python -m unittest tests.test_agent_manager_web.AgentManagerWebTests.test_inventory_view_explains_and_filters_records -v`

Expected: FAIL，指出新控件不存在。

- [ ] **Step 3: 增加摘要、范围、筛选、来源说明和六列表头**

表头固定为 Skill、来源、工具、状态、路径、操作。来源说明使用原生 `<details>`，不增加弹窗。

- [ ] **Step 4: 写控件联动与清除筛选失败测试**

断言刷新只替换原始记录并保留筛选；空结果显示“当前筛选下没有库存记录。”；清除恢复默认范围、空搜索和其余 `all`。

- [ ] **Step 5: 实现控件、摘要与表格渲染**

摘要动态显示受管、异常、当前结果和全部数量；来源与 flag 使用中文映射；详情抽屉保留原始值；操作列显示“查看详情”。

- [ ] **Step 6: 增加库存布局 CSS**

新增 `.data-panel`、`.list-toolbar`、`.segmented-control`、`.status-badge`、`.table-action`；路径单行省略；受管行使用蓝色 route rail，异常行使用橙色 route rail；窄屏筛选改为单列。

- [ ] **Step 7: 运行 Web 测试并提交**

Run: `uv run python -m unittest tests.test_agent_manager_web -q`

Commit: `feat(agent-manager): 重构库存页面信息层级`

---

### Task 3: 统一 Skills 与个人约束列表布局

**Files:**
- Modify: `tests/test_agent_manager_web.py`
- Modify: `tools/agent_manager/web/index.html`
- Modify: `tools/agent_manager/web/app.js`
- Modify: `tools/agent_manager/web/app.css`

**Interfaces:**
- 保留现有 button id、详情抽屉、错误定位、preview handler 和 HTTP body

- [ ] **Step 1: 写共享布局失败测试**

断言 Skills 使用 `.skill-identity`、`.skill-description-clamped`、`.route-status-button`；个人约束存在 `.instruction-grid-header`，列标题为目标、加载位置、覆盖工具、状态、操作；操作按钮使用 `.compact-action`；三个页面共同使用 `.data-panel`。

- [ ] **Step 2: 运行测试确认旧页面失败**

Run: `uv run python -m unittest tests.test_agent_manager_web.AgentManagerWebTests.test_management_lists_share_alignment_contract -v`

Expected: FAIL，指出共享布局类缺失。

- [ ] **Step 3: 调整 Skills 和个人约束渲染**

Skills 首列只展示复选框、名称、slug 和一行描述；工具列使用等宽状态/查看按钮。个人约束增加五列表头，三类 preview 按钮等宽靠右；Copilot Desktop 使用同一网格。

- [ ] **Step 4: 统一按钮、行高和响应式 CSS**

列表操作统一 32px 高；表格单元格垂直居中；长描述和路径不撑高；小于 900px 时个人约束改为单列并显示字段标签。

- [ ] **Step 5: 运行全量验证并提交**

Run:

```bash
uv run python -m unittest tests.test_agent_manager_web -q
uv run python -m unittest tests.test_agent_manager_http -q
uv run python -m unittest discover -s tests -p 'test_*.py' -q
git diff --check
uv lock --check
node --check tools/agent_manager/web/app.js
```

Commit: `feat(agent-manager): 统一管理列表与操作布局`

---

### Task 4: 浏览器验收与最终历史检查

**Files:**
- No product file changes expected

- [ ] **Step 1: 使用真实 HOME 采集只读清单**

记录 75 个 Skill 目标、5 个 Instructions 目标和 manager state roots。

- [ ] **Step 2: 启动临时服务并检查四个视图**

Run: `uv run agent-manager serve --open`

确认库存默认“受管 + 异常”，所有筛选有效，三类列表列与按钮对齐，页面无 console error/warning。只执行 preview/cancel。

- [ ] **Step 3: 比较验收前后清单并停止服务**

Expected: 除捕获时间外逐字段一致，真实 HOME 零写入。

- [ ] **Step 4: 检查最终提交历史**

Run: `git log --reverse --format='%h %s' 2e4e7a6..HEAD`

Expected: 所有 subject/body/验证说明为中文，type/scope、BREAKING CHANGE 和 Codex trailer 保留；不 push，不 apply。
