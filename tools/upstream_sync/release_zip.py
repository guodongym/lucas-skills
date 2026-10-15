"""从官方版本索引同步发布 ZIP；只修改配置指定的上游目录和来源记录。"""
from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

MAX_BYTES = 128 * 1024 * 1024


def download(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('发布文件超过 128 MiB，停止同步')
    return content


def read_archive(content: bytes, root: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(content)) as package:
        if sum(item.file_size for item in package.infolist()) > MAX_BYTES:
            raise ValueError('ZIP 解压内容超过 128 MiB')
        for item in package.infolist():
            path = PurePosixPath(item.filename)
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                    or not path.parts or path.parts[0] != root
                    or mode not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError(f'不安全的发布包路径: {item.filename}')
            if item.is_dir():
                continue
            relative = str(path.relative_to(root))
            if relative == '.' or relative in files:
                raise ValueError(f'重复或无效的发布包路径: {item.filename}')
            files[relative] = package.read(item)
    if not files:
        raise ValueError('发布包没有文件')
    if any(str(parent) in files for name in files for parent in PurePosixPath(name).parents):
        raise ValueError('发布包包含文件与目录路径冲突')
    return files


def safe_target(repo: Path, relative: str) -> Path:
    repo = repo.resolve()
    target = repo / relative
    if not target.resolve().is_relative_to(repo.resolve()):
        raise ValueError(f'目标不在仓库内: {relative}')
    if any(path.is_symlink() for path in (target, *target.parents) if path.is_relative_to(repo)):
        raise ValueError(f'目标路径包含符号链接: {relative}')
    if any(path.exists() and not path.is_dir() for path in target.parents if path.is_relative_to(repo)):
        raise ValueError(f'目标父目录被文件占用: {relative}')
    return target


def compare_files(dest: Path, files: dict[str, bytes]) -> dict[str, list[str]]:
    local = {str(p.relative_to(dest)): p for p in dest.rglob('*') if p.is_file()}
    return {
        '+': sorted(set(files) - set(local)),
        '~': sorted(name for name in files.keys() & local.keys() if files[name] != local[name].read_bytes()),
        '-': sorted(set(local) - set(files)),
    }


def write_release(config: dict, repo: Path, files: dict[str, bytes], manifest: dict) -> None:
    destinations = {name: safe_target(repo, str(Path(config['dst']) / name)) for name in files}
    record = safe_target(repo, config['manifest'])
    if any(path.exists() and not path.is_file() for path in [*destinations.values(), record]):
        raise ValueError('目标文件被目录或特殊文件占用')
    for name, path in destinations.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[name])
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def process(config: dict, lock: dict, repo: Path, mode: str) -> bool:
    version = download(config['version_url']).decode('utf-8').strip().removeprefix('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?', version):
        raise ValueError(f'无效的发布版本: {version!r}')
    previous = lock.get(config['name'], {}).get('version')
    if previous == version:
        print(f"[OK]     {config['name']}: 已是最新 ({version})")
        return False
    if mode == 'check':
        print(f"[UPDATE] {config['name']}: {previous or '未同步'} -> {version}")
        return True
    source = config['archive_url'].format(version=version)
    content = download(source)
    files = read_archive(content, config['archive_root'])
    dest = safe_target(repo, config['dst'])
    changes = compare_files(dest, files)
    for marker, names in changes.items():
        for name in names:
            suffix = ' [WARN] 上游已删除，本地保留' if marker == '-' else ''
            print(f'    {marker} {name}{suffix}')
    if mode == 'sync':
        manifest = {
            'version': version, 'source': source, 'guide': config['guide'],
            'archive_sha256': hashlib.sha256(content).hexdigest(),
            'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
        }
        write_release(config, repo, files, manifest)
        lock[config['name']] = {
            'version': version, 'archive_sha256': manifest['archive_sha256'],
            'synced_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        print(f"  {config['archive_root']} -> {Path(config['manifest']).parent}: 新增 {len(changes['+'])}, 更新 {len(changes['~'])}")
    return True
