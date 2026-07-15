# lucas-skills 仓库目录与 CLI 统一设计

**日期：** 2026-07-15
**状态：** 已实施

## 1. 背景与目标

仓库根目录目前同时平铺上游同步工具、全局 Skill 管理器、配置文件、设计文档和一张未引用的评审截图。受 Git 管理的根目录文件数量不算大，但两个工具子系统缺少一致的归属边界，新增全局 Skill 管理器后可读性下降。

本次调整的目标是：

1. 根目录只保留仓库级入口、元数据和主要内容目录。
2. 上游同步与全局 Skill 管理器统一放入 `tools/`，但保持两个独立 CLI。
3. 使用单个 `pyproject.toml` 和 `uv.lock` 管理 Python 版本、依赖、构建和命令入口。
4. 保持现有工具行为、安全边界和真实迁移确认门不变。

## 2. 非目标

- 不把仓库改造成需要发布到 PyPI 的通用包。
- 不把两个职责不同的工具合并成一个 `lucas-skills` 总命令。
- 不重构全局 Skill 管理器或上游同步工具的业务逻辑。
- 不执行真实 `adopt --apply`，也不改写任何 Agent 的全局 Skill 链接。
- 不处理 `doctor` 已识别的外部损坏项或重名 Skill。

## 3. 目标目录结构

```text
lucas-skills/
├── .github/
├── docs/
│   ├── upstream-sync.md
│   └── superpowers/
├── skills/
├── tests/
│   ├── test_project_layout.py
│   ├── test_skill_manager.py
│   └── test_upstream_sync.py
├── tools/
│   ├── __init__.py
│   ├── skill_manager/
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── core.py
│   │   └── web/
│   │       └── index.html
│   └── upstream_sync/
│       ├── __init__.py
│       ├── vendor.py
│       ├── upstream.yml
│       └── upstream.lock.yml
├── .gitignore
├── AGENTS.md
├── LICENSE
├── README.md
├── pyproject.toml
└── uv.lock
```

对应移动关系：

| 当前路径 | 目标路径 |
| --- | --- |
| `skill_manager.py` | `tools/skill_manager/cli.py` |
| `skill_manager_core.py` | `tools/skill_manager/core.py` |
| `skill_manager_web/index.html` | `tools/skill_manager/web/index.html` |
| `vendor.py` | `tools/upstream_sync/vendor.py` |
| `upstream.yml` | `tools/upstream_sync/upstream.yml` |
| `upstream.lock.yml` | `tools/upstream_sync/upstream.lock.yml` |
| `DESIGN.md` | `docs/upstream-sync.md` |
| `img.png` | 删除 |

`img.png` 是一次 `AGENTS.md` 精简评审的对比截图。其有效结论已经写入当前 `AGENTS.md`，图片没有仓库引用且会随规则演进而过时，因此不迁入 `docs/assets/`，也不新增重复说明文档。Git 历史继续保留原图和产生背景。

## 4. Python 项目与依赖

根目录新增 `pyproject.toml`，采用以下项目边界：

```toml
[project]
name = "lucas-skills-tools"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["PyYAML"]

[project.scripts]
skill-manager = "tools.skill_manager.cli:main"
upstream-sync = "tools.upstream_sync.vendor:main"

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-root = ""
module-name = "tools"
```

实现时使用本机 `uv` 0.11+ 生成并提交 `uv.lock`，由 CI 固定的 uv 0.11.28 执行冻结校验。本仓库属于私有应用仓库，`uv run` 以项目环境运行两个入口；不增加发布配置、版本自动化或额外打包工具。

顶层包名固定为 `tools`。这个名称只服务于本仓库的隔离 uv 项目环境，不作为公共 Python 包发布；当前运行依赖 `PyYAML` 不提供同名顶层包，因此接受通用名称带来的局部命名风险，不再增加 `src/` 或 `lucas_tools` 命名层。

`uv run` 默认在仓库根目录创建 `.venv/`。`.gitignore` 必须显式忽略 `.venv/`，避免统一命令体系反而产生新的根目录 Git 噪声；`uv.lock` 仍纳入版本控制。

现有测试只依赖 Python 标准库和运行依赖 `PyYAML`，不创建空的开发依赖组。未来出现真实的测试或 lint 依赖时再加入 `[dependency-groups]`。

## 5. CLI 契约

