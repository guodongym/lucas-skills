# lucas-skills

私有 skill 仓库，部分内容来源于公开仓库。通过 `vendor.py` 追踪上游变更并按需同步，通过 GitHub Actions 实现每周自动检测。

## 目录结构

```
lucas-skills/
├── upstream.yml          # 上游来源配置（手动维护）
├── upstream.lock.yml     # 同步状态记录（自动生成，建议提交到 git）
├── vendor.py             # 同步脚本
├── .github/
│   └── workflows/
│       └── sync-upstream.yml  # 自动检测 & 开 PR 的 Actions workflow
└── skills/               # 本地 skill 文件
    ├── skill-creator/
    ├── frontend-design/
    └── ...
```

## 方案设计

### 核心思路

- `upstream.yml` 声明每个上游仓库的地址和需要同步的路径映射
- `upstream.lock.yml` 记录每个上游上次同步时的 commit hash，作为"基准线"
- `vendor.py check` 用 `git ls-remote` 快速对比远端最新 commit 与 lock 文件，**无需 clone**，秒级完成
- `vendor.py sync` 执行 sparse clone/fetch（只拉取映射的路径），将变更覆写到本地，更新 lock 文件
- 删除策略：上游删除的文件**不会自动删除**本地文件，只打印 `[WARN]` 提示，由你手动决定

方案选型对比详见 [DESIGN.md](DESIGN.md#为什么不用现有工具)。

## 快速开始

### 安装依赖

```bash
pip install pyyaml
```

### 查看帮助

```bash
python vendor.py help
```

### 检测上游是否有更新（只读，无需 clone）

```bash
python vendor.py check
```

输出示例：

```
[UPDATE] anthropics-skills: 有更新  abc12345 -> def67890
[OK]     my-other-upstream: 已是最新 (ff001122)
```

### 查看具体变更内容

```bash
python vendor.py diff
```

输出示例：

```
=== anthropics-skills ===
  skills/skill-creator -> skills/skill-creator:
    + new-file.md
    ~ SKILL.md
    - old-file.md  [上游已删除，本地保留]
```

### 执行同步

```bash
# 同步所有上游
python vendor.py sync

# 只同步指定上游
python vendor.py sync --upstream anthropics-skills
```

## 添加新的上游来源

编辑 `upstream.yml`，在 `upstreams` 列表中追加一项：

```yaml
upstreams:
  - name: my-upstream          # 自定义名称，唯一标识
    repo: https://github.com/user/repo
    branch: main
    mappings:
      - src: path/in/upstream  # 上游仓库中的目录路径
        dst: skills/local-name # 本地目标路径
      - src: another/path
        dst: skills/another
```

然后执行 `python vendor.py sync` 完成首次同步。

## GitHub Actions 自动化

`.github/workflows/sync-upstream.yml` 会在每周一 09:00 UTC 自动运行：

1. 执行 `vendor.py check` 检测是否有上游更新
2. 如有更新，自动运行 `vendor.py sync`
3. 将变更提交到新分支 `upstream-sync/YYYY-MM-DD`
4. 自动开 PR，PR body 中包含同步详情和所有 `[WARN]` 提示

也可以在 Actions 页面手动触发（`workflow_dispatch`）。

> **注意**：首次使用需在仓库 Settings → Actions → General → Workflow permissions 中开启 "Read and write permissions"，Actions 才能创建分支和 PR。

## 文件说明

| 文件 | 说明 |
|------|------|
| `upstream.yml` | 上游配置，手动维护 |
| `upstream.lock.yml` | 同步状态，自动生成，**建议提交到 git** |
| `vendor.py` | 同步脚本，依赖 `pyyaml` + `git` |
| `~/.cache/upstream-sync/` | clone 缓存目录，可安全删除，下次 sync 自动重建 |
