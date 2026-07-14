from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tomllib
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import yaml


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class SkillRecord:
    slug: str
    name: str
    description: str
    path: Path
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanIssue:
    code: str
    path: Path
    message: str


@dataclass(frozen=True)
class RepositoryScan:
    repo_root: Path
    skills_root: Path
    skills: tuple[SkillRecord, ...]
    issues: tuple[ScanIssue, ...]


def _read_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter")
    try:
        closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("unterminated YAML frontmatter") from exc
    data = yaml.safe_load("\n".join(lines[1:closing]))
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def scan_repository(repo_root: Path) -> RepositoryScan:
    repo_root = repo_root.expanduser().resolve()
    skills_root = repo_root / "skills"
    candidates: list[SkillRecord] = []
    issues: list[ScanIssue] = []
    if not skills_root.is_dir():
        return RepositoryScan(
            repo_root,
            skills_root,
            (),
            (ScanIssue("missing-skills-root", skills_root, "skills directory does not exist"),),
        )

    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        slug = skill_dir.name
        skill_file = skill_dir / "SKILL.md"
        if not SLUG_RE.fullmatch(slug):
            issues.append(ScanIssue("invalid-slug", skill_dir, f"invalid directory slug: {slug}"))
            continue
        if not skill_file.is_file():
            issues.append(ScanIssue("missing-skill-file", skill_dir, "SKILL.md does not exist"))
            continue
        try:
            metadata = _read_frontmatter(skill_file)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            issues.append(ScanIssue("invalid-frontmatter", skill_file, str(exc)))
            continue
        name = metadata.get("name")
        description = metadata.get("description")
        if not isinstance(name, str) or not SLUG_RE.fullmatch(name):
            issues.append(ScanIssue("invalid-name", skill_file, "name must be a lowercase hyphenated slug"))
            continue
        if not isinstance(description, str) or not description.strip():
            issues.append(ScanIssue("invalid-description", skill_file, "description must be a non-empty string"))
            continue
        warnings = ("name-mismatch",) if name != slug else ()
        candidates.append(SkillRecord(slug, name, description.strip(), skill_dir.resolve(), warnings))

    name_counts = Counter(skill.name for skill in candidates)
    valid: list[SkillRecord] = []
    for skill in candidates:
        if name_counts[skill.name] > 1:
            issues.append(ScanIssue("duplicate-name", skill.path, f"duplicate name: {skill.name}"))
        else:
            valid.append(skill)
    return RepositoryScan(repo_root, skills_root, tuple(valid), tuple(issues))


class LinkState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    LEGACY = "legacy"
    CONFLICT = "conflict"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class TargetAdapter:
    key: str
    tool: str
    home: Path
    root: Path
    surfaces: tuple[str, ...]
    manifest_path: Path | None = None
    manifest_content: str | None = None


@dataclass(frozen=True)
class SurfaceStatus:
    key: str
    installed: bool
    detector: str


@dataclass(frozen=True)
class TargetStatus:
    slug: str
    adapter_key: str
    tool: str
    state: LinkState
    path: Path
    raw_target: Path | None
    resolved_target: Path | None
    message: str


@dataclass(frozen=True)
class ManagedState:
    repository: RepositoryScan
    adapters: tuple[TargetAdapter, ...]
    surfaces: tuple[SurfaceStatus, ...]
    targets: tuple[TargetStatus, ...]


@dataclass(frozen=True)
class InventorySource:
    root: Path
    tools: tuple[str, ...]
    surfaces: tuple[str, ...]
    source_type: str
    flat_markdown: bool = False


@dataclass(frozen=True)
class InventoryRecord:
    slug: str
    name: str
    description: str
    path: Path
    raw_target: Path | None
    resolved_target: Path | None
    tools: tuple[str, ...]
    surfaces: tuple[str, ...]
    source_type: str
    flags: tuple[str, ...]


@dataclass(frozen=True)
class PathSnapshot:
    kind: str
    link_target: str | None = None


@dataclass(frozen=True)
class PlannedChange:
    action: str
    slug: str
    adapter_key: str
    source: Path
    target: Path
    expected: PathSnapshot
    reason: str


@dataclass(frozen=True)
class ChangePlan:
    changes: tuple[PlannedChange, ...]
    repository: RepositoryScan | None = None


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    code: str
    slug: str
    adapter_key: str
    path: Path
    message: str


@dataclass(frozen=True)
class BatchResult:
    ok: bool
    results: tuple[OperationResult, ...]


@dataclass(frozen=True)
class ContainerChange:
    adapter_key: str
    root: Path
    expected: PathSnapshot
    links: tuple[tuple[str, Path], ...]
    reason: str


@dataclass(frozen=True)
class BridgeRemoval:
    adapter_key: str
    path: Path
    expected: PathSnapshot
    legacy_root: Path
    legacy_entries: tuple[tuple[str, PathSnapshot, Path], ...]
    required_links: tuple[tuple[Path, Path], ...]
    reason: str


@dataclass(frozen=True)
class AdoptionPlan:
    link_changes: tuple[PlannedChange, ...]
    container_changes: tuple[ContainerChange, ...]
    bridge_removals: tuple[BridgeRemoval, ...]
    snapshot_path: Path
    repository: RepositoryScan | None = None


ANTIGRAVITY_MANIFEST = """{
  \"$schema\": \"https://antigravity.google/schemas/v1/plugin.json\",
  \"name\": \"lucas-skills\",
  \"description\": \"Global skills managed by lucas-skills.\"
}\n"""


def build_adapters(home: Path) -> tuple[TargetAdapter, ...]:
    plugin_root = home / ".gemini/antigravity-cli/plugins/lucas-skills"
    return (
        TargetAdapter(
            "claude-shared",
            "claude",
            home,
            home / ".claude/skills",
            ("claude-desktop", "claude-cli"),
        ),
        TargetAdapter(
            "codex-shared",
            "codex",
            home,
            home / ".codex/skills",
            ("codex-desktop", "codex-cli"),
        ),
        TargetAdapter(
            "copilot-shared",
            "copilot",
            home,
            home / ".copilot/skills",
            ("copilot-desktop", "copilot-cli"),
        ),
        TargetAdapter(
            "antigravity-desktop",
            "antigravity",
            home,
            home / ".gemini/config/skills",
            ("antigravity-desktop",),
        ),
        TargetAdapter(
            "antigravity-cli",
            "antigravity",
            home,
            plugin_root / "skills",
            ("antigravity-cli",),
            plugin_root / "plugin.json",
            ANTIGRAVITY_MANIFEST,
        ),
    )


