# Antigravity 统一管理恢复设计

- 日期：2026-11-19
- 状态：已获用户确认（方案 1 + 纳入内置 Skill 库存 + 合入 `main` 后执行真实 HOME preview → apply）
- 结论：在 `agent-manager` 中按 Antigravity 2.0 与 `agy` v1.5.4 的当前统一目录规范恢复 Antigravity 支持，收敛为与 Claude / Codex / Copilot 对称的单共享 Skill 适配器（`antigravity-shared` → `~/.gemini/config/skills`）和独立全局指令目标（`antigravity` → `~/.gemini/GEMINI.md`），同时在 `doctor` 只读库存中纳入内置技能目录并按 `config.json` + `plugin.json` 规则过滤已禁用插件；不恢复 WorkBuddy、旧 CLI 合成插件容器或历史桥接代码。

## 1. 背景与现场核实

`v0.6.0`（提交 `d81c9db`）曾移除 Antigravity 与 WorkBuddy 支持，此后 `tools/agent_manager/` 未发生代码变更。2026-11-19 的只读现场检查确认：

- Desktop：`/Applications/Antigravity.app` 已安装；
- CLI：`/Users/zhaoguodong/.local/bin/agy` 已安装，版本 `1.5.4`；
- 统一配置目录：`agy plugin list --json` 实际返回的路径全部位于 `~/.gemini/config/plugins/*`，与内置文档 `agy-customizations/SKILL.md` 一致，确认 Antigravity Desktop 与 `agy` CLI 已共用 `~/.gemini/config/`；
- 全局 Skills：`~/.gemini/config/skills/` 已存在且为空目录；仓库 `skills/` 当前 20 个 Skill 与本机已加载的内置技能、`superpowers`、`chrome-devtools-plugin` 零重名冲突；
- 全局规则：`~/.gemini/GEMINI.md` 当前缺失，本仓库 `AGENTS.md` 为 12,605 字节，低于 Antigravity 24,000 字节单文件上限，且 Antigravity 按真实解析路径去重；
- 插件启用态：`~/.gemini/config/config.json` 的 `plugins` 映射以**安装目录名**为键，且默认启用插件可能省略 `"enabled"` 字段（例如本机 `superpowers` 仅含 `installedFrom`）；
- 内置技能：`~/.gemini/antigravity/builtin/skills`（15 项）与 `~/.gemini/antigravity-cli/builtin/skills`（13 项）均含合法 YAML frontmatter。

## 2. 目标与非目标

### 2.1 目标

1. 恢复 Antigravity 工具族，使 `agent-manager` 统一管理 Claude、Codex、GitHub Copilot、Antigravity 四个工具族、八个检测表面。
2. 以单共享适配器 `antigravity-shared` 将仓库 `skills/<slug>` 软链到 `~/.gemini/config/skills/<slug>`，同时覆盖 Desktop 与 `agy` CLI。
3. 以 `antigravity` Instructions 目标将仓库 `AGENTS.md` 软链到 `~/.gemini/GEMINI.md`，保持原有 preview / fingerprint / 快照 / 原子替换 / 回滚契约。
4. 在 `doctor` 与 `/api/inventory` 只读库存中准确扫描 Antigravity 用户目录、Desktop/CLI 内置技能目录，以及**已启用**的用户/市场插件技能目录；对损坏的 `config.json`、损坏的 `plugin.json` 或越界 `skills` 软链返回结构化 `ScanIssue`，不中断其余扫描。
5. 同步更新 CLI、HTTP 服务、Web 控制台、单元测试和 `README.md`。

### 2.2 非目标

- 不恢复 WorkBuddy 支持。
- 不恢复旧 `antigravity-cli` 独立适配器、`~/.gemini/antigravity-cli/plugins/lucas-skills/` 合成插件清单（`manifest_path` / `manifest_content`）或扁平 `.md` 扫描（`flat_markdown`）。
- 不恢复已退役的 `BridgeRemoval`（`custom-skills/skills` 转接）与 `~/.gemini/skills` 历史遗留根。
- 不把 Antigravity 挂接到 `shared`（`~/.agents/AGENTS.md`），避免将项目级目录约定误显示为 Antigravity 全局规则路由。
- 不修改 `~/.gemini/config/config.json` 或管理 Antigravity 插件的启停、安装与卸载。

## 3. 适配矩阵与核心设计

### 3.1 Skills 适配器与表面检测

- `build_adapters(home)` 新增：
  - `TargetAdapter("antigravity-shared", "antigravity", home, home / ".gemini/config/skills", ("antigravity-desktop", "antigravity-cli"))`
- `detect_surfaces()` 新增：
  - Desktop：`"antigravity-desktop": (applications / "Antigravity.app",)`
  - CLI：`"antigravity-cli": "agy"`

### 3.2 Instructions 目标

