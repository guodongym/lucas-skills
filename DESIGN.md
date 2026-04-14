# 设计文档：上游 Skill 追踪与同步工具

## 背景

私有 skill 仓库中，部分 skill 来源于多个公开仓库的部分路径拷贝。需要一套轻量工具来感知上游变更并按需同步，不引入 vendir 等外部依赖。

## 为什么不用现有工具

| 方案 | 问题 |
|------|------|
| `git subtree` | 只能整目录映射，不支持多上游多路径，会将上游 commit 混入本仓库历史 |
| `git submodule` | 引用整个仓库，无法只取部分路径，协作时依赖外部仓库可访问性 |
| `git sparse-checkout` | 需为每个上游维护独立 clone，无变更检测机制（无 lock 文件），多上游管理全靠手动脚本；本方案内部已封装此能力 |
| `vendir` | 需要安装额外工具，引入外部依赖 |
| **本方案** | 只依赖 Python 3 + pyyaml + git，配置即文档，lock 文件可 git 追踪 |

---

## 文件结构

```
lucas-skills/
├── upstream.yml               # 上游来源配置（手动维护）
├── upstream.lock.yml          # 同步状态记录（自动生成，建议提交到 git）
├── vendor.py                  # 同步脚本
├── .github/
│   └── workflows/
│       └── sync-upstream.yml  # 每周自动检测并开 PR 的 Actions workflow
└── skills/                    # 本地 skill 文件
    ├── skill-creator/
    ├── frontend-design/
    └── ...
```

---

## 配置文件格式

### upstream.yml

```yaml
upstreams:
  - name: anthropics-skills
    repo: https://github.com/anthropics/skills
    branch: main
    mappings:
      - src: skills/skill-creator     # 上游仓库中的路径（相对于仓库根）
        dst: skills/skill-creator     # 本地目标路径（相对于此文件所在目录）
      - src: skills/frontend-design
        dst: skills/frontend-design
```

### upstream.lock.yml（自动生成）

```yaml
# 此文件由 vendor.py 自动生成，请勿手动编辑
# 建议提交到 git，记录上次同步状态
anthropics-skills:
  commit: 12ab35c2eb5668c95810e6a6066f40f4218adc39
  synced_at: '2026-04-13T15:22:19Z'
```

---

## vendor.py 内部流程

### check 命令

```
for 每个 upstream:
  1. git ls-remote <repo> refs/heads/<branch>
     → 获取远端当前 HEAD commit hash（无需 clone，秒级完成）
  2. 读取 upstream.lock.yml 中该 upstream 的 commit 字段
  3. 两者相同 → [OK]；不同 → [UPDATE]
```

### sync 命令

```
for 每个 upstream:
  1. git ls-remote 获取远端 HEAD
  2. 与 lock 对比，相同则跳过
  3. 若 ~/.cache/upstream-sync/<name>/ 不存在：
       git clone --depth=1 --filter=blob:none --no-checkout <repo>
       git sparse-checkout init --cone
       git sparse-checkout set <所有 src 路径>
       git checkout
     若已存在：
       git fetch origin <branch> --depth=1
       git sparse-checkout set <所有 src 路径>
       git reset --hard FETCH_HEAD
  4. 对比每个 mapping 的 src（clone 目录）与 dst（本地目录）：
       - 新增/修改的文件 → 覆写本地
       - 上游已删除的文件 → 不删除本地，打印 [WARN] 提示
  5. 更新 upstream.lock.yml 中的 commit hash 和 synced_at
```

### 删除策略

默认只新增/覆写，不自动删除本地文件。上游删除文件时输出：

```
[WARN] 上游已删除以下文件，本地未自动删除，请手动确认：
  - skills/skill-creator/old-file.md
```

### clone 缓存

持久化缓存在 `~/.cache/upstream-sync/<name>/`：

- `check` 命令：不使用缓存，只用 `git ls-remote`
- `sync/diff` 命令：复用已有 clone，只做增量 fetch

可安全删除缓存目录，下次 sync 时自动重建。

---

## GitHub Actions 自动化流程

`.github/workflows/sync-upstream.yml` 每周一 09:00 UTC 自动触发：

```
1. checkout 仓库
2. 安装 pyyaml
3. 运行 vendor.py check
   → 无更新：直接结束
   → 有更新：继续下一步
4. 创建新分支 upstream-sync/YYYY-MM-DD
5. 运行 vendor.py sync
6. git add -A && git commit
7. git push origin <branch>
8. gh pr create，PR body 包含 sync 输出详情
```

也支持在 Actions 页面手动触发（`workflow_dispatch`）。

> **权限要求**：Settings → Actions → General → Workflow permissions → 选 "Read and write permissions"。