def detect_surfaces(
    which: Callable[[str], str | None] = shutil.which,
    applications: Path = Path("/Applications"),
) -> dict[str, SurfaceStatus]:
    app_candidates = {
        "claude-desktop": (applications / "Claude.app", applications / "Claude Code.app"),
        "codex-desktop": (applications / "ChatGPT.app", applications / "Codex.app"),
        "copilot-desktop": (applications / "GitHub Copilot.app",),
        "antigravity-desktop": (applications / "Antigravity.app",),
    }
    cli_commands = {
        "claude-cli": "claude",
        "codex-cli": "codex",
        "copilot-cli": "copilot",
        "antigravity-cli": "agy",
    }
    result = {
        key: SurfaceStatus(key, any(path.exists() for path in paths), "application")
        for key, paths in app_candidates.items()
    }
    result.update(
        {
            key: SurfaceStatus(key, which(command) is not None, f"command:{command}")
            for key, command in cli_commands.items()
        }
    )
    return result


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _absolute_link_target(path: Path) -> Path:
    raw = Path(os.readlink(path))
    return raw if raw.is_absolute() else path.parent / raw


def _under(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
        return True
    except ValueError:
        return False


def _adapter_available(
    adapter: TargetAdapter,
    surfaces: Mapping[str, SurfaceStatus],
) -> bool:
    return any(surfaces[key].installed for key in adapter.surfaces)


def _classify_target(
    skill: SkillRecord,
    adapter: TargetAdapter,
    surfaces: Mapping[str, SurfaceStatus],
    legacy_roots: tuple[Path, ...],
    repository_skills_root: Path,
) -> TargetStatus:
    target = adapter.root / skill.slug
    if not _adapter_available(adapter, surfaces):
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.UNAVAILABLE,
            target,
            None,
            None,
            "surface not installed",
        )
    if adapter.root.is_symlink():
        resolved_root = adapter.root.resolve(strict=False)
        if not resolved_root.exists():
            return TargetStatus(
                skill.slug,
                adapter.key,
                adapter.tool,
                LinkState.ERROR,
                target,
                adapter.root,
                resolved_root,
                "target root is a broken symlink",
            )
        if resolved_root == repository_skills_root.resolve(strict=False):
            return TargetStatus(
                skill.slug,
                adapter.key,
                adapter.tool,
                LinkState.LEGACY,
                target,
                adapter.root,
                skill.path,
                "whole-directory link requires adoption",
            )
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.CONFLICT,
            target,
            adapter.root,
            resolved_root,
            "target root is an unmanaged symlink",
        )
    if _lexists(adapter.root) and not adapter.root.is_dir():
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.CONFLICT,
            target,
            None,
            adapter.root.resolve(strict=False),
            "target root is not a directory",
        )
    if not _lexists(target):
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.DISABLED,
            target,
            None,
            None,
            "target is absent",
        )
    if not target.is_symlink():
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.CONFLICT,
            target,
            None,
            target.resolve(strict=False),
            "target is not a symlink",
        )
    raw_target = _absolute_link_target(target)
    resolved = target.resolve(strict=False)
    if not resolved.exists():
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.ERROR,
            target,
            raw_target,
            resolved,
            "broken symlink",
        )
    expected = skill.path.resolve()
    if Path(os.path.abspath(raw_target)) == expected:
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.ENABLED,
            target,
            raw_target,
            resolved,
            "direct repository link",
        )
    if resolved == expected and any(_under(raw_target, root) for root in legacy_roots):
        return TargetStatus(
            skill.slug,
            adapter.key,
            adapter.tool,
            LinkState.LEGACY,
            target,
            raw_target,
            resolved,
            "recognized legacy link",
        )
    return TargetStatus(
        skill.slug,
        adapter.key,
        adapter.tool,
        LinkState.CONFLICT,
        target,
        raw_target,
        resolved,
        "symlink belongs to another source",
    )


def scan_managed_state(
    repository: RepositoryScan,
    adapters: Sequence[TargetAdapter],
    surfaces: Mapping[str, SurfaceStatus],
) -> ManagedState:
    if not adapters:
        return ManagedState(repository, (), tuple(surfaces.values()), ())
    home = adapters[0].home
    legacy_roots = (home / ".cc-switch/skills", home / ".gemini/skills")
    targets = tuple(
        _classify_target(skill, adapter, surfaces, legacy_roots, repository.skills_root)
        for adapter in adapters
        for skill in repository.skills
    )
    return ManagedState(repository, tuple(adapters), tuple(surfaces.values()), targets)


def _fixed_inventory_sources(home: Path) -> list[InventorySource]:
    return [
        InventorySource(
            home / ".claude/skills",
            ("claude",),
            ("claude-desktop", "claude-cli"),
            "user-root",
        ),
        InventorySource(
            home / ".codex/skills",
            ("codex",),
            ("codex-desktop", "codex-cli"),
            "user-root",
        ),
        InventorySource(
            home / ".codex/skills/.system",
            ("codex",),
            ("codex-desktop", "codex-cli"),
            "built-in",
        ),
        InventorySource(
            home / ".copilot/skills",
            ("copilot",),
            ("copilot-desktop", "copilot-cli"),
            "user-root",
        ),
        InventorySource(
            home / ".agents/skills",
            ("copilot",),
            ("copilot-desktop", "copilot-cli"),
            "shared-user-root",
        ),
        InventorySource(
            home / ".gemini/config/skills",
            ("antigravity",),
            ("antigravity-desktop",),
            "user-root",
        ),
        InventorySource(
            home / ".gemini/antigravity-cli/skills",
            ("antigravity",),
            ("antigravity-cli",),
            "user-root",
            True,
        ),
        InventorySource(
            home / "Library/Application Support/com.github.githubapp/app-skills",
            ("copilot",),
            ("copilot-desktop",),
            "built-in",
        ),
    ]


