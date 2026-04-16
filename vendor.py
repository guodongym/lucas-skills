#!/usr/bin/env python3
"""vendor.py - 追踪并同步来自多个上游 git 仓库的部分文件。

用法: python vendor.py <命令> [选项]
运行 'python vendor.py help' 查看完整说明。
"""

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误: 需要安装 pyyaml: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

CACHE_DIR = Path.home() / ".cache" / "upstream-sync"
CONFIG_FILE = Path("upstream.yml")
LOCK_FILE = Path("upstream.lock.yml")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def run(cmd, cwd=None, check=True):
    """运行命令，返回 stdout 字符串；check=True 时失败抛出 RuntimeError。"""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"命令失败: {' '.join(str(c) for c in cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def load_config():
    if not CONFIG_FILE.exists():
        print(f"错误: 找不到配置文件 {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def load_lock():
    if not LOCK_FILE.exists():
        return {}
    with open(LOCK_FILE) as f:
        return yaml.safe_load(f) or {}


def save_lock(lock):
    header = "# 此文件由 vendor.py 自动生成，请勿手动编辑\n# 建议提交到 git，记录上次同步状态\n"
    with open(LOCK_FILE, "w") as f:
        f.write(header)
        yaml.dump(lock, f, default_flow_style=False, allow_unicode=True)


def get_remote_commit(repo, branch):
    """通过 git ls-remote 获取远端 commit hash，无需本地 clone。"""
    output = run(["git", "ls-remote", repo, f"refs/heads/{branch}"])
    if not output:
        raise RuntimeError(f"找不到远端分支: {branch} @ {repo}")
    return output.split()[0]


def ensure_clone(name, repo, branch, src_paths):
    """确保本地有最新的 sparse clone，返回 clone 目录路径。"""
    clone_dir = CACHE_DIR / name
    if clone_dir.exists():
        print(f"  正在 fetch {name}...")
        run(["git", "fetch", "origin", branch, "--depth=1"], cwd=clone_dir)
        run(["git", "sparse-checkout", "set"] + src_paths, cwd=clone_dir)
        run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=clone_dir)
    else:
        print(f"  正在 clone {name}...")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth=1", "--filter=blob:none",
             "--no-checkout", repo, str(clone_dir)])
        run(["git", "sparse-checkout", "init", "--cone"], cwd=clone_dir)
        run(["git", "sparse-checkout", "set"] + src_paths, cwd=clone_dir)
        run(["git", "checkout"], cwd=clone_dir)
    return clone_dir


def collect_files(directory):
    """返回 {相对路径: 绝对路径} 的字典，递归遍历目录下所有文件。"""
    base = Path(directory)
    if not base.exists():
        return {}
    return {
        str(f.relative_to(base)): f
        for f in base.rglob("*")
        if f.is_file()
    }


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def print_help():
    print("""用法: python vendor.py <命令> [选项]

命令:
  help                          显示此帮助信息
  check                         检测所有上游是否有新 commit（只读，无需 clone）
  diff                          显示每个映射路径的具体文件变更（需要 clone）
  sync [--upstream <name>]      执行同步，可通过 --upstream 指定只同步某个上游

示例:
  python vendor.py check
  python vendor.py diff
  python vendor.py sync
  python vendor.py sync --upstream anthropics-skills

文件说明:
  upstream.yml       上游配置（手动维护）
  upstream.lock.yml  同步状态记录（自动生成，建议提交到 git）
  ~/.cache/upstream-sync/  clone 缓存目录（可安全删除，下次 sync 会重建）
""")


def cmd_check():
    config = load_config()
    lock = load_lock()
    has_updates = False

    for upstream in config["upstreams"]:
        name = upstream["name"]
        repo = upstream["repo"]
        branch = upstream.get("branch", "main")
        try:
            remote = get_remote_commit(repo, branch)
        except RuntimeError as e:
            print(f"[ERROR]  {name}: {e}")
            continue

        local = lock.get(name, {}).get("commit", "")
        if remote == local:
            print(f"[OK]     {name}: 已是最新 ({remote[:8]})")
        else:
            has_updates = True
            old = local[:8] if local else "（未同步）"
            print(f"[UPDATE] {name}: 有更新  {old} -> {remote[:8]}")

    if has_updates:
        print("\n运行 'python vendor.py diff' 查看详情，或 'python vendor.py sync' 执行同步。")
    else:
        print("\n所有上游均为最新。")


