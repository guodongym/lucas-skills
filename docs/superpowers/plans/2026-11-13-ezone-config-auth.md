# Ezone 项目配置与个人认证实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 完成用户已批准的项目配置、个人令牌存储、登录退出与首次使用说明；独立复核通过后发布公开仓库。

**Architecture:** 完整 Skill 内新增标准库配置模块；项目提供非机密上下文，用户目录按 HTTPS origin 保存凭据，环境令牌用于临时覆盖和 CI。公开仓库不实现项目 Skill 同步；项目随后自行选择多个 Skill、固定来源提交、同步并提交代码。

**Tech Stack:** Python 3.11+ 标准库、unittest；不新增依赖。

**Spec:** 本计划记录本轮已批准的对话方案及实现细节，不另造重复设计文档。

## Global Constraints

- 项目 `.ezone.json` 只接受字符串字段 `host`、`repo`、`company`，禁止凭据；从当前目录向上查找最近配置，到最近 `.git` 边界停止；非 Git 目录只查当前目录。
- 上下文优先级：显式全局参数 > 同名 `EZONE_*` 环境变量 > 项目文件。没有项目文件时保留现有独立调用。
- 个人凭据固定在 `~/.config/ezone/credentials.json`，格式为 `{"hosts": {"https://origin": "token"}}`。完整 HTTPS origin 规范化后精确匹配，不能跨平台复用；同 origin 单账号。
- 认证优先级：非空 `EZONE_TOKEN` > 匹配 origin 的个人凭据。独立复核补充：环境令牌必须由可信 `EZONE_HOST` 或显式 `--host` 绑定发送目标，不由项目文件单独决定。项目文件、参数、URL 不接受令牌；拒绝空白及 CR/LF 令牌。
- `auth login` 只允许交互式隐藏输入，执行现有只读仓库列表探测成功后才保存；失败保留旧凭据。不自动申请令牌、不提供完整账号身份保证。
- macOS/Linux 凭据文件权限 `600`、新目录 `700`；写入用同目录临时文件和原子替换；拒绝凭据文件软链、异常格式和过宽权限，不自动覆盖损坏数据。
- `auth logout` 只移除当前 origin 的本机凭据，不联网、不撤销远端令牌、不清除当前进程外的环境变量；其他平台保留。
- `doctor` 不联网，只报告是否配置、来源、配置路径，不返回令牌；错误不能包含凭据或原始配置正文。
- 用户已授权本仓库实现、复核后合并／push／tag／GitHub Release；未授权清理任务工作区或修改项目仓库。本轮先完成公开仓库发布。

## Review Focus

1. 从子目录调用、嵌套仓库和 worktree 的 `.git` 文件不能越界读取另一项目配置。
2. 环境覆盖、不同 origin（含端口）、无凭据和损坏文件不能导致静默错误账号或泄露。
3. 登录失败、输入中断、非交互输入、磁盘失败保留原凭据，错误不包含令牌。
4. 退出保留其他平台且说明环境覆盖仍存在；离线诊断不能触网。
5. 复制完整 Skill 后，首次使用和新模块导入不依赖源仓库、真实 HOME 或第三方包。

## Task 1: 配置、凭据及认证命令

**Files:** Create `skills/ezone/scripts/ezone_config.py`, `tests/test_ezone_config.py`; Modify `skills/ezone/scripts/ezone.py`, `skills/ezone/scripts/ezone_client.py`。

**Interfaces:** 配置模块提供 `EzoneError`, `canonical_host`, `project_config`, `context`, `credentials_path`, `load_token`, `save_token`, `remove_token`；Client 保留导出的 EzoneError 和原有调用形式，增加显式 token 供登录探测。CLI 在边界解析配置并传递凭据。

- [x] 新增真实临时 HOME／项目文件测试：配置查找、边界、优先级、凭据隔离、权限与原子写、坏输入、交互登录／失败／退出／诊断。
- [x] 运行 `uv run python -m unittest discover -s tests -p 'test_ezone_config.py' -v`，确认缺功能导致失败。
- [x] 实现最小配置模块和命令；回归现有 HTTP 与资源命令。
- [x] 运行全部 `test_ezone*.py`，确认通过后提交；记录 RED／GREEN 数量。

## Task 2: 首次使用、发布文档与完整目录验收

**Files:** Modify `skills/ezone/SKILL.md`, `skills/ezone/references/commands.md`, `skills/ezone/evals/evals.json`, `tests/test_ezone_skill.py`, `README.md`, `CHANGELOG.md`, `docs/ezone-validation.md`。

- [x] 提供项目配置样例与完整首次使用、CI、令牌更换／退出、故障排查和安全边界；更新 CLI 版本为 `0.2.0`。
- [x] 离线子进程演练复制后项目配置发现、隐藏输入登录（合成探测）、凭据持久读取、退出及未配置提示；真实 HOME 与旧令牌不用。
- [x] 校验 Skill 链接／元数据、实际命令解析及完整测试；不把模拟认证测试称为真实认证验收。
- [x] 发起一次全分支独立审查，修复阻塞问题，再以实际测试结果更新验收记录。

## Task 3: 发布核验步骤

以下为发布执行清单，实际状态以远端 main、标签及原生 Release 回读为准，不预填外部操作完成态。

- 核对远端、主分支与当前工作区；保留主工作区无关／唯一未保存文件。
- 按仓库既有版本规则新增 `v0.10.0` CHANGELOG；GitHub 最新发布或远端出现冲突时重新核对版本。
- 集成最终树、验证、生成完整 Skill 发布包，检查包中无凭据、缓存或内部测试材料。
- push main 和带注释标签，创建 GitHub Release 并上传包，分别回读 SHA、tag 与 Release／附件。
- 报告发布、验证、已知限制；项目多 Skill 同步另在项目仓库实施，不借本轮发布改写项目。