def _enabled_codex_plugin_sources(
    home: Path,
) -> tuple[list[InventorySource], list[ScanIssue]]:
    config_path = home / ".codex/config.toml"
    if not config_path.is_file():
        return [], []
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    plugins = config.get("plugins", {})
    sources: list[InventorySource] = []
    issues: list[ScanIssue] = []
    for key, settings in plugins.items():
        if (
            not isinstance(settings, dict)
            or settings.get("enabled") is not True
            or "@" not in key
        ):
            continue
        plugin, marketplace = key.rsplit("@", 1)
        cache = home / ".codex/plugins/cache"
        remote = cache / f"{marketplace}-remote" / plugin
        regular = cache / marketplace / plugin
        plugin_root = (
            remote
            if (remote / ".codex-remote-plugin-install.json").is_file()
            else regular
        )
        manifests = list(plugin_root.glob("*/.codex-plugin/plugin.json"))
        manifests.extend(plugin_root.glob("*/.claude-plugin/plugin.json"))
        if not manifests:
            issues.append(
                ScanIssue(
                    "plugin-manifest-missing",
                    plugin_root,
                    f"enabled plugin has no manifest: {key}",
                )
            )
            continue
        manifest_mtimes: list[tuple[int, Path]] = []
        manifest_error = False
        for manifest_path in manifests:
            try:
                manifest_mtimes.append((manifest_path.stat().st_mtime_ns, manifest_path))
            except OSError as exc:
                issues.append(
                    ScanIssue(
                        "plugin-manifest-invalid",
                        manifest_path,
                        f"enabled plugin manifest cannot be inspected: {key}: {exc}",
                    )
                )
                manifest_error = True
                break
        if manifest_error:
            continue
        manifest_path = max(manifest_mtimes, key=lambda item: item[0])[1]
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest must be an object")
            skills_rel = manifest.get("skills", "skills")
            if not isinstance(skills_rel, str):
                raise ValueError("manifest skills must be a string")
        except (OSError, UnicodeError, ValueError) as exc:
            issues.append(
                ScanIssue(
                    "plugin-manifest-invalid",
                    manifest_path,
                    f"enabled plugin manifest cannot be parsed: {key}: {exc}",
                )
            )
            continue
        version_root = manifest_path.parent.parent
        relative_skills = Path(skills_rel)
        try:
            if relative_skills.is_absolute() or ".." in relative_skills.parts:
                raise ValueError("manifest skills must be a safe relative path")
            skills_root = version_root / relative_skills
            resolved_version_root = version_root.resolve(strict=True)
            resolved_skills_root = skills_root.resolve(strict=False)
            resolved_skills_root.relative_to(resolved_version_root)
        except (OSError, RuntimeError, ValueError) as exc:
            issues.append(
                ScanIssue(
                    "plugin-skills-path-invalid",
                    manifest_path,
                    f"enabled plugin skills path is unsafe: {key}: {exc}",
                )
            )
            continue
        sources.append(
            InventorySource(
                skills_root,
                ("codex",),
                ("codex-desktop", "codex-cli"),
                "plugin",
            )
        )
    return sources, issues


def _scan_inventory_source(
    source: InventorySource,
    managed_paths: set[Path],
) -> list[InventoryRecord]:
    if not source.root.is_dir():
        return []
    candidates = set(source.root.glob("*.md")) if source.flat_markdown else set()
    candidates.update(
        path for path in source.root.iterdir() if path.is_dir() or path.is_symlink()
    )
    records: list[InventoryRecord] = []
    for candidate in sorted(candidates, key=lambda path: path.name):
        if candidate.name.startswith("."):
            continue
        metadata_path = candidate if candidate.suffix == ".md" else candidate / "SKILL.md"
        slug = candidate.stem if candidate.suffix == ".md" else candidate.name
        source_type = source.source_type
        flags: list[str] = []
        if candidate.is_symlink():
            raw_target: Path | None = None
            try:
                raw_target = Path(os.readlink(candidate))
                resolved: Path | None = candidate.resolve(strict=False)
                link_exists = candidate.exists()
            except (OSError, RuntimeError):
                resolved = None
                link_exists = False
        else:
            raw_target = None
            resolved = candidate.resolve(strict=False)
            link_exists = True
        if not link_exists:
            resolved = None
            records.append(
                InventoryRecord(
                    slug,
                    slug,
                    "",
                    candidate,
                    raw_target,
                    resolved,
                    source.tools,
                    source.surfaces,
                    "broken",
                    ("broken-link",),
                )
            )
            continue
        if resolved in managed_paths:
            source_type = "managed"
        elif candidate.is_symlink():
            source_type = "external-link"
        elif source.source_type not in {"built-in", "plugin"}:
            source_type = "local-copy"
        try:
            metadata = _read_frontmatter(metadata_path)
            name = str(metadata.get("name", "")).strip()
            description = str(metadata.get("description", "")).strip()
            if not name:
                raise ValueError("missing frontmatter name")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            name, description, source_type = slug, "", "broken"
            flags.append(f"invalid-skill:{exc}")
        records.append(
            InventoryRecord(
                slug,
                name,
                description,
                candidate,
                raw_target,
                resolved,
                source.tools,
                source.surfaces,
                source_type,
                tuple(flags),
            )
        )
    return records


def scan_inventory(state: ManagedState, home: Path) -> tuple[InventoryRecord, ...]:
    plugin_sources = [
        InventorySource(
            path,
            ("antigravity",),
            ("antigravity-desktop",),
            "plugin",
        )
        for path in home.glob(".gemini/config/plugins/*/skills")
    ]
    plugin_sources.extend(
        InventorySource(
            path,
            ("antigravity",),
            ("antigravity-cli",),
            "plugin",
        )
        for path in home.glob(".gemini/antigravity-cli/plugins/*/skills")
    )
    codex_sources, _issues = _enabled_codex_plugin_sources(home)
    managed_paths = {skill.path.resolve() for skill in state.repository.skills}
    records = [
        record
        for source in [*_fixed_inventory_sources(home), *plugin_sources, *codex_sources]
        for record in _scan_inventory_source(source, managed_paths)
    ]
    duplicate_counts = Counter(
        (surface, record.name)
        for record in records
        for surface in record.surfaces
    )
    duplicate_keys = {
        key for key, count in duplicate_counts.items() if count > 1
    }
    return tuple(
        InventoryRecord(
            record.slug,
            record.name,
            record.description,
            record.path,
            record.raw_target,
            record.resolved_target,
            record.tools,
            record.surfaces,
            record.source_type,
            record.flags
            + (
                ("duplicate-name",)
                if any(
                    (surface, record.name) in duplicate_keys
                    for surface in record.surfaces
                )
                else ()
            ),
        )
        for record in records
    )


def snapshot_path(path: Path) -> PathSnapshot:
    if not _lexists(path):
        return PathSnapshot("missing")
    if path.is_symlink():
        return PathSnapshot("symlink", os.readlink(path))
    if path.is_dir():
        return PathSnapshot("directory")
    return PathSnapshot("file")


def plan_set(
    state: ManagedState,
    slugs: Sequence[str],
    tools: Sequence[str],
    enabled: bool,
) -> ChangePlan:
    skill_by_slug = {skill.slug: skill for skill in state.repository.skills}
    selected_adapters = {
        adapter.key
        for adapter in state.adapters
        if adapter.tool in tools or "all" in tools
    }
    statuses = {(item.adapter_key, item.slug): item for item in state.targets}
    changes: list[PlannedChange] = []
    for slug in dict.fromkeys(slugs):
        if slug not in skill_by_slug:
            raise ValueError(f"unknown skill slug: {slug}")
        skill = skill_by_slug[slug]
        for adapter in state.adapters:
            if adapter.key not in selected_adapters:
                continue
            status = statuses[(adapter.key, slug)]
            if enabled and status.state == LinkState.DISABLED:
                action, reason = "create", "enable skill"
            elif (
                not enabled
                and status.state == LinkState.LEGACY
                and status.raw_target == adapter.root
            ):
                action, reason = (
                    "requires-adopt",
                    "legacy directory link must be adopted before disabling skills",
                )
            elif not enabled and status.state in {LinkState.ENABLED, LinkState.LEGACY}:
                action, reason = "remove", "disable managed skill"
            elif (enabled and status.state == LinkState.ENABLED) or (
                not enabled and status.state == LinkState.DISABLED
            ):
                action, reason = "no-op", "already in requested state"
            elif status.state == LinkState.UNAVAILABLE:
                action, reason = "unavailable", "surface is not installed"
            elif enabled and status.state == LinkState.LEGACY:
                action, reason = "requires-adopt", "legacy link must be adopted first"
            else:
                action, reason = "blocked", status.message
            changes.append(
                PlannedChange(
                    action,
                    slug,
                    adapter.key,
                    skill.path,
                    status.path,
                    snapshot_path(status.path),
                    reason,
                )
            )
    return ChangePlan(tuple(changes), state.repository)