def cmd_diff():
    config = load_config()
    lock = load_lock()

    for upstream in config["upstreams"]:
        name = upstream["name"]
        repo = upstream["repo"]
        branch = upstream.get("branch", "main")
        mappings = upstream["mappings"]
        print(f"\n=== {name} ===")

        try:
            remote = get_remote_commit(repo, branch)
        except RuntimeError as e:
            print(f"[ERROR] {e}")
            continue

        local = lock.get(name, {}).get("commit", "")
        if remote == local:
            print("已是最新，无变更。")
            continue

        src_paths = [m["src"] for m in mappings]
        try:
            clone_dir = ensure_clone(name, repo, branch, src_paths)
        except RuntimeError as e:
            print(f"[ERROR] clone 失败: {e}")
            continue

        for mapping in mappings:
            src, dst = mapping["src"], mapping["dst"]
            up_files = collect_files(clone_dir / src)
            lo_files = collect_files(Path(dst))
            added = set(up_files) - set(lo_files)
            removed = set(lo_files) - set(up_files)
            modified = {
                f for f in set(up_files) & set(lo_files)
                if up_files[f].read_bytes() != lo_files[f].read_bytes()
            }
            if not added and not removed and not modified:
                print(f"  {src}: 无变更")
                continue
            print(f"  {src} -> {dst}:")
            for f in sorted(added):
                print(f"    + {f}")
            for f in sorted(modified):
                print(f"    ~ {f}")
            for f in sorted(removed):
                print(f"    - {f}  [上游已删除，本地保留]")


def cmd_sync(upstream_filter=None):
    config = load_config()
    lock = load_lock()
    upstreams = config["upstreams"]

    if upstream_filter:
        upstreams = [u for u in upstreams if u["name"] == upstream_filter]
        if not upstreams:
            print(f"错误: 找不到上游 '{upstream_filter}'", file=sys.stderr)
            sys.exit(1)

    for upstream in upstreams:
        name = upstream["name"]
        repo = upstream["repo"]
        branch = upstream.get("branch", "main")
        mappings = upstream["mappings"]
        print(f"\n=== 同步 {name} ===")

        try:
            remote = get_remote_commit(repo, branch)
        except RuntimeError as e:
            print(f"[ERROR] {e}")
            continue

        local = lock.get(name, {}).get("commit", "")
        if remote == local:
            print("已是最新，跳过。")
            continue

        src_paths = [m["src"] for m in mappings]
        try:
            clone_dir = ensure_clone(name, repo, branch, src_paths)
        except RuntimeError as e:
            print(f"[ERROR] clone 失败: {e}")
            continue

        deletions = []
        for mapping in mappings:
            src, dst = mapping["src"], mapping["dst"]
            up_path = clone_dir / src
            lo_path = Path(dst)

            if not up_path.exists():
                print(f"  [WARN] 上游路径不存在: {src}")
                continue

            up_files = collect_files(up_path)
            lo_files = collect_files(lo_path)
            lo_path.mkdir(parents=True, exist_ok=True)

            for rel, src_file in up_files.items():
                dst_file = lo_path / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)

            for rel in sorted(set(lo_files) - set(up_files)):
                deletions.append(f"{dst}/{rel}")

            print(f"  {src} -> {dst}: 已同步 {len(up_files)} 个文件")

        if deletions:
            print("\n  [WARN] 上游已删除以下文件，本地未自动删除，请手动确认：")
            for f in deletions:
                print(f"    - {f}")

        lock[name] = {
            "commit": remote,
            "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        save_lock(lock)
        print(f"  lock 已更新 -> {remote[:8]}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args or args[0] == "help":
        print_help()
        return

    cmd = args[0]
    if cmd == "check":
        cmd_check()
    elif cmd == "diff":
        cmd_diff()
    elif cmd == "sync":
        upstream_filter = None
        if "--upstream" in args:
            idx = args.index("--upstream")
            if idx + 1 >= len(args):
                print("错误: --upstream 需要指定名称", file=sys.stderr)
                sys.exit(1)
            upstream_filter = args[idx + 1]
        cmd_sync(upstream_filter)
    else:
        print(f"错误: 未知命令 '{cmd}'", file=sys.stderr)
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
