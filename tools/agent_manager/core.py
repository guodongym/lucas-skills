from __future__ import annotations

import base64
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathSnapshot:
    kind: str
    link_target: str | None = None


@dataclass(frozen=True)
class FileSnapshot:
    kind: str
    link_target: str | None = None
    mode: int | None = None
    sha256: str | None = None
    content_base64: str | None = None
    device: int | None = None
    inode: int | None = None


class FileSnapshotChangedError(OSError):
    pass


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


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def capture_file_snapshot(path: Path, *, include_content: bool) -> FileSnapshot:
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return FileSnapshot("missing")

    if stat.S_ISLNK(before.st_mode):
        link_target = os.readlink(path)
        try:
            after_link = os.lstat(path)
        except FileNotFoundError as exc:
            raise FileSnapshotChangedError(f"link changed while reading: {path}") from exc
        if not _same_file_identity(before, after_link):
            raise FileSnapshotChangedError(f"link changed while reading: {path}")
        return FileSnapshot(
            "symlink",
            link_target=link_target,
            device=before.st_dev,
            inode=before.st_ino,
        )
    if stat.S_ISDIR(before.st_mode):
        return FileSnapshot(
            "directory",
            mode=stat.S_IMODE(before.st_mode),
            device=before.st_dev,
            inode=before.st_ino,
        )
    if not stat.S_ISREG(before.st_mode):
        return FileSnapshot(
            "special",
            mode=stat.S_IMODE(before.st_mode),
            device=before.st_dev,
            inode=before.st_ino,
        )

    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        try:
            after_open = os.lstat(path)
        except FileNotFoundError as exc:
            raise FileSnapshotChangedError(f"file changed while opening: {path}") from exc
        if not (
            stat.S_ISREG(opened.st_mode)
            and _same_file_identity(before, opened)
            and _same_file_identity(opened, after_open)
        ):
            raise FileSnapshotChangedError(f"file changed while opening: {path}")

        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        content = b"".join(chunks)

        after_read = os.fstat(descriptor)
        try:
            final_path = os.lstat(path)
        except FileNotFoundError as exc:
            raise FileSnapshotChangedError(f"file changed while reading: {path}") from exc
        if not (
            _same_file_identity(opened, after_read)
            and _same_file_identity(opened, final_path)
        ):
            raise FileSnapshotChangedError(f"file changed while reading: {path}")
    finally:
        os.close(descriptor)

    return FileSnapshot(
        "file",
        mode=stat.S_IMODE(opened.st_mode),
        sha256=hashlib.sha256(content).hexdigest(),
        content_base64=(
            base64.b64encode(content).decode("ascii") if include_content else None
        ),
        device=opened.st_dev,
        inode=opened.st_ino,
    )


def install_backup_noreplace(directory_fd: int, backup: str, target: str) -> None:
    """Install an isolated object at an empty name without a check/rename race."""
    os.link(
        backup,
        target,
        src_dir_fd=directory_fd,
        dst_dir_fd=directory_fd,
        follow_symlinks=False,
    )
    try:
        os.unlink(backup, dir_fd=directory_fd)
    except BaseException:
        # The destination may be replaced by a competitor after link(2).
        # Never unlink it from this cleanup path; retain both known names.
        raise