def _write_snapshot(plan: AdoptionPlan) -> None:
    plan.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "links": [
            {
                "path": str(item.target),
                "kind": item.expected.kind,
                "link_target": item.expected.link_target,
            }
            for item in plan.link_changes
        ],
        "containers": [
            {
                "path": str(item.root),
                "kind": item.expected.kind,
                "link_target": item.expected.link_target,
            }
            for item in plan.container_changes
        ],
        "bridges": [
            {
                "path": str(item.path),
                "kind": item.expected.kind,
                "link_target": item.expected.link_target,
            }
            for item in plan.bridge_removals
        ],
    }
    plan.snapshot_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _inspect_repository_container(repository: RepositoryScan) -> tuple[bool, str]:
    if repository.issues:
        return False, "repository skills root contains invalid entries"
    managed = {skill.slug for skill in repository.skills}
    try:
        children = {
            child.name
            for child in repository.skills_root.iterdir()
            if child.name != ".DS_Store"
        }
    except OSError as exc:
        return False, f"repository skills root cannot be inspected: {exc}"
    if children != managed:
        unmanaged = sorted(children - managed)
        missing = sorted(managed - children)
        details: list[str] = []
        if unmanaged:
            details.append(f"unmanaged: {', '.join(unmanaged)}")
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        return False, (
            "repository skills root differs from managed skills "
            f"({'; '.join(details)})"
        )
    for skill in repository.skills:
        expected = repository.skills_root / skill.slug
        if expected.is_symlink() or not expected.is_dir() or skill.path != expected:
            return False, "repository skills root contains invalid entries"
    return True, "repository skills root contains only managed skills"


def _inspect_antigravity_legacy_container(
    home: Path,
    repository: RepositoryScan,
) -> tuple[bool, str]:
    plugin_skills = home / ".gemini/config/plugins/custom-skills/skills"
    if not plugin_skills.is_symlink():
        return False, "legacy custom-skills entry not found"
    resolved_root = plugin_skills.resolve(strict=False)
    if not resolved_root.is_dir():
        return False, "legacy custom-skills entry is broken"
    expected = {skill.path.resolve() for skill in repository.skills}
    children = [path for path in resolved_root.iterdir() if not path.name.startswith(".")]
    if not children or any(
        not path.is_symlink() or path.resolve(strict=False) not in expected
        for path in children
    ):
        return False, "mixed or unmanaged entries in legacy custom-skills container"
    return True, "safe legacy custom-skills container"


def _plan_antigravity_legacy_bridge(
    state: ManagedState,
    existing_changes: Sequence[PlannedChange],
) -> tuple[list[PlannedChange], BridgeRemoval | None]:
    home = state.adapters[0].home
    bridge = home / ".gemini/config/plugins/custom-skills/skills"
    if not _lexists(bridge):
        return [], None
    desktop = next(
        adapter for adapter in state.adapters if adapter.key == "antigravity-desktop"
    )
    surfaces = {surface.key: surface for surface in state.surfaces}
    if not _adapter_available(desktop, surfaces):
        return [
            PlannedChange(
                "unavailable",
                "*",
                desktop.key,
                state.repository.skills_root,
                bridge,
                snapshot_path(bridge),
                "Antigravity Desktop surface is not installed",
            )
        ], None
    safe, reason = _inspect_antigravity_legacy_container(home, state.repository)
    if not safe:
        blocked = PlannedChange(
            "blocked",
            "*",
            desktop.key,
            state.repository.skills_root,
            bridge,
            snapshot_path(bridge),
            reason,
        )
        return [blocked], None
    legacy_root = bridge.resolve(strict=False)
    legacy_entries = tuple(
        (child.name, snapshot_path(child), child.resolve(strict=False))
        for child in sorted(legacy_root.iterdir(), key=lambda path: path.name)
        if not child.name.startswith(".")
    )
    existing_by_target = {
        change.target: change
        for change in existing_changes
        if change.adapter_key == desktop.key
    }
    changes: list[PlannedChange] = []
    required: list[tuple[Path, Path]] = []
    for skill in state.repository.skills:
        target = desktop.root / skill.slug
        current = snapshot_path(target)
        existing = existing_by_target.get(target)
        if existing is not None:
            required.append((target, skill.path))
            continue
        if current.kind == "missing":
            action, message = "create", "move Antigravity skill to official user root"
        elif _target_is_direct_link(target, skill.path):
            action, message = (
                "no-op",
                "official user-root link already resolves to repository",
            )
        else:
            action, message = "blocked", "official Antigravity target is occupied"
        changes.append(
            PlannedChange(
                action,
                skill.slug,
                desktop.key,
                skill.path,
                target,
                current,
                message,
            )
        )
        required.append((target, skill.path))
    removal = BridgeRemoval(
        desktop.key,
        bridge,
        snapshot_path(bridge),
        legacy_root,
        legacy_entries,
        tuple(required),
        "remove verified legacy custom-skills bridge",
    )
    return changes, removal


def plan_adoption(state: ManagedState, state_dir: Path) -> AdoptionPlan:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    repository_root = state.repository.skills_root
    sources = {skill.slug: skill.path for skill in state.repository.skills}
    link_changes: list[PlannedChange] = []
    container_changes: list[ContainerChange] = []
    container_adapters: set[str] = set()
    surfaces = {surface.key: surface for surface in state.surfaces}
    for adapter in state.adapters:
        root_snapshot = snapshot_path(adapter.root)
        if (
            root_snapshot.kind == "symlink"
            and adapter.root.resolve(strict=False) == repository_root.resolve()
        ):
            container_adapters.add(adapter.key)
            if not _adapter_available(adapter, surfaces):
                link_changes.append(
                    PlannedChange(
                        "unavailable",
                        "*",
                        adapter.key,
                        repository_root,
                        adapter.root,
                        root_snapshot,
                        "surface is not installed; whole-directory link was not adopted",
                    )
                )
                continue
            safe, reason = _inspect_repository_container(state.repository)
            if safe:
                container_changes.append(
                    ContainerChange(
                        adapter.key,
                        adapter.root,
                        root_snapshot,
                        tuple(
                            (skill.slug, skill.path)
                            for skill in state.repository.skills
                        ),
                        "whole repository link",
                    )
                )
            else:
                link_changes.append(
                    PlannedChange(
                        "blocked",
                        "*",
                        adapter.key,
                        repository_root,
                        adapter.root,
                        root_snapshot,
                        reason,
                    )
                )
    for target in state.targets:
        if target.adapter_key in container_adapters or target.state != LinkState.LEGACY:
            continue
        link_changes.append(
            PlannedChange(
                "create",
                target.slug,
                target.adapter_key,
                sources[target.slug],
                target.path,
                snapshot_path(target.path),
                "replace legacy link with direct repository link",
            )
        )
    bridge_changes, bridge_removal = _plan_antigravity_legacy_bridge(
        state,
        link_changes,
    )
    link_changes.extend(bridge_changes)
    bridge_removals = () if bridge_removal is None else (bridge_removal,)
    return AdoptionPlan(
        tuple(link_changes),
        tuple(container_changes),
        bridge_removals,
        state_dir / "snapshots" / f"{timestamp}.json",
        state.repository,
    )