两个工具统一使用 `uv run`，但保持独立入口和独立帮助：

```bash
uv run skill-manager status
uv run skill-manager doctor
uv run skill-manager set docx --tool codex --on --json
uv run skill-manager adopt --json
uv run skill-manager serve --open

uv run upstream-sync check
uv run upstream-sync diff
uv run upstream-sync sync
uv run upstream-sync sync --upstream anthropics-skills
```

旧命令 `python3 skill_manager.py ...`、`python vendor.py ...` 不保留根目录兼容 shim。README、当前设计文档、测试和 GitHub Actions 中的可执行调用全部切换到新入口，避免长期维护两套命令。已完成的 2026-07-14 spec/plan 保留当时真实执行命令，作为不可改写的历史证据；残留扫描显式排除这两份历史文档。

## 6. 路径解析

目录移动后，工具不得依赖调用者先切换到某个子目录：

- `tools.skill_manager.cli` 从模块文件位置向上解析仓库根目录，再定位根目录下的 `skills/`。
- Skill 管理页面从 `tools/skill_manager/web/index.html` 读取。
- `tools.upstream_sync.vendor` 从自身目录读取 `upstream.yml` 和 `upstream.lock.yml`。
- 上游同步映射中的 `dst` 仍相对仓库根目录解析；配置文件移动不能把目标误解析到 `tools/upstream_sync/skills/`。
- clone 缓存仍位于 `~/.cache/upstream-sync/`，不改变现有缓存与删除策略。

路径解析需要覆盖“从仓库根目录调用”和“入口由 `uv run` 调用”两种方式。工具仍是仓库内应用，不承诺脱离本仓库安装后管理其他目录。

## 7. GitHub Actions

`.github/workflows/sync-upstream.yml` 使用官方 setup action 的 v8.1.0 commit SHA，并启用依赖缓存：

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
  with:
    version: "0.11.28"
    enable-cache: true
```

工作流命令替换为冻结 lock 的调用：

```bash
uv run --frozen upstream-sync check
uv run --frozen upstream-sync sync
```

工作流继续生成 `upstream-sync/YYYY-MM-DD` 分支和 PR，提交范围、告警提取、lock 文件提交及删除保护语义保持不变。现有 `git add -A` 会自动覆盖移动后的 lock 文件路径，无需增加或修改显式 pathspec。

## 8. 测试与验收

本次属于目录和命令契约迁移，验证路径如下：

1. 在 `tests/test_project_layout.py` 添加针对 `pyproject.toml`、两个 console entry point、`.venv/` ignore 和目标根目录结构的失败测试。
2. 在 `tests/test_upstream_sync.py` 添加针对上游配置路径、lock 路径、仓库根目录和映射 `dst` 解析的失败测试。
3. 在 `tests/test_skill_manager.py` 调整模块导入，并添加仓库根目录和 web 文件解析的失败测试。
4. 移动文件并调整导入后，使新测试通过。
5. 使用 `uv lock --check` 验证 lock 与 `pyproject.toml` 一致。
6. 使用 `uv run python -m unittest discover -s tests -p 'test_*.py'` 运行完整测试。
7. 使用 `uv run python -m py_compile ...` 检查移动后的 Python 文件。
8. 提取 `tools/skill_manager/web/index.html` 的主脚本并执行 `node --check`。
9. 分别运行两个入口的 `--help`，并执行只读的 `skill-manager status --json`、`doctor --json`、`adopt --json`。
10. 对只读验收前后的真实 Skill 链接计算哈希，确认目录迁移没有改写全局链接。
11. 检查 README、`docs/upstream-sync.md`、workflow 和测试中不存在旧根目录命令或旧路径残留；2026-07-14 历史 spec/plan 以及描述迁移动作的本轮 spec/plan 显式排除。

真实 `adopt --apply` 继续需要独立明确授权，不属于本次目录整理验收。

## 9. 提交边界

实施建议保持两个提交：

1. `refactor(repo): 整理工具目录并统一 uv 入口`
   - 目录移动、`pyproject.toml`、`uv.lock`、入口、路径解析、测试和 workflow。
2. `docs(repo): 更新目录与命令说明`
   - README、上游同步设计、全局 Skill 管理器 spec/plan 中的路径与命令。

若代码移动与文档契约测试无法形成独立通过的中间状态，可以合并为一个闭环提交；最终提交必须包含 body、验证结果和 Codex trailer。
