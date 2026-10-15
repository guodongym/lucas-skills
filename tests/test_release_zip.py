from __future__ import annotations

import hashlib
import io
import json
import stat
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.upstream_sync import release_zip, vendor


def archive(entries: list[tuple[str | zipfile.ZipInfo, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as package:
        for name, data in entries:
            package.writestr(name, data)
    return buffer.getvalue()


class ReleaseZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {
            'name': 'wps365', 'type': 'release-zip',
            'version_url': 'https://example.com/latest.txt',
            'archive_url': 'https://example.com/v{version}/skills-{version}.zip',
            'archive_root': 'wps365-skills', 'dst': 'skills/wps365/.official',
            'manifest': 'skills/wps365/upstream.json',
            'guide': 'https://example.com/guide',
        }
        self.package = archive([('wps365-skills/a/SKILL.md', b'official')])
        self.lock = {}

    def run_mode(self, mode: str, package: bytes | None = None) -> str:
        output = io.StringIO()
        values = [b'v0.3.6\n']
        if mode != 'check' and self.lock.get('wps365', {}).get('version') != '0.3.6':
            values.append(self.package if package is None else package)
        with patch.object(release_zip, 'download', side_effect=values), redirect_stdout(output):
            release_zip.process(self.config, self.lock, self.root, mode)
        return output.getvalue()

    def test_check_detects_release_without_writing_files_or_lock(self) -> None:
        self.assertIn('[UPDATE] wps365:', self.run_mode('check'))
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.lock, {})

    def test_sync_preserves_router_records_hashes_and_is_idempotent(self) -> None:
        router = self.root / 'skills/wps365/SKILL.md'
        router.parent.mkdir(parents=True)
        router.write_text('local router')
        self.run_mode('sync')
        official = self.root / self.config['dst'] / 'a/SKILL.md'
        self.assertEqual(official.read_bytes(), b'official')
        self.assertEqual(router.read_text(), 'local router')
        manifest = json.loads((self.root / self.config['manifest']).read_text())
        self.assertEqual(manifest['files']['a/SKILL.md'], hashlib.sha256(b'official').hexdigest())
        self.assertEqual(manifest['archive_sha256'], hashlib.sha256(self.package).hexdigest())
        self.assertEqual(self.lock['wps365']['version'], '0.3.6')
        before = (self.root / self.config['manifest']).read_bytes()
        self.assertIn('已是最新', self.run_mode('sync'))
        self.assertEqual((self.root / self.config['manifest']).read_bytes(), before)

    def test_diff_reports_files_and_does_not_write(self) -> None:
        self.assertIn('+ a/SKILL.md', self.run_mode('diff'))
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.lock, {})

    def test_rejects_unsafe_or_unexpected_archive_before_any_write(self) -> None:
        link = zipfile.ZipInfo('wps365-skills/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        cases = [
            [('wps365-skills/../outside', b'x')],
            [('/absolute', b'x')],
            [('wps365-skills/a\\b', b'x')],
            [('other-root/a', b'x')],
            [('wps365-skills/a', b'x'), ('wps365-skills/./a', b'y')],
            [(link, b'/outside')],
            [('wps365-skills/a', b'x'), ('wps365-skills/a/b', b'y')],
            [],
        ]
        for entries in cases:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.run_mode('sync', archive(entries))
            self.assertEqual(list(self.root.iterdir()), [])
            self.assertEqual(self.lock, {})

    def test_refuses_destination_symlink_without_modifying_external_file(self) -> None:
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'SKILL.md').write_text('private')
        dest = self.root / self.config['dst']
        dest.mkdir(parents=True)
        (dest / 'a').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.run_mode('sync')
        self.assertEqual((outside / 'SKILL.md').read_text(), 'private')
        self.assertEqual(self.lock, {})

    def test_preserves_removed_upstream_files_with_warning(self) -> None:
        old = self.root / self.config['dst'] / 'old.md'
        old.parent.mkdir(parents=True)
        old.write_text('keep')
        output = self.run_mode('sync')
        self.assertEqual(old.read_text(), 'keep')
        self.assertIn('[WARN]', output)

    def test_rejects_invalid_remote_version(self) -> None:
        with patch.object(release_zip, 'download', return_value=b'../../evil'):
            with self.assertRaises(ValueError):
                release_zip.process(self.config, self.lock, self.root, 'check')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_cli_dispatches_archive_sources_for_all_modes(self) -> None:
        for mode in ['check', 'diff', 'sync']:
            with self.subTest(mode=mode), patch.object(vendor, 'load_config', return_value={'upstreams':[self.config]}), patch.object(vendor, 'load_lock', return_value={}), patch.object(vendor, 'save_lock'), patch.object(release_zip, 'process') as process, redirect_stdout(io.StringIO()):
                self.assertEqual(vendor.main([mode]), 0)
                process.assert_called_once()
                self.assertEqual(process.call_args.args[-1], mode)

    def test_parent_file_collision_is_rejected_before_any_file_is_written(self) -> None:
        dest = self.root / self.config['dst']
        dest.mkdir(parents=True)
        (dest / 'blocked').write_text('keep')
        package = archive([
            ('wps365-skills/first.md', b'new'),
            ('wps365-skills/blocked/child.md', b'bad'),
        ])
        with self.assertRaises(ValueError):
            self.run_mode('sync', package)
        self.assertFalse((dest / 'first.md').exists())
        self.assertEqual((dest / 'blocked').read_text(), 'keep')
        self.assertEqual(self.lock, {})