VALID_PLAN_ACTIONS = frozenset(
    {"create", "remove", "no-op", "unavailable", "requires-adopt", "blocked"}
)


class _InvalidPlanError(ValueError):
    pass


class _StateChangedError(RuntimeError):
    pass


class _TargetConflictError(OSError):
    pass


def _trusted_source(plan: ChangePlan, change: PlannedChange) -> Path:
    if plan.repository is None:
        raise _InvalidPlanError("plan has no repository provenance")
    fresh = scan_repository(plan.repository.repo_root)
    if fresh.repo_root != plan.repository.repo_root.resolve():
        raise _InvalidPlanError("repository provenance does not match repository root")
    expected_skills_root = fresh.repo_root / "skills"
    if fresh.skills_root != expected_skills_root:
        raise _InvalidPlanError("repository skills root is invalid")
    trusted = {skill.slug: skill for skill in fresh.skills}.get(change.slug)
    if trusted is None:
        raise _StateChangedError("repository skill changed after planning")
    expected_source = expected_skills_root / change.slug
    skill_file = expected_source / "SKILL.md"
    if (
        expected_source.is_symlink()
        or trusted.path != expected_source
        or not skill_file.is_file()
        or skill_file.is_symlink()
    ):
        raise _InvalidPlanError("repository skill is not a trusted in-repository directory")
    if change.source != trusted.path:
        raise _InvalidPlanError("planned source is not the trusted repository skill")
    return trusted.path


def _validate_adapter_root(adapter: TargetAdapter) -> None:
    home = Path(os.path.abspath(adapter.home))
    root = Path(os.path.abspath(adapter.root))
    try:
        relative = root.relative_to(home)
    except ValueError as exc:
        raise _InvalidPlanError("adapter root is outside adapter home") from exc
    expected_resolved = adapter.home.resolve(strict=False) / relative
    if adapter.root.is_symlink() or adapter.root.resolve(strict=False) != expected_resolved:
        raise _StateChangedError("adapter root or parent changed after planning")
    if _lexists(adapter.root) and not adapter.root.is_dir():
        raise _StateChangedError("adapter root is not a directory")


def _validate_change(
    plan: ChangePlan,
    change: PlannedChange,
    adapters: Mapping[str, TargetAdapter],
) -> tuple[TargetAdapter, Path]:
    if not isinstance(change.action, str) or change.action not in VALID_PLAN_ACTIONS:
        raise _InvalidPlanError(f"unknown plan action: {change.action}")
    if not isinstance(change.slug, str) or not SLUG_RE.fullmatch(change.slug):
        raise _InvalidPlanError(f"invalid skill slug: {change.slug}")
    try:
        adapter = adapters[change.adapter_key]
    except (KeyError, TypeError) as exc:
        raise _InvalidPlanError(f"unknown adapter: {change.adapter_key}") from exc
    if not isinstance(change.target, Path) or change.target != adapter.root / change.slug:
        raise _InvalidPlanError("planned target does not match adapter root and slug")
    if not isinstance(change.source, Path):
        raise _InvalidPlanError("planned source is not a path")
    source = _trusted_source(plan, change)
    return adapter, source


def _open_adapter_root(adapter: TargetAdapter, create: bool) -> tuple[int, Path]:
    _validate_adapter_root(adapter)
    if create:
        adapter.root.mkdir(parents=True, exist_ok=True)
        _validate_adapter_root(adapter)
    if not adapter.root.is_dir():
        raise _StateChangedError("adapter root does not exist")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(adapter.root, flags)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise _StateChangedError("adapter root is not a directory")
        _validate_adapter_root(adapter)
        return fd, adapter.root.resolve(strict=True)
    except BaseException:
        os.close(fd)
        raise


def _snapshot_entry(fd: int, name: str) -> PathSnapshot:
    try:
        metadata = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return PathSnapshot("missing")
    if stat.S_ISLNK(metadata.st_mode):
        return PathSnapshot("symlink", os.readlink(name, dir_fd=fd))
    if stat.S_ISDIR(metadata.st_mode):
        return PathSnapshot("directory")
    return PathSnapshot("file")


def _entry_is_managed_link(
    fd: int,
    name: str,
    parent: Path,
    source: Path,
    adapter: TargetAdapter,
    allow_legacy: bool,
) -> bool:
    snapshot = _snapshot_entry(fd, name)
    if snapshot.kind != "symlink" or snapshot.link_target is None:
        return False
    raw_path = Path(snapshot.link_target)
    absolute_raw = raw_path if raw_path.is_absolute() else parent / raw_path
    absolute_raw = Path(os.path.abspath(absolute_raw))
    expected = source.resolve(strict=True)
    direct = absolute_raw == expected
    legacy = allow_legacy and any(
        _under(absolute_raw, root)
        for root in (adapter.home / ".cc-switch/skills", adapter.home / ".gemini/skills")
    )
    return (direct or legacy) and absolute_raw.resolve(strict=False) == expected


def _entry_raw_points_to_source(
    fd: int,
    name: str,
    parent: Path,
    source: Path,
) -> bool:
    snapshot = _snapshot_entry(fd, name)
    if snapshot.kind != "symlink" or snapshot.link_target is None:
        return False
    raw = Path(snapshot.link_target)
    absolute_raw = raw if raw.is_absolute() else parent / raw
    return Path(os.path.abspath(absolute_raw)) == source


def _source_still_valid(source: Path) -> bool:
    return (
        source.is_dir()
        and not source.is_symlink()
        and (source / "SKILL.md").is_file()
        and not (source / "SKILL.md").is_symlink()
    )


def _target_is_direct_link(target: Path, source: Path) -> bool:
    if not target.is_symlink():
        return False
    raw = Path(os.readlink(target))
    absolute_raw = raw if raw.is_absolute() else target.parent / raw
    return (
        Path(os.path.abspath(absolute_raw)) == source.resolve(strict=True)
        and target.resolve(strict=False) == source.resolve(strict=True)
    )


