#!/usr/bin/env python3
"""Read-only Git history inspection for git-history-rewrite.

This script only runs Git read commands. It does not create refs, edit files,
rewrite commits, fetch, pull, push, or change the index.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class GitResult:
    ok: bool
    stdout: str
    stderr: str


def git(*args: str) -> GitResult:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return GitResult(proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip())


def must_git(*args: str) -> str:
    result = git(*args)
    if not result.ok:
        joined = " ".join(args)
        raise SystemExit(f"git {joined} failed: {result.stderr or result.stdout}")
    return result.stdout


def split_lines(value: str) -> list[str]:
    return [line for line in value.splitlines() if line.strip()]


def detect_upstream() -> str | None:
    result = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    return result.stdout if result.ok and result.stdout else None


def detect_base(explicit_base: str | None, upstream: str | None) -> tuple[str | None, str]:
    if explicit_base:
        return explicit_base, "explicit"
    if upstream:
        result = git("merge-base", "HEAD", upstream)
        if result.ok and result.stdout:
            return result.stdout, f"merge-base with {upstream}"
    result = git("merge-base", "HEAD", "origin/main")
    if result.ok and result.stdout:
        return result.stdout, "merge-base with origin/main"
    return None, "unresolved"


def count_ahead_behind(upstream: str | None) -> dict[str, int | None]:
    if not upstream:
        return {"ahead": None, "behind": None}
    result = git("rev-list", "--left-right", "--count", f"{upstream}...HEAD")
    if not result.ok or not result.stdout:
        return {"ahead": None, "behind": None}
    left, right = result.stdout.split()
    return {"behind": int(left), "ahead": int(right)}


def inspect(base_arg: str | None) -> dict[str, Any]:
    inside = git("rev-parse", "--is-inside-work-tree")
    if not inside.ok or inside.stdout != "true":
        raise SystemExit("not inside a Git work tree")

    branch = must_git("branch", "--show-current") or "(detached HEAD)"
    head = must_git("rev-parse", "--short", "HEAD")
    upstream = detect_upstream()
    base, base_source = detect_base(base_arg, upstream)
    status = split_lines(must_git("status", "--short"))
    dirty = bool(status)
    ahead_behind = count_ahead_behind(upstream)

    commits: list[str] = []
    merge_commits: list[str] = []
    diff_stat = ""
    if base:
        commits = split_lines(must_git("log", "--reverse", "--oneline", f"{base}..HEAD"))
        merge_commits = split_lines(must_git("log", "--merges", "--oneline", f"{base}..HEAD"))
        diff_stat_result = git("diff", "--stat", f"{base}..HEAD")
        diff_stat = diff_stat_result.stdout if diff_stat_result.ok else ""

    risks: list[str] = []
    if dirty:
        risks.append("working tree has uncommitted changes")
    if not base:
        risks.append("base commit could not be resolved")
    if merge_commits:
        risks.append("candidate range contains merge commits")
    if ahead_behind.get("behind"):
        risks.append("branch is behind its upstream")
    if upstream and ahead_behind.get("ahead"):
        risks.append("branch has commits not in upstream; remote rewrite may need force-with-lease if already pushed")
    if not upstream:
        risks.append("branch has no upstream; confirm target branch/base manually")

    return {
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "base": base,
        "base_source": base_source,
        "ahead_behind": ahead_behind,
        "dirty": dirty,
        "status": status,
        "commits": commits,
        "merge_commits": merge_commits,
        "diff_stat": diff_stat,
        "risks": risks,
    }


def print_text(report: dict[str, Any]) -> None:
    print("Git history inspection")
    print(f"- branch: {report['branch']}")
    print(f"- head: {report['head']}")
    print(f"- upstream: {report['upstream'] or '(none)'}")
    print(f"- base: {report['base'] or '(unresolved)'} ({report['base_source']})")
    ahead_behind = report["ahead_behind"]
    print(f"- ahead/behind: {ahead_behind.get('ahead')}/{ahead_behind.get('behind')}")
    print(f"- dirty: {str(report['dirty']).lower()}")

    print("\nCommits:")
    if report["commits"]:
        for line in report["commits"]:
            print(f"  {line}")
    else:
        print("  (none or base unresolved)")

    if report["merge_commits"]:
        print("\nMerge commits in range:")
        for line in report["merge_commits"]:
            print(f"  {line}")

    if report["status"]:
        print("\nWorking tree status:")
        for line in report["status"]:
            print(f"  {line}")

    if report["diff_stat"]:
        print("\nDiff stat:")
        print(report["diff_stat"])

    print("\nRisks:")
    if report["risks"]:
        for risk in report["risks"]:
            print(f"  - {risk}")
    else:
        print("  (none detected by read-only inspection)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Git history rewrite preflight report.")
    parser.add_argument("--base", help="Base revision for the candidate rewrite range.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    args = parser.parse_args()

    report = inspect(args.base)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
