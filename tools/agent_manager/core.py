from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathSnapshot:
    kind: str
    link_target: str | None = None


class InvalidPlanError(ValueError):
    pass


class StateChangedError(RuntimeError):
    pass


class TargetConflictError(OSError):
    pass


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def under(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    except ValueError:
        return False
    return True


def path_snapshot(path: Path) -> PathSnapshot:
    if not lexists(path):
        return PathSnapshot("missing")
    if path.is_symlink():
        return PathSnapshot("symlink", os.readlink(path))
    if path.is_dir():
        return PathSnapshot("directory")
    return PathSnapshot("file")