def _install_link(source: Path, target: Path, adapter: TargetAdapter) -> None:
    fd, parent = _open_adapter_root(adapter, create=True)
    try:
        os.symlink(source, target.name, dir_fd=fd)
        if not _source_still_valid(source):
            if _entry_raw_points_to_source(fd, target.name, parent, source):
                os.unlink(target.name, dir_fd=fd)
            raise _StateChangedError("repository skill changed during creation")
        if not _entry_is_managed_link(
            fd,
            target.name,
            parent,
            source,
            adapter,
            allow_legacy=False,
        ):
            raise OSError("post-operation verification failed")
    finally:
        os.close(fd)


def _restore_isolated_link(fd: int, temporary: str, target: str) -> bool:
    raw = os.readlink(temporary, dir_fd=fd)
    try:
        os.symlink(raw, target, dir_fd=fd)
    except FileExistsError:
        return False
    os.unlink(temporary, dir_fd=fd)
    return True


def _remove_link(
    change: PlannedChange,
    adapter: TargetAdapter,
    source: Path,
) -> tuple[bool, str, str]:
    fd, parent = _open_adapter_root(adapter, create=False)
    temporary = f".{change.target.name}.lucas-skills-{uuid.uuid4().hex}.old"
    try:
        if _snapshot_entry(fd, change.target.name) != change.expected:
            return False, "state-changed", "target changed before isolation"
        if _snapshot_entry(fd, temporary).kind != "missing":
            return False, "verification-failed", "temporary isolation path already exists"
        os.rename(
            change.target.name,
            temporary,
            src_dir_fd=fd,
            dst_dir_fd=fd,
        )
        isolated = _snapshot_entry(fd, temporary)
        if isolated != change.expected:
            restored = _restore_isolated_link(fd, temporary, change.target.name)
            suffix = "" if restored else f"; isolated link retained as {temporary}"
            return False, "state-changed", f"target changed during isolation{suffix}"
        try:
            _validate_adapter_root(adapter)
            if not adapter.root.is_dir():
                raise _StateChangedError("adapter root disappeared during removal")
        except _StateChangedError as exc:
            restored = _restore_isolated_link(fd, temporary, change.target.name)
            suffix = "" if restored else f"; isolated link retained as {temporary}"
            return False, "state-changed", f"{exc}{suffix}"
        if not _source_still_valid(source):
            restored = _restore_isolated_link(fd, temporary, change.target.name)
            suffix = "" if restored else f"; isolated link retained as {temporary}"
            return False, "state-changed", f"repository skill changed during removal{suffix}"
        if not _entry_is_managed_link(
            fd,
            temporary,
            parent,
            source,
            adapter,
            allow_legacy=True,
        ):
            restored = _restore_isolated_link(fd, temporary, change.target.name)
            suffix = "" if restored else f"; isolated link retained as {temporary}"
            return False, "target-conflict", f"target is not a recognized managed link{suffix}"
        os.unlink(temporary, dir_fd=fd)
        if _snapshot_entry(fd, change.target.name).kind != "missing":
            return False, "verification-failed", "target reappeared during removal"
        return True, "applied", change.reason
    finally:
        os.close(fd)


def _operation_result(
    ok: bool,
    code: str,
    change: PlannedChange,
    message: str,
) -> OperationResult:
    path = change.target if isinstance(change.target, Path) else Path(".")
    return OperationResult(ok, code, change.slug, change.adapter_key, path, message)


def _trusted_adoption_sources(plan: AdoptionPlan) -> dict[str, Path]:
    if plan.repository is None:
        raise _InvalidPlanError("adoption plan has no repository provenance")
    fresh = scan_repository(plan.repository.repo_root)
    if fresh.repo_root != plan.repository.repo_root.resolve():
        raise _InvalidPlanError("repository provenance does not match repository root")
    if fresh.skills_root != fresh.repo_root / "skills":
        raise _InvalidPlanError("repository skills root is invalid")
    planned = tuple((skill.slug, skill.path) for skill in plan.repository.skills)
    current = tuple((skill.slug, skill.path) for skill in fresh.skills)
    if current != planned:
        raise _StateChangedError("repository skills changed after planning")
    sources: dict[str, Path] = {}
    for skill in fresh.skills:
        expected = fresh.skills_root / skill.slug
        skill_file = expected / "SKILL.md"
        if (
            expected.is_symlink()
            or skill.path != expected
            or not skill_file.is_file()
            or skill_file.is_symlink()
        ):
            raise _InvalidPlanError(
                "repository skill is not a trusted in-repository directory"
            )
        sources[skill.slug] = skill.path
    return sources


def _validate_adoption_location(adapter: TargetAdapter, path: Path) -> None:
    if path != adapter.root:
        raise _InvalidPlanError("planned container does not match adapter root")
    home = Path(os.path.abspath(adapter.home))
    root = Path(os.path.abspath(adapter.root))
    try:
        relative = root.relative_to(home)
    except ValueError as exc:
        raise _InvalidPlanError("adapter root is outside adapter home") from exc
    expected_parent = adapter.home.resolve(strict=False) / relative.parent
    if adapter.root.parent.resolve(strict=False) != expected_parent:
        raise _StateChangedError("adapter root parent changed after planning")


def _validate_container_change(
    plan: AdoptionPlan,
    change: ContainerChange,
    adapters: Mapping[str, TargetAdapter],
) -> tuple[TargetAdapter, dict[str, Path]]:
    try:
        adapter = adapters[change.adapter_key]
    except (KeyError, TypeError) as exc:
        raise _InvalidPlanError(f"unknown adapter: {change.adapter_key}") from exc
    _validate_adoption_location(adapter, change.root)
    sources = _trusted_adoption_sources(plan)
    current_repository = scan_repository(plan.repository.repo_root)
    safe, reason = _inspect_repository_container(current_repository)
    if not safe:
        raise _StateChangedError(reason)
    if change.expected.kind != "symlink" or change.expected.link_target is None:
        raise _InvalidPlanError("planned container is not a directory link")
    if snapshot_path(change.root) != change.expected:
        raise _StateChangedError("container changed after planning")
    if change.root.resolve(strict=False) != plan.repository.skills_root.resolve():
        raise _StateChangedError("container no longer points to repository skills")
    if change.links != tuple(sources.items()):
        raise _InvalidPlanError("planned container links do not match repository skills")
    return adapter, sources


def _raw_link_points_to(path: Path, source: Path) -> bool:
    if not path.is_symlink():
        return False
    raw = Path(os.readlink(path))
    absolute_raw = raw if raw.is_absolute() else path.parent / raw
    return Path(os.path.abspath(absolute_raw)) == source