- `_TARGETS` 新增：
  - `("antigravity", ".gemini/GEMINI.md", ("antigravity-desktop", "antigravity-cli"))`
- `shared`（`~/.agents/AGENTS.md`）的 `surfaces` 保持不变，不包含 `antigravity-*`。

### 3.3 只读库存扫描与插件启用态过滤

1. `_fixed_inventory_sources(home)` 新增 3 项：
   - `~/.gemini/config/skills` → tools `("antigravity",)`，surfaces `("antigravity-desktop", "antigravity-cli")`，type `"user-root"`
   - `~/.gemini/antigravity/builtin/skills` → tools `("antigravity",)`，surfaces `("antigravity-desktop",)`，type `"built-in"`
   - `~/.gemini/antigravity-cli/builtin/skills` → tools `("antigravity",)`，surfaces `("antigravity-cli",)`，type `"built-in"`
   - Desktop 与 CLI 内置目录分别归属各自 surface，避免同一内置 Skill 在 `duplicate_counts` 中与自身误报重名，同时可准确检测仓库 Skill 与任一表面内置 Skill 的重名。
2. 新增 `_enabled_antigravity_plugin_sources(home)`：
   - 扫描 `~/.gemini/config/plugins/` 一级子目录（忽略隐藏项与非目录）。
   - 若 `~/.gemini/config/config.json` 存在（按 `lexists` 探测），读取其 `plugins` 对象；若 `config.json` 为失效软链/非普通文件、读取或 JSON 解析失败、顶层非对象或 `plugins` 非对象（且非 `null`），记录 `ScanIssue("antigravity-config-invalid", config_path, ...)` 并返回空来源列表。
   - 按官方插件清单顺序以 `lstat` 探测：`plugin.json`、`.antigravity-plugin/plugin.json`、`.gemini-plugin/plugin.json`；三者均不存在的目录视为非插件并跳过；若探测遇到权限等 `OSError`，记录 `ScanIssue("plugin-manifest-invalid", ...)` 并继续扫描其余插件。
   - 清单读取前校验解析路径未逃逸插件根目录且为普通文件，并按 JSONC（在保留双引号字符串的前提下剥离 `//`、`/* ... */` 注释与合法尾随逗号）解析，损坏或越界清单记录 `ScanIssue("plugin-manifest-invalid", manifest_path, ...)` 并继续扫描其余插件。
   - 启用态判定严格遵循 Antigravity 规则：若 `config.json` 中 `plugins[dir_name].enabled` 为显式布尔值，则以该值为准；否则以 `manifest.get("disabled") is not True` 为准（默认启用）。
   - 已启用插件若不含 `skills` 子目录则静默跳过（例如纯规则/MCP 插件）；若存在 `skills` 目录但解析路径逃逸插件根目录，记录 `ScanIssue("plugin-skills-path-invalid", manifest_path, ...)` 并跳过。
   - 合法 `skills` 目录返回 `InventorySource(skills_root, ("antigravity",), ("antigravity-desktop", "antigravity-cli"), "plugin")`。
3. 新增 `_enabled_plugin_sources(home)` 汇总 Codex 与 Antigravity 插件来源及 `ScanIssue`，由 `scan_inventory`、CLI `doctor` 与 HTTP `/api/inventory`（通过 `_doctor_issues`）统一复用。

### 3.4 CLI、HTTP 与 Web 控制台

- `cli.py` 与 `server.py`：
  - `TOOLS = ("claude", "codex", "copilot", "antigravity")`
  - `INSTRUCTION_TARGETS = ("shared", "claude", "codex", "copilot", "antigravity")`
- `web/app.js`：`TOOL_FAMILIES` 新增 `{ key: "antigravity", label: "Antigravity" }`，`renderSkills` 空态 `colspan` 更新为 `"5"`。
- `web/index.html`：批量工具下拉框、Skills 表头与初始 `colspan="5"`、库存工具筛选下拉框均补入 `Antigravity`。

## 4. 验证计划

1. **TDD 单元与集成测试**：覆盖适配器、表面检测、Instructions 扫描/计划/原子应用/回滚、JSONC 清单与禁用插件过滤、越界路径拒绝、CLI/HTTP 参数白名单与契约对齐、Web 拓扑与表格渲染、`README.md` 合同检查。
2. **全量回归**：运行完整 `unittest` 套件、`uv lock --check`、`git diff --check` 及独立代码审查。
3. **合入 `main` 后真实 HOME 落地**（已获用户授权）：
   - 先运行只读 `status --json`、`doctor --json`、Skills `set --all --tool antigravity --on --json` preview 与 Instructions `set --target antigravity --on --json` preview；
   - 核对无冲突后执行对应 `--apply`（Instructions 携带精确 `--expect-fingerprint`）；
   - 回读 `status --json`、`doctor --json` 并确认软链目标、零新增错误及 `agy` 侧状态正常。