def _remove_owned_directory(
    directory: Path,
    links: tuple[tuple[str, Path], ...],
    *,
    allow_partial: bool,
) -> bool:
    if not directory.is_dir() or directory.is_symlink():
        return False
    expected = dict(links)
    children = tuple(directory.iterdir())
    if not allow_partial and {child.name for child in children} != set(expected):
        return False
    if any(
        child.name not in expected or not _raw_link_points_to(child, expected[child.name])
        for child in children
    ):
        return False
    for child in children:
        child.unlink()
    directory.rmdir()
    return True


def _restore_container_link(
    root: Path,
    backup: Path,
    expected: PathSnapshot,
) -> None:
    if expected.kind != "symlink" or snapshot_path(backup) != expected:
        raise OSError("original container backup changed during recovery")
    raw_target = os.readlink(backup)
    os.symlink(raw_target, root, target_is_directory=True)
    if snapshot_path(root) != expected:
        raise OSError("restored container link failed verification")
    backup.unlink()


def _apply_container_change(
    plan: AdoptionPlan,
    change: ContainerChange,
    adapters: Mapping[str, TargetAdapter],
) -> None:
    _adapter, sources = _validate_container_change(plan, change, adapters)
    temporary = change.root.parent / f".{change.root.name}.lucas-skills-{uuid.uuid4().hex}.tmp"
    backup = change.root.parent / f".{change.root.name}.lucas-skills-{uuid.uuid4().hex}.old"
    isolated = False
    installed = False
    try:
        temporary.mkdir()
        for slug, source in change.links:
            if sources.get(slug) != source or not _source_still_valid(source):
                raise _StateChangedError("repository skill changed during adoption")
            (temporary / slug).symlink_to(source)
        if snapshot_path(change.root) != change.expected:
            raise _StateChangedError("container changed before isolation")
        os.replace(change.root, backup)
        isolated = True
        if snapshot_path(backup) != change.expected:
            raise _StateChangedError("container changed during isolation")
        os.replace(temporary, change.root)
        installed = True
        for slug, source in change.links:
            if not _source_still_valid(source) or not _target_is_direct_link(
                change.root / slug, source
            ):
                raise OSError(f"verification failed for {slug}")
        backup.unlink()
        isolated = False
    except Exception as exc:
        recovery: Path | None = None
        try:
            if installed and not _remove_owned_directory(
                change.root,
                change.links,
                allow_partial=False,
            ):
                if _lexists(change.root):
                    recovery = change.root.parent / (
                        f".{change.root.name}.lucas-skills-"
                        f"{uuid.uuid4().hex}.recovery"
                    )
                    os.replace(change.root, recovery)
                installed = False
            if isolated:
                if not _lexists(backup):
                    raise OSError("original container backup is missing")
                _restore_container_link(change.root, backup, change.expected)
                isolated = False
        except Exception as rollback_exc:
            retained = []
            if _lexists(change.root):
                retained.append(f"occupied root retained at {change.root}")
            if recovery is not None and _lexists(recovery):
                retained.append(f"failed directory retained at {recovery}")
            if _lexists(backup):
                retained.append(f"original link retained at {backup}")
            locations = "; ".join(retained) or "no recovery path could be confirmed"
            raise RuntimeError(
                f"{exc}; rollback failed: {rollback_exc}; {locations}"
            ) from exc
        if recovery is not None:
            raise RuntimeError(
                f"{exc}; original link restored; failed directory retained at {recovery}"
            ) from exc
        raise
    finally:
        if _lexists(temporary):
            _remove_owned_directory(temporary, change.links, allow_partial=True)


def _apply_link_adoption(
    plan: AdoptionPlan,
    change: PlannedChange,
    adapters: Mapping[str, TargetAdapter],
) -> None:
    if change.action != "create":
        raise _InvalidPlanError("adoption link change must create a direct link")
    sources = _trusted_adoption_sources(plan)
    adapter, source = _validate_change(
        ChangePlan(plan.link_changes, plan.repository),
        change,
        adapters,
    )
    if sources.get(change.slug) != source:
        raise _InvalidPlanError("planned source is not a current repository skill")
    if change.expected.kind == "missing":
        _validate_adapter_root(adapter)
        if snapshot_path(change.target) != change.expected:
            raise _StateChangedError("target changed after planning")
        _install_link(source, change.target, adapter)
        if not _target_is_direct_link(change.target, source):
            raise OSError("post-operation verification failed")
        return
    if change.expected.kind != "symlink" or change.expected.link_target is None:
        raise _InvalidPlanError("planned legacy target is not a symlink")
    _validate_adapter_root(adapter)
    fd, parent = _open_adapter_root(adapter, create=False)
    backup = f".{change.target.name}.lucas-skills-{uuid.uuid4().hex}.old"
    isolated = False
    created = False
    try:
        if _snapshot_entry(fd, change.target.name) != change.expected:
            raise _StateChangedError("target changed after planning")
        if not _entry_is_managed_link(
            fd,
            change.target.name,
            parent,
            source,
            adapter,
            allow_legacy=True,
        ) or _entry_raw_points_to_source(fd, change.target.name, parent, source):
            raise _StateChangedError("target is no longer a recognized legacy link")
        os.rename(change.target.name, backup, src_dir_fd=fd, dst_dir_fd=fd)
        isolated = True
        if _snapshot_entry(fd, backup) != change.expected:
            raise _StateChangedError("target changed during isolation")
        _validate_adapter_root(adapter)
        os.symlink(source, change.target.name, dir_fd=fd)
        created = True
        if not _source_still_valid(source) or not _entry_is_managed_link(
            fd,
            change.target.name,
            parent,
            source,
            adapter,
            allow_legacy=False,
        ):
            raise OSError("post-operation verification failed")
        os.unlink(backup, dir_fd=fd)
        isolated = False
    except Exception:
        if created and _entry_raw_points_to_source(
            fd, change.target.name, parent, source
        ):
            os.unlink(change.target.name, dir_fd=fd)
        if isolated and _snapshot_entry(fd, change.target.name).kind == "missing":
            os.rename(backup, change.target.name, src_dir_fd=fd, dst_dir_fd=fd)
            isolated = False
        raise
    finally:
        os.close(fd)


def _apply_bridge_removal(change: BridgeRemoval) -> None:
    if snapshot_path(change.path) != change.expected:
        raise _StateChangedError("bridge changed after planning")
    legacy_root = change.path.resolve(strict=False)
    if legacy_root != change.legacy_root or not legacy_root.is_dir():
        raise _StateChangedError("legacy custom-skills container changed after planning")
    current_entries = {
        child.name: child
        for child in legacy_root.iterdir()
        if not child.name.startswith(".")
    }
    expected_entries = {
        name: (expected, source)
        for name, expected, source in change.legacy_entries
    }
    if set(current_entries) != set(expected_entries):
        raise _StateChangedError("legacy custom-skills container changed after planning")
    for name, child in current_entries.items():
        expected, source = expected_entries[name]
        if (
            snapshot_path(child) != expected
            or not child.is_symlink()
            or not _source_still_valid(source)
            or child.resolve(strict=False) != source
        ):
            raise _StateChangedError(
                f"legacy custom-skills entry changed after planning: {name}"
            )
    for target, source in change.required_links:
        if not _target_is_direct_link(target, source):
            raise _StateChangedError(f"required direct link missing: {target}")
    change.path.unlink()


def _prepare_adapter(adapter: TargetAdapter) -> None:
    if adapter.manifest_path is None:
        adapter.root.mkdir(parents=True, exist_ok=True)
        return
    plugin_root = adapter.manifest_path.parent
    if plugin_root.exists() and not plugin_root.is_dir():
        raise OSError("plugin root is not a directory")
    plugin_root.mkdir(parents=True, exist_ok=True)
    if adapter.manifest_path.exists():
        data = json.loads(adapter.manifest_path.read_text(encoding="utf-8"))
        if data.get("name") != "lucas-skills":
            raise _TargetConflictError("plugin manifest belongs to another owner")
    else:
        temporary = plugin_root / f".plugin-{uuid.uuid4().hex}.tmp"
        temporary.write_text(adapter.manifest_content or "", encoding="utf-8")
        os.replace(temporary, adapter.manifest_path)
    if _lexists(adapter.root) and not adapter.root.is_dir():
        raise OSError("plugin skills path is not a directory")
    adapter.root.mkdir(parents=True, exist_ok=True)


def apply_plan(
    plan: ChangePlan,
    adapters: Mapping[str, TargetAdapter],
) -> BatchResult:
    results: list[OperationResult] = []
    for change in plan.changes:
        try:
            adapter, source = _validate_change(plan, change, adapters)
            if change.action == "unavailable":
                results.append(_operation_result(True, "unavailable", change, change.reason))
                continue
            if change.action in {"blocked", "requires-adopt"}:
                results.append(_operation_result(False, change.action, change, change.reason))
                continue
            _validate_adapter_root(adapter)
            current = snapshot_path(change.target)
            if change.action == "no-op":
                terminal = current.kind == "missing" or _target_is_direct_link(
                    change.target, source
                )
                if current != change.expected or not terminal:
                    raise _StateChangedError("target changed after planning")
                results.append(_operation_result(True, "no-op", change, change.reason))
                continue
            if current != change.expected:
                if change.action == "create" and _target_is_direct_link(
                    change.target, source
                ):
                    results.append(
                        _operation_result(True, "no-op", change, "already enabled")
                    )
                    continue
                if change.action == "remove" and current.kind == "missing":
                    results.append(
                        _operation_result(True, "no-op", change, "already disabled")
                    )
                    continue
                raise _StateChangedError("target changed after planning")
            if change.action == "create":
                try:
                    _prepare_adapter(adapter)
                    _install_link(source, change.target, adapter)
                except FileExistsError:
                    if _target_is_direct_link(change.target, source):
                        results.append(
                            _operation_result(True, "no-op", change, "already enabled")
                        )
                        continue
                    raise _StateChangedError("target appeared during creation")
                _validate_adapter_root(adapter)
                if not _target_is_direct_link(change.target, source):
                    raise OSError("post-operation verification failed")
                results.append(_operation_result(True, "applied", change, change.reason))
            else:
                if change.expected.kind != "symlink":
                    results.append(
                        _operation_result(
                            False,
                            "target-conflict",
                            change,
                            "target is not a symlink",
                        )
                    )
                    continue
                ok, code, message = _remove_link(change, adapter, source)
                results.append(_operation_result(ok, code, change, message))
        except _InvalidPlanError as exc:
            results.append(_operation_result(False, "invalid-plan", change, str(exc)))
        except _StateChangedError as exc:
            results.append(_operation_result(False, "state-changed", change, str(exc)))
        except _TargetConflictError as exc:
            results.append(_operation_result(False, "target-conflict", change, str(exc)))
        except PermissionError as exc:
            results.append(_operation_result(False, "permission-denied", change, str(exc)))
        except (OSError, RuntimeError, ValueError) as exc:
            results.append(_operation_result(False, "verification-failed", change, str(exc)))
        except Exception as exc:
            results.append(_operation_result(False, "verification-failed", change, str(exc)))
    return BatchResult(all(item.ok for item in results), tuple(results))


def apply_adoption(
    plan: AdoptionPlan,
    adapters: Mapping[str, TargetAdapter],
) -> BatchResult:
    has_writes = bool(
        plan.container_changes
        or plan.bridge_removals
        or any(change.action in {"create", "remove"} for change in plan.link_changes)
    )
    if has_writes:
        _write_snapshot(plan)
    results: list[OperationResult] = []
    for change in plan.container_changes:
        try:
            _apply_container_change(plan, change, adapters)
            results.append(
                OperationResult(
                    True,
                    "applied",
                    "*",
                    change.adapter_key,
                    change.root,
                    change.reason,
                )
            )
        except (OSError, RuntimeError, ValueError) as exc:
            results.append(
                OperationResult(
                    False,
                    "adoption-failed",
                    "*",
                    change.adapter_key,
                    change.root,
                    str(exc),
                )
            )
    for change in plan.link_changes:
        if change.action == "unavailable":
            results.append(_operation_result(True, "unavailable", change, change.reason))
            continue
        if change.action in {"blocked", "requires-adopt"}:
            results.append(_operation_result(False, change.action, change, change.reason))
            continue
        try:
            if change.action == "no-op":
                _adapter, source = _validate_change(
                    ChangePlan(plan.link_changes, plan.repository),
                    change,
                    adapters,
                )
                if (
                    snapshot_path(change.target) != change.expected
                    or not _target_is_direct_link(change.target, source)
                ):
                    raise _StateChangedError("target changed after planning")
                results.append(_operation_result(True, "no-op", change, change.reason))
                continue
            _apply_link_adoption(plan, change, adapters)
            results.append(_operation_result(True, "applied", change, change.reason))
        except _InvalidPlanError as exc:
            results.append(_operation_result(False, "invalid-plan", change, str(exc)))
        except _StateChangedError as exc:
            results.append(_operation_result(False, "state-changed", change, str(exc)))
        except PermissionError as exc:
            results.append(_operation_result(False, "permission-denied", change, str(exc)))
        except (OSError, RuntimeError, ValueError) as exc:
            results.append(_operation_result(False, "adoption-failed", change, str(exc)))
    for change in plan.bridge_removals:
        try:
            _apply_bridge_removal(change)
            results.append(
                OperationResult(
                    True,
                    "applied",
                    "*",
                    change.adapter_key,
                    change.path,
                    change.reason,
                )
            )
        except (OSError, RuntimeError) as exc:
            results.append(
                OperationResult(
                    False,
                    "bridge-removal-failed",
                    "*",
                    change.adapter_key,
                    change.path,
                    str(exc),
                )
            )
    return BatchResult(all(item.ok for item in results), tuple(results))
